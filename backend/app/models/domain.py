import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    diet_type: Mapped[str | None] = mapped_column(String(40))
    household_size: Mapped[int | None] = mapped_column(Integer)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    facts: Mapped[list["ProfileFact"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    footprint_sessions: Mapped[list["FootprintSession"]] = relationship(back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (CheckConstraint("household_size IS NULL OR household_size > 0", name="ck_profiles_household_size_positive"),)


class ProfileFact(Base):
    __tablename__ = "profile_facts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="USER_ENTERED", nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    confirmed: Mapped[bool] = mapped_column(default=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="facts")

    __table_args__ = (
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_profile_facts_confidence_range"),
        CheckConstraint("source IN ('USER_ENTERED','ONBOARDING','BILL_UPLOAD','RECEIPT_UPLOAD','INTEGRATION','ESTIMATED','AI_SUGGESTED')", name="ck_profile_facts_source"),
        Index("ix_profile_facts_profile_key", "profile_id", "key"),
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="USER_ENTERED", nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile: Mapped[Profile] = relationship(back_populates="assets")
    events: Mapped[list["AssetEvent"]] = relationship(back_populates="asset", cascade="all, delete-orphan", order_by="AssetEvent.created_at")
    vehicle: Mapped["Vehicle | None"] = relationship(back_populates="asset", cascade="all, delete-orphan", uselist=False)
    appliance: Mapped["Appliance | None"] = relationship(back_populates="asset", cascade="all, delete-orphan", uselist=False)

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_assets_status"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_assets_confidence_range"),
        CheckConstraint("source IN ('USER_ENTERED','ONBOARDING','BILL_UPLOAD','RECEIPT_UPLOAD','INTEGRATION','ESTIMATED')", name="ck_assets_source"),
        Index("ix_assets_profile_status", "profile_id", "status"),
    )


class AssetEvent(Base):
    __tablename__ = "asset_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    asset: Mapped[Asset] = relationship(back_populates="events")

    __table_args__ = (CheckConstraint("event_type IN ('CREATED','EDITED','RETIRED')", name="ck_asset_events_type"),)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("assets.id", ondelete="SET NULL"), index=True)
    activity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="USER_ENTERED", nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile: Mapped[Profile] = relationship(back_populates="activities")
    calculations: Mapped[list["CalculationRecord"]] = relationship(back_populates="activity", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_activities_quantity_nonnegative"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_activities_confidence_range"),
        CheckConstraint("source IN ('USER_ENTERED','OCR','BILL_UPLOAD','EMAIL','INTEGRATION','ESTIMATED','AI_SUGGESTED')", name="ck_activities_source"),
        Index("ix_activities_profile_occurred", "profile_id", "occurred_at"),
    )


