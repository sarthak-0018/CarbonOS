"""Allow approved factors with documented source metadata and no dated validity."""
from alembic import op

revision = "20261006_0006"
down_revision = "20261006_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_verified_factor_has_provenance", "emission_factors", type_="check")
    op.create_check_constraint(
        "ck_verified_factor_has_provenance", "emission_factors",
        "(status NOT IN ('VERIFIED','APPROVED')) OR (value_kg_co2e_per_unit IS NOT NULL AND source_name IS NOT NULL AND source_url IS NOT NULL AND source_version IS NOT NULL AND accessed_on IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint("ck_verified_factor_has_provenance", "emission_factors", type_="check")
    op.create_check_constraint(
        "ck_verified_factor_has_provenance", "emission_factors",
        "(status NOT IN ('VERIFIED','APPROVED')) OR (value_kg_co2e_per_unit IS NOT NULL AND source_name IS NOT NULL AND source_url IS NOT NULL AND source_version IS NOT NULL AND accessed_on IS NOT NULL AND valid_from IS NOT NULL)",
    )
