"""Retained Telegram intake comparison streams and windows."""

import sqlalchemy as sa

from alembic import op

revision = "c9d45e37f201"
down_revision = "b8c34d26e190"
branch_labels = None
depends_on = None

STREAMS = "telegram_intake_selection_streams"
WINDOWS = "telegram_intake_selection_windows"


def _checks(kind, dialect, ranges, digests, payloads):
    checks = [(column, f"{column} BETWEEN {low} AND {high}") for column, low, high in ranges]
    checks.extend((column, f"length({column}) <= {limit}") for column, limit in payloads)
    checks.append(
        (
            "created_at",
            (
                "created_at >= '0001-01-01 00:00:00+00' AND "
                "created_at <= '9999-12-31 23:59:59.999999+00'"
            ),
        )
    )
    checks.extend(
        (
            f"{column}_digest",
            f"length({column}) = 64 AND "
            + "replace(" * 16
            + column
            + "".join(f",'{digit}','')" for digit in "0123456789abcdef")
            + " = ''",
        )
        for column in digests
    )
    if kind == "window":
        checks.append(("algorithm_version", "algorithm_version = 'intake-selection-v1'"))
    if dialect == "sqlite":
        checks.extend(
            (f"{column}_sqlite", f"typeof({column}) = 'integer'") for column, _, _ in ranges
        )
        text_columns = [*digests, *(column for column, _ in payloads)]
        if kind == "window":
            text_columns.append("algorithm_version")
        checks.extend(
            (
                f"{column}_sqlite",
                f"typeof({column}) = 'text' AND length(CAST({column} AS BLOB)) = length({column})",
            )
            for column in text_columns
        )
        checks.append(
            (
                "created_at_sqlite",
                (
                    "typeof(created_at) = 'text' AND "
                    "length(created_at) = 26 AND length(CAST(created_at AS BLOB)) = 26 AND "
                    "substr(created_at,20,1) = '.' AND "
                    "substr(created_at,21,6) NOT GLOB '*[^0-9]*' AND "
                    "strftime('%Y-%m-%d %H:%M:%S', substr(created_at,1,19), '+0 days') "
                    "IS substr(created_at,1,19)"
                ),
            )
        )
    else:
        checks.extend(
            (
                "payload_postgresql" if kind == "stream" else f"{column}_postgresql",
                f"octet_length({column}) = length({column})",
            )
            for column, _ in payloads
        )
    return [
        sa.CheckConstraint(expression, name=f"ck_intake_{kind}_{name}")
        for name, expression in checks
    ]


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Telegram intake ledger requires supported storage")
    signed64 = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    maximum = 9223372036854775807
    op.create_table(
        STREAMS,
        sa.Column("id", signed64, primary_key=True),
        sa.Column(
            "mapping_id",
            sa.Integer(),
            sa.ForeignKey("channel_mappings.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("policy_binding_sha256", sa.String(64), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("policy_payload", sa.Text(), nullable=False),
        sa.Column("carry", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_sequence", signed64, server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("mapping_id", "policy_binding_sha256", name="uq_intake_stream_binding"),
        *_checks(
            "stream",
            dialect,
            [
                ("id", 1, maximum),
                ("mapping_id", 1, maximum),
                ("carry", 0, 99),
                ("next_sequence", 1, maximum),
            ],
            ["policy_binding_sha256", "policy_sha256"],
            [("policy_payload", 256)],
        ),
    )
    op.create_table(
        WINDOWS,
        sa.Column("id", signed64, primary_key=True),
        sa.Column(
            "stream_id",
            signed64,
            sa.ForeignKey(f"{STREAMS}.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence", signed64, nullable=False),
        sa.Column("window_key", sa.String(64), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("algorithm_version", sa.String(32), nullable=False),
        sa.Column("carry_in", sa.Integer(), nullable=False),
        sa.Column("carry_out", sa.Integer(), nullable=False),
        sa.Column("input_payload", sa.Text(), nullable=False),
        sa.Column("result_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("stream_id", "window_key", name="uq_intake_window_key"),
        sa.UniqueConstraint("stream_id", "sequence", name="uq_intake_window_sequence"),
        *_checks(
            "window",
            dialect,
            [
                ("id", 1, maximum),
                ("stream_id", 1, maximum),
                ("sequence", 1, maximum - 1),
                ("carry_in", 0, 99),
                ("carry_out", 0, 99),
            ],
            ["window_key", "input_sha256"],
            [("input_payload", 262144), ("result_payload", 262144)],
        ),
    )
    _install_guards(dialect)


def _install_guards(dialect):
    distinct = "IS NOT" if dialect == "sqlite" else "IS DISTINCT FROM"
    immutable = " OR ".join(
        f"NEW.{column} {distinct} OLD.{column}"
        for column in (
            "id",
            "mapping_id",
            "policy_binding_sha256",
            "policy_sha256",
            "policy_payload",
            "created_at",
        )
    )
    stream_initial = (
        "NEW.carry <> 0 OR NEW.next_sequence <> 1 OR "
        "NOT EXISTS (SELECT 1 FROM channel_mappings WHERE id = NEW.mapping_id) OR "
        f"EXISTS (SELECT 1 FROM {STREAMS} WHERE id = NEW.id OR "
        "(mapping_id = NEW.mapping_id AND policy_binding_sha256 = NEW.policy_binding_sha256))"
    )
    stream_advance = (
        f"{immutable} OR OLD.next_sequence = 9223372036854775807 OR "
        "NEW.next_sequence <> OLD.next_sequence + 1 OR "
        f"NOT EXISTS (SELECT 1 FROM {WINDOWS} WHERE stream_id = OLD.id AND "
        "sequence = OLD.next_sequence AND carry_in = OLD.carry AND carry_out = NEW.carry)"
    )
    window_initial = (
        f"NOT EXISTS (SELECT 1 FROM {STREAMS} WHERE id = NEW.stream_id AND "
        "next_sequence = NEW.sequence AND carry = NEW.carry_in) OR "
        f"EXISTS (SELECT 1 FROM {WINDOWS} WHERE id = NEW.id OR "
        "(stream_id = NEW.stream_id AND "
        "(window_key = NEW.window_key OR sequence = NEW.sequence)))"
    )
    always = "1" if dialect == "sqlite" else "TRUE"
    for name, action, table, condition, returns, message, lock in (
        (
            "intake_stream_initial",
            "INSERT",
            STREAMS,
            stream_initial,
            "NEW",
            "Telegram intake stream initial identity is invalid",
            "PERFORM 1 FROM channel_mappings WHERE id = NEW.mapping_id FOR UPDATE;",
        ),
        (
            "intake_stream_advance",
            "UPDATE",
            STREAMS,
            stream_advance,
            "NEW",
            "Telegram intake stream advancement is invalid",
            "",
        ),
        (
            "intake_stream_no_delete",
            "DELETE",
            STREAMS,
            always,
            "OLD",
            "Telegram intake streams are retained",
            "",
        ),
        (
            "intake_window_initial",
            "INSERT",
            WINDOWS,
            window_initial,
            "NEW",
            "Telegram intake window initial identity is invalid",
            f"PERFORM 1 FROM {STREAMS} WHERE id = NEW.stream_id FOR UPDATE;",
        ),
        (
            "intake_window_no_update",
            "UPDATE",
            WINDOWS,
            always,
            "NEW",
            "Telegram intake windows are immutable",
            "",
        ),
        (
            "intake_window_no_delete",
            "DELETE",
            WINDOWS,
            always,
            "OLD",
            "Telegram intake windows are retained",
            "",
        ),
    ):
        if dialect == "sqlite":
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {action} ON {table} WHEN {condition} "
                f"BEGIN SELECT RAISE(ABORT, '{message}'); END"
            )
        else:
            op.execute(
                f"CREATE FUNCTION {name}() RETURNS trigger LANGUAGE plpgsql AS $$ "
                f"BEGIN {lock} IF {condition} THEN RAISE EXCEPTION '{message}'; "
                f"END IF; RETURN {returns}; END; $$"
            )
            op.execute(
                f"CREATE TRIGGER {name} BEFORE {action} ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {name}()"
            )
    if dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION intake_no_truncate() RETURNS trigger LANGUAGE plpgsql AS $$ "
            f"BEGIN IF EXISTS (SELECT 1 FROM {STREAMS}) OR "
            f"EXISTS (SELECT 1 FROM {WINDOWS}) THEN "
            "RAISE EXCEPTION 'Telegram intake comparison history is retained'; "
            "END IF; RETURN NULL; END; $$"
        )
        for table in (STREAMS, WINDOWS):
            op.execute(
                f"CREATE TRIGGER intake_no_truncate BEFORE TRUNCATE ON {table} "
                "FOR EACH STATEMENT EXECUTE FUNCTION intake_no_truncate()"
            )


def downgrade():
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("Telegram intake ledger requires supported storage")
    if dialect == "postgresql":
        op.execute(f"LOCK TABLE channel_mappings, {STREAMS}, {WINDOWS} IN ACCESS EXCLUSIVE MODE")
    else:
        op.execute(f"UPDATE {STREAMS} SET carry = carry WHERE 1 = 0")
    stream_count = connection.scalar(sa.text(f"SELECT count(*) FROM {STREAMS}"))
    window_count = connection.scalar(sa.text(f"SELECT count(*) FROM {WINDOWS}"))
    if stream_count or window_count:
        raise RuntimeError("Refusing downgrade: Telegram intake comparison history is retained")
    op.drop_table(WINDOWS)
    op.drop_table(STREAMS)
    if dialect == "postgresql":
        for name in (
            "intake_stream_initial",
            "intake_stream_advance",
            "intake_stream_no_delete",
            "intake_window_initial",
            "intake_window_no_update",
            "intake_window_no_delete",
            "intake_no_truncate",
        ):
            op.execute(f"DROP FUNCTION {name}()")
