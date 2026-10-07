"""Persist account-scoped input channels outside StringSession memory."""

import sqlalchemy as sa

from alembic import op

revision = "b18e63d2a5c4"
down_revision = "a07d92e1b4f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "telegram_peers",
        sa.Column("telegram_account_id", sa.Integer(), nullable=False),
        sa.Column("telegram_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("encrypted_peer", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["telegram_account_id"], ["telegram_accounts.id"]),
        sa.PrimaryKeyConstraint("telegram_account_id", "telegram_channel_id"),
        sa.CheckConstraint("telegram_channel_id < -1000000000000"),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM telegram_peers")):
        raise RuntimeError("Refusing to discard persisted Telegram peer recovery data")
    op.drop_table("telegram_peers")
