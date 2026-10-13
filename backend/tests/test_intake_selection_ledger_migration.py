"""Synthetic migrated comparison evidence; no ingress or provider activation."""

from os import getenv

import pytest
from alembic.config import Config
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.persistence import models

STREAMS = "telegram_intake_selection_streams"
WINDOWS = "telegram_intake_selection_windows"
PREVIOUS = "b8c34d26e190"
HEAD = "c9d45e37f201"
STAMP = "2030-01-01 00:00:00.000000"
BINDING = "a" * 64
POLICY_HASH = "b" * 64
WINDOW_KEY = "c" * 64
INPUT_HASH = "d" * 64


@pytest.fixture(autouse=True)
def no_rewrite_calls(monkeypatch):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter import OpenRouterRewriteProvider

    def forbidden(*args, **kwargs):
        pytest.fail("Intake schema invoked rewrite provider")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(OpenRouterRewriteProvider, "rewrite", forbidden)


def seed_old_rows(engine):
    with Session(engine) as session, session.begin():
        session.add(
            models.TelegramAccount(
                id=1, name="synthetic", telegram_user_id=41, encrypted_session=""
            )
        )
        session.flush()
        session.add(
            models.DonorChannel(
                id=1, telegram_account_id=1, telegram_channel_id=-1000000000001, title="synthetic"
            )
        )
        session.add(
            models.OutputChannel(
                id=1, telegram_account_id=1, telegram_channel_id=-1000000000002, title="synthetic"
            )
        )
        session.flush()
        session.add(
            models.ChannelMappingModel(
                id=1,
                donor_channel_id=1,
                output_channel_id=1,
                intake_percent=30,
                target_mix_percent=0,
            )
        )
        session.add(
            models.IncomingPostModel(
                id=1,
                telegram_account_id="1",
                donor_channel_id="-1000000000001",
                telegram_message_id=7,
                state="RECEIVED",
            )
        )
        session.flush()
        session.add(
            models.ContentRevisionModel(
                incoming_post_id=1, revision_number=1, source_text="Synthetic unchanged source"
            )
        )
        session.add(
            models.EditorialDecisionModel(
                content_key="1:-1000000000001:7:revision:1",
                status="REJECT",
                rewrite_allowed=False,
                sentiment="neutral",
                framing="neutral",
            )
        )


def assert_old_rows(connection):
    assert connection.scalar(text("SELECT source_text FROM incoming_post_revisions")) == (
        "Synthetic unchanged source"
    )
    assert connection.execute(
        text("SELECT status,rewrite_allowed FROM editorial_decisions")
    ).one() == ("REJECT", False)
    for table in ("rewrite_jobs", "rewrite_usage", "outbox_events"):
        assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def insert_stream(connection, *, expression=None, replace=False, **overrides):
    values = {
        "id": 1,
        "mapping_id": 1,
        "policy_binding_sha256": BINDING,
        "policy_sha256": POLICY_HASH,
        "policy_payload": "{}",
        "carry": 0,
        "next_sequence": 1,
        "created_at": STAMP,
    }
    values.update(overrides)
    slots = {key: f":{key}" for key in values}
    if expression:
        slots.update(expression)
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    connection.execute(
        text(f"{verb} INTO {STREAMS} ({','.join(values)}) VALUES ({','.join(slots.values())})"),
        values,
    )


def insert_window(connection, *, expression=None, replace=False, **overrides):
    values = {
        "id": 1,
        "stream_id": 1,
        "sequence": 1,
        "window_key": WINDOW_KEY,
        "input_sha256": INPUT_HASH,
        "algorithm_version": "intake-selection-v1",
        "carry_in": 0,
        "carry_out": 30,
        "input_payload": "{}",
        "result_payload": "{}",
        "created_at": STAMP,
    }
    values.update(overrides)
    slots = {key: f":{key}" for key in values}
    if expression:
        slots.update(expression)
    verb = "INSERT OR REPLACE" if replace else "INSERT"
    connection.execute(
        text(f"{verb} INTO {WINDOWS} ({','.join(values)}) VALUES ({','.join(slots.values())})"),
        values,
    )


