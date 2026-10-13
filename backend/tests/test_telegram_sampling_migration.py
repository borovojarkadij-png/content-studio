"""Synthetic migrated retention guards; no credentials or provider execution."""

import pytest
from alembic.config import Config
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from alembic import command
from newsflow.persistence import models

TABLE = "telegram_engagement_sampling_jobs"
STAMP = "2030-01-01 00:00:00.000000"
LATER = "2030-01-01 00:01:00.000000"
CLAIM = (
    "state='RUNNING',attempts=1,claim_token='12345678-1234-4234-8234-123456789abc',"
    f"lease_expires_at='{LATER}',expected_user_id=41,session_digest='" + "a" * 64 + "'"
)


@pytest.fixture
def store(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'sampling.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incoming_posts "
                "(id,telegram_account_id,donor_channel_id,telegram_message_id,state,created_at) "
                f"VALUES (1,'1','-1000000000001',7,'RECEIVED','{STAMP}')"
            )
        )
        connection.execute(
            text(
                f"INSERT INTO {TABLE} "
                "(incoming_post_id,state,step,attempts,missed_windows,available_at,created_at) "
                f"VALUES (1,'QUEUED',0,0,0,'{STAMP}','{STAMP}')"
            )
        )
    with Session(engine) as session, session.begin():
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
    yield engine, config
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT source_text FROM incoming_post_revisions"))
            == "Synthetic unchanged source"
        )
        assert connection.execute(
            text("SELECT status,rewrite_allowed FROM editorial_decisions")
        ).one() == ("REJECT", 0)
        for table in ("rewrite_jobs", "rewrite_usage", "outbox_events"):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    engine.dispose()


def test_raw_invalid_state_is_rejected_by_migrated_database(store):
    engine, _ = store
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {TABLE} SET state='INVALID'"))


@pytest.fixture(autouse=True)
def no_rewrite_calls(monkeypatch):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter import OpenRouterRewriteProvider

    def forbidden(*args, **kwargs):
        pytest.fail("Sampling schema invoked rewrite provider")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(OpenRouterRewriteProvider, "rewrite", forbidden)


@pytest.mark.parametrize(
    "assignment",
    [
        "step=-1",
        "step=8",
        "step=1.5",
        "step='invalid'",
        "attempts=-1",
        "attempts=4",
        "attempts=1.5",
        "attempts='invalid'",
        "missed_windows=-1",
        "missed_windows=7",
        "missed_windows=1.5",
        "missed_windows='invalid'",
        "state='RUNNING'",
        "step=7",
        "claim_token='12345678-1234-4234-8234-123456789abc'",
        f"lease_expires_at='{LATER}'",
        "expected_user_id=41",
        "session_digest='" + "a" * 64 + "'",
        "state='SUCCEEDED'",
        "state='BLOCKED'",
        "state='FAILED'",
        "last_error_code='raw exception'",
        "available_at='invalid'",
        "available_at='2030-02-30 00:00:00.000000'",
        "available_at='2030-01-01 00:00:00'",
        "available_at='2030-01-01 00:00:00.00000x'",
        "available_at='0000-01-01 00:00:00.000000'",
        "available_at='10000-01-01 00:00:00.000000'",
        "available_at=CAST('2030-01-01 00:00:00.000000' AS BLOB)",
        "available_at='2030-01-01 00:00:00.000000'||char(0)||'hidden'",
        "available_at='2029-12-31 23:59:59.999999'",
        f"created_at='{LATER}'",
        "incoming_post_id=2",
    ],
)
def test_raw_invalid_job_updates_are_rejected(store, assignment):
    engine, _ = store
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {TABLE} SET {assignment}"))


