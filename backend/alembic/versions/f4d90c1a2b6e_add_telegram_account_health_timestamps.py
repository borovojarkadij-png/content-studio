"""add Telegram account health timestamps

Revision ID: f4d90c1a2b6e
Revises: 1836e7c14dde
"""

from alembic import op
import sqlalchemy as sa


revision = "f4d90c1a2b6e"
down_revision = "1836e7c14dde"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_accounts",
        sa.Column("health_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "telegram_accounts",
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("telegram_accounts", "cooldown_until")
    op.drop_column("telegram_accounts", "health_checked_at")