class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    factor_key: Mapped[str] = mapped_column(String(100), nullable=False)
    geography_code: Mapped[str] = mapped_column(String(12), default="IN", nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    activity_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    value_kg_co2e_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    output_unit: Mapped[str] = mapped_column(String(16), default="kgCO2e", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="TODO", nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_version: Mapped[str | None] = mapped_column(String(100))
    data_version: Mapped[str | None] = mapped_column(String(100))
    source_license: Mapped[str | None] = mapped_column(String(160))
    checksum: Mapped[str | None] = mapped_column(String(128))
    accessed_on: Mapped[date | None] = mapped_column(Date)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    methodology_note: Mapped[str | None] = mapped_column(Text)
    # Canonical names for provenance-facing consumers; legacy aliases above remain API compatible.
    activity_type: Mapped[str | None] = mapped_column(String(100))
    geography: Mapped[str | None] = mapped_column(String(80))
    unit: Mapped[str | None] = mapped_column(String(32))
    factor: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    factor_unit: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(String(200))
    source_year: Mapped[int | None] = mapped_column(Integer)
    gas: Mapped[str] = mapped_column(String(8), default="CO2E", nullable=False)
    reference_period_start: Mapped[date | None] = mapped_column(Date)
    reference_period_end: Mapped[date | None] = mapped_column(Date)
    methodology: Mapped[str | None] = mapped_column(Text)
    uncertainty: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    calculations: Mapped[list["CalculationRecord"]] = relationship(back_populates="factor")

    __table_args__ = (
        UniqueConstraint("factor_key", "geography_code", "version", name="uq_emission_factor_key_geo_version"),
        CheckConstraint("version > 0", name="ck_emission_factor_version_positive"),
        CheckConstraint("status IN ('TODO','DRAFT','VERIFIED','RETIRED','REVIEW','APPROVED','DEPRECATED')", name="ck_emission_factor_status"),
        CheckConstraint("value_kg_co2e_per_unit IS NULL OR value_kg_co2e_per_unit >= 0", name="ck_emission_factor_value_nonnegative"),
        CheckConstraint("gas IN ('CO2','CH4','N2O','CO2E')", name="ck_emission_factor_gas"),
        CheckConstraint("reference_period_end IS NULL OR reference_period_start IS NULL OR reference_period_end >= reference_period_start", name="ck_emission_factor_reference_period"),
        CheckConstraint("(status NOT IN ('VERIFIED','APPROVED')) OR (value_kg_co2e_per_unit IS NOT NULL AND source_name IS NOT NULL AND source_url IS NOT NULL AND source_version IS NOT NULL AND accessed_on IS NOT NULL)", name="ck_verified_factor_has_provenance"),
        CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_emission_factor_validity_range"),
        Index("ix_emission_factor_lookup", "factor_key", "geography_code", "status", "valid_from"),
    )


class CalculationRecord(Base):
    __tablename__ = "calculation_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    factor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("emission_factors.id", ondelete="RESTRICT"), nullable=False, index=True)
    activity_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    activity_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_value_snapshot: Mapped[Decimal] = mapped_column(Numeric(24, 12), nullable=False)
    emissions_kg_co2e: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(40), nullable=False)
    gas: Mapped[str] = mapped_column(String(8), default="CO2E", nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    activity: Mapped[Activity] = relationship(back_populates="calculations")
    factor: Mapped[EmissionFactor] = relationship(back_populates="calculations")

    __table_args__ = (
        CheckConstraint("activity_quantity >= 0", name="ck_calculation_quantity_nonnegative"),
        CheckConstraint("factor_value_snapshot >= 0", name="ck_calculation_factor_nonnegative"),
        CheckConstraint("emissions_kg_co2e >= 0", name="ck_calculation_emissions_nonnegative"),
        Index("ix_calculations_activity_time", "activity_id", "calculated_at"),
    )


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id", ondelete="CASCADE"), unique=True, nullable=False)
    fuel_type: Mapped[str | None] = mapped_column(String(32))
    engine_capacity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    fuel_efficiency: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    model_year: Mapped[int | None] = mapped_column(Integer)
    asset: Mapped[Asset] = relationship(back_populates="vehicle")


class Appliance(Base):
    __tablename__ = "appliances"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id", ondelete="CASCADE"), unique=True, nullable=False)
    appliance_type: Mapped[str] = mapped_column(String(40), nullable=False)
    capacity: Mapped[str | None] = mapped_column(String(40))
    energy_rating: Mapped[str | None] = mapped_column(String(20))
    estimated_kwh_year: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    usage_hours_day: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    asset: Mapped[Asset] = relationship(back_populates="appliance")


class FootprintSession(Base):
    __tablename__ = "footprint_sessions"
    __table_args__ = (CheckConstraint("period_end >= period_start", name="ck_footprint_period_range"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    calculation_version: Mapped[str] = mapped_column(String(40), nullable=False)
    factor_version: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_co2e: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), default="kgCO2e", nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(8), default="CO2E", nullable=False)
    period_kind: Mapped[str] = mapped_column(String(24), default="YTD_ACTUAL", nullable=False)
    totals_by_gas: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    data_quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(String(16), default="COMPLETE", nullable=False)
    data_quality_breakdown: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    missing_factors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    profile: Mapped[Profile] = relationship(back_populates="footprint_sessions")
    results: Mapped[list["FootprintResult"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class FootprintResult(Base):
    __tablename__ = "footprint_results"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("footprint_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    co2e: Mapped[Decimal] = mapped_column(Numeric(24, 6), nullable=False)
    measurement_type: Mapped[str] = mapped_column(String(8), default="CO2E", nullable=False)
    percentage: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    calculation_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    session: Mapped[FootprintSession] = relationship(back_populates="results")
