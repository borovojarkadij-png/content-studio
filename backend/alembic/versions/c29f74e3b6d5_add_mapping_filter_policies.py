"""Persist explicit per-mapping technical filter configuration."""

import sqlalchemy as sa

from alembic import op

revision = "c29f74e3b6d5"
down_revision = "b18e63d2a5c4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mapping_filter_policies",
        sa.Column("mapping_id", sa.Integer(), nullable=False),
        sa.Column("allowed_media_types", sa.JSON(), nullable=False),
        sa.Column("blocked_domains", sa.JSON(), nullable=False),
        sa.Column("ad_markers", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["mapping_id"], ["channel_mappings.id"]),
        sa.PrimaryKeyConstraint("mapping_id"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM mapping_filter_policies")):
        raise RuntimeError("Refusing to discard configured mapping filters")
    op.drop_table("mapping_filter_policies")
