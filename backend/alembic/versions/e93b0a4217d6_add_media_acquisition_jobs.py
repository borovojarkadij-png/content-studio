"""Durable internet illustration acquisition jobs."""

import sqlalchemy as sa

from alembic import op

revision = "e93b0a4217d6"
down_revision = "d82f6a190bc4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "media_acquisition_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "candidate_id", sa.Integer(), sa.ForeignKey("publication_candidates.id"), nullable=False
        ),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "selected_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id"), nullable=True
        ),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.UniqueConstraint("candidate_id", "binding_sha256", name="uq_media_job_binding"),
        sa.CheckConstraint(
            "state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'NO_MATCH', 'BLOCKED', 'FAILED')"
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 2"),
        sa.CheckConstraint("length(binding_sha256) = 64"),
        sa.CheckConstraint(
            "state <> 'RUNNING' OR (claim_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
        sa.CheckConstraint("state <> 'SUCCEEDED' OR selected_asset_id IS NOT NULL"),
    )
    op.create_index(
        "ix_media_acquisition_jobs_candidate_id", "media_acquisition_jobs", ["candidate_id"]
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM media_acquisition_jobs")):
        raise RuntimeError("Refusing to discard durable media acquisition history")
    op.drop_index("ix_media_acquisition_jobs_candidate_id", table_name="media_acquisition_jobs")
    op.drop_table("media_acquisition_jobs")
