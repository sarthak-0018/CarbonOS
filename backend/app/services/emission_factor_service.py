"""Validated and versioned factor catalog service; public writes are intentionally absent."""
from datetime import date
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.models import EmissionFactor
from app.schemas.factors import FactorImportInput, FactorVersionInput
from app.services.factors import FactorCatalogService

class EmissionFactorService(FactorCatalogService):
    def find_approved(self, key: str, geography: str, effective_on: date) -> EmissionFactor | None:
        query = select(EmissionFactor).where(
            EmissionFactor.factor_key == key, EmissionFactor.geography_code == geography.upper(),
            EmissionFactor.status.in_(("VERIFIED", "APPROVED")), EmissionFactor.value_kg_co2e_per_unit.is_not(None),
            or_(EmissionFactor.valid_from.is_(None), EmissionFactor.valid_from <= effective_on),
            (EmissionFactor.valid_to.is_(None) | (EmissionFactor.valid_to >= effective_on)))
        rows = list(self.session.scalars(query))
        # OWID food factors are explicitly global proxies. Keep this fallback scoped
        # to imported food activity keys; electricity and transport remain unchanged.
        if not rows and key.startswith("food_") and geography.upper() != "GLOBAL":
            rows = list(self.session.scalars(select(EmissionFactor).where(
                EmissionFactor.factor_key == key, EmissionFactor.geography_code == "GLOBAL",
                EmissionFactor.status.in_(("VERIFIED", "APPROVED")), EmissionFactor.value_kg_co2e_per_unit.is_not(None),
                or_(EmissionFactor.valid_from.is_(None), EmissionFactor.valid_from <= effective_on),
                (EmissionFactor.valid_to.is_(None) | (EmissionFactor.valid_to >= effective_on)))))
        if len(rows) > 1:
            raise ValueError("More than one approved factor matches this date and geography")
        return rows[0] if rows else None

    def import_record(self, payload: dict) -> str:
        canonical = FactorImportInput.model_validate(payload)
        data = FactorVersionInput(
            factor_key=canonical.activity_type,
            geography_code="IN" if canonical.geography.casefold() == "india" else canonical.geography,
            geography=canonical.geography,
            category=canonical.category,
            activity_unit=canonical.unit,
            value_kg_co2e_per_unit=canonical.factor,
            status=canonical.status if canonical.status in {"APPROVED", "DEPRECATED"} else "REVIEW",
            source_name=canonical.source,
            source_url=canonical.source_url,
            source_version=canonical.source_version,
            source_year=canonical.source_year,
            factor_unit=canonical.factor_unit,
            uncertainty=canonical.uncertainty,
            source_license=canonical.source_license,
            accessed_on=date.today(),
            valid_from=canonical.valid_from or canonical.reference_period_start,
            valid_to=canonical.valid_to,
            methodology_note=canonical.methodology,
            gas=canonical.gas,
            reference_period_start=canonical.reference_period_start,
            reference_period_end=canonical.reference_period_end,
        )
        prior = self.session.scalar(select(EmissionFactor).where(
            EmissionFactor.factor_key == data.factor_key,
            EmissionFactor.geography_code == data.geography_code,
            EmissionFactor.valid_from == data.valid_from,
            EmissionFactor.source_version == data.source_version))
        if prior:
            same_record = (
                prior.value_kg_co2e_per_unit == data.value_kg_co2e_per_unit
                and prior.category == data.category
                and prior.activity_unit == data.activity_unit
                and prior.source_name == data.source_name
                and prior.source_url == data.source_url
                and prior.source_year == data.source_year
                and prior.methodology_note == data.methodology_note
                and prior.valid_to == data.valid_to
                and prior.gas == data.gas
                and prior.reference_period_start == data.reference_period_start
                and prior.reference_period_end == data.reference_period_end
            )
            if prior.status in {"VERIFIED", "APPROVED", "DRAFT", "REVIEW"} and same_record:
                return "Skipped"
            raise ValueError("An existing factor version differs; append a new source version instead of overwriting")
        self.add_version(data)
        return "Imported"
