"""Create append-only illustration review history, not an approval permission."""

import sqlalchemy as sa

from alembic import op

revision = "c5e81b29a704"
down_revision = "a8d310f62c94"
branch_labels = None
depends_on = None


def _digest_check(column):
    remaining = column
    for character in "0123456789abcdef":
        remaining = f"replace({remaining}, '{character}', '')"
    return f"length({column}) = 64 AND {remaining} = ''"


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Illustration review history requires supported append-only storage")
    op.create_table(
        "illustration_review_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_key", sa.String(128), nullable=False),
        sa.Column("record_kind", sa.String(16), nullable=False),
        sa.Column(
            "revokes_review_id", sa.Integer(), sa.ForeignKey("illustration_review_records.id")
        ),
        sa.Column(
            "candidate_id", sa.Integer(), sa.ForeignKey("publication_candidates.id"), nullable=False
        ),
        sa.Column(
            "output_channel_id", sa.Integer(), sa.ForeignKey("output_channels.id"), nullable=False
        ),
        sa.Column("mapping_id", sa.Integer(), sa.ForeignKey("channel_mappings.id"), nullable=False),
        sa.Column("content_key", sa.String(255), nullable=False),
        sa.Column(
            "source_revision_id",
            sa.Integer(),
            sa.ForeignKey("incoming_post_revisions.id"),
            nullable=False,
        ),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column(
            "rewrite_output_id", sa.Integer(), sa.ForeignKey("rewrite_outputs.id"), nullable=False
        ),
        sa.Column("draft_sha256", sa.String(64), nullable=False),
        sa.Column("media_asset_id", sa.Integer(), sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("media_sha256", sa.String(64), nullable=False),
        sa.Column("asset_metadata_sha256", sa.String(64), nullable=False),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=False),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=True),
        sa.Column("illustration_acknowledged", sa.Boolean(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("operation_key", name="uq_illustration_review_operation"),
        sa.UniqueConstraint("revokes_review_id", name="uq_illustration_review_revocation"),
        sa.CheckConstraint(
            "id > 0 AND reviewer_id > 0 AND candidate_id > 0 AND output_channel_id > 0 "
            "AND mapping_id > 0 AND source_revision_id > 0 "
            "AND rewrite_output_id > 0 AND media_asset_id > 0",
            name="ck_illustration_review_ids",
        ),
        sa.CheckConstraint(
            "provenance = 'AUTHENTICATED_HUMAN_V1'", name="ck_illustration_review_provenance"
        ),
        *(
            [
                sa.CheckConstraint(
                    "typeof(reviewer_id) = 'integer'", name="ck_illustration_review_reviewer_type"
                )
            ]
            if dialect == "sqlite"
            else []
        ),
        sa.CheckConstraint(
            "illustration_acknowledged IS NULL OR illustration_acknowledged IN (false, true)",
            name="ck_illustration_review_ack",
        ),
        sa.CheckConstraint(
            "length(operation_key) BETWEEN 1 AND 128 AND length(trim(operation_key)) > 0",
            name="ck_illustration_review_operation",
        ),
        sa.CheckConstraint(
            "length(content_key) BETWEEN 1 AND 255 AND length(trim(content_key)) > 0",
            name="ck_illustration_review_content",
        ),
        sa.CheckConstraint(
            "length(review_note) BETWEEN 1 AND 2048 AND length(trim(review_note)) > 0",
            name="ck_illustration_review_note",
        ),
        sa.CheckConstraint(
            "(record_kind = 'REVIEW' AND revokes_review_id IS NULL "
            "AND verdict IS NOT NULL AND verdict IN "
            "('APPROVED_ILLUSTRATION', 'REJECTED', 'UNCERTAIN') "
            "AND illustration_acknowledged IS NOT NULL "
            "AND (verdict <> 'APPROVED_ILLUSTRATION' OR illustration_acknowledged = true)) "
            "OR (record_kind = 'REVOCATION' AND revokes_review_id IS NOT NULL "
            "AND revokes_review_id < id AND verdict IS NULL "
            "AND illustration_acknowledged IS NULL)",
            name="ck_illustration_review_kind",
        ),
        *(
            sa.CheckConstraint(_digest_check(column), name=f"ck_illustration_review_{column}")
            for column in ("source_sha256", "draft_sha256", "media_sha256", "asset_metadata_sha256")
        ),
    )
    op.create_index(
        "ix_illustration_review_candidate", "illustration_review_records", ["candidate_id", "id"]
    )
    parent_match = " AND ".join(
        f"original.{column} = NEW.{column}"
        for column in (
            "candidate_id",
            "output_channel_id",
            "mapping_id",
            "content_key",
            "source_revision_id",
            "source_sha256",
            "rewrite_output_id",
            "draft_sha256",
            "media_asset_id",
            "media_sha256",
            "asset_metadata_sha256",
        )
    )
    missing_parent = (
        "NEW.record_kind = 'REVOCATION' AND NOT EXISTS "
        "(SELECT 1 FROM illustration_review_records AS original "
        "WHERE original.id = NEW.revokes_review_id AND original.record_kind = 'REVIEW' "
        f"AND {parent_match})"
    )
    if dialect == "sqlite":
        # SQLite connections may leave foreign_keys disabled. Do not silently
        # accept an immutable audit row pointing at nonexistent canonical data;
        # keep this guard local instead of changing unrelated connection policy.
        missing_reference = " OR ".join(
            f"NOT EXISTS (SELECT 1 FROM {table} WHERE id = NEW.{column})"
            for table, column in (
                ("publication_candidates", "candidate_id"),
                ("output_channels", "output_channel_id"),
                ("channel_mappings", "mapping_id"),
                ("incoming_post_revisions", "source_revision_id"),
                ("rewrite_outputs", "rewrite_output_id"),
                ("media_assets", "media_asset_id"),
            )
        )
        op.execute(
            sa.text(
                "CREATE TRIGGER illustration_review_require_references "
                f"BEFORE INSERT ON illustration_review_records WHEN {missing_reference} "
                "BEGIN SELECT RAISE(ABORT, 'Canonical illustration references required'); END"
            )
        )
        op.execute(
            sa.text(
                "CREATE TRIGGER illustration_review_require_parent "
                f"BEFORE INSERT ON illustration_review_records WHEN {missing_parent} "
                "BEGIN SELECT RAISE(ABORT, 'Exact original illustration review required'); END"
            )
        )
        # OR REPLACE implicitly deletes conflicting rows without invoking DELETE
        # triggers when recursive_triggers is off (the default). Fence every
        # replacement-capable key before SQLite performs that deletion.
        op.execute(
            sa.text(
                "CREATE TRIGGER illustration_review_no_replace "
                "BEFORE INSERT ON illustration_review_records "
                "WHEN EXISTS (SELECT 1 FROM illustration_review_records "
                "WHERE id = NEW.id OR operation_key = NEW.operation_key "
                "OR (NEW.revokes_review_id IS NOT NULL "
                "AND revokes_review_id = NEW.revokes_review_id)) "
                "BEGIN SELECT RAISE(ABORT, 'Illustration review history is append-only'); END"
            )
        )
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                sa.text(
                    f"CREATE TRIGGER illustration_review_no_{operation.lower()} "
                    f"BEFORE {operation} ON illustration_review_records BEGIN "
                    "SELECT RAISE(ABORT, 'Illustration review history is append-only'); END"
                )
            )
    else:
        op.execute(
            sa.text(
                "CREATE FUNCTION illustration_review_require_parent() RETURNS trigger "
                f"LANGUAGE plpgsql AS $$ BEGIN IF {missing_parent} THEN "
                "RAISE EXCEPTION 'Exact original illustration review required'; "
                "END IF; RETURN NEW; END; $$"
            )
        )
        op.execute(
            sa.text(
                "CREATE TRIGGER illustration_review_require_parent "
                "BEFORE INSERT ON illustration_review_records "
                "FOR EACH ROW EXECUTE FUNCTION illustration_review_require_parent()"
            )
        )
        op.execute(
            sa.text(
                "CREATE FUNCTION illustration_review_refuse_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'Illustration review history is append-only'; END; $$"
            )
        )
        op.execute(
            sa.text(
                "CREATE TRIGGER illustration_review_no_mutation "
                "BEFORE UPDATE OR DELETE ON illustration_review_records "
                "FOR EACH ROW EXECUTE FUNCTION illustration_review_refuse_mutation()"
            )
        )
        # TRUNCATE bypasses row DELETE triggers, including a table's self-FK.
        op.execute(
            sa.text(
                "CREATE TRIGGER illustration_review_no_truncate "
                "BEFORE TRUNCATE ON illustration_review_records "
                "FOR EACH STATEMENT EXECUTE FUNCTION illustration_review_refuse_mutation()"
            )
        )


def downgrade():
    # Hold write/exclusive protection BEFORE counting through DROP. Otherwise
    # another connection can commit the first review after COUNT=0 and lose it.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("LOCK TABLE illustration_review_records IN ACCESS EXCLUSIVE MODE"))
    else:
        # A zero-row DML statement acquires SQLite's write transaction even
        # under legacy SELECT/DDL autocommit. It never updates a history row.
        op.execute(sa.text("UPDATE illustration_review_records SET id = id WHERE 1 = 0"))
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM illustration_review_records")):
        raise RuntimeError("Refusing to discard immutable illustration review history")
    op.drop_table("illustration_review_records")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP FUNCTION illustration_review_refuse_mutation()"))
        op.execute(sa.text("DROP FUNCTION illustration_review_require_parent()"))
