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


def _eligible_outputs(bind, content_key):
    # Freeze the historical hard gate here: migrations must not import future
    # mutable application policy. Unknown/corrupt classification fails closed.
    decision = (
        bind.execute(
            sa.text("SELECT * FROM editorial_decisions WHERE content_key = :key"),
            {"key": content_key},
        )
        .mappings()
        .one_or_none()
    )
    if (
        decision is None
        or decision["status"] != "PASS"
        or decision["rewrite_allowed"] not in (True, 1)
        or not isinstance(decision["sentiment"], str)
        or decision["sentiment"].lower() not in {"negative", "neutral", "positive"}
        or not isinstance(decision["framing"], str)
        or decision["framing"].lower() not in {"hostile", "neutral", "positive"}
        or not isinstance(decision["protected_entities"], str)
    ):
        return set()
    if any(value.strip() for value in decision["protected_entities"].split(",")) and (
        decision["sentiment"].lower() == "negative" or decision["framing"].lower() == "hostile"
    ):
        return set()
    return set(
        bind.execute(
            sa.text(
                "SELECT output_channel_id FROM publication_candidates "
                "WHERE content_key = :key AND state = 'AWAITING_REWRITE'"
            ),
            {"key": content_key},
        ).scalars()
    )


def _scope_legacy_jobs(bind) -> None:
    """Make pending legacy fan-out explicit instead of cross-activating it.

    A former global rewrite job can safely retain its state only if precisely
    one awaiting candidate exists. More than one output needs independently
    styled rewrites, so preserve the old job as audit evidence and create fresh
    per-output dispatches.
    """
    legacy_jobs = bind.execute(
        sa.text("SELECT id, content_key FROM rewrite_jobs WHERE output_channel_id IS NULL")
    ).mappings()
    for job in legacy_jobs:
        output_ids = (
            bind.execute(
                sa.text(
                    "SELECT DISTINCT output_channel_id FROM publication_candidates "
                    "WHERE content_key = :content_key"
                ),
                {"content_key": job["content_key"]},
            )
            .scalars()
            .all()
        )
        if len(output_ids) == 1:
            output_channel_id = output_ids[0]
            idempotency_key = f"rewrite.requested:{job['content_key']}:{output_channel_id}"
            bind.execute(
                sa.text(
                    "UPDATE rewrite_jobs SET output_channel_id = :output_channel_id, "
                    "idempotency_key = :idempotency_key WHERE id = :id"
                ),
                {
                    "id": job["id"],
                    "output_channel_id": output_channel_id,
                    "idempotency_key": idempotency_key,
                },
            )
            bind.execute(
                sa.text(
                    "UPDATE outbox_events SET idempotency_key = :idempotency_key "
                    "WHERE idempotency_key = :legacy_key"
                ),
                {
                    "idempotency_key": idempotency_key,
                    "legacy_key": f"rewrite.requested:{job['content_key']}",
                },
            )
            continue
        if len(output_ids) < 2:
            continue
        bind.execute(
            sa.text("UPDATE rewrite_jobs SET state = 'SUPERSEDED' WHERE id = :id"),
            {"id": job["id"]},
        )
        bind.execute(
            sa.text(
                "UPDATE outbox_events SET event_type = 'rewrite.superseded' "
                "WHERE idempotency_key = :legacy_key"
            ),
            {"legacy_key": f"rewrite.requested:{job['content_key']}"},
        )
        for output_channel_id in sorted(_eligible_outputs(bind, job["content_key"])):
            idempotency_key = f"rewrite.requested:{job['content_key']}:{output_channel_id}"
            bind.execute(
                sa.text(
                    "INSERT INTO rewrite_jobs "
                    "(content_key, output_channel_id, idempotency_key, state) "
                    "VALUES (:content_key, :output_channel_id, :idempotency_key, 'DISPATCHED')"
                ),
                {
                    "content_key": job["content_key"],
                    "output_channel_id": output_channel_id,
                    "idempotency_key": idempotency_key,
                },
            )
            bind.execute(
                sa.text(
                    "INSERT INTO outbox_events (event_type, aggregate_key, idempotency_key) "
                    "VALUES ('rewrite.requested', :content_key, :idempotency_key)"
                ),
                {
                    "content_key": job["content_key"],
                    "idempotency_key": idempotency_key,
                },
            )


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
        _scope_legacy_jobs(bind)
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
    _scope_legacy_jobs(bind)


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
