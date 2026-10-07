"""add durable per-output rewrite drafts and approvals

Revision ID: d7a1e4c2b805
Revises: c4e6b2a891d3
"""

import sqlalchemy as sa

from alembic import op

revision = "d7a1e4c2b805"
down_revision = "c4e6b2a891d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rewrite_outputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rewrite_job_id", sa.Integer(), nullable=False),
        sa.Column("output_channel_id", sa.Integer(), nullable=False),
        sa.Column("content_key", sa.String(length=255), nullable=False),
        sa.Column("rewritten_text", sa.String(), nullable=False),
        sa.Column("approval_state", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "approval_state IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_rewrite_output_approval_state",
        ),
        sa.ForeignKeyConstraint(["output_channel_id"], ["output_channels.id"]),
        sa.ForeignKeyConstraint(["rewrite_job_id"], ["rewrite_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rewrite_job_id", name="uq_rewrite_output_job"),
    )
    op.create_index(
        op.f("ix_rewrite_outputs_rewrite_job_id"),
        "rewrite_outputs",
        ["rewrite_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rewrite_outputs_output_channel_id"),
        "rewrite_outputs",
        ["output_channel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rewrite_outputs_content_key"),
        "rewrite_outputs",
        ["content_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rewrite_outputs_content_key"), table_name="rewrite_outputs")
    op.drop_index(op.f("ix_rewrite_outputs_output_channel_id"), table_name="rewrite_outputs")
    op.drop_index(op.f("ix_rewrite_outputs_rewrite_job_id"), table_name="rewrite_outputs")
    op.drop_table("rewrite_outputs")
