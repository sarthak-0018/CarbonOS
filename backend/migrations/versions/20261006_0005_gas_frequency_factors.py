"""Add gas-aware footprint measurements and dated factor provenance."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_0005"
down_revision = "20261004_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_emission_factor_status", "emission_factors", type_="check")
    op.drop_constraint("ck_verified_factor_has_provenance", "emission_factors", type_="check")
    op.create_check_constraint(
        "ck_emission_factor_status", "emission_factors",
        "status IN ('TODO','DRAFT','VERIFIED','RETIRED','REVIEW','APPROVED','DEPRECATED')",
    )
    op.execute("UPDATE emission_factors SET status='DEPRECATED' WHERE status='TODO'")
    op.execute("UPDATE emission_factors SET status='REVIEW' WHERE status='DRAFT'")
    op.execute("UPDATE emission_factors SET status='DEPRECATED' WHERE status='RETIRED'")
    op.execute("UPDATE emission_factors SET status='APPROVED' WHERE status='VERIFIED'")
    op.create_check_constraint(
        "ck_verified_factor_has_provenance", "emission_factors",
        "(status NOT IN ('VERIFIED','APPROVED')) OR (value_kg_co2e_per_unit IS NOT NULL AND source_name IS NOT NULL AND source_url IS NOT NULL AND source_version IS NOT NULL AND accessed_on IS NOT NULL)",
    )
    op.add_column("emission_factors", sa.Column("gas", sa.String(8), nullable=False, server_default="CO2E"))
    op.add_column("emission_factors", sa.Column("reference_period_start", sa.Date(), nullable=True))
    op.add_column("emission_factors", sa.Column("reference_period_end", sa.Date(), nullable=True))
    op.create_check_constraint("ck_emission_factor_gas", "emission_factors", "gas IN ('CO2','CH4','N2O','CO2E')")
    op.create_check_constraint("ck_emission_factor_reference_period", "emission_factors", "reference_period_end IS NULL OR reference_period_start IS NULL OR reference_period_end >= reference_period_start")
    op.add_column("calculation_records", sa.Column("gas", sa.String(8), nullable=False, server_default="CO2E"))
    op.add_column("footprint_sessions", sa.Column("measurement_type", sa.String(8), nullable=False, server_default="CO2E"))
    op.add_column("footprint_sessions", sa.Column("period_kind", sa.String(24), nullable=False, server_default="YTD_ACTUAL"))
    op.add_column("footprint_sessions", sa.Column("totals_by_gas", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("footprint_results", sa.Column("measurement_type", sa.String(8), nullable=False, server_default="CO2E"))


def downgrade():
    op.drop_column("footprint_results", "measurement_type")
    op.drop_column("footprint_sessions", "measurement_type")
    op.drop_column("footprint_sessions", "period_kind")
    op.drop_column("footprint_sessions", "totals_by_gas")
    op.drop_column("calculation_records", "gas")
    op.drop_constraint("ck_emission_factor_reference_period", "emission_factors", type_="check")
    op.drop_constraint("ck_emission_factor_gas", "emission_factors", type_="check")
    op.drop_column("emission_factors", "reference_period_end")
    op.drop_column("emission_factors", "reference_period_start")
    op.drop_column("emission_factors", "gas")
    op.drop_constraint("ck_verified_factor_has_provenance", "emission_factors", type_="check")
    op.drop_constraint("ck_emission_factor_status", "emission_factors", type_="check")
    op.create_check_constraint("ck_emission_factor_status", "emission_factors", "status IN ('TODO','DRAFT','VERIFIED','RETIRED')")
    op.create_check_constraint("ck_verified_factor_has_provenance", "emission_factors", "(status != 'VERIFIED') OR (value_kg_co2e_per_unit IS NOT NULL AND source_name IS NOT NULL AND source_url IS NOT NULL AND source_version IS NOT NULL AND source_license IS NOT NULL AND accessed_on IS NOT NULL AND valid_from IS NOT NULL)")
