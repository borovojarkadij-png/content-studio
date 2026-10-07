"""Durable semantic verification leases and per-attempt usage."""

import sqlalchemy as sa

from alembic import op

revision = "d82f6a190bc4"
down_revision = "b7d2e904a613"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "semantic_verification_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "rewrite_output_id", sa.Integer(), sa.ForeignKey("rewrite_outputs.id"), nullable=False
        ),
        sa.Column(
            "source_revision_id",
            sa.Integer(),
            sa.ForeignKey("incoming_post_revisions.id"),
            nullable=False,
        ),
        sa.Column(
            "release_id",
            sa.Integer(),
            sa.ForeignKey("semantic_verifier_releases.id"),
            nullable=False,
        ),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("draft_sha256", sa.String(64), nullable=False),
        sa.Column("release_sha256", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "evidence_id", sa.Integer(), sa.ForeignKey("semantic_evidence.id"), nullable=True
        ),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.UniqueConstraint(
            "rewrite_output_id",
            "release_id",
            "source_sha256",
            "draft_sha256",
            "release_sha256",
            name="uq_semantic_job_binding",
        ),
        sa.CheckConstraint(
            "state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'REVIEW', 'BLOCKED', 'FAILED')"
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 2"),
        sa.CheckConstraint(
            "state <> 'RUNNING' OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
    )
    op.create_index(
        "ix_semantic_verification_jobs_rewrite_output_id",
        "semantic_verification_jobs",
        ["rewrite_output_id"],
    )
    op.create_table(
        "semantic_verification_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "verification_job_id",
            sa.Integer(),
            sa.ForeignKey("semantic_verification_jobs.id"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(20, 10), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("verification_job_id", "attempt", name="uq_semantic_usage_attempt"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 2 AND input_tokens >= 0 AND output_tokens >= 0"),
        sa.CheckConstraint("cached_tokens >= 0 AND cached_tokens <= input_tokens"),
        sa.CheckConstraint("estimated_cost_usd IS NULL OR estimated_cost_usd >= 0"),
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT COUNT(*) FROM semantic_verification_jobs")
    ) or connection.scalar(sa.text("SELECT COUNT(*) FROM semantic_verification_usage")):
        raise RuntimeError("Refusing to discard durable semantic attempts/usage")
    op.drop_table("semantic_verification_usage")
    op.drop_index(
        "ix_semantic_verification_jobs_rewrite_output_id", table_name="semantic_verification_jobs"
    )
    op.drop_table("semantic_verification_jobs")
