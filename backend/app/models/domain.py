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
    household_size: Mapped[int | None] = mapped_column(Integer)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    facts: Mapped[list["ProfileFact"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(back_populates="profile", cascade="all, delete-orphan")

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    calculations: Mapped[list["CalculationRecord"]] = relationship(back_populates="factor")

    __table_args__ = (
        UniqueConstraint("factor_key", "geography_code", "version", name="uq_emission_factor_key_geo_version"),
        CheckConstraint("version > 0", name="ck_emission_factor_version_positive"),
        CheckConstraint("status IN ('TODO','DRAFT','VERIFIED','RETIRED')", name="ck_emission_factor_status"),
        CheckConstraint("value_kg_co2e_per_unit IS NULL OR value_kg_co2e_per_unit >= 0", name="ck_emission_factor_value_nonnegative"),
        CheckConstraint("(status != 'VERIFIED') OR (value_kg_co2e_per_unit IS NOT NULL AND source_name IS NOT NULL AND source_url IS NOT NULL AND source_version IS NOT NULL AND source_license IS NOT NULL AND accessed_on IS NOT NULL AND valid_from IS NOT NULL)", name="ck_verified_factor_has_provenance"),
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
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    activity: Mapped[Activity] = relationship(back_populates="calculations")
    factor: Mapped[EmissionFactor] = relationship(back_populates="calculations")

    __table_args__ = (
        CheckConstraint("activity_quantity >= 0", name="ck_calculation_quantity_nonnegative"),
        CheckConstraint("factor_value_snapshot >= 0", name="ck_calculation_factor_nonnegative"),
        CheckConstraint("emissions_kg_co2e >= 0", name="ck_calculation_emissions_nonnegative"),
        Index("ix_calculations_activity_time", "activity_id", "calculated_at"),
    )
