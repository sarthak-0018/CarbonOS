from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class FactorVersionInput(BaseModel):
    factor_key: str = Field(min_length=1, max_length=100)
    geography_code: str = Field(default="IN", min_length=2, max_length=12)
    geography: str | None = Field(default=None, max_length=80)
    category: str = Field(min_length=1, max_length=40)
    activity_unit: str = Field(min_length=1, max_length=32)
    value_kg_co2e_per_unit: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=12)
    status: Literal["DRAFT", "VERIFIED", "REVIEW", "APPROVED", "DEPRECATED"] = "DRAFT"
    source_name: str | None = Field(default=None, min_length=1, max_length=200)
    source_url: str | None = Field(default=None, min_length=1)
    source_version: str | None = Field(default=None, min_length=1, max_length=100)
    source_year: int | None = Field(default=None, ge=1900, le=2200)
    factor_unit: str | None = Field(default=None, min_length=1, max_length=32)
    uncertainty: Decimal | None = Field(default=None, ge=0)
    data_version: str | None = Field(default=None, max_length=100)
    source_license: str | None = Field(default=None, min_length=1, max_length=160)
    checksum: str | None = Field(default=None, max_length=128)
    accessed_on: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    gas: Literal["CO2", "CH4", "N2O", "CO2E"] = "CO2E"
    reference_period_start: date | None = None
    reference_period_end: date | None = None
    methodology_note: str | None = None

    @field_validator("geography_code")
    @classmethod
    def uppercase_geography(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_verified_provenance(self):
        effective_start = self.valid_from or self.reference_period_start
        if self.valid_to and effective_start and self.valid_to < effective_start:
            raise ValueError("valid_to must be on or after valid_from")
        if self.status in {"VERIFIED", "APPROVED"}:
            required = ("value_kg_co2e_per_unit", "source_name", "source_url", "source_version", "source_year", "methodology_note", "accessed_on")
            missing = [name for name in required if getattr(self, name) is None]
            if missing:
                raise ValueError(f"Verified factors require complete provenance: {', '.join(missing)}")
        return self


class FactorImportInput(BaseModel):
    category: str = Field(min_length=1, max_length=40)
    activity_type: str = Field(min_length=1, max_length=100)
    geography: str = Field(min_length=2, max_length=80)
    unit: str = Field(min_length=1, max_length=32)
    factor: Decimal = Field(ge=0, max_digits=24, decimal_places=12)
    factor_unit: str = Field(min_length=1, max_length=32)
    source: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=1)
    source_year: int = Field(ge=1900, le=2200)
    source_version: str = Field(min_length=1, max_length=100)
    methodology: str = Field(min_length=1)
    valid_from: date | None = None
    valid_to: date | None = None
    uncertainty: Decimal | None = Field(default=None, ge=0)
    status: Literal["REVIEW", "APPROVED"] = "REVIEW"
    source_license: str | None = Field(default=None, max_length=160)
    gas: Literal["CO2", "CH4", "N2O", "CO2E"] = "CO2E"
    reference_period_start: date | None = None
    reference_period_end: date | None = None

    @model_validator(mode="after")
    def validate_factor_unit_and_dates(self):
        effective_start = self.valid_from or self.reference_period_start
        if self.valid_to and effective_start and self.valid_to < effective_start:
            raise ValueError("valid_to must be on or after valid_from")
        if self.reference_period_start and self.reference_period_end and self.reference_period_end < self.reference_period_start:
            raise ValueError("reference_period_end must be on or after reference_period_start")
        if not self.factor_unit.endswith(f"/{self.unit}"):
            raise ValueError("factor_unit must state emissions per activity unit, e.g. kgCO2e/kWh")
        return self
