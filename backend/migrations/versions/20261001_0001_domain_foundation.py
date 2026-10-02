"""Create persistent profile/activity and versioned-factor foundation.

Only TODO emission-factor records are seeded. Values remain NULL until sourced and reviewed.
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone

revision = "20261001_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("household_size", sa.Integer(), nullable=True),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("household_size IS NULL OR household_size > 0", name="ck_profiles_household_size_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "emission_factors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("factor_key", sa.String(length=100), nullable=False),
        sa.Column("geography_code", sa.String(length=12), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("activity_unit", sa.String(length=32), nullable=False),
        sa.Column("value_kg_co2e_per_unit", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("output_unit", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_version", sa.String(length=100), nullable=True),
        sa.Column("data_version", sa.String(length=100), nullable=True),
        sa.Column("source_license", sa.String(length=160), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("accessed_on", sa.Date(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("methodology_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_emission_factor_version_positive"),
        sa.CheckConstraint("status IN ('TODO','DRAFT','VERIFIED','RETIRED')", name="ck_emission_factor_status"),
        sa.CheckConstraint("value_kg_co2e_per_unit IS NULL OR value_kg_co2e_per_unit >= 0", name="ck_emission_factor_value_nonnegative"),
        sa.CheckConstraint("(status != 'VERIFIED') OR (value_kg_co2e_per_unit IS NOT NULL AND source_name IS NOT NULL AND source_url IS NOT NULL AND source_version IS NOT NULL AND source_license IS NOT NULL AND accessed_on IS NOT NULL AND valid_from IS NOT NULL)", name="ck_verified_factor_has_provenance"),
        sa.CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_emission_factor_validity_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("factor_key", "geography_code", "version", name="uq_emission_factor_key_geo_version"),
    )
    op.create_index("ix_emission_factor_lookup", "emission_factors", ["factor_key", "geography_code", "status", "valid_from"])
    op.create_table(
        "profile_facts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_profile_facts_confidence_range"),
        sa.CheckConstraint("source IN ('USER_ENTERED','ONBOARDING','BILL_UPLOAD','RECEIPT_UPLOAD','INTEGRATION','ESTIMATED','AI_SUGGESTED')", name="ck_profile_facts_source"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profile_facts_profile_id", "profile_facts", ["profile_id"])
    op.create_index("ix_profile_facts_profile_key", "profile_facts", ["profile_id", "key"])
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("asset_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_assets_status"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_assets_confidence_range"),
        sa.CheckConstraint("source IN ('USER_ENTERED','ONBOARDING','BILL_UPLOAD','RECEIPT_UPLOAD','INTEGRATION','ESTIMATED')", name="ck_assets_source"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_profile_id", "assets", ["profile_id"])
    op.create_index("ix_assets_profile_status", "assets", ["profile_id", "status"])
    op.create_table(
        "asset_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_type IN ('CREATED','EDITED','RETIRED')", name="ck_asset_events_type"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asset_events_asset_id", "asset_events", ["asset_id"])
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column("activity_type", sa.String(length=60), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity >= 0", name="ck_activities_quantity_nonnegative"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_activities_confidence_range"),
        sa.CheckConstraint("source IN ('USER_ENTERED','OCR','BILL_UPLOAD','EMAIL','INTEGRATION','ESTIMATED','AI_SUGGESTED')", name="ck_activities_source"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activities_asset_id", "activities", ["asset_id"])
    op.create_index("ix_activities_profile_id", "activities", ["profile_id"])
    op.create_index("ix_activities_profile_occurred", "activities", ["profile_id", "occurred_at"])
    op.create_table(
        "calculation_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("factor_id", sa.Uuid(), nullable=False),
        sa.Column("activity_quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("activity_unit", sa.String(length=32), nullable=False),
        sa.Column("factor_value_snapshot", sa.Numeric(precision=24, scale=12), nullable=False),
        sa.Column("emissions_kg_co2e", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("methodology_version", sa.String(length=40), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("activity_quantity >= 0", name="ck_calculation_quantity_nonnegative"),
        sa.CheckConstraint("factor_value_snapshot >= 0", name="ck_calculation_factor_nonnegative"),
        sa.CheckConstraint("emissions_kg_co2e >= 0", name="ck_calculation_emissions_nonnegative"),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["factor_id"], ["emission_factors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calculation_records_activity_id", "calculation_records", ["activity_id"])
    op.create_index("ix_calculation_records_factor_id", "calculation_records", ["factor_id"])
    op.create_index("ix_calculations_activity_time", "calculation_records", ["activity_id", "calculated_at"])

    factors = sa.table(
        "emission_factors",
        sa.column("id", sa.Uuid()), sa.column("factor_key", sa.String()), sa.column("geography_code", sa.String()), sa.column("version", sa.Integer()),
        sa.column("category", sa.String()), sa.column("activity_unit", sa.String()),
        sa.column("value_kg_co2e_per_unit", sa.Numeric()), sa.column("output_unit", sa.String()),
        sa.column("status", sa.String()), sa.column("source_name", sa.String()), sa.column("source_url", sa.Text()),
        sa.column("source_version", sa.String()), sa.column("data_version", sa.String()), sa.column("source_license", sa.String()), sa.column("checksum", sa.String()),
        sa.column("accessed_on", sa.Date()), sa.column("valid_from", sa.Date()),
        sa.column("valid_to", sa.Date()), sa.column("methodology_note", sa.Text()), sa.column("created_at", sa.DateTime(timezone=True)),
    )
    placeholder_note = "TODO: source, review and version an authoritative factor before activation."
    seeds = [
        ("electricity_grid_kwh", "home", "kWh"),
        ("road_travel_car_km", "transport", "km"),
        ("road_travel_two_wheeler_km", "transport", "km"),
        ("public_transport_rail_km", "transport", "passenger_km"),
        ("household_lpg_kg", "home", "kg"),
        ("food_rice_kg", "food", "kg"),
        ("food_dairy_litre", "food", "litre"),
        ("waste_general_kg", "waste", "kg"),
    ]
    created_at = datetime.now(timezone.utc)
    op.bulk_insert(factors, [
        {"id": uuid.uuid4(), "factor_key": key, "geography_code": "IN", "version": 1, "category": category,
         "activity_unit": unit, "value_kg_co2e_per_unit": None, "output_unit": "kgCO2e", "status": "TODO",
         "source_name": None, "source_url": None, "source_version": None, "data_version": None,
         "source_license": None, "checksum": None, "accessed_on": None,
         "valid_from": None, "valid_to": None, "methodology_note": placeholder_note, "created_at": created_at}
        for key, category, unit in seeds
    ])


def downgrade():
    op.drop_index("ix_calculations_activity_time", table_name="calculation_records")
    op.drop_index("ix_calculation_records_factor_id", table_name="calculation_records")
    op.drop_index("ix_calculation_records_activity_id", table_name="calculation_records")
    op.drop_table("calculation_records")
    op.drop_index("ix_activities_profile_occurred", table_name="activities")
    op.drop_index("ix_activities_profile_id", table_name="activities")
    op.drop_index("ix_activities_asset_id", table_name="activities")
    op.drop_table("activities")
    op.drop_index("ix_asset_events_asset_id", table_name="asset_events")
    op.drop_table("asset_events")
    op.drop_index("ix_assets_profile_status", table_name="assets")
    op.drop_index("ix_assets_profile_id", table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_profile_facts_profile_key", table_name="profile_facts")
    op.drop_index("ix_profile_facts_profile_id", table_name="profile_facts")
    op.drop_table("profile_facts")
    op.drop_index("ix_emission_factor_lookup", table_name="emission_factors")
    op.drop_table("emission_factors")
    op.drop_table("profiles")