@pytest.mark.parametrize(
    "assignment",
    [
        "claim_token='12345678-1234-4234-8234-123456789abz'",
        "claim_token='123456781234-4234-8234-123456789abc'",
        "claim_token='12345678-1234-4234-8234-123456789ABC'",
        "claim_token=NULL",
        "lease_expires_at=NULL",
        "expected_user_id=NULL",
        "session_digest=NULL",
        "expected_user_id=0",
        "expected_user_id=-1",
        "expected_user_id=9223372036854775808",
        "expected_user_id=1.5",
        "expected_user_id='invalid'",
        "session_digest='invalid'",
        "session_digest='" + "G" * 64 + "'",
        "session_digest='" + "A" * 64 + "'",
        "attempts=0",
        "step=7",
        "lease_expires_at='invalid'",
        "lease_expires_at='2030-02-30 00:00:00.000000'",
        "claim_token=CAST('12345678-1234-4234-8234-123456789abc' AS BLOB)",
        "session_digest=CAST('" + "a" * 64 + "' AS BLOB)",
        "session_digest='" + "a" * 64 + "'||char(0)||'hidden'",
        "claim_token='12345678-1234-4234-8234-123456789abc'||char(0)||'hidden'",
        f"lease_expires_at='{STAMP}'",
        "lease_expires_at='2029-12-31 23:59:59.999999'",
    ],
)
def test_claim_identity_and_time_guards(store, assignment):
    engine, _ = store
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE {TABLE} SET {CLAIM}"))
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {TABLE} SET {assignment}"))


def clear_claim():
    return "claim_token=NULL,lease_expires_at=NULL,expected_user_id=NULL,session_digest=NULL"


@pytest.mark.parametrize("state", ["SUCCEEDED", "BLOCKED", "FAILED"])
@pytest.mark.parametrize("operation", ["UPDATE", "NOOP", "DELETE", "REPLACE"])
def test_terminal_jobs_never_mutate_revive_or_disappear(store, state, operation):
    engine, _ = store
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE {TABLE} SET {CLAIM}"))
        terminal = (
            "step=7,attempts=0" if state == "SUCCEEDED" else "last_error_code='SOURCE_UNAVAILABLE'"
        )
        connection.execute(text(f"UPDATE {TABLE} SET state='{state}',{terminal},{clear_claim()}"))
    statement = {
        "UPDATE": f"UPDATE {TABLE} SET state='QUEUED',step=0,attempts=0",
        "NOOP": f"UPDATE {TABLE} SET state=state",
        "DELETE": f"DELETE FROM {TABLE}",
        "REPLACE": f"INSERT OR REPLACE INTO {TABLE} SELECT * FROM {TABLE}",
    }[operation]
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(statement))
    with engine.connect() as connection:
        assert connection.scalar(text(f"SELECT state FROM {TABLE}")) == state


@pytest.mark.parametrize(
    "statement",
    [
        f"DELETE FROM {TABLE}",
        f"INSERT OR REPLACE INTO {TABLE} SELECT * FROM {TABLE}",
        "DELETE FROM incoming_posts",
        "UPDATE incoming_posts SET id=2",
        "UPDATE incoming_posts SET telegram_account_id='2'",
        "UPDATE incoming_posts SET donor_channel_id='-1000000000002'",
        "UPDATE incoming_posts SET telegram_message_id=8",
        f"UPDATE incoming_posts SET created_at='{LATER}'",
        "INSERT OR REPLACE INTO incoming_posts SELECT * FROM incoming_posts",
        "INSERT OR REPLACE INTO incoming_posts (id,telegram_account_id,donor_channel_id,telegram_message_id,state) VALUES (2,'1','-1000000000001',7,'RECEIVED')",
    ],
)
def test_retention_and_parent_identity_even_with_foreign_keys_disabled(store, statement):
    engine, _ = store
    with engine.begin() as connection, pytest.raises(DBAPIError):
        assert connection.scalar(text("PRAGMA foreign_keys")) == 0
        connection.execute(text(statement))


@pytest.mark.parametrize(
    "changes",
    [
        "state='RUNNING'",
        "step=1",
        "attempts=1",
        "missed_windows=1",
        "incoming_post_id=999",
        "incoming_post_id=1.5",
    ],
)
def test_initial_insert_must_be_fresh_queued_with_existing_parent(store, changes):
    engine, _ = store
    with engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO incoming_posts (id,telegram_account_id,donor_channel_id,telegram_message_id,state,created_at) VALUES (2,'1','-1000000000001',8,'RECEIVED','{STAMP}')"
            )
        )
    values = {
        "incoming_post_id": "2",
        "state": "'QUEUED'",
        "step": "0",
        "attempts": "0",
        "missed_windows": "0",
        "available_at": f"'{STAMP}'",
        "created_at": f"'{STAMP}'",
    }
    name, value = changes.split("=", 1)
    values[name] = value
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(
            text(f"INSERT INTO {TABLE} ({','.join(values)}) VALUES ({','.join(values.values())})")
        )