@pytest.fixture
def store(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'intake.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, PREVIOUS)
    engine = create_engine(url)
    seed_old_rows(engine)
    command.upgrade(config, "head")
    try:
        yield engine, config
    finally:
        with engine.connect() as connection:
            assert_old_rows(connection)
        engine.dispose()


def test_migration_exposes_both_ledger_tables(store):
    engine, _ = store
    assert inspect(engine).has_table(STREAMS)
    assert inspect(engine).has_table(WINDOWS)


@pytest.fixture
def stream(store):
    engine, config = store
    with engine.begin() as connection:
        insert_stream(connection)
    return engine, config


@pytest.fixture
def history(stream):
    engine, config = stream
    with engine.begin() as connection:
        insert_window(connection)
        connection.execute(text(f"UPDATE {STREAMS} SET carry=30,next_sequence=2"))
    return engine, config


def test_window_raw_update_is_refused_even_when_row_checks_remain_valid(stream):
    engine, _ = stream
    with engine.begin() as connection:
        insert_window(connection)
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {WINDOWS} SET carry_out=99"))


def test_stream_cannot_advance_without_corresponding_window(stream):
    engine, _ = stream
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {STREAMS} SET carry=30,next_sequence=2"))


BAD_DIGESTS = [
    None,
    "",
    "a" * 63,
    "a" * 65,
    "A" * 64,
    "g" * 64,
    "a" * 63 + "é",
    "a" * 64 + "\x00hidden",
    b"a" * 64,
]


@pytest.mark.parametrize("column", ["policy_binding_sha256", "policy_sha256"])
@pytest.mark.parametrize("value", BAD_DIGESTS)
def test_stream_digest_storage_rejects_malformed_uppercase_nul_and_blob(store, column, value):
    engine, _ = store
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_stream(connection, **{column: value})


@pytest.mark.parametrize("column", ["window_key", "input_sha256"])
@pytest.mark.parametrize("value", BAD_DIGESTS)
def test_window_digest_storage_rejects_malformed_uppercase_nul_and_blob(stream, column, value):
    engine, _ = stream
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_window(connection, **{column: value})


@pytest.mark.parametrize(
    "column,values",
    [
        ("id", [0, -1, 1.5, "invalid", b"1", "9223372036854775808"]),
        ("mapping_id", [0, -1, 2, 1.5, "invalid", b"1", "9223372036854775808"]),
        ("carry", [-1, 100, 1.5, "invalid", b"0", 1, 99]),
        ("next_sequence", [0, -1, 1.5, "invalid", b"1", 2, "9223372036854775808"]),
    ],
)
def test_stream_identity_initial_state_and_integer_storage(store, column, values):
    engine, _ = store
    for value in values:
        with engine.begin() as connection, pytest.raises(DBAPIError):
            insert_stream(connection, **{column: value})


@pytest.mark.parametrize(
    "column,values",
    [
        ("id", [0, -1, 1.5, "invalid", b"1", "9223372036854775808"]),
        ("stream_id", [0, -1, 2, 1.5, "invalid", b"1", "9223372036854775808"]),
        ("sequence", [0, -1, 2, 1.5, "invalid", b"1", "9223372036854775807"]),
        ("carry_in", [-1, 100, 1, 1.5, "invalid", b"0"]),
        ("carry_out", [-1, 100, 1.5, "invalid", b"0"]),
        ("algorithm_version", ["invalid", "intake-selection-v1\x00hidden", b"intake-selection-v1"]),
    ],
)
def test_window_identity_state_integer_and_version_storage(stream, column, values):
    engine, _ = stream
    for value in values:
        with engine.begin() as connection, pytest.raises(DBAPIError):
            insert_window(connection, **{column: value})


@pytest.mark.parametrize(
    "table,column,limit",
    [
        (STREAMS, "policy_payload", 256),
        (WINDOWS, "input_payload", 262144),
        (WINDOWS, "result_payload", 262144),
    ],
)
def test_payload_storage_is_bounded_ascii_text(stream, table, column, limit):
    engine, _ = stream
    for value in ("x" * (limit + 1), "é", "{}\x00hidden", b"{}"):
        with engine.begin() as connection, pytest.raises(DBAPIError):
            if table == STREAMS:
                insert_stream(connection, id=2, policy_binding_sha256="e" * 64, **{column: value})
            else:
                insert_window(connection, **{column: value})


@pytest.mark.parametrize("table", [STREAMS, WINDOWS])
@pytest.mark.parametrize(
    "value",
    [
        None,
        "invalid",
        "2030-02-30 00:00:00.000000",
        "2030-01-01 00:00:00",
        "2030-01-01 00:00:00.00000x",
        "0000-01-01 00:00:00.000000",
        "10000-01-01 00:00:00.000000",
        STAMP + "\x00hidden",
        STAMP.encode(),
    ],
)
def test_created_at_storage_is_strict_and_bounded(stream, table, value):
    engine, _ = stream
    with engine.begin() as connection, pytest.raises(DBAPIError):
        if table == STREAMS:
            insert_stream(connection, id=2, policy_binding_sha256="e" * 64, created_at=value)
        else:
            insert_window(connection, created_at=value)


@pytest.mark.parametrize(
    "assignment",
    [
        "id=2",
        "mapping_id=2",
        "policy_binding_sha256='" + "e" * 64 + "'",
        "policy_sha256='" + "e" * 64 + "'",
        "policy_payload='{ }'",
        "created_at='2030-01-02 00:00:00.000000'",
    ],
)
def test_stream_identity_policy_and_time_cannot_change_during_valid_advance(stream, assignment):
    engine, _ = stream
    with engine.begin() as connection:
        insert_window(connection)
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {STREAMS} SET carry=30,next_sequence=2,{assignment}"))


@pytest.mark.parametrize(
    "assignment",
    [
        "carry=0,next_sequence=1",
        "carry=31,next_sequence=2",
        "carry=30,next_sequence=3",
        "carry=30,next_sequence=0",
        "carry=30,next_sequence=1.5",
        "carry=30,next_sequence='invalid'",
        "carry=1.5,next_sequence=2",
        "carry=100,next_sequence=2",
        "carry=-1,next_sequence=2",
    ],
)
def test_stream_advance_requires_exact_next_window_and_carry(stream, assignment):
    engine, _ = stream
    with engine.begin() as connection:
        insert_window(connection)
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {STREAMS} SET {assignment}"))


@pytest.mark.parametrize(
    "statement",
    [
        f"UPDATE {WINDOWS} SET carry_out=99",
        f"UPDATE {WINDOWS} SET id=id",
        f"UPDATE {WINDOWS} SET input_payload='{{ }}'",
        f"DELETE FROM {WINDOWS}",
        f"DELETE FROM {STREAMS}",
    ],
)
def test_history_updates_noops_and_deletes_are_forbidden(history, statement):
    engine, _ = history
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(statement))
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT carry,next_sequence FROM {STREAMS}")).one() == (
            30,
            2,
        )
        assert connection.execute(text(f"SELECT carry_in,carry_out FROM {WINDOWS}")).one() == (
            0,
            30,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"id": 2},
        {"policy_binding_sha256": "e" * 64},
    ],
)
def test_stream_replace_cannot_erase_primary_or_binding_identity(history, overrides):
    engine, _ = history
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_stream(connection, replace=True, **overrides)
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT id,carry,next_sequence FROM {STREAMS}")).one() == (
            1,
            30,
            2,
        )


