"""Persist trusted per-channel pts without inventing legacy baselines."""

import sqlalchemy as sa

from alembic import op

revision = "eab7590cde48"
down_revision = "d9a648fbcd37"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "channel_difference_cursors",
        sa.Column(
            "donor_channel_id", sa.Integer(), sa.ForeignKey("donor_channels.id"), primary_key=True
        ),
        sa.Column(
            "telegram_account_id",
            sa.Integer(),
            sa.ForeignKey("telegram_accounts.id"),
            nullable=False,
        ),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("pts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.CheckConstraint("pts BETWEEN 1 AND 2147483647", name="ck_difference_pts"),
        sa.CheckConstraint(
            "telegram_account_id > 0 AND telegram_user_id > 0", name="ck_difference_account"
        ),
        sa.CheckConstraint("telegram_channel_id < -1000000000000", name="ck_difference_channel"),
        sa.CheckConstraint(
            "(claim_token IS NULL AND lease_expires_at IS NULL) OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_difference_lease",
        ),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM channel_difference_cursors")):
        raise RuntimeError("Refusing to discard channel difference history")
    op.drop_table("channel_difference_cursors")
