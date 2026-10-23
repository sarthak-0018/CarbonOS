"""Add Indian receipt header and package review fields."""
from alembic import op
import sqlalchemy as sa

revision = "20261022_0009"
down_revision = "20261013_0008"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("store_address", sa.Text()), ("invoice_number", sa.String(100)), ("gstin", sa.String(20)),
        ("subtotal", sa.Numeric(12, 2)), ("discount_total", sa.Numeric(12, 2)),
        ("tax_total", sa.Numeric(12, 2)), ("file_sha256", sa.String(64)),
    ):
        op.add_column("receipts", sa.Column(name, kind, nullable=True))
    op.add_column("receipts", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("receipts", sa.Column("processing_error", sa.String(500), nullable=True))
    op.add_column("receipts", sa.Column("ocr_data", sa.JSON(), nullable=True))
    op.add_column("receipt_items", sa.Column("package_size", sa.Numeric(12, 4), nullable=True))
    op.add_column("receipt_items", sa.Column("package_size_unit", sa.String(20), nullable=True))
    op.add_column("receipt_items", sa.Column("match_confidence", sa.Numeric(4, 3), nullable=True))
    op.create_index("ix_receipts_profile_sha256", "receipts", ["profile_id", "file_sha256"])


def downgrade():
    op.drop_index("ix_receipts_profile_sha256", table_name="receipts")
    op.drop_column("receipt_items", "package_size_unit")
    op.drop_column("receipt_items", "package_size")
    op.drop_column("receipt_items", "match_confidence")
    for name in ("ocr_data", "processing_error", "updated_at", "file_sha256", "tax_total", "discount_total", "subtotal", "gstin", "invoice_number", "store_address"):
        op.drop_column("receipts", name)
