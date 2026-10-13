from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.calculations.normalization import normalize_activity_key, normalize_unit

Source = Literal["USER_ENTERED", "ONBOARDING", "BILL_UPLOAD", "RECEIPT_UPLOAD", "INTEGRATION", "ESTIMATED", "AI_SUGGESTED"]
ActivitySource = Literal["USER_ENTERED", "OCR", "BILL_UPLOAD", "EMAIL", "INTEGRATION", "ESTIMATED", "AI_SUGGESTED"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProfileCreate(BaseModel):
    display_name: str = Field(default="", max_length=120)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    household_size: int | None = Field(default=None, gt=0)
    diet_type: str | None = Field(default=None, max_length=40)
    preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator("country_code")
    @classmethod
    def uppercase_country(cls, value: str) -> str:
        return value.upper()


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    household_size: int | None = Field(default=None, gt=0)
    diet_type: str | None = Field(default=None, max_length=40)
    preferences: dict[str, Any] | None = None

    @field_validator("country_code")
    @classmethod
    def uppercase_updated_country(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("country_code cannot be null")
        return value.upper()

    @field_validator("display_name", "preferences")
    @classmethod
    def reject_null_required_profile_values(cls, value):
        if value is None:
            raise ValueError("This profile field cannot be cleared with null")
        return value


class ProfileRead(ORMModel):
    id: UUID
    display_name: str
    country_code: str
    city: str | None
    state: str | None
    household_size: int | None
    diet_type: str | None
    preferences: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class FactCreate(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: Any
    source: Source = "USER_ENTERED"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    confirmed: bool = True


class FactUpdate(BaseModel):
    value: Any
    source: Source = "USER_ENTERED"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    confirmed: bool = True


class FactRead(ORMModel):
    id: UUID
    profile_id: UUID
    key: str
    value: Any
    source: str
    confidence: Decimal | None
    confirmed: bool
    added_at: datetime
    updated_at: datetime


class AssetCreate(BaseModel):
    asset_type: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    attributes: dict[str, Any] = Field(default_factory=dict)
    source: Source = "USER_ENTERED"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)


class OnboardingProfileCreate(BaseModel):
    profile: ProfileCreate
    facts: list[FactCreate] = Field(default_factory=list)
    assets: list[AssetCreate] = Field(default_factory=list)


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    attributes: dict[str, Any] | None = None
    source: Source = "USER_ENTERED"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)

    @field_validator("name", "attributes")
    @classmethod
    def reject_null_asset_values(cls, value):
        if value is None:
            raise ValueError("This asset field cannot be cleared with null")
        return value


class AssetRead(ORMModel):
    id: UUID
    profile_id: UUID
    asset_type: str
    name: str
    attributes: dict[str, Any]
    status: str
    source: str
    confidence: Decimal | None
    added_at: datetime
    updated_at: datetime
    retired_at: datetime | None


class AssetEventRead(ORMModel):
    id: UUID
    asset_id: UUID
    event_type: str
    snapshot: dict[str, Any]
    source: str
    created_at: datetime


class ActivityCreate(BaseModel):
    asset_id: UUID | None = None
    activity_type: str = Field(min_length=1, max_length=60, description="Normalized key used to match an emission factor")
    quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    unit: str = Field(min_length=1, max_length=32)
    occurred_at: datetime
    source: ActivitySource = "USER_ENTERED"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @field_validator("activity_type")
    @classmethod
    def canonical_activity_key(cls, value: str) -> str:
        return normalize_activity_key(value)

    @field_validator("unit")
    @classmethod
    def canonical_activity_unit(cls, value: str) -> str:
        return normalize_unit(value)


class ActivityUpdate(BaseModel):
    asset_id: UUID | None = None
    activity_type: str | None = Field(default=None, min_length=1, max_length=60)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    occurred_at: datetime | None = None
    source: ActivitySource = "USER_ENTERED"
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    details: dict[str, Any] | None = None

    @field_validator("occurred_at")
    @classmethod
    def updated_timestamp_must_include_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None:
            raise ValueError("occurred_at cannot be null")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @field_validator("activity_type")
    @classmethod
    def canonical_updated_activity_key(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("activity_type cannot be null")
        return normalize_activity_key(value)

    @field_validator("unit")
    @classmethod
    def canonical_updated_activity_unit(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("unit cannot be null")
        return normalize_unit(value)

    @field_validator("quantity")
    @classmethod
    def reject_null_updated_quantity(cls, value: Decimal | None) -> Decimal:
        if value is None:
            raise ValueError("quantity cannot be null")
        return value

    @field_validator("details")
    @classmethod
    def reject_null_updated_details(cls, value: dict[str, Any] | None) -> dict[str, Any]:
        if value is None:
            raise ValueError("details cannot be null; pass an empty object to clear it")
        return value


class ActivityRead(ORMModel):
    id: UUID
    profile_id: UUID
    asset_id: UUID | None
    activity_type: str
    quantity: Decimal
    unit: str
    occurred_at: datetime
    source: str
    confidence: Decimal | None
    details: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class FactorRead(ORMModel):
    id: UUID
    factor_key: str
    geography_code: str
    version: int
    category: str
    activity_unit: str
    value_kg_co2e_per_unit: Decimal | None
    output_unit: str
    status: str
    source_name: str | None
    source_url: str | None
    source_version: str | None
    data_version: str | None
    source_license: str | None
    checksum: str | None
    accessed_on: date | None
    valid_from: date | None
    valid_to: date | None
    methodology_note: str | None
    activity_type: str | None = None
    geography: str | None = None
    unit: str | None = None
    factor: Decimal | None = None
    factor_unit: str | None = None
    source: str | None = None
    source_year: int | None = None
    gas: str = "CO2E"
    reference_period_start: date | None = None
    reference_period_end: date | None = None
    methodology: str | None = None
    uncertainty: Decimal | None = None
    updated_at: datetime | None = None


class CalculationRead(ORMModel):
    id: UUID
    activity_id: UUID
    factor_id: UUID
    activity_quantity: Decimal
    activity_unit: str
    factor_value_snapshot: Decimal
    emissions_kg_co2e: Decimal
    methodology_version: str
    calculated_at: datetime
    factor_key: str
    factor_version: int
    gas: str = "CO2E"


class FootprintCalculateRequest(BaseModel):
    period_start: date
    period_end: date
    @field_validator("period_end")
    @classmethod
    def valid_period(cls, value, info):
        start = info.data.get("period_start")
        if start and value < start:
            raise ValueError("period_end must be on or after period_start")
        return value


class FootprintResultRead(ORMModel):
    id: UUID
    category: str
    co2e: Decimal
    percentage: Decimal
    calculation_details: dict[str, Any]
    measurement_type: str = "CO2E"

    @computed_field
    @property
    def value(self) -> Decimal:
        return self.co2e

    @computed_field
    @property
    def unit(self) -> str:
        return f"kg{self.measurement_type}"


class FootprintSessionRead(ORMModel):
    id: UUID
    calculation_version: str
    factor_version: str
    period_start: date
    period_end: date
    total_co2e: Decimal
    unit: str
    measurement_type: str = "CO2E"
    period_kind: str = "YTD_ACTUAL"
    totals_by_gas: dict[str, Decimal] = Field(default_factory=dict)
    data_quality_score: Decimal | None
    status: str = "COMPLETE"
    data_quality_breakdown: dict[str, Any] = Field(default_factory=dict)
    missing_factors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    results: list[FootprintResultRead]

    @computed_field
    @property
    def total(self) -> dict[str, Any]:
        if self.status == "UNAVAILABLE":
            return {"value": None, "unit": self.unit, "measurement_type": self.measurement_type}
        if self.measurement_type == "MIXED":
            return {"value": None, "unit": "mixed", "by_gas": self.totals_by_gas}
        return {"value": self.total_co2e, "unit": self.unit, "measurement_type": self.measurement_type}
