"""add mapping content fingerprints

Revision ID: a2c5e8f1b7d4
Revises: f4d90c1a2b6e
"""

from alembic import op
import sqlalchemy as sa


revision = "a2c5e8f1b7d4"
down_revision = "f4d90c1a2b6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mapping_content_fingerprints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mapping_id", sa.String(length=100), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mapping_id", "fingerprint", name="uq_mapping_content_fingerprint"),
    )
    op.create_index(
        op.f("ix_mapping_content_fingerprints_mapping_id"),
        "mapping_content_fingerprints",
        ["mapping_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mapping_content_fingerprints_mapping_id"), table_name="mapping_content_fingerprints")
    op.drop_table("mapping_content_fingerprints")
