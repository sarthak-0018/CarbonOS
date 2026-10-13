"""Canonicalize legacy factor states without deleting referenced versions."""
from alembic import op

revision = "20261006_0007"
down_revision = "20261006_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE emission_factors SET status='REVIEW' WHERE status='DRAFT'")
    op.execute("UPDATE emission_factors SET status='DEPRECATED' WHERE status IN ('TODO','RETIRED')")
    op.execute("UPDATE emission_factors SET status='APPROVED' WHERE status='VERIFIED'")


def downgrade():
    op.execute("UPDATE emission_factors SET status='VERIFIED' WHERE status='APPROVED'")
    op.execute("UPDATE emission_factors SET status='RETIRED' WHERE status='DEPRECATED'")
    op.execute("UPDATE emission_factors SET status='DRAFT' WHERE status='REVIEW'")