def test_counters_are_monotonic_attempt_reset_requires_step_advance(store):
    engine, _ = store
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE {TABLE} SET {CLAIM}"))
        connection.execute(text(f"UPDATE {TABLE} SET attempts=2"))
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {TABLE} SET attempts=1"))
    with engine.begin() as connection:
        connection.execute(
            text(
                f"UPDATE {TABLE} SET state='QUEUED',step=3,attempts=0,missed_windows=2,{clear_claim()}"
            )
        )
    for assignment in ("step=2", "missed_windows=1"):
        with engine.begin() as connection, pytest.raises(DBAPIError):
            connection.execute(text(f"UPDATE {TABLE} SET {assignment}"))
    with engine.begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text(f"UPDATE {TABLE} SET state='SUCCEEDED',step=7"))


def test_all_private_codes_and_valid_transitions_survive_reopen(store):
    engine, _ = store
    for code in (
        "WAIT_SYNC",
        "WAIT_COOLDOWN",
        "RETRY_PROVIDER",
        "FLOOD_WAIT",
        "SOURCE_UNAVAILABLE",
        "SESSION_UNAVAILABLE",
        "INVALID_OBSERVATION",
        "ATTEMPTS_EXHAUSTED",
        "INVALID_SCHEDULE",
    ):
        with engine.begin() as connection:
            connection.execute(text(f"UPDATE {TABLE} SET last_error_code='{code}'"))
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE {TABLE} SET {CLAIM}"))
        connection.execute(text(f"UPDATE {TABLE} SET state='QUEUED',{clear_claim()}"))
        connection.execute(text(f"UPDATE {TABLE} SET {CLAIM}"))
        connection.execute(
            text(
                f"UPDATE {TABLE} SET step=7,state='SUCCEEDED',attempts=0,last_error_code=NULL,{clear_claim()}"
            )
        )
    engine.dispose()
    with engine.connect() as connection:
        row = connection.execute(
            text(f"SELECT state,step,attempts,missed_windows,session_digest FROM {TABLE}")
        ).one()
        assert row == ("SUCCEEDED", 7, 0, 0, None)


def test_populated_downgrade_refuses_before_ddl_and_preserves_exact_rows_version(store):
    engine, config = store
    with engine.connect() as connection:
        before = connection.execute(text(f"SELECT * FROM {TABLE}")).all()
    with pytest.raises(RuntimeError, match="sampling"):
        command.downgrade(config, "a7e239bc5180")
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT * FROM {TABLE}")).all() == before
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b8c34d26e190"


def test_empty_roundtrip_matches_metadata_and_preserves_old_sentinels(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "a7e239bc5180")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incoming_posts (id,telegram_account_id,donor_channel_id,telegram_message_id,state) VALUES (9,'1','-1000000000001',9,'RECEIVED')"
            )
        )
        before = connection.execute(text("SELECT * FROM incoming_posts")).all()
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "a7e239bc5180")
    assert TABLE not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT * FROM incoming_posts")).all() == before
    engine.dispose()


def test_empty_downgrade_serializes_before_count_and_drop(tmp_path, monkeypatch):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'serialized.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO incoming_posts (id,telegram_account_id,donor_channel_id,telegram_message_id,state,created_at) VALUES (1,'1','-1000000000001',7,'RECEIVED','{STAMP}')"
            )
        )
    original = Connection.scalar
    outcomes = []

    def after_count(connection, statement, *args, **kwargs):
        result = original(connection, statement, *args, **kwargs)
        if str(statement) == f"SELECT count(*) FROM {TABLE}":
            assert result == 0
            with engine.connect() as writer:
                writer.execute(text("PRAGMA busy_timeout=0"))
                with pytest.raises(DBAPIError):
                    writer.execute(
                        text(
                            f"INSERT INTO {TABLE} (incoming_post_id,state,step,attempts,missed_windows,available_at,created_at) VALUES (1,'QUEUED',0,0,0,'{STAMP}','{STAMP}')"
                        )
                    )
                writer.rollback()
                outcomes.append("blocked")
        return result

    monkeypatch.setattr(Connection, "scalar", after_count)
    command.downgrade(config, "a7e239bc5180")
    assert outcomes == ["blocked"]
    engine.dispose()
