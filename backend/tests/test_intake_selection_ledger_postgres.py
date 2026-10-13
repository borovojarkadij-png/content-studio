"""Create-only native PostgreSQL ledger contracts; namespaces are retained."""

from concurrent.futures import ThreadPoolExecutor
from os import getenv
from threading import Barrier, Event
from time import monotonic

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from test_intake_selection_ledger import (
    KEY,
    load,
    record,
    rows,
    zero_rewrite_calls,
)
from test_intake_selection_ledger_migration import assert_old_rows, seed_old_rows
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.domain.intake_selection import IntakeSelectionPolicy

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
    def bounded(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '10s'")
            cursor.execute("SET statement_timeout = '15s'")
        connection.commit()

    record_property("synthetic_namespace", engine.url.query["options"].split("=", 1)[1])
    seed_old_rows(engine)
    try:
        yield sessionmaker(engine)
    finally:
        with engine.connect() as connection:
            assert_old_rows(connection)
        engine.dispose()


@pytest.mark.parametrize("same_window", [True, False])
def test_independent_connections_serialize_decision_and_fractional_carry(postgres, same_window):
    factory = postgres
    workers = 2 if same_window else 4
    barrier = Barrier(workers)
    pids = set()

    def worker(number):
        with factory.begin() as session:
            pids.add(session.connection().connection.driver_connection.info.backend_pid)
            barrier.wait(timeout=5)
            return record(
                session,
                window_key=KEY if same_window else f"{number:064x}",
                candidates=rows(1),
                policy=IntakeSelectionPolicy(30),
            )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker, number) for number in range(1, workers + 1)]
        values = [future.result(timeout=20) for future in futures]
    assert len(pids) == workers
    if same_window:
        assert sorted(value.replayed for value in values) == [False, True]
        assert {value.window_id for value in values} == {values[0].window_id}
        assert [(value.sequence, value.carry_in, value.result.carry_out) for value in values] == [
            (1, 0, 30),
            (1, 0, 30),
        ]
        expected_count, expected_carry = 1, 30
    else:
        ordered = sorted(values, key=lambda value: value.sequence)
        assert [
            (value.sequence, value.carry_in, value.result.carry_out, value.replayed)
            for value in ordered
        ] == [(1, 0, 30, False), (2, 30, 60, False), (3, 60, 90, False), (4, 90, 20, False)]
        assert [value.result.quota for value in ordered] == [0, 0, 0, 1]
        expected_count, expected_carry = 4, 20
    with factory.begin() as session:
        assert (
            session.scalar(text("SELECT count(*) FROM telegram_intake_selection_windows"))
            == expected_count
        )
        assert session.execute(
            text("SELECT carry,next_sequence FROM telegram_intake_selection_streams")
        ).one() == (expected_carry, expected_count + 1)


def test_waiting_writer_after_owner_rollback_uses_original_carry(postgres):
    factory = postgres
    engine = factory.kw["bind"]
    inserted, waiting, release = Event(), Event(), Event()
    pids = {}

    def before(connection, cursor, statement, parameters, context, executemany):
        if (
            connection.info.get("ledger_contender")
            and "FROM channel_mappings" in statement
            and "FOR UPDATE" in statement
        ):
            waiting.set()

    def owner():
        with pytest.raises(RuntimeError, match="owner rollback"), factory.begin() as session:
            pids["owner"] = session.connection().connection.driver_connection.info.backend_pid
            record(session, candidates=rows(1), policy=IntakeSelectionPolicy(30))
            inserted.set()
            assert release.wait(8)
            raise RuntimeError("owner rollback")

    def contender():
        assert inserted.wait(5)
        with factory.begin() as session:
            connection = session.connection()
            connection.info["ledger_contender"] = True
            pids["contender"] = connection.connection.driver_connection.info.backend_pid
            try:
                return record(session, candidates=rows(1), policy=IntakeSelectionPolicy(30))
            finally:
                connection.info.pop("ledger_contender", None)

    event.listen(engine, "before_cursor_execute", before)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = executor.submit(owner), executor.submit(contender)
            try:
                assert waiting.wait(5)
                # Native server lock evidence closes the gap between the before
                # cursor event and sending its statement. No sleeps or fake locks.
                deadline = monotonic() + 5
                with engine.connect() as observer:
                    while monotonic() < deadline:
                        blockers = observer.scalar(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["contender"]}
                        )
                        if pids["owner"] in blockers:
                            break
                    else:
                        pytest.fail("Contender never waited on owner mapping lock")
                assert pids["owner"] != pids["contender"]
            finally:
                release.set()
            first.result(timeout=20)
            result = second.result(timeout=20)
    finally:
        event.remove(engine, "before_cursor_execute", before)
    assert (result.sequence, result.carry_in, result.result.carry_out, result.replayed) == (
        1,
        0,
        30,
        False,
    )
    with factory.begin() as session:
        assert load(session).result == result.result
        assert session.scalar(text("SELECT count(*) FROM telegram_intake_selection_windows")) == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE telegram_intake_selection_windows SET carry_out=carry_out",
        "DELETE FROM telegram_intake_selection_windows",
        "DELETE FROM telegram_intake_selection_streams",
        "UPDATE telegram_intake_selection_streams SET carry=99,next_sequence=next_sequence+1",
        "TRUNCATE telegram_intake_selection_windows CASCADE",
        "TRUNCATE channel_mappings CASCADE",
    ],
)
def test_native_history_is_immutable_and_reopen_replays(postgres, statement):
    with postgres.begin() as session:
        first = record(session)
    with postgres.begin() as session, pytest.raises(DBAPIError):
        session.execute(text(statement))
    postgres.kw["bind"].dispose()
    with postgres.begin() as session:
        replay = record(session)
        assert replay.result == first.result
        assert (replay.window_id, replay.sequence, replay.replayed) == (first.window_id, 1, True)


def test_native_sql_failure_after_window_insert_rolls_back_carry_and_history(postgres):
    with postgres.begin() as session:
        first = record(session, candidates=rows(1), policy=IntakeSelectionPolicy(30))
    engine = postgres.kw["bind"]
    with engine.begin() as connection:
        connection.exec_driver_sql("""CREATE FUNCTION intake_synthetic_failure()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic intake SQL failure'; END; $$""")
        connection.exec_driver_sql("""CREATE TRIGGER intake_synthetic_failure
            BEFORE UPDATE ON telegram_intake_selection_streams
            FOR EACH ROW EXECUTE FUNCTION intake_synthetic_failure()""")
    with (
        pytest.raises(DBAPIError, match="synthetic intake SQL failure"),
        postgres.begin() as session,
    ):
        record(session, window_key="e" * 64, candidates=rows(1), policy=IntakeSelectionPolicy(30))
    with postgres.begin() as session:
        value = load(session)
        assert (value.sequence, value.carry_in, value.result.carry_out) == (1, 0, 30)
        assert value.result == first.result
        assert session.scalar(text("SELECT count(*) FROM telegram_intake_selection_windows")) == 1
        assert session.execute(
            text("SELECT carry,next_sequence FROM telegram_intake_selection_streams")
        ).one() == (30, 2)
