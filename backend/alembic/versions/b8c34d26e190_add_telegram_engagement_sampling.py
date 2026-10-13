"""Retained Telegram engagement sampling jobs."""

import sqlalchemy as sa

from alembic import op

revision = "b8c34d26e190"
down_revision = "a7e239bc5180"
branch_labels = None
depends_on = None

TABLE = "telegram_engagement_sampling_jobs"


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Telegram sampling requires supported storage")
    checks = [
        ("state IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'BLOCKED', 'FAILED')", "state"),
        ("step BETWEEN 0 AND 7", "step"),
        ("attempts BETWEEN 0 AND 3", "attempts"),
        ("missed_windows BETWEEN 0 AND 6", "missed"),
        (
            "available_at >= created_at AND (lease_expires_at IS NULL OR lease_expires_at > available_at)",
            "time_order",
        ),
        (
            "incoming_post_id BETWEEN 1 AND 9223372036854775807 AND (expected_user_id IS NULL OR expected_user_id BETWEEN 1 AND 9223372036854775807)",
            "identity",
        ),
        (
            "last_error_code IS NULL OR last_error_code IN ('WAIT_SYNC', 'WAIT_COOLDOWN', 'RETRY_PROVIDER', 'FLOOD_WAIT', 'SOURCE_UNAVAILABLE', 'SESSION_UNAVAILABLE', 'INVALID_OBSERVATION', 'ATTEMPTS_EXHAUSTED', 'INVALID_SCHEDULE')",
            "error",
        ),
        (
            "(state = 'RUNNING' AND step <= 6 AND attempts BETWEEN 1 AND 3 AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL AND expected_user_id IS NOT NULL AND session_digest IS NOT NULL) OR (state <> 'RUNNING' AND claim_token IS NULL AND lease_expires_at IS NULL AND expected_user_id IS NULL AND session_digest IS NULL AND ((state = 'QUEUED' AND step <= 6) OR (state = 'SUCCEEDED' AND step = 7 AND attempts = 0) OR (state IN ('BLOCKED', 'FAILED') AND step <= 6 AND last_error_code IS NOT NULL)))",
            "claim",
        ),
    ]
    for column in ("available_at", "created_at", "lease_expires_at"):
        checks.append(
            (
                f"{column} IS NULL OR ({column} >= '0001-01-01 00:00:00+00' AND {column} <= '9999-12-31 23:59:59.999999+00')",
                f"{column}_time",
            )
        )
        if dialect == "sqlite":
            checks.append(
                (
                    f"{column} IS NULL OR (typeof({column}) = 'text' AND length({column}) = 26 AND length(CAST({column} AS BLOB)) = 26 AND substr({column},20,1) = '.' AND substr({column},21,6) NOT GLOB '*[^0-9]*' AND strftime('%Y-%m-%d %H:%M:%S', substr({column},1,19), '+0 days') IS substr({column},1,19))",
                    f"{column}_sqlite",
                )
            )
    if dialect == "sqlite":
        checks.extend(
            (f"{column} IS NULL OR typeof({column}) = 'integer'", f"{column}_sqlite")
            for column in (
                "incoming_post_id",
                "step",
                "attempts",
                "missed_windows",
                "expected_user_id",
            )
        )
        checks.extend(
            [
                (
                    "claim_token IS NULL OR (typeof(claim_token) = 'text' AND length(claim_token) = 36 AND length(CAST(claim_token AS BLOB)) = 36 AND substr(claim_token,9,1) = '-' AND substr(claim_token,14,1) = '-' AND substr(claim_token,19,1) = '-' AND substr(claim_token,24,1) = '-' AND length(replace(claim_token,'-','')) = 32 AND replace(claim_token,'-','') NOT GLOB '*[^0-9a-f]*')",
                    "token_sqlite",
                ),
                (
                    "session_digest IS NULL OR (typeof(session_digest) = 'text' AND length(session_digest) = 64 AND length(CAST(session_digest AS BLOB)) = 64 AND session_digest NOT GLOB '*[^0-9a-f]*')",
                    "digest_sqlite",
                ),
            ]
        )
    else:
        checks.extend(
            [
                (
                    "claim_token IS NULL OR claim_token ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'",
                    "token_postgresql",
                ),
                (
                    "session_digest IS NULL OR session_digest ~ '^[0-9a-f]{64}$'",
                    "digest_postgresql",
                ),
            ]
        )
    op.create_table(
        TABLE,
        sa.Column(
            "incoming_post_id",
            sa.Integer(),
            sa.ForeignKey("incoming_posts.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missed_windows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claim_token", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("expected_user_id", sa.BigInteger()),
        sa.Column("session_digest", sa.String(64)),
        sa.Column("last_error_code", sa.String(64)),
        *(
            sa.CheckConstraint(expression, name=f"ck_sampling_{name}")
            for expression, name in checks
        ),
    )
    op.create_index("ix_sampling_due", TABLE, ["state", "available_at", "lease_expires_at"])
    initial_invalid = (
        "NEW.state <> 'QUEUED' OR NEW.step <> 0 OR NEW.attempts <> 0 OR NEW.missed_windows <> 0"
    )
    duplicate = f"EXISTS (SELECT 1 FROM {TABLE} WHERE incoming_post_id = NEW.incoming_post_id)"
    missing_parent = "NOT EXISTS (SELECT 1 FROM incoming_posts WHERE id = NEW.incoming_post_id)"
    invalid_update = (
        "OLD.state IN ('SUCCEEDED', 'BLOCKED', 'FAILED') OR "
        "NEW.incoming_post_id <> OLD.incoming_post_id OR NEW.created_at <> OLD.created_at OR "
        "NEW.step < OLD.step OR NEW.missed_windows < OLD.missed_windows OR "
        "(NEW.step = OLD.step AND NEW.attempts < OLD.attempts) OR "
        "(OLD.state = 'QUEUED' AND NEW.state NOT IN ('QUEUED', 'RUNNING', 'BLOCKED', 'FAILED')) OR "
        "(OLD.state = 'RUNNING' AND NEW.state NOT IN ('RUNNING', 'QUEUED', 'SUCCEEDED', 'BLOCKED', 'FAILED'))"
    )
    retained = f"EXISTS (SELECT 1 FROM {TABLE} WHERE incoming_post_id = OLD.id)"
    changed_identity = " OR ".join(
        f"NEW.{column} <> OLD.{column}"
        for column in (
            "id",
            "telegram_account_id",
            "donor_channel_id",
            "telegram_message_id",
            "created_at",
        )
    )
    replaces_parent = f"EXISTS (SELECT 1 FROM incoming_posts p JOIN {TABLE} j ON j.incoming_post_id = p.id WHERE p.id = NEW.id OR (p.telegram_account_id = NEW.telegram_account_id AND p.donor_channel_id = NEW.donor_channel_id AND p.telegram_message_id = NEW.telegram_message_id))"
    if dialect == "sqlite":
        for name, action, table, condition, message in (
            (
                "sampling_initial",
                "INSERT",
                TABLE,
                f"{initial_invalid} OR {duplicate} OR {missing_parent}",
                "Telegram sampling initial identity is invalid",
            ),
            (
                "sampling_transition",
                "UPDATE",
                TABLE,
                invalid_update,
                "Telegram sampling transition is invalid",
            ),
            ("sampling_no_delete", "DELETE", TABLE, "1", "Telegram sampling jobs are retained"),
            (
                "sampling_incoming_no_delete",
                "DELETE",
                "incoming_posts",
                retained,
                "Telegram sampling source is retained",
            ),
            (
                "sampling_incoming_no_rebind",
                "UPDATE",
                "incoming_posts",
                f"{retained} AND ({changed_identity})",
                "Telegram sampling source is immutable",
            ),
            (
                "sampling_incoming_no_replace",
                "INSERT",
                "incoming_posts",
                replaces_parent,
                "Telegram sampling source is retained",
            ),
        ):
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT, '{message}'); END"
            )
    else:
        # Serialize admission with parent mutations even for non-key creation time.
        op.execute(
            f"CREATE FUNCTION sampling_initial() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM 1 FROM incoming_posts WHERE id = NEW.incoming_post_id FOR UPDATE; IF {initial_invalid} OR {duplicate} OR {missing_parent} THEN RAISE EXCEPTION 'Telegram sampling initial identity is invalid'; END IF; RETURN NEW; END; $$"
        )
        op.execute(
            f"CREATE TRIGGER sampling_initial BEFORE INSERT ON {TABLE} FOR EACH ROW EXECUTE FUNCTION sampling_initial()"
        )
        for name, action, table, condition, returns, message in (
            (
                "sampling_transition",
                "UPDATE",
                TABLE,
                invalid_update,
                "NEW",
                "Telegram sampling transition is invalid",
            ),
            (
                "sampling_no_delete",
                "DELETE",
                TABLE,
                "TRUE",
                "OLD",
                "Telegram sampling jobs are retained",
            ),
            (
                "sampling_incoming_no_delete",
                "DELETE",
                "incoming_posts",
                retained,
                "OLD",
                "Telegram sampling source is retained",
            ),
            (
                "sampling_incoming_no_rebind",
                "UPDATE",
                "incoming_posts",
                f"{retained} AND ({changed_identity})",
                "NEW",
                "Telegram sampling source is immutable",
            ),
            (
                "sampling_incoming_no_replace",
                "INSERT",
                "incoming_posts",
                replaces_parent,
                "NEW",
                "Telegram sampling source is retained",
            ),
        ):
            op.execute(
                f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF {condition} THEN RAISE EXCEPTION '{message}'; END IF; RETURN {returns}; END; $$"
            )
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {action} ON {table} FOR EACH ROW EXECUTE FUNCTION {name}()"
            )
        op.execute(
            f"CREATE FUNCTION sampling_no_truncate() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF EXISTS (SELECT 1 FROM {TABLE}) THEN RAISE EXCEPTION 'Telegram sampling jobs are retained'; END IF; RETURN NULL; END; $$"
        )
        for table in ("incoming_posts", TABLE):
            op.execute(
                f"CREATE TRIGGER sampling_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION sampling_no_truncate()"
            )


def downgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute(f"LOCK TABLE incoming_posts, {TABLE} IN ACCESS EXCLUSIVE MODE")
    else:
        op.execute(f"UPDATE {TABLE} SET incoming_post_id = incoming_post_id WHERE 1 = 0")
    if connection.scalar(sa.text(f"SELECT count(*) FROM {TABLE}")):
        raise RuntimeError("Refusing downgrade: Telegram sampling jobs are retained")
    for name in (
        "sampling_incoming_no_delete",
        "sampling_incoming_no_rebind",
        "sampling_incoming_no_replace",
    ):
        op.execute(
            f"DROP TRIGGER {name}"
            + (" ON incoming_posts" if connection.dialect.name == "postgresql" else "")
        )
    if connection.dialect.name == "postgresql":
        op.execute("DROP TRIGGER sampling_no_truncate ON incoming_posts")
    op.drop_table(TABLE)
    if connection.dialect.name == "postgresql":
        for name in (
            "sampling_initial",
            "sampling_transition",
            "sampling_no_delete",
            "sampling_incoming_no_delete",
            "sampling_incoming_no_rebind",
            "sampling_incoming_no_replace",
            "sampling_no_truncate",
        ):
            op.execute(f"DROP FUNCTION {name}()")
