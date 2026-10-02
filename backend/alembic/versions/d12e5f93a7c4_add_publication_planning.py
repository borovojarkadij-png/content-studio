"""add durable publication planning records

Revision ID: d12e5f93a7c4
Revises: ca71b8e32f09
"""

from alembic import op
import sqlalchemy as sa


revision = "d12e5f93a7c4"
down_revision = "ca71b8e32f09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publication_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("output_channel_id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("slot_minutes", sa.String(length=128), nullable=False),
        sa.CheckConstraint("mode IN ('MANUAL', 'AUTOMATIC')", name="ck_publication_plan_mode"),
        sa.CheckConstraint("daily_limit BETWEEN 1 AND 24", name="ck_publication_plan_daily_limit"),
        sa.ForeignKeyConstraint(["output_channel_id"], ["output_channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("output_channel_id"),
    )
    op.create_index(
        op.f("ix_publication_plans_output_channel_id"),
        "publication_plans",
        ["output_channel_id"],
        unique=False,
    )
    op.create_table(
        "publication_candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("output_channel_id", sa.Integer(), nullable=False),
        sa.Column("content_key", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["output_channel_id"], ["output_channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("output_channel_id", "content_key", name="uq_publication_candidate_content"),
    )
    op.create_index(
        op.f("ix_publication_candidates_output_channel_id"),
        "publication_candidates",
        ["output_channel_id"],
        unique=False,
    )
    op.create_table(
        "planned_publications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("output_channel_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["publication_candidates.id"]),
        sa.ForeignKeyConstraint(["output_channel_id"], ["output_channels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", name="uq_planned_publication_candidate"),
        sa.UniqueConstraint("output_channel_id", "scheduled_for", name="uq_planned_publication_slot"),
    )
    op.create_index(
        op.f("ix_planned_publications_scheduled_for"),
        "planned_publications",
        ["scheduled_for"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_planned_publications_scheduled_for"), table_name="planned_publications")
    op.drop_table("planned_publications")
    op.drop_index(op.f("ix_publication_candidates_output_channel_id"), table_name="publication_candidates")
    op.drop_table("publication_candidates")
    op.drop_index(op.f("ix_publication_plans_output_channel_id"), table_name="publication_plans")
    op.drop_table("publication_plans")
