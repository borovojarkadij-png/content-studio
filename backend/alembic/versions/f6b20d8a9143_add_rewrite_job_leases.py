"""Add durable retry/claim fencing without resetting existing jobs."""

import sqlalchemy as sa

from alembic import op

revision = "f6b20d8a9143"
down_revision = "e82a9c7b3061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rewrite_jobs") as batch:
        batch.add_column(sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("available_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("claim_token", sa.String(36), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_error_code", sa.String(64), nullable=True))
        batch.create_check_constraint("ck_rewrite_attempts_nonnegative", "attempts >= 0")


def downgrade() -> None:
    jobs = sa.table("rewrite_jobs", sa.column("attempts"), sa.column("claim_token"))
    if op.get_bind().scalar(
        sa.select(sa.func.count())
        .select_from(jobs)
        .where((jobs.c.attempts > 0) | jobs.c.claim_token.is_not(None))
    ):
        raise RuntimeError("Refusing to discard rewrite execution/recovery history")
    with op.batch_alter_table("rewrite_jobs") as batch:
        batch.drop_constraint("ck_rewrite_attempts_nonnegative", type_="check")
        for name in (
            "last_error_code",
            "lease_expires_at",
            "claim_token",
            "available_at",
            "attempts",
        ):
            batch.drop_column(name)
