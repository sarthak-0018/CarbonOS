"""Add structured vehicle/appliance assets and reproducible footprint snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "20261002_0002"
down_revision = "20261001_0001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("profiles", sa.Column("state", sa.String(120), nullable=True))
    op.add_column("profiles", sa.Column("diet_type", sa.String(40), nullable=True))
    op.create_table("vehicles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("fuel_type", sa.String(32)), sa.Column("engine_capacity", sa.Numeric(10, 2)),
        sa.Column("fuel_efficiency", sa.Numeric(10, 4)), sa.Column("model_year", sa.Integer()))
    op.create_table("appliances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("appliance_type", sa.String(40), nullable=False), sa.Column("capacity", sa.String(40)),
        sa.Column("energy_rating", sa.String(20)), sa.Column("estimated_kwh_year", sa.Numeric(12, 3)),
        sa.Column("usage_hours_day", sa.Numeric(8, 3)))
    op.create_table("footprint_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("calculation_version", sa.String(40), nullable=False), sa.Column("factor_version", sa.String(100), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False), sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("total_co2e", sa.Numeric(24, 6), nullable=False), sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("data_quality_score", sa.Numeric(5, 2)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("period_end >= period_start", name="ck_footprint_period_range"))
    op.create_index("ix_footprint_sessions_profile_id", "footprint_sessions", ["profile_id"])
    op.create_table("footprint_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("footprint_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(40), nullable=False), sa.Column("co2e", sa.Numeric(24, 6), nullable=False),
        sa.Column("percentage", sa.Numeric(7, 4), nullable=False), sa.Column("calculation_details", sa.JSON(), nullable=False))
    op.create_index("ix_footprint_results_session_id", "footprint_results", ["session_id"])

def downgrade():
    op.drop_index("ix_footprint_results_session_id", table_name="footprint_results")
    op.drop_table("footprint_results")
    op.drop_index("ix_footprint_sessions_profile_id", table_name="footprint_sessions")
    op.drop_table("footprint_sessions")
    op.drop_table("appliances")
    op.drop_table("vehicles")
    op.drop_column("profiles", "diet_type")
    op.drop_column("profiles", "state")
