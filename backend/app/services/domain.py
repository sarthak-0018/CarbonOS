import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calculations.contracts import CalculationInput
from app.calculations.engine import DeterministicCalculationEngine, METHODOLOGY_VERSION, UnitMismatchError
from app.models import Activity, Asset, AssetEvent, CalculationRecord, EmissionFactor, Profile, ProfileFact
from app.schemas.domain import ActivityCreate, ActivityUpdate, AssetCreate, AssetUpdate, FactCreate, FactUpdate, OnboardingProfileCreate, ProfileCreate, ProfileUpdate

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
        self.session.add(AssetEvent(asset_id=item.id, event_type="CREATED", snapshot=self._asset_snapshot(item), source=item.source))
        return self._commit(item)

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
        effective_on = activity.occurred_at.date()
        geography_code = str(activity.details.get("geography_code", profile.country_code)).upper()
        candidates = list(self.session.scalars(select(EmissionFactor).where(
            EmissionFactor.factor_key == activity.activity_type,
            EmissionFactor.geography_code == geography_code,
            EmissionFactor.status == "VERIFIED",
            EmissionFactor.valid_from <= effective_on,
            (EmissionFactor.valid_to.is_(None) | (EmissionFactor.valid_to >= effective_on)),
        )))
        if not candidates:
            placeholder = self.session.scalar(select(EmissionFactor).where(EmissionFactor.factor_key == activity.activity_type, EmissionFactor.geography_code == geography_code).order_by(EmissionFactor.version.desc()))
            raise FactorUnavailableError(activity.activity_type, "No verified factor is valid for the activity date", placeholder.status if placeholder else None)
        if len(candidates) != 1:
            raise FactorUnavailableError(activity.activity_type, "Multiple verified factors match the activity date; resolve the factor validity overlap")
        factor = candidates[0]
        if factor.value_kg_co2e_per_unit is None:
            raise FactorUnavailableError(activity.activity_type, "Verified factor has no numeric value", factor.status)
        try:
            result = DeterministicCalculationEngine().calculate(CalculationInput(
                activity_value=Decimal(activity.quantity),
                activity_unit=activity.unit,
                factor_value_kg_co2e_per_unit=Decimal(factor.value_kg_co2e_per_unit),
                factor_activity_unit=factor.activity_unit,
                factor_id=str(factor.id),
                factor_version=factor.version,
                methodology_version=METHODOLOGY_VERSION,
            ))
        except UnitMismatchError as exc:
            raise FactorUnavailableError(activity.activity_type, str(exc), factor.status) from exc
        record = CalculationRecord(
            activity_id=activity.id,
            factor_id=factor.id,
            activity_quantity=activity.quantity,
            activity_unit=activity.unit,
            factor_value_snapshot=result.factor_value_kg_co2e_per_unit,
            emissions_kg_co2e=result.emissions_kg_co2e,
            methodology_version=result.methodology_version,
        )
        self.session.add(record)
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
