"""Trusted factor-catalog write path. Keep it behind future authenticated admin tooling."""

from datetime import date, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EmissionFactor
from app.schemas.factors import FactorVersionInput


class FactorVersionConflict(ValueError):
    pass


class FactorCatalogService:
    def __init__(self, session: Session):
        self.session = session

    def add_version(self, data: FactorVersionInput) -> EmissionFactor:
        """Append a version; only the prior open validity window may be closed."""
        close_previous = []
        if data.status in {"VERIFIED", "APPROVED"}:
            data_start = data.valid_from or data.reference_period_start or date.min
            existing = self.session.scalars(select(EmissionFactor).where(
                EmissionFactor.factor_key == data.factor_key,
                EmissionFactor.geography_code == data.geography_code,
                EmissionFactor.status.in_(("VERIFIED", "APPROVED")),
            ))
            for factor in existing:
                if factor.activity_unit != data.activity_unit:
                    raise FactorVersionConflict(
                        f"Factor key {data.factor_key!r} is already defined in {factor.activity_unit!r}; use a new key for another unit"
                    )
                factor_start = factor.valid_from or factor.reference_period_start or date.min
                overlaps = (data.valid_to is None or factor_start <= data.valid_to) and (
                    factor.valid_to is None or factor.valid_to >= data_start
                )
                if overlaps:
                    if factor.valid_to is None and factor_start < data_start:
                        close_previous.append((factor, data_start - timedelta(days=1)))
                    else:
                        raise FactorVersionConflict(
                            f"Verified factor validity overlaps version {factor.version}; choose non-overlapping dates"
                        )
        for previous, final_valid_to in close_previous:
            previous.valid_to = final_valid_to
        current_version = self.session.scalar(select(func.max(EmissionFactor.version)).where(
            EmissionFactor.factor_key == data.factor_key,
            EmissionFactor.geography_code == data.geography_code,
        )) or 0
        values = data.model_dump()
        factor = EmissionFactor(version=current_version + 1, **values)
        factor.activity_type = data.factor_key
        factor.geography = data.geography or data.geography_code
        factor.unit = data.activity_unit
        factor.factor = data.value_kg_co2e_per_unit
        factor.factor_unit = data.factor_unit or f"kgCO2e/{data.activity_unit}"
        factor.source = data.source_name
        factor.source_year = data.source_year
        factor.methodology = data.methodology_note
        factor.uncertainty = data.uncertainty
        factor.output_unit = f"kg{data.gas}"
        self.session.add(factor)
        self.session.commit()
        self.session.refresh(factor)
        return factor
