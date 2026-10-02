"""scope rewrite jobs to output channels

Revision ID: e7d3a4f810bc
Revises: f51c8a04b2de
"""

import sqlalchemy as sa
from alembic import op


revision = "e7d3a4f810bc"
down_revision = "f51c8a04b2de"
branch_labels = None
depends_on = None


def _create_rewrite_jobs_table(name: str, *, scoped: bool) -> None:
    columns = [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_key", sa.String(length=255), nullable=False),
    ]
    if scoped:
        columns.append(sa.Column("output_channel_id", sa.Integer(), nullable=True))
    columns.extend(
        [
            sa.Column("idempotency_key", sa.String(length=255), nullable=False),
            sa.Column("state", sa.String(length=32), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("idempotency_key"),
        ]
    )
    if scoped:
        columns.extend(
            [
                sa.ForeignKeyConstraint(["output_channel_id"], ["output_channels.id"]),
                sa.UniqueConstraint(
                    "content_key", "output_channel_id", name="uq_rewrite_job_content_output"
                ),
            ]
        )
    else:
        columns.append(sa.UniqueConstraint("content_key", name="uq_rewrite_job_content"))
    op.create_table(name, *columns)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _create_rewrite_jobs_table("rewrite_jobs_new", scoped=True)
        op.execute(
            "INSERT INTO rewrite_jobs_new "
            "(id, content_key, output_channel_id, idempotency_key, state, created_at) "
            "SELECT id, content_key, NULL, idempotency_key, state, created_at FROM rewrite_jobs"
        )
        op.drop_table("rewrite_jobs")
        op.rename_table("rewrite_jobs_new", "rewrite_jobs")
        op.create_index(
            op.f("ix_rewrite_jobs_output_channel_id"),
            "rewrite_jobs",
            ["output_channel_id"],
            unique=False,
        )
        return

    op.add_column(
        "rewrite_jobs",
        sa.Column(
            "output_channel_id",
            sa.Integer(),
            sa.ForeignKey("output_channels.id"),
            nullable=True,
        ),
    )
    for constraint in sa.inspect(bind).get_unique_constraints("rewrite_jobs"):
        if constraint["column_names"] == ["content_key"] and constraint["name"]:
            op.drop_constraint(constraint["name"], "rewrite_jobs", type_="unique")
    op.create_unique_constraint(
        "uq_rewrite_job_content_output", "rewrite_jobs", ["content_key", "output_channel_id"]
    )
    op.create_index(
        op.f("ix_rewrite_jobs_output_channel_id"),
        "rewrite_jobs",
        ["output_channel_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    duplicate_content = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT content_key FROM rewrite_jobs GROUP BY content_key HAVING COUNT(*) > 1"
            ") AS duplicate_content"
        )
    ).scalar_one()
    if duplicate_content:
        raise RuntimeError("Unsafe downgrade: output-scoped rewrite jobs share content")

    if bind.dialect.name == "sqlite":
        _create_rewrite_jobs_table("rewrite_jobs_old", scoped=False)
        op.execute(
            "INSERT INTO rewrite_jobs_old (id, content_key, idempotency_key, state, created_at) "
            "SELECT id, content_key, idempotency_key, state, created_at FROM rewrite_jobs"
        )
        op.drop_table("rewrite_jobs")
        op.rename_table("rewrite_jobs_old", "rewrite_jobs")
        return

    op.drop_index(op.f("ix_rewrite_jobs_output_channel_id"), table_name="rewrite_jobs")
    op.drop_constraint("uq_rewrite_job_content_output", "rewrite_jobs", type_="unique")
    for foreign_key in sa.inspect(bind).get_foreign_keys("rewrite_jobs"):
        if foreign_key["constrained_columns"] == ["output_channel_id"] and foreign_key["name"]:
            op.drop_constraint(foreign_key["name"], "rewrite_jobs", type_="foreignkey")
    op.drop_column("rewrite_jobs", "output_channel_id")
    op.create_unique_constraint("uq_rewrite_job_content", "rewrite_jobs", ["content_key"])