@pytest.mark.parametrize("replace", [False, True])
@pytest.mark.parametrize("overrides", [{}, {"id": 2}, {"id": 2, "window_key": "e" * 64}])
def test_duplicate_pending_window_cannot_replace_any_identity(stream, replace, overrides):
    engine, _ = stream
    with engine.begin() as connection:
        insert_window(connection)
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_window(connection, replace=replace, **overrides)
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT id,window_key,sequence FROM {WINDOWS}")).one() == (
            1,
            WINDOW_KEY,
            1,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"id": 2},
        {"id": 2, "window_key": "e" * 64},
        {"id": 2, "sequence": 2, "carry_in": 30},
        {"sequence": 2, "carry_in": 30, "window_key": "e" * 64},
    ],
)
def test_window_replace_cannot_erase_primary_key_window_key_or_sequence(history, overrides):
    engine, _ = history
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_window(connection, replace=True, **overrides)
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT id,sequence,carry_out FROM {WINDOWS}")).one() == (
            1,
            1,
            30,
        )


def test_missing_stream_is_rejected_without_sqlite_foreign_key_assumptions(store):
    engine, _ = store
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_window(connection)


def test_replace_can_insert_new_identity_but_cannot_bypass_missing_parent(store):
    engine, _ = store
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_stream(connection, replace=True, mapping_id=2)
    with engine.begin() as connection, pytest.raises(DBAPIError):
        insert_window(connection, replace=True)
    with engine.begin() as connection:
        insert_stream(connection, replace=True)
        insert_window(connection, replace=True)
        connection.execute(text(f"UPDATE {STREAMS} SET carry=30,next_sequence=2"))
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT carry,next_sequence FROM {STREAMS}")).one() == (
            30,
            2,
        )


