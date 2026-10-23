"""Add persisted grocery receipts and reviewable receipt items."""
from alembic import op
import sqlalchemy as sa
revision = "20261013_0008"
down_revision = "20261006_0007"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("receipts", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False), sa.Column("merchant_name", sa.String(200)), sa.Column("receipt_date", sa.Date()), sa.Column("currency", sa.String(8)), sa.Column("total_amount", sa.Numeric(12,2)), sa.Column("image_storage_key", sa.String(255), nullable=False), sa.Column("raw_ocr_text", sa.Text(), nullable=False), sa.Column("ocr_engine", sa.String(80), nullable=False), sa.Column("ocr_status", sa.String(24), nullable=False), sa.Column("calculation_status", sa.String(24), nullable=False), sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_receipts_profile_id", "receipts", ["profile_id"])
    op.create_table("receipt_items", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("receipt_id", sa.Uuid(), sa.ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False), sa.Column("line_index", sa.Integer(), nullable=False), sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("raw_product_name", sa.String(240), nullable=False), sa.Column("normalized_product_name", sa.String(240)), sa.Column("quantity", sa.Numeric(12,4)), sa.Column("quantity_unit", sa.String(20)), sa.Column("unit_price", sa.Numeric(12,2)), sa.Column("line_total", sa.Numeric(12,2)), sa.Column("food_category", sa.String(100)), sa.Column("matched_factor_id", sa.Uuid(), sa.ForeignKey("emission_factors.id", ondelete="RESTRICT")), sa.Column("match_method", sa.String(32)), sa.Column("ocr_confidence", sa.Numeric(4,3)), sa.Column("parse_confidence", sa.Numeric(4,3)), sa.Column("quantity_evidence", sa.String(40)), sa.Column("emissions_kg_co2e", sa.Numeric(18,6)), sa.Column("emissions_status", sa.String(32), nullable=False), sa.Column("calculation_details", sa.JSON(), nullable=False), sa.Column("user_corrected", sa.Boolean(), nullable=False))
    op.create_index("ix_receipt_items_receipt_id", "receipt_items", ["receipt_id"])
def downgrade():
    op.drop_index("ix_receipt_items_receipt_id", table_name="receipt_items"); op.drop_table("receipt_items")
    op.drop_index("ix_receipts_profile_id", table_name="receipts"); op.drop_table("receipts")
