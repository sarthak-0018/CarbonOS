"""Add canonical factor provenance fields alongside compatible legacy aliases."""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0004"
down_revision = "20261004_0003"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("emission_factors", sa.Column("activity_type", sa.String(100)))
    op.add_column("emission_factors", sa.Column("geography", sa.String(80)))
    op.add_column("emission_factors", sa.Column("unit", sa.String(32)))
    op.add_column("emission_factors", sa.Column("factor", sa.Numeric(24, 12)))
    op.add_column("emission_factors", sa.Column("factor_unit", sa.String(32)))
    op.add_column("emission_factors", sa.Column("source", sa.String(200)))
    op.add_column("emission_factors", sa.Column("source_year", sa.Integer()))
    op.add_column("emission_factors", sa.Column("methodology", sa.Text()))
    op.add_column("emission_factors", sa.Column("uncertainty", sa.Numeric(12, 6)))
    op.add_column("emission_factors", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE emission_factors SET activity_type=factor_key, geography=geography_code, unit=activity_unit, factor=value_kg_co2e_per_unit, factor_unit=activity_unit, source=source_name, methodology=methodology_note, updated_at=created_at")
    op.alter_column("emission_factors", "updated_at", nullable=False)
    op.create_check_constraint("ck_emission_factors_factor_nonnegative", "emission_factors", "factor IS NULL OR factor >= 0")
    op.create_index("ix_emission_factors_category", "emission_factors", ["category"])
    op.create_index("ix_emission_factors_activity_type", "emission_factors", ["activity_type"])
    op.create_index("ix_emission_factors_geography", "emission_factors", ["geography"])
    op.create_index("ix_emission_factors_status", "emission_factors", ["status"])
    op.create_index("ix_emission_factors_validity", "emission_factors", ["valid_from", "valid_to"])

def downgrade():
    for name in ("ix_emission_factors_validity", "ix_emission_factors_status", "ix_emission_factors_geography", "ix_emission_factors_activity_type", "ix_emission_factors_category"):
        op.drop_index(name, table_name="emission_factors")
    op.drop_constraint("ck_emission_factors_factor_nonnegative", "emission_factors", type_="check")
    for name in ("updated_at", "uncertainty", "methodology", "source_year", "source", "factor_unit", "factor", "unit", "geography", "activity_type"):
        op.drop_column("emission_factors", name)
