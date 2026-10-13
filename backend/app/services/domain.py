import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calculations.contracts import CalculationInput
from app.calculations.engine import DeterministicCalculationEngine, METHODOLOGY_VERSION, UnitMismatchError
from app.calculations.unit_conversion import convert
from app.calculations.frequency import annualize, normalize_frequency
from app.models import Activity, Appliance, Asset, AssetEvent, CalculationRecord, EmissionFactor, FootprintResult, FootprintSession, Profile, ProfileFact, Vehicle
from app.services.emission_factor_service import EmissionFactorService
from app.schemas.domain import ActivityCreate, ActivityUpdate, AssetCreate, AssetUpdate, FactCreate, FactUpdate, FootprintCalculateRequest, OnboardingProfileCreate, ProfileCreate, ProfileUpdate

class NotFoundError(Exception):
    pass


class FactorUnavailableError(Exception):
    def __init__(self, factor_key: str, reason: str, factor_status: str | None = None):
        self.factor_key = factor_key
        self.reason = reason
        self.factor_status = factor_status
        super().__init__(reason)


class DomainService:
    def __init__(self, session: Session):
        self.session = session

    def _commit(self, obj=None):
        self.session.commit()
        if obj is not None:
            self.session.refresh(obj)
        return obj

    def _profile(self, profile_id: uuid.UUID) -> Profile:
        item = self.session.get(Profile, profile_id)
        if item is None:
            raise NotFoundError("Profile was not found")
        return item

    def _asset(self, profile_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
        item = self.session.scalar(select(Asset).where(Asset.id == asset_id, Asset.profile_id == profile_id))
        if item is None:
            raise NotFoundError("Asset was not found")
        return item

    def _activity(self, profile_id: uuid.UUID, activity_id: uuid.UUID) -> Activity:
        item = self.session.scalar(select(Activity).where(Activity.id == activity_id, Activity.profile_id == profile_id, Activity.deleted_at.is_(None)))
        if item is None:
            raise NotFoundError("Activity was not found")
        return item

    def create_profile(self, data: ProfileCreate) -> Profile:
        item = Profile(**data.model_dump())
        self.session.add(item)
        return self._commit(item)

    def create_profile_from_onboarding(self, data: OnboardingProfileCreate) -> Profile:
        """Persist the initial profile, confirmed facts, assets and asset history atomically."""
        profile = Profile(**data.profile.model_dump())
        self.session.add(profile)
        self.session.flush()
        for fact_data in data.facts:
            self.session.add(ProfileFact(profile_id=profile.id, **fact_data.model_dump()))
        for asset_data in data.assets:
            asset = Asset(profile_id=profile.id, **asset_data.model_dump())
            self.session.add(asset)
            self.session.flush()
            self._create_typed_asset(asset)
            self.session.add(AssetEvent(asset_id=asset.id, event_type="CREATED", snapshot=self._asset_snapshot(asset), source=asset.source))
        return self._commit(profile)

    def get_profile(self, profile_id: uuid.UUID) -> Profile:
        return self._profile(profile_id)

    def update_profile(self, profile_id: uuid.UUID, data: ProfileUpdate) -> Profile:
        item = self._profile(profile_id)
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        return self._commit(item)

    def list_facts(self, profile_id: uuid.UUID) -> list[ProfileFact]:
        self._profile(profile_id)
        return list(self.session.scalars(select(ProfileFact).where(ProfileFact.profile_id == profile_id).order_by(ProfileFact.added_at.desc())))

    def create_fact(self, profile_id: uuid.UUID, data: FactCreate) -> ProfileFact:
        self._profile(profile_id)
        item = ProfileFact(profile_id=profile_id, **data.model_dump())
        self.session.add(item)
        return self._commit(item)

    def update_fact(self, profile_id: uuid.UUID, fact_id: uuid.UUID, data: FactUpdate) -> ProfileFact:
        item = self.session.scalar(select(ProfileFact).where(ProfileFact.id == fact_id, ProfileFact.profile_id == profile_id))
        if item is None:
            raise NotFoundError("Profile fact was not found")
        for key, value in data.model_dump().items():
            setattr(item, key, value)
        return self._commit(item)

    def delete_fact(self, profile_id: uuid.UUID, fact_id: uuid.UUID) -> None:
        item = self.session.scalar(select(ProfileFact).where(ProfileFact.id == fact_id, ProfileFact.profile_id == profile_id))
        if item is None:
            raise NotFoundError("Profile fact was not found")
        self.session.delete(item)
        self.session.commit()

    @staticmethod
    def _asset_snapshot(asset: Asset) -> dict:
        return {"asset_type": asset.asset_type, "name": asset.name, "attributes": asset.attributes, "status": asset.status, "source": asset.source, "confidence": str(asset.confidence) if asset.confidence is not None else None}

    def list_assets(self, profile_id: uuid.UUID, include_inactive: bool = False) -> list[Asset]:
        self._profile(profile_id)
        query = select(Asset).where(Asset.profile_id == profile_id)
        if not include_inactive:
            query = query.where(Asset.status == "ACTIVE")
        return list(self.session.scalars(query.order_by(Asset.added_at.desc())))

    def create_asset(self, profile_id: uuid.UUID, data: AssetCreate) -> Asset:
        self._profile(profile_id)
        item = Asset(profile_id=profile_id, **data.model_dump())
        self.session.add(item)
        self.session.flush()
        self._create_typed_asset(item)
        self.session.add(AssetEvent(asset_id=item.id, event_type="CREATED", snapshot=self._asset_snapshot(item), source=item.source))
        return self._commit(item)

    def _create_typed_asset(self, item: Asset) -> None:
        attrs = item.attributes or {}
        asset_type = item.asset_type.lower()
        if asset_type in {"vehicle", "car", "motorcycle", "scooter", "ev"}:
            self.session.add(Vehicle(asset_id=item.id, fuel_type=attrs.get("fuel_type"), engine_capacity=attrs.get("engine_capacity"), fuel_efficiency=attrs.get("fuel_efficiency"), model_year=attrs.get("model_year")))
        elif asset_type in {"appliance", "refrigerator", "air_conditioner", "washing_machine", "television", "geyser"}:
            self.session.add(Appliance(asset_id=item.id, appliance_type=attrs.get("appliance_type", asset_type), capacity=attrs.get("capacity"), energy_rating=attrs.get("energy_rating"), estimated_kwh_year=attrs.get("estimated_kwh_year"), usage_hours_day=attrs.get("usage_hours_day")))

    def update_asset(self, profile_id: uuid.UUID, asset_id: uuid.UUID, data: AssetUpdate) -> Asset:
        item = self._asset(profile_id, asset_id)
        if item.status != "ACTIVE":
            raise NotFoundError("Inactive assets cannot be edited")
        changes = data.model_dump(exclude_unset=True)
        event_source = changes.pop("source", "USER_ENTERED")
        for key, value in changes.items():
            setattr(item, key, value)
        self.session.flush()
        self.session.add(AssetEvent(asset_id=item.id, event_type="EDITED", snapshot=self._asset_snapshot(item), source=event_source))
        return self._commit(item)

    def retire_asset(self, profile_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
        item = self._asset(profile_id, asset_id)
        if item.status == "ACTIVE":
            item.status = "INACTIVE"
            item.retired_at = datetime.now(timezone.utc)
            self.session.flush()
            self.session.add(AssetEvent(asset_id=item.id, event_type="RETIRED", snapshot=self._asset_snapshot(item), source="USER_ENTERED"))
            self._commit(item)
        return item

    def list_asset_events(self, profile_id: uuid.UUID, asset_id: uuid.UUID) -> list[AssetEvent]:
        self._asset(profile_id, asset_id)
        return list(self.session.scalars(select(AssetEvent).where(AssetEvent.asset_id == asset_id).order_by(AssetEvent.created_at)))

    def list_activities(self, profile_id: uuid.UUID, limit: int = 100, offset: int = 0) -> list[Activity]:
        self._profile(profile_id)
        return list(self.session.scalars(select(Activity).where(Activity.profile_id == profile_id, Activity.deleted_at.is_(None)).order_by(Activity.occurred_at.desc()).limit(limit).offset(offset)))

    def create_activity(self, profile_id: uuid.UUID, data: ActivityCreate) -> Activity:
        self._profile(profile_id)
        if data.asset_id is not None:
            self._asset(profile_id, data.asset_id)
        item = Activity(profile_id=profile_id, **data.model_dump())
        self.session.add(item)
        return self._commit(item)

    def update_activity(self, profile_id: uuid.UUID, activity_id: uuid.UUID, data: ActivityUpdate) -> Activity:
        item = self._activity(profile_id, activity_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("asset_id") is not None:
            self._asset(profile_id, changes["asset_id"])
        for key, value in changes.items():
            setattr(item, key, value)
        return self._commit(item)

    def delete_activity(self, profile_id: uuid.UUID, activity_id: uuid.UUID) -> None:
        item = self._activity(profile_id, activity_id)
        from app.models.domain import utc_now
        item.deleted_at = utc_now()
        self._commit(item)

    def list_factors(self, factor_key: str | None = None, status: str | None = None, geography_code: str | None = None) -> list[EmissionFactor]:
        query = select(EmissionFactor)
        if factor_key:
            query = query.where(EmissionFactor.factor_key == factor_key)
        if status:
            query = query.where(EmissionFactor.status == status.upper())
        if geography_code:
            query = query.where(EmissionFactor.geography_code == geography_code.upper())
        return list(self.session.scalars(query.order_by(EmissionFactor.factor_key, EmissionFactor.version.desc())))

    def calculate_activity(self, profile_id: uuid.UUID, activity_id: uuid.UUID) -> tuple[CalculationRecord, EmissionFactor]:
        activity = self._activity(profile_id, activity_id)
        profile = self._profile(profile_id)
        record, factor = self._resolve_activity(activity, profile)
        self.session.commit()
        self.session.refresh(record)
        return record, factor

    def list_calculations(self, profile_id: uuid.UUID, activity_id: uuid.UUID) -> list[tuple[CalculationRecord, EmissionFactor]]:
        self._activity(profile_id, activity_id)
        rows = self.session.execute(
            select(CalculationRecord, EmissionFactor)
            .join(EmissionFactor, CalculationRecord.factor_id == EmissionFactor.id)
            .where(CalculationRecord.activity_id == activity_id)
            .order_by(CalculationRecord.calculated_at.desc())
        )
        return list(rows.tuples())

    def list_footprint_history(self, profile_id: uuid.UUID, limit: int = 50) -> list[FootprintSession]:
        self._profile(profile_id)
        return list(self.session.scalars(select(FootprintSession).options(selectinload(FootprintSession.results)).where(
            FootprintSession.profile_id == profile_id
        ).order_by(FootprintSession.created_at.desc()).limit(limit)))

    def calculate_footprint(self, profile_id: uuid.UUID, period: FootprintCalculateRequest) -> FootprintSession:
        """Persist a reproducible snapshot while reporting categories whose factors are unavailable."""
        profile = self._profile(profile_id)
        activities = list(self.session.scalars(select(Activity).where(
            Activity.profile_id == profile_id, Activity.deleted_at.is_(None),
            Activity.occurred_at >= datetime.combine(period.period_start, datetime.min.time(), tzinfo=timezone.utc),
            Activity.occurred_at < datetime.combine(period.period_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
        ).order_by(Activity.occurred_at, Activity.id)))
        category_totals: dict[str, Decimal] = {}
        category_gases: dict[str, str] = {}
        gas_totals: dict[str, Decimal] = {}
        details: dict[str, list[dict]] = {}
        factor_versions: set[str] = set()
        source_counts = {"actual": 0, "user_entered": 0, "estimated": 0}
        missing_factors: list[dict] = []
        for activity in activities:
            source_bucket = "estimated" if activity.source == "ESTIMATED" else ("actual" if activity.source in {"BILL_UPLOAD", "INTEGRATION"} else "user_entered")
            source_counts[source_bucket] += 1
            try:
                record, factor = self._resolve_activity(activity, profile)
            except FactorUnavailableError as exc:
                missing_factors.append({"category": self._category_for_activity(activity), "activity_type": activity.activity_type,
                                        "factor_key": exc.factor_key, "reason": exc.reason, "status": "FACTOR_UNAVAILABLE"})
                continue
            category_totals[factor.category] = category_totals.get(factor.category, Decimal("0")) + record.emissions_kg_co2e
            gas = factor.gas or "CO2E"
            category_gases[factor.category] = gas
            gas_totals[gas] = gas_totals.get(gas, Decimal("0")) + record.emissions_kg_co2e
            frequency = normalize_frequency(activity.details.get("frequency") or ("MONTHLY" if activity.details.get("period") == "monthly" else "ONE_TIME"))
            reference_period = None
            if factor.reference_period_start or factor.reference_period_end:
                reference_period = {"start": str(factor.reference_period_start) if factor.reference_period_start else None,
                                    "end": str(factor.reference_period_end) if factor.reference_period_end else None}
            latest_policy = bool(record.latest_factor_policy)
            factor_unit = factor.factor_unit or f"kg{gas}/{factor.activity_unit}"
            details.setdefault(factor.category, []).append({
                "activity_id": str(activity.id), "activity_type": activity.activity_type,
                "quantity": str(activity.quantity), "unit": activity.unit,
                "input_period": frequency,
                "calculation_quantity": str(record.activity_quantity),
                "normalized_quantity": str(record.activity_quantity),
                "activity_unit": record.activity_unit,
                "annualized": frequency != "ONE_TIME",
                "fuel_type": getattr(record, "fuel_type", None),
                "fuel_efficiency_km_per_litre": str(record.fuel_efficiency_km_per_litre) if getattr(record, "fuel_efficiency_km_per_litre", None) else None,
                "normalized_distance_km": str(record.distance_quantity) if activity.activity_type == "road_travel_car_km" else None,
                "source": activity.source, "data_class": "ESTIMATED" if activity.source == "ESTIMATED" else ("ACTUAL" if activity.source in {"BILL_UPLOAD", "INTEGRATION"} else "USER_ENTERED"),
                "factor_id": str(factor.id), "factor_key": factor.factor_key,
                "factor_value": str(record.factor_value_snapshot), "factor_unit": factor_unit,
                "factor_version": factor.version, "source_name": factor.source_name,
                "gas": gas, "source_year": factor.source_year, "source_version": factor.source_version,
                "reference_period": reference_period,
                "factor_policy": "Calculated using the latest published CEA grid factor available at the time of calculation." if latest_policy and factor.source_name == "Central Electricity Authority" else None,
                "source_url": factor.source_url, "source_version": factor.source_version, "source_year": factor.source_year,
                "methodology": factor.methodology or factor.methodology_note,
                "emissions_kg_co2e": str(record.emissions_kg_co2e),
                "formula": f"{record.activity_quantity} {record.activity_unit} × {record.factor_value_snapshot} {factor_unit} = {record.emissions_kg_co2e} kg{gas}",
            })
            factor_versions.add(f"{factor.geography_code}:{factor.factor_key}:v{factor.version}")
        distinct_gases = set(gas_totals)
        measurement_type = next(iter(distinct_gases)) if len(distinct_gases) == 1 else ("MIXED" if distinct_gases else "CO2E")
        total = next(iter(gas_totals.values())) if len(gas_totals) == 1 else Decimal("0")
        version_list = ";".join(sorted(factor_versions)) or "no-factors-used"
        version_snapshot = version_list if len(version_list) <= 100 else "sha256:" + hashlib.sha256(version_list.encode("utf-8")).hexdigest()
        session = FootprintSession(
            profile_id=profile_id, calculation_version=METHODOLOGY_VERSION,
            factor_version=version_snapshot,
            period_start=period.period_start, period_end=period.period_end,
            total_co2e=total, unit=f"kg{measurement_type}" if measurement_type != "MIXED" else "mixed",
            measurement_type=measurement_type,
            period_kind="ANNUALIZED_ESTIMATE" if any(
                normalize_frequency(x.details.get("frequency") or ("MONTHLY" if x.details.get("period") == "monthly" else "ONE_TIME")) != "ONE_TIME" for x in activities
            ) else "YTD_ACTUAL",
            totals_by_gas={gas: str(value) for gas, value in gas_totals.items()},
            # Input-quality score: bill/integration 100, user-entered 80, estimated 40; arithmetic mean over included activity records.
            data_quality_score=(sum((source_counts["actual"] * 100, source_counts["user_entered"] * 80, source_counts["estimated"] * 40), Decimal("0")) / len(activities)) if activities else Decimal("0"),
            status=("UNAVAILABLE" if not category_totals else ("PARTIAL" if missing_factors or measurement_type in {"CO2", "MIXED"} else "COMPLETE")),
            data_quality_breakdown=source_counts,
            missing_factors=missing_factors,
        )
        self.session.add(session)
        self.session.flush()
        for category, emissions in sorted(category_totals.items()):
            self.session.add(FootprintResult(
                session_id=session.id, category=category, co2e=emissions,
                percentage=(emissions * 100 / gas_totals[category_gases[category]]) if gas_totals.get(category_gases[category]) else Decimal("0"),
                measurement_type=category_gases[category],
                calculation_details={"methodology_version": METHODOLOGY_VERSION, "activities": details[category]},
            ))
        self.session.commit()
        self.session.refresh(session)
        return session

    @staticmethod
    def _category_for_activity(activity: Activity) -> str:
        key = activity.activity_type
        if key == "electricity_grid_kwh":
            return "electricity"
        if key.startswith("electricity_") or key.startswith("household_"):
            return "home"
        if key.startswith("road_") or key.startswith("public_transport_"):
            return "transport"
        if key.startswith("food_"):
            return "food"
        return "other"

    def _resolve_activity(self, activity: Activity, profile: Profile):
        geography_code = str(activity.details.get("geography_code", profile.country_code)).upper()
        day = activity.occurred_at.date()
        factor_service = EmissionFactorService(self.session)
        factor_key = activity.activity_type
        fuel_efficiency = None
        fuel_type = None
        if activity.activity_type == "road_travel_car_km":
            vehicle = self.session.scalar(select(Vehicle).where(Vehicle.asset_id == activity.asset_id)) if activity.asset_id else None
            fuel_type = str(activity.details.get("fuel_type") or (vehicle.fuel_type if vehicle else "") or "").casefold()
            if fuel_type not in {"petrol", "diesel"}:
                raise FactorUnavailableError("road_travel_car_km", "A supported vehicle fuel type (petrol or diesel) is required")
            try:
                fuel_efficiency = Decimal(str(activity.details.get("fuel_efficiency_km_per_litre") or (vehicle.fuel_efficiency if vehicle else "") or ""))
            except Exception as exc:
                raise FactorUnavailableError(f"fuel_{fuel_type}_litre", "Vehicle efficiency in km/litre is required") from exc
            if not fuel_efficiency.is_finite() or fuel_efficiency <= 0:
                raise FactorUnavailableError(f"fuel_{fuel_type}_litre", "Vehicle efficiency in km/litre must be positive")
            factor_key = f"fuel_{fuel_type}_litre"
        try:
            matched = factor_service.find_approved(factor_key, geography_code, day)
        except ValueError as exc:
            raise FactorUnavailableError(factor_key, str(exc)) from exc
        candidates = [matched] if matched else []
        # CEA publishes fiscal-year grid data; if a later calendar activity has
        # no date-matched factor, use the newest approved Indian grid factor.
        if not candidates and activity.activity_type == "electricity_grid_kwh" and geography_code == "IN":
            latest = self.session.scalar(select(EmissionFactor).where(
                EmissionFactor.factor_key == factor_key,
                EmissionFactor.geography_code == geography_code,
                EmissionFactor.status.in_(("VERIFIED", "APPROVED")),
                EmissionFactor.value_kg_co2e_per_unit.is_not(None),
            ).order_by(EmissionFactor.source_year.desc(), EmissionFactor.version.desc()))
            candidates = [latest] if latest else []
        if len(candidates) != 1:
            status = None
            if not candidates:
                placeholder = self.session.scalar(select(EmissionFactor).where(
                    EmissionFactor.factor_key == factor_key,
                    EmissionFactor.geography_code == geography_code,
                ).order_by(EmissionFactor.version.desc()))
                status = placeholder.status if placeholder else None
                raise FactorUnavailableError(factor_key, "No unique approved emission factor is available for the activity date", status)
        factor = candidates[0]
        quantity = Decimal(activity.quantity)
        calculation_unit = activity.unit
        frequency = normalize_frequency(activity.details.get("frequency") or ("MONTHLY" if activity.details.get("period") == "monthly" else "ONE_TIME"))
        if activity.activity_type == "electricity_grid_kwh":
            quantity = convert(quantity, activity.unit, "kWh")
            calculation_unit = "kWh"
        elif activity.activity_type == "road_travel_car_km":
            quantity = convert(quantity, activity.unit, "km")
            calculation_unit = "km"
        if frequency != "ONE_TIME":
            quantity = annualize(quantity, frequency)
        if fuel_efficiency is not None:
            quantity = quantity / fuel_efficiency
            calculation_unit = "litre"
        try:
            result = DeterministicCalculationEngine().calculate(CalculationInput(
                quantity, calculation_unit,
                Decimal(factor.value_kg_co2e_per_unit), factor.activity_unit,
                str(factor.id), factor.version, METHODOLOGY_VERSION,
            ))
        except (UnitMismatchError, TypeError) as exc:
            raise FactorUnavailableError(activity.activity_type, str(exc), factor.status) from exc
        record = CalculationRecord(
            activity_id=activity.id, factor_id=factor.id,
            activity_quantity=quantity, activity_unit=calculation_unit,
            factor_value_snapshot=result.factor_value_kg_co2e_per_unit,
            emissions_kg_co2e=result.emissions_kg_co2e, methodology_version=result.methodology_version,
            gas=factor.gas or "CO2E",
        )
        record.frequency = frequency
        record.annualized = frequency != "ONE_TIME"
        factor_start = factor.reference_period_start or factor.valid_from
        record.latest_factor_policy = bool((factor_start is not None and day < factor_start) or (factor.reference_period_end is not None and day > factor.reference_period_end))
        record.fuel_type = fuel_type
        record.fuel_efficiency_km_per_litre = fuel_efficiency
        record.distance_quantity = annualize(convert(Decimal(activity.quantity), activity.unit, "km"), frequency) if activity.activity_type == "road_travel_car_km" else None
        self.session.add(record)
        return record, factor
