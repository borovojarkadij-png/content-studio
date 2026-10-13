"""Immutable Telegram source publication times and aggregate observation history."""

import sqlalchemy as sa

from alembic import op

revision = "a7e239bc5180"
down_revision = "f6a42c91b805"
branch_labels = None
depends_on = None

SOURCES = "telegram_engagement_sources"
SNAPSHOTS = "telegram_engagement_snapshots"


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Telegram engagement history requires supported storage")
    op.create_table(
        SOURCES,
        sa.Column(
            "incoming_post_id",
            sa.Integer(),
            sa.ForeignKey("incoming_posts.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "published_at >= '0001-01-01 00:00:00+00' AND published_at <= '9999-12-31 23:59:59.999999+00'",
            name="ck_engagement_source_time",
        ),
        *(
            [
                sa.CheckConstraint(
                    "length(published_at) = 26 AND substr(published_at,20,1) = '.' AND substr(published_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%d %H:%M:%S', substr(published_at,1,19), '+0 days') IS substr(published_at,1,19)",
                    name="ck_engagement_source_time_sqlite",
                )
            ]
            if dialect == "sqlite"
            else []
        ),
    )
    op.create_table(
        SNAPSHOTS,
        sa.Column(
            "incoming_post_id",
            sa.Integer(),
            sa.ForeignKey(f"{SOURCES}.incoming_post_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), primary_key=True),
        *(
            sa.Column(metric, sa.BigInteger(), nullable=True)
            for metric in ("views", "forwards", "reactions")
        ),
        sa.CheckConstraint(
            "observed_at >= '0001-01-01 00:00:00+00' AND observed_at <= '9999-12-31 23:59:59.999999+00'",
            name="ck_engagement_snapshot_time",
        ),
        *(
            sa.CheckConstraint(
                f"{metric} IS NULL OR {metric} BETWEEN 0 AND 9223372036854775807",
                name=f"ck_engagement_{metric}_signed64",
            )
            for metric in ("views", "forwards", "reactions")
        ),
        *(
            [
                sa.CheckConstraint(
                    "length(observed_at) = 26 AND substr(observed_at,20,1) = '.' AND substr(observed_at,21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%d %H:%M:%S', substr(observed_at,1,19), '+0 days') IS substr(observed_at,1,19)",
                    name="ck_engagement_snapshot_time_sqlite",
                ),
                *(
                    sa.CheckConstraint(
                        f"{metric} IS NULL OR typeof({metric}) = 'integer'",
                        name=f"ck_engagement_{metric}_type_sqlite",
                    )
                    for metric in ("views", "forwards", "reactions")
                ),
            ]
            if dialect == "sqlite"
            else []
        ),
    )
    for table, parent, parent_key, unique in (
        (SOURCES, "incoming_posts", "id", "incoming_post_id = NEW.incoming_post_id"),
        (
            SNAPSHOTS,
            SOURCES,
            "incoming_post_id",
            "incoming_post_id = NEW.incoming_post_id AND observed_at = NEW.observed_at",
        ),
    ):
        parent_check = f"EXISTS (SELECT 1 FROM {parent} WHERE {parent_key} = NEW.incoming_post_id)"
        if table == SNAPSHOTS:
            comparison = "NEW.observed_at >= published_at"
            parent_check = f"EXISTS (SELECT 1 FROM {SOURCES} WHERE incoming_post_id = NEW.incoming_post_id AND {comparison})"
        if dialect == "sqlite":
            op.execute(
                f"CREATE TRIGGER {table}_require_parent BEFORE INSERT ON {table} WHEN NOT {parent_check} BEGIN SELECT RAISE(ABORT, 'Telegram engagement parent/time required'); END"
            )
            op.execute(
                f"CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE {unique}) BEGIN SELECT RAISE(ABORT, 'Telegram engagement history is append-only'); END"
            )
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Telegram engagement history is append-only'); END"
                )
        else:
            op.execute(
                f"CREATE FUNCTION {table}_require_parent() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NOT {parent_check} THEN RAISE EXCEPTION 'Telegram engagement parent/time required'; END IF; RETURN NEW; END; $$"
            )
            op.execute(
                f"CREATE TRIGGER {table}_require_parent BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_require_parent()"
            )
            op.execute(
                f"CREATE FUNCTION {table}_refuse_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Telegram engagement history is append-only'; END; $$"
            )
            op.execute(
                f"CREATE TRIGGER {table}_no_mutation BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {table}_refuse_mutation()"
            )
            op.execute(
                f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {table}_refuse_mutation()"
            )
    # Parent identity must remain meaningful even with SQLite FK enforcement off.
    identity_change = " OR ".join(
        f"NEW.{name} <> OLD.{name}"
        for name in ("id", "telegram_account_id", "donor_channel_id", "telegram_message_id")
    )
    retained = f"EXISTS (SELECT 1 FROM {SOURCES} WHERE incoming_post_id = OLD.id)"
    if dialect == "sqlite":
        op.execute(
            f"CREATE TRIGGER engagement_incoming_no_delete BEFORE DELETE ON incoming_posts WHEN {retained} BEGIN SELECT RAISE(ABORT, 'Telegram engagement source is retained'); END"
        )
        op.execute(
            f"CREATE TRIGGER engagement_incoming_no_rebind BEFORE UPDATE ON incoming_posts WHEN {retained} AND ({identity_change}) BEGIN SELECT RAISE(ABORT, 'Telegram engagement source is immutable'); END"
        )
        op.execute(
            f"CREATE TRIGGER engagement_incoming_no_replace BEFORE INSERT ON incoming_posts WHEN EXISTS (SELECT 1 FROM incoming_posts p JOIN {SOURCES} s ON s.incoming_post_id = p.id WHERE p.id = NEW.id OR (p.telegram_account_id = NEW.telegram_account_id AND p.donor_channel_id = NEW.donor_channel_id AND p.telegram_message_id = NEW.telegram_message_id)) BEGIN SELECT RAISE(ABORT, 'Telegram engagement source is retained'); END"
        )
    else:
        op.execute(
            f"CREATE FUNCTION engagement_incoming_no_rebind() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {retained} AND ({identity_change}) THEN RAISE EXCEPTION 'Telegram engagement source is immutable'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            "CREATE TRIGGER engagement_incoming_no_rebind BEFORE UPDATE ON incoming_posts FOR EACH ROW EXECUTE FUNCTION engagement_incoming_no_rebind()"
        )


def downgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Writers take the incoming lock first; use the same order before removing
        # its new retention trigger, which itself requires an exclusive table lock.
        op.execute(f"LOCK TABLE incoming_posts, {SOURCES}, {SNAPSHOTS} IN ACCESS EXCLUSIVE MODE")
    else:
        op.execute(f"UPDATE {SOURCES} SET incoming_post_id = incoming_post_id WHERE 1 = 0")
    for table in (SNAPSHOTS, SOURCES):
        if connection.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError(
                "Refusing downgrade: immutable Telegram engagement history is populated"
            )
    if connection.dialect.name == "sqlite":
        for suffix in ("no_delete", "no_rebind", "no_replace"):
            op.execute(f"DROP TRIGGER engagement_incoming_{suffix}")
    else:
        op.execute("DROP TRIGGER engagement_incoming_no_rebind ON incoming_posts")
        op.execute("DROP FUNCTION engagement_incoming_no_rebind()")
    for table in (SNAPSHOTS, SOURCES):
        op.drop_table(table)
        if connection.dialect.name == "postgresql":
            op.execute(f"DROP FUNCTION {table}_require_parent()")
            op.execute(f"DROP FUNCTION {table}_refuse_mutation()")
