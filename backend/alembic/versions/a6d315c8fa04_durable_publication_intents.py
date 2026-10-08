"""Durable publication intents, fenced attempts and acknowledgement history."""

import sqlalchemy as sa

from alembic import op

revision = "a6d315c8fa04"
down_revision = "f5c204b7e903"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "publication_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "planned_id", sa.Integer(), sa.ForeignKey("planned_publications.id"), nullable=False
        ),
        sa.Column(
            "telegram_account_id",
            sa.Integer(),
            sa.ForeignKey("telegram_accounts.id"),
            nullable=False,
        ),
        sa.Column("telegram_channel_id", sa.BigInteger(), nullable=False),
        sa.Column("request_nonce", sa.BigInteger(), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_message_id", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.UniqueConstraint("planned_id", name="uq_publication_job_plan"),
        sa.UniqueConstraint(
            "telegram_account_id", "request_nonce", name="uq_publication_job_nonce"
        ),
        sa.CheckConstraint(
            "state IN ('QUEUED', 'CLAIMED', 'SENDING', 'SUCCEEDED', 'BLOCKED', 'FAILED', 'NEEDS_RECONCILIATION')",
            name="ck_publication_job_state",
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 2", name="ck_publication_job_attempts"),
        sa.CheckConstraint("length(binding_sha256) = 64", name="ck_publication_job_binding"),
        sa.CheckConstraint(
            "request_nonce > 0 AND request_nonce <= 9223372036854775807 AND telegram_channel_id < -1000000000000",
            name="ck_publication_job_identity",
        ),
        sa.CheckConstraint(
            "(state IN ('CLAIMED', 'SENDING') AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL AND attempts > 0) OR (state NOT IN ('CLAIMED', 'SENDING') AND claim_token IS NULL AND lease_expires_at IS NULL)",
            name="ck_publication_job_lease",
        ),
        sa.CheckConstraint(
            "(state = 'SUCCEEDED' AND sent_message_id IS NOT NULL AND sent_message_id > 0 AND completed_at IS NOT NULL AND attempts > 0) OR (state <> 'SUCCEEDED' AND sent_message_id IS NULL AND completed_at IS NULL)",
            name="ck_publication_job_receipt",
        ),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM publication_jobs")):
        raise RuntimeError("Refusing to discard publication intent/acknowledgement history")
    op.drop_table("publication_jobs")
