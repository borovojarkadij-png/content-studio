"""Preserve per-channel style and known per-attempt provider usage."""

import sqlalchemy as sa

from alembic import op

revision = "a91c73bd204e"
down_revision = "f6b20d8a9143"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("output_channels") as batch:
        batch.add_column(
            sa.Column("rewrite_style", sa.String(16), nullable=False, server_default="NEUTRAL")
        )
        batch.create_check_constraint(
            "ck_channel_rewrite_style", "rewrite_style IN ('NEUTRAL', 'TABLOID')"
        )
    op.create_table(
        "rewrite_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rewrite_job_id", sa.Integer(), sa.ForeignKey("rewrite_jobs.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("style", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(20, 10), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("rewrite_job_id", "attempt", name="uq_rewrite_usage_attempt"),
        sa.CheckConstraint("attempt >= 1 AND input_tokens >= 0 AND output_tokens >= 0"),
        sa.CheckConstraint("cached_tokens >= 0 AND cached_tokens <= input_tokens"),
        sa.CheckConstraint("estimated_cost_usd IS NULL OR estimated_cost_usd >= 0"),
        sa.CheckConstraint("style IN ('NEUTRAL', 'TABLOID')"),
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM rewrite_usage")) or connection.scalar(
        sa.text("SELECT COUNT(*) FROM output_channels WHERE rewrite_style <> 'NEUTRAL'")
    ):
        raise RuntimeError("Refusing to discard rewrite usage or selected style")
    op.drop_table("rewrite_usage")
    with op.batch_alter_table("output_channels") as batch:
        batch.drop_constraint("ck_channel_rewrite_style", type_="check")
        batch.drop_column("rewrite_style")
