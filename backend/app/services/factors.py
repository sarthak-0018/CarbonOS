"""Trusted factor-catalog write path. Keep it behind future authenticated admin tooling."""

from datetime import timedelta
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
        if data.status == "VERIFIED":
            existing = self.session.scalars(select(EmissionFactor).where(
                EmissionFactor.factor_key == data.factor_key,
                EmissionFactor.geography_code == data.geography_code,
                EmissionFactor.status == "VERIFIED",
            ))
            for factor in existing:
                if factor.activity_unit != data.activity_unit:
                    raise FactorVersionConflict(
                        f"Factor key {data.factor_key!r} is already defined in {factor.activity_unit!r}; use a new key for another unit"
                    )
                overlaps = (data.valid_to is None or factor.valid_from <= data.valid_to) and (
                    factor.valid_to is None or factor.valid_to >= data.valid_from
                )
                if overlaps:
                    if factor.valid_to is None and factor.valid_from < data.valid_from:
                        close_previous.append(factor)
                    else:
                        raise FactorVersionConflict(
                            f"Verified factor validity overlaps version {factor.version}; choose non-overlapping dates"
                        )
        for previous in close_previous:
            previous.valid_to = data.valid_from - timedelta(days=1)
        current_version = self.session.scalar(select(func.max(EmissionFactor.version)).where(
            EmissionFactor.factor_key == data.factor_key,
            EmissionFactor.geography_code == data.geography_code,
        )) or 0
        factor = EmissionFactor(version=current_version + 1, **data.model_dump())
        self.session.add(factor)
        self.session.commit()
        self.session.refresh(factor)
        return factor
