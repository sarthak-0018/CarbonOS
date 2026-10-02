from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class FactorVersionInput(BaseModel):
    factor_key: str = Field(min_length=1, max_length=100)
    geography_code: str = Field(default="IN", min_length=2, max_length=12)
    category: str = Field(min_length=1, max_length=40)
    activity_unit: str = Field(min_length=1, max_length=32)
    value_kg_co2e_per_unit: Decimal | None = Field(default=None, ge=0, max_digits=24, decimal_places=12)
    status: Literal["DRAFT", "VERIFIED"] = "DRAFT"
    source_name: str | None = Field(default=None, min_length=1, max_length=200)
    source_url: str | None = Field(default=None, min_length=1)
    source_version: str | None = Field(default=None, min_length=1, max_length=100)
    data_version: str | None = Field(default=None, max_length=100)
    source_license: str | None = Field(default=None, min_length=1, max_length=160)
    checksum: str | None = Field(default=None, max_length=128)
    accessed_on: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    methodology_note: str | None = None

    @field_validator("geography_code")
    @classmethod
    def uppercase_geography(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_verified_provenance(self):
        if self.valid_to and self.valid_from and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        if self.status == "VERIFIED":
            required = ("value_kg_co2e_per_unit", "source_name", "source_url", "source_version", "source_license", "accessed_on", "valid_from")
            missing = [name for name in required if getattr(self, name) is None]
            if missing:
                raise ValueError(f"Verified factors require complete provenance: {', '.join(missing)}")
        return self
