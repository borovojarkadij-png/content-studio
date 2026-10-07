"""Durable donor high-water marks and polling leases."""

import sqlalchemy as sa

from alembic import op

revision = "f04c8b31d9a2"
down_revision = "e93b0a4217d6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "donor_ingestion_cursors",
        sa.Column(
            "donor_channel_id", sa.Integer(), sa.ForeignKey("donor_channels.id"), primary_key=True
        ),
        sa.Column("last_message_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.CheckConstraint("last_message_id >= 0"),
        sa.CheckConstraint(
            "(claim_token IS NULL AND lease_expires_at IS NULL) OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM donor_ingestion_cursors")):
        raise RuntimeError("Refusing to discard donor ingestion recovery progress")
    op.drop_table("donor_ingestion_cursors")