def test_valid_linked_window_advances_once_and_survives_reopen(history):
    engine, _ = history
    with engine.begin() as connection:
        insert_window(connection, id=2, sequence=2, carry_in=30, carry_out=99, window_key="e" * 64)
        connection.execute(text(f"UPDATE {STREAMS} SET carry=99,next_sequence=3"))
    engine.dispose()
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT carry,next_sequence FROM {STREAMS}")).one() == (
            99,
            3,
        )
        assert connection.execute(
            text(f"SELECT sequence,carry_in,carry_out FROM {WINDOWS} ORDER BY sequence")
        ).all() == [(1, 0, 30), (2, 30, 99)]
        assert_old_rows(connection)


def test_signed64_ids_and_boundary_payloads_are_retained(store):
    engine, _ = store
    maximum = 9223372036854775807
    with engine.begin() as connection:
        insert_stream(
            connection,
            id=maximum,
            policy_payload="x" * 256,
            created_at="0001-01-01 00:00:00.000000",
        )
        insert_window(
            connection,
            id=maximum,
            stream_id=maximum,
            input_payload="x" * 262144,
            result_payload="y" * 262144,
            carry_out=0,
            created_at="9999-12-31 23:59:59.999999",
        )
        connection.execute(
            text(f"UPDATE {STREAMS} SET next_sequence=2 WHERE id=:id"), {"id": maximum}
        )
        assert connection.scalar(text(f"SELECT id FROM {WINDOWS}")) == maximum


@pytest.mark.parametrize("with_window", [False, True])
def test_populated_downgrade_refuses_before_ddl_preserving_tables_history_head(stream, with_window):
    engine, config = stream
    if with_window:
        with engine.begin() as connection:
            insert_window(connection)
    with engine.connect() as connection:
        before = [
            connection.execute(text(f"SELECT * FROM {table}")).all() for table in (STREAMS, WINDOWS)
        ]
        before_version = connection.scalar(text("SELECT version_num FROM alembic_version"))
    with pytest.raises(RuntimeError, match="intake"):
        command.downgrade(config, PREVIOUS)
    with engine.connect() as connection:
        assert [
            connection.execute(text(f"SELECT * FROM {table}")).all() for table in (STREAMS, WINDOWS)
        ] == before
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == before_version
            == HEAD
        )


def test_empty_downgrade_reupgrade_check_preserves_old_rows(store):
    engine, config = store
    command.check(config)
    command.downgrade(config, PREVIOUS)
    assert not inspect(engine).has_table(STREAMS)
    assert not inspect(engine).has_table(WINDOWS)
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert_old_rows(connection)


def test_empty_downgrade_locks_writers_before_count_and_ddl(store, monkeypatch):
    engine, config = store
    original = Connection.scalar
    outcomes = []

    def after_count(connection, statement, *args, **kwargs):
        result = original(connection, statement, *args, **kwargs)
        if str(statement) == f"SELECT count(*) FROM {STREAMS}":
            assert result == 0
            with engine.connect() as writer:
                writer.execute(text("PRAGMA busy_timeout=0"))
                with pytest.raises(DBAPIError):
                    insert_stream(writer)
                writer.rollback()
                outcomes.append("blocked")
        return result

    monkeypatch.setattr(Connection, "scalar", after_count)
    command.downgrade(config, PREVIOUS)
    assert outcomes == ["blocked"]


