"""Persist detected retail receipt columns and semantics."""
from alembic import op
import sqlalchemy as sa

revision = "20261022_0010"
down_revision = "20261022_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("receipt_items", sa.Column("mrp", sa.Numeric(12, 2), nullable=True))
    op.add_column("receipt_items", sa.Column("price_column_value", sa.Numeric(12, 2), nullable=True))
    op.add_column("receipt_items", sa.Column("price_column_semantics", sa.String(24), nullable=True))
    op.add_column("receipt_items", sa.Column("quantity_unit_inferred", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("receipt_items", sa.Column("source_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade():
    for name in ("source_metadata", "quantity_unit_inferred", "price_column_semantics", "price_column_value", "mrp"):
        op.drop_column("receipt_items", name)
