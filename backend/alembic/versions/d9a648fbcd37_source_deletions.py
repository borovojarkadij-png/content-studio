"""Retain channel deletion identities without erasing historical sources."""

import sqlalchemy as sa

from alembic import op

revision = "d9a648fbcd37"
down_revision = "c8f537eabc26"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "source_deletions",
        sa.Column("telegram_account_id", sa.String(100), primary_key=True),
        sa.Column("donor_channel_id", sa.String(100), primary_key=True),
        sa.Column("telegram_message_id", sa.Integer(), primary_key=True),
        sa.Column("latest_pts", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(telegram_account_id) BETWEEN 1 AND 100", name="ck_source_deletion_account"
        ),
        sa.CheckConstraint(
            "length(donor_channel_id) BETWEEN 1 AND 100", name="ck_source_deletion_channel"
        ),
        sa.CheckConstraint(
            "telegram_message_id BETWEEN 1 AND 2147483647", name="ck_source_deletion_message"
        ),
        sa.CheckConstraint("latest_pts BETWEEN 1 AND 2147483647", name="ck_source_deletion_pts"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM source_deletions")):
        raise RuntimeError("Refusing to discard source deletion history")
    op.drop_table("source_deletions")
