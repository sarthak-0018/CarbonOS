"""Persist partial calculation state without changing historical rows."""
from alembic import op
import sqlalchemy as sa

revision = "20261004_0003"
down_revision = "20261002_0002"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("footprint_sessions", sa.Column("status", sa.String(16), nullable=False, server_default="COMPLETE"))
    op.add_column("footprint_sessions", sa.Column("data_quality_breakdown", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("footprint_sessions", sa.Column("missing_factors", sa.JSON(), nullable=False, server_default="[]"))
    op.create_check_constraint("ck_footprint_sessions_status", "footprint_sessions", "status IN ('COMPLETE','PARTIAL','UNAVAILABLE')")

def downgrade():
    op.drop_constraint("ck_footprint_sessions_status", "footprint_sessions", type_="check")
    op.drop_column("footprint_sessions", "missing_factors")
    op.drop_column("footprint_sessions", "data_quality_breakdown")
    op.drop_column("footprint_sessions", "status")