@pytest.fixture
def postgres_store(record_property):
    raw = getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL")
    if raw is None:
        pytest.skip("PostgreSQL-only: explicit synthetic NEWSFLOW_UNATTENDED_POSTGRES_URL required")
    url = create_postgres_namespace(raw)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, PREVIOUS)
    engine = create_engine(url)
    seed_old_rows(engine)
    command.upgrade(config, "head")
    record_property("synthetic_namespace", engine.url.query["options"].split("=", 1)[1])
    try:
        yield engine, config
    finally:
        with engine.connect() as connection:
            assert_old_rows(connection)
        engine.dispose()


@pytest.mark.parametrize(
    "statement",
    [
        f"TRUNCATE {STREAMS} CASCADE",
        f"TRUNCATE {WINDOWS} CASCADE",
        "TRUNCATE channel_mappings CASCADE",
        "TRUNCATE donor_channels CASCADE",
    ],
)
def test_postgres_truncate_refuses_when_either_table_has_history(postgres_store, statement):
    engine, _ = postgres_store
    with engine.begin() as connection:
        insert_stream(connection)
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(statement))
    with engine.connect() as connection:
        assert connection.scalar(text(f"SELECT count(*) FROM {STREAMS}")) == 1


def test_postgres_signed64_identity_guards_and_empty_roundtrip(postgres_store):
    engine, config = postgres_store
    command.check(config)
    command.downgrade(config, PREVIOUS)
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        insert_stream(connection, id=9223372036854775807)
        insert_window(connection, id=9223372036854775807, stream_id=9223372036854775807)
        connection.execute(text(f"UPDATE {STREAMS} SET carry=30,next_sequence=2"))
    for statement in (
        f"UPDATE {WINDOWS} SET id=id",
        f"DELETE FROM {STREAMS}",
        f"UPDATE {STREAMS} SET next_sequence=3",
        f"TRUNCATE {WINDOWS} CASCADE",
    ):
        with engine.begin() as connection, pytest.raises(DBAPIError):
            connection.execute(text(statement))
    with pytest.raises(RuntimeError, match="intake"):
        command.downgrade(config, PREVIOUS)
    with engine.connect() as connection:
        assert connection.scalar(text(f"SELECT id FROM {WINDOWS}")) == 9223372036854775807
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD


@pytest.mark.parametrize("with_window", [False, True])
def test_postgres_storage_initial_state_and_retention_guards(postgres_store, with_window):
    engine, _ = postgres_store
    # These bind to native PostgreSQL types and execute the installed guards.
    # Payload semantic JSON validation remains the repository's responsibility.
    for overrides in (
        {"id": 0},
        {"mapping_id": 2},
        {"carry": 1},
        {"next_sequence": 2},
        {"policy_binding_sha256": "A" * 64},
        {"policy_sha256": "g" * 64},
        {"policy_sha256": "a" * 63},
        {"policy_payload": "é"},
        {"policy_payload": "x" * 257},
        {"created_at": "infinity"},
    ):
        with engine.begin() as connection, pytest.raises(DBAPIError):
            insert_stream(connection, **overrides)
    with engine.begin() as connection:
        insert_stream(connection)
    if with_window:
        with engine.begin() as connection:
            insert_window(connection)
    for overrides in (
        {"id": 0},
        {"stream_id": 2},
        {"sequence": 2},
        {"carry_in": 1},
        {"carry_out": 100},
        {"window_key": "A" * 64},
        {"input_sha256": "g" * 64},
        {"algorithm_version": "invalid"},
        {"input_payload": "é"},
        {"result_payload": "x" * 262145},
        {"created_at": "infinity"},
    ):
        with engine.begin() as connection, pytest.raises(DBAPIError):
            insert_window(connection, **{"id": 2, **overrides})
    for statement in (
        f"UPDATE {STREAMS} SET carry=31,next_sequence=2",
        f"UPDATE {STREAMS} SET carry=30,next_sequence=2,policy_payload='{{ }}'",
        f"UPDATE {STREAMS} SET next_sequence=next_sequence",
        f"DELETE FROM {STREAMS}",
        f"TRUNCATE {WINDOWS} CASCADE",
    ):
        with engine.begin() as connection, pytest.raises(DBAPIError):
            connection.execute(text(statement))
    if with_window:
        with engine.begin() as connection:
            connection.execute(text(f"UPDATE {STREAMS} SET carry=30,next_sequence=2"))
