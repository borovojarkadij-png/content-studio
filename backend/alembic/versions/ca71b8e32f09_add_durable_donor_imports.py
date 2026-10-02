"""add durable donor import queue and 64-bit Telegram identities

Revision ID: ca71b8e32f09
Revises: a2c5e8f1b7d4
"""

import sqlalchemy as sa

from alembic import op

revision = "ca71b8e32f09"
down_revision = "a2c5e8f1b7d4"
branch_labels = None
depends_on = None


def _alter_telegram_identity_types(type_: sa.types.TypeEngine) -> None:
    # SQLite requires a table rebuild for ALTER COLUMN. PostgreSQL runs the
    # direct ALTER, preserving existing production data in place.
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("telegram_accounts") as batch:
            batch.alter_column("telegram_user_id", existing_type=sa.Integer(), type_=type_)
        for table in ("donor_channels", "output_channels"):
            with op.batch_alter_table(table) as batch:
                batch.alter_column("telegram_channel_id", existing_type=sa.Integer(), type_=type_)
        return
    op.alter_column(
        "telegram_accounts", "telegram_user_id", existing_type=sa.Integer(), type_=type_
    )
    for table in ("donor_channels", "output_channels"):
        op.alter_column(table, "telegram_channel_id", existing_type=sa.Integer(), type_=type_)


def upgrade() -> None:
    _alter_telegram_identity_types(sa.BigInteger())
    op.create_table(
        "donor_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_account_id", sa.Integer(), nullable=False),
        sa.Column("identifier", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["telegram_account_id"], ["telegram_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_account_id", "identifier"),
    )
    op.create_index(
        op.f("ix_donor_imports_telegram_account_id"),
        "donor_imports",
        ["telegram_account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_donor_imports_telegram_account_id"), table_name="donor_imports")
    op.drop_table("donor_imports")
    _alter_telegram_identity_types(sa.Integer())
