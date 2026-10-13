"""Explicit create-only PostgreSQL engagement contracts; namespaces are retained."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from os import getenv
from threading import Event, current_thread

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from test_telegram_engagement_history import (
    NOW,
    assert_preserved,
    history,
    observation,
    seed,
    zero_rewrite_calls,
)
from unattended_postgres import create_postgres_namespace

from alembic import command

__all__ = ["zero_rewrite_calls"]


@pytest.fixture
def postgres(record_property):
    raw = getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL")
    if raw is None:
        pytest.skip("PostgreSQL-only: explicit synthetic NEWSFLOW_UNATTENDED_POSTGRES_URL required")
    url = create_postgres_namespace(raw)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def bounded_connection(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '10s'")
            cursor.execute("SET statement_timeout = '15s'")
        connection.commit()

    record_property("synthetic_namespace", engine.url.query["options"].split("=", 1)[1])
    factory = sessionmaker(engine)
    seed(factory)
    try:
        yield factory
        assert_preserved(factory)
    finally:
        engine.dispose()  # Never DROP/reset/reuse the separately owned namespace.


def test_postgres_record_reopen_null_zero_limit_and_caller_rollback(postgres):
    with postgres.begin() as session:
        assert history(session).record(observation())
        assert history(session).record(
            observation(observed_at=NOW + timedelta(minutes=3), views=2**63 - 1)
        )
        assert history(session).record(
            observation(observed_at=NOW + timedelta(minutes=2), views=None, reactions=0)
        )
    postgres.kw["bind"].dispose()
    with postgres() as session:
        result = history(session).history(1, limit=2)
        assert [row.views for row in result] == [None, 2**63 - 1]
        assert result[0].reactions == 0
        assert history(session).record(observation(observed_at=NOW + timedelta(minutes=4)))
        session.rollback()
    with postgres() as session:
        assert len(history(session).history(1)) == 3


@pytest.mark.parametrize("change", ["replay", "counter", "publication"])
def test_postgres_independent_committed_writers_serialize_first_publication(postgres, change):
    engine = postgres.kw["bind"]
    first_locked, second_reached = Event(), Event()
    pids = {}

    def before(connection, cursor, statement, parameters, context, executemany):
        role = current_thread().name
        if "FROM incoming_posts" in statement and "FOR UPDATE" in statement:
            pids[role] = connection.connection.driver_connection.info.backend_pid
            if role == "engagement-second":
                second_reached.set()

    def after(connection, cursor, statement, parameters, context, executemany):
        if (
            current_thread().name == "engagement-first"
            and "FROM incoming_posts" in statement
            and "FOR UPDATE" in statement
        ):
            first_locked.set()
            assert second_reached.wait(5), "Second independent writer never attempted source lock"

    def first():
        current_thread().name = "engagement-first"
        with postgres.begin() as session:
            return history(session).record(observation())

    def second():
        current_thread().name = "engagement-second"
        assert first_locked.wait(5), "First writer did not lock canonical source"
        changes = {
            "counter": {"views": 11},
            "publication": {"published_at": NOW - timedelta(seconds=1)},
        }.get(change, {})
        with postgres.begin() as session:
            if change == "replay":
                return history(session).record(observation(**changes))
            with pytest.raises(ValueError):
                history(session).record(observation(**changes))
            # Conflict must leave the caller's transaction usable.
            assert history(session).record(observation(observed_at=NOW + timedelta(minutes=2)))
            return "conflict"

    event.listen(engine, "before_cursor_execute", before)
    event.listen(engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_result, second_result = executor.submit(first), executor.submit(second)
            assert first_result.result(timeout=20) is True
            assert second_result.result(timeout=20) == (False if change == "replay" else "conflict")
        assert set(pids) == {"engagement-first", "engagement-second"}
        assert len(set(pids.values())) == 2
    finally:
        event.remove(engine, "before_cursor_execute", before)
        event.remove(engine, "after_cursor_execute", after)
    with postgres() as session:
        result = history(session).history(1)
        assert result[0] == observation()
        assert len(result) == (1 if change == "replay" else 2)


@pytest.mark.parametrize("table", ["telegram_engagement_sources", "telegram_engagement_snapshots"])
@pytest.mark.parametrize("action", ["UPDATE", "DELETE", "TRUNCATE", "DUPLICATE", "UPSERT"])
def test_postgres_uniqueness_and_append_only_history(postgres, table, action):
    with postgres.begin() as session:
        history(session).record(observation())
    update = (
        "published_at = EXCLUDED.published_at"
        if table.endswith("sources")
        else "views = EXCLUDED.views"
    )
    key = "incoming_post_id" if table.endswith("sources") else "incoming_post_id, observed_at"
    statement = {
        "UPDATE": f"UPDATE {table} SET incoming_post_id = incoming_post_id",
        "DELETE": f"DELETE FROM {table}",
        "TRUNCATE": f"TRUNCATE TABLE {table} CASCADE",
        "DUPLICATE": f"INSERT INTO {table} SELECT * FROM {table}",
        "UPSERT": f"INSERT INTO {table} SELECT * FROM {table} ON CONFLICT ({key}) DO UPDATE SET {update}",
    }[action]
    with postgres() as session, pytest.raises(DBAPIError) as failure:
        session.execute(text(statement))
    assert failure.value.orig.sqlstate == ("23505" if action == "DUPLICATE" else "P0001")
    with postgres() as session:
        assert history(session).history(1) == (observation(),)


@pytest.mark.parametrize(
    "statement,sqlstate",
    [
        ("INSERT INTO telegram_engagement_sources VALUES (999,'2030-01-01')", "P0001"),
        ("INSERT INTO telegram_engagement_sources VALUES (2,'infinity')", "23514"),
        (
            "INSERT INTO telegram_engagement_snapshots (incoming_post_id,observed_at) VALUES (999,'2030-01-01')",
            "P0001",
        ),
        (
            "INSERT INTO telegram_engagement_snapshots (incoming_post_id,observed_at) VALUES (1,'2029-12-31 23:59:59.999999')",
            "P0001",
        ),
        (
            "INSERT INTO telegram_engagement_snapshots (incoming_post_id,observed_at,views) VALUES (1,'2030-01-02',-1)",
            "23514",
        ),
        (
            "INSERT INTO telegram_engagement_snapshots (incoming_post_id,observed_at,forwards) VALUES (1,'2030-01-02',9223372036854775808)",
            "22003",
        ),
        (
            "INSERT INTO telegram_engagement_snapshots (incoming_post_id,observed_at,reactions) VALUES (1,'2030-01-02',-1)",
            "23514",
        ),
        ("UPDATE incoming_posts SET telegram_message_id = 8 WHERE id = 1", "P0001"),
        ("DELETE FROM incoming_posts WHERE id = 1", "23503"),
    ],
)
def test_postgres_foreign_temporal_and_signed64_constraints(postgres, statement, sqlstate):
    with postgres.begin() as session:
        history(session).record(observation())
        session.execute(
            text(
                "INSERT INTO incoming_posts (id,telegram_account_id,donor_channel_id,telegram_message_id,state) VALUES (2,'1','-1000000000001',8,'RECEIVED')"
            )
        )
    with postgres() as session, pytest.raises(DBAPIError) as failure:
        session.execute(text(statement))
    assert failure.value.orig.sqlstate == sqlstate
    with postgres() as session:
        assert history(session).history(1) == (observation(),)


def test_postgres_first_source_snapshot_rollback_is_atomic(postgres):
    with postgres() as session:
        assert history(session).record(observation())
        session.rollback()
    with postgres() as session:
        assert history(session).history(1) == ()
        assert session.scalar(text("SELECT count(*) FROM telegram_engagement_sources")) == 0


@pytest.mark.parametrize("populated", [False, True])
def test_postgres_downgrade_retains_history_and_empty_cycle_preserves_source(postgres, populated):
    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        postgres.kw["bind"].url.render_as_string(hide_password=False).replace("%", "%%"),
    )
    if populated:
        with postgres.begin() as session:
            history(session).record(observation())
        with pytest.raises(RuntimeError, match="engagement history"):
            command.downgrade(config, "f6a42c91b805")
        with postgres() as session:
            assert history(session).history(1) == (observation(),)
    else:
        command.check(config)
        command.downgrade(config, "f6a42c91b805")
        assert_preserved(postgres)
        command.upgrade(config, "head")
        command.check(config)
        with postgres() as session:
            assert history(session).history(1) == ()
