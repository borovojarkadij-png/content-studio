"""Create-only explicit PostgreSQL sampling contracts; owned namespaces retained."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from os import getenv
from threading import Barrier, Event, current_thread

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from test_telegram_sampling_runner import (
    NOW,
    Fake,
    admitted_claim,
    assert_preserved,
    history,
    job_after,
    runner,
    seed_sampling,
    zero_rewrite_calls,
)
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.persistence import models

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
    factory = sessionmaker(engine)
    seed_sampling(factory)
    try:
        yield factory, config
        assert_preserved(factory)
    finally:
        engine.dispose()  # No DROP, reset, reseed, public mutation or operational targets.


def test_postgres_independent_concurrent_admission_is_idempotent(postgres):
    factory, _ = postgres
    barrier = Barrier(2)
    engine = factory.kw["bind"]
    pids = set()

    def after(connection, cursor, statement, parameters, context, executemany):
        if "SELECT incoming_posts.id" in statement and "FOR UPDATE" not in statement:
            pids.add(connection.connection.driver_connection.info.backend_pid)
            barrier.wait(timeout=5)

    event.listen(engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(runner(factory).enqueue_window, now=NOW) for _ in range(2)]
            values = [future.result(timeout=20) for future in futures]
    finally:
        event.remove(engine, "after_cursor_execute", after)
    assert len(pids) == 2
    assert sorted(value.queued_ids for value in values) == [(), (1,)]
    with factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(models.TelegramEngagementSamplingJobModel)
            )
            == 1
        )


def add_second_source(factory):
    with factory.begin() as session:
        session.add(
            models.IncomingPostModel(
                id=2,
                telegram_account_id="1",
                donor_channel_id="-1000000000001",
                telegram_message_id=8,
                state="RECEIVED",
                created_at=NOW,
            )
        )
        session.flush()
        session.add(
            models.ContentRevisionModel(
                incoming_post_id=2, revision_number=1, source_text="second synthetic source"
            )
        )


def test_postgres_claim_skips_locked_incoming_and_commits_other_candidate(postgres):
    factory, _ = postgres
    add_second_source(factory)
    service = runner(factory)
    assert service.enqueue_window(now=NOW).queued_ids == (1, 2)
    with factory.begin() as locker:
        locker.scalar(
            select(models.IncomingPostModel)
            .where(models.IncomingPostModel.id == 1)
            .with_for_update()
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            claim = executor.submit(service.claim_next, now=NOW).result(timeout=5)
            assert claim.incoming_post_id == 2
    assert service.claim_next(now=NOW).incoming_post_id == 1
    assert service.claim_next(now=NOW) is None


def test_postgres_simultaneous_independent_claims_have_one_committed_owner(postgres):
    factory, _ = postgres
    service = runner(factory)
    service.enqueue_window(now=NOW)
    barrier = Barrier(2)
    engine = factory.kw["bind"]
    pids = set()

    def after(connection, cursor, statement, parameters, context, executemany):
        if (
            "SELECT telegram_engagement_sampling_jobs.incoming_post_id" in statement
            and "FOR UPDATE" not in statement
        ):
            pids.add(connection.connection.driver_connection.info.backend_pid)
            barrier.wait(timeout=5)

    event.listen(engine, "after_cursor_execute", after)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(service.claim_next, now=NOW) for _ in range(2)]
            values = [future.result(timeout=20) for future in futures]
    finally:
        event.remove(engine, "after_cursor_execute", after)
    claims = [value for value in values if value is not None]
    assert len(pids) == 2 and len(claims) == 1
    assert (job_after(factory).claim_token, job_after(factory).attempts) == (claims[0].token, 1)


def test_postgres_claim_window_never_acquires_seventeenth_locked_candidate(postgres):
    factory, _ = postgres
    with factory.begin() as session:
        for post_id in range(2, 18):
            session.add(
                models.IncomingPostModel(
                    id=post_id,
                    telegram_account_id="1",
                    donor_channel_id="-1000000000001",
                    telegram_message_id=post_id + 10,
                    state="RECEIVED",
                    created_at=NOW,
                )
            )
        session.flush()
        for post_id in range(2, 18):
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post_id,
                    revision_number=1,
                    source_text="bounded synthetic source",
                )
            )
    service = runner(factory)
    assert len(service.enqueue_window(now=NOW).queued_ids) == 16
    assert service.enqueue_window(now=NOW, after_id=16).queued_ids == (17,)
    with factory.begin() as locker:
        assert (
            len(
                locker.scalars(
                    select(models.IncomingPostModel)
                    .where(models.IncomingPostModel.id <= 16)
                    .with_for_update()
                ).all()
            )
            == 16
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(service.claim_next, now=NOW).result(timeout=5) is None
    with factory() as session:
        assert session.get(models.TelegramEngagementSamplingJobModel, 17).attempts == 0
        assert (
            session.scalar(
                select(func.count())
                .select_from(models.TelegramEngagementSamplingJobModel)
                .where(models.TelegramEngagementSamplingJobModel.state == "RUNNING")
            )
            == 0
        )
    assert service.claim_next(now=NOW).incoming_post_id == 1


def test_postgres_claim_skips_locked_job_and_account(postgres):
    factory, _ = postgres
    service = runner(factory)
    service.enqueue_window(now=NOW)
    for model in (models.TelegramEngagementSamplingJobModel, models.TelegramAccount):
        with factory.begin() as locker:
            locker.scalar(select(model).with_for_update())
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(service.claim_next, now=NOW).result(timeout=5) is None
    assert job_after(factory).attempts == 0
    assert service.claim_next(now=NOW) is not None


def test_postgres_expired_takeover_stale_owner_and_restart(postgres):
    factory, _ = postgres
    provider = Fake()
    _service, first = admitted_claim(factory, provider=provider)
    factory.kw["bind"].dispose()
    when = NOW + timedelta(seconds=60)
    replacement = runner(factory, provider, when)
    second = replacement.claim_next(now=when)
    assert second.token != first.token
    assert replacement.execute(first) == "STALE_CLAIM"
    assert replacement.execute(second) == "SAMPLED"
    factory.kw["bind"].dispose()
    factory.kw["bind"].dispose()
    with factory() as session:
        assert len(history(session).history(1)) == 1
    assert len(provider.calls) == 1


def test_postgres_lease_expiring_while_final_account_lock_waits_is_stale(postgres):
    factory, _ = postgres
    engine = factory.kw["bind"]
    start_locker, locked, final_wait = Event(), Event(), Event()
    current = [NOW]
    account_locks = []

    def before(connection, cursor, statement, parameters, context, executemany):
        if (
            current_thread().name == "sampling-finalizer"
            and "FROM telegram_accounts" in statement
            and "FOR UPDATE" in statement
        ):
            account_locks.append(True)
            if len(account_locks) == 2:
                final_wait.set()

    def callback():
        start_locker.set()
        assert locked.wait(5)

    service, claim = admitted_claim(factory, provider=Fake(callback=callback))
    service._clock = lambda: current[0]

    def locker():
        assert start_locker.wait(5)
        with factory.begin() as session:
            session.scalar(
                select(models.TelegramAccount)
                .where(models.TelegramAccount.id == 1)
                .with_for_update()
            )
            locked.set()
            assert final_wait.wait(5)
            current[0] = NOW + timedelta(seconds=60)

    def finalizer():
        current_thread().name = "sampling-finalizer"
        return service.execute(claim)

    event.listen(engine, "before_cursor_execute", before)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            holder, result = executor.submit(locker), executor.submit(finalizer)
            assert result.result(timeout=20) == "STALE_CLAIM"
            holder.result(timeout=20)
    finally:
        event.remove(engine, "before_cursor_execute", before)
    with factory() as session:
        assert history(session).history(1) == ()
    assert job_after(factory).claim_token == claim.token


def test_postgres_nullable_history_and_job_commit_are_atomic(postgres):
    factory, _ = postgres
    service, claim = admitted_claim(factory)
    engine = factory.kw["bind"]

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE telegram_engagement_sampling_jobs"):
            raise RuntimeError("synthetic interruption")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="synthetic interruption"):
            service.execute(claim)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with factory() as session:
        assert history(session).history(1) == ()
        assert (
            session.scalar(select(func.count()).select_from(models.TelegramEngagementSourceModel))
            == 0
        )
    assert job_after(factory).claim_token == claim.token
    assert service.execute(claim) == "SAMPLED"
    with factory() as session:
        value = history(session).history(1)[0]
        assert (value.views, value.forwards, value.reactions) == (10, 0, None)


def test_postgres_native_sql_failure_rolls_back_history_and_retains_committed_lease(postgres):
    factory, _ = postgres
    service, claim = admitted_claim(factory)
    with factory.kw["bind"].begin() as connection:
        connection.exec_driver_sql("""CREATE FUNCTION sampling_synthetic_failure()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic SQL failure'; END; $$""")
        connection.exec_driver_sql("""CREATE TRIGGER sampling_synthetic_failure
            BEFORE UPDATE ON telegram_engagement_sampling_jobs
            FOR EACH ROW EXECUTE FUNCTION sampling_synthetic_failure()""")
    with pytest.raises(DBAPIError, match="synthetic SQL failure"):
        service.execute(claim)
    with factory() as session:
        assert history(session).history(1) == ()
        assert (
            session.scalar(select(func.count()).select_from(models.TelegramEngagementSourceModel))
            == 0
        )
    assert (job_after(factory).state, job_after(factory).claim_token) == ("RUNNING", claim.token)


@pytest.mark.parametrize(
    "assignment",
    [
        "attempts = 4",
        "step = -1",
        "missed_windows = 7",
        "created_at = '2031-01-01'",
        "available_at = '2029-01-01'",
        "state = 'RUNNING'",
        "expected_user_id = 0",
    ],
)
def test_postgres_migrated_raw_job_constraints_reject_invalid_state(postgres, assignment):
    factory, _ = postgres
    runner(factory).enqueue_window(now=NOW)
    with factory() as session, pytest.raises(DBAPIError):
        session.execute(text("UPDATE telegram_engagement_sampling_jobs SET " + assignment))
    assert (job_after(factory).state, job_after(factory).attempts) == ("QUEUED", 0)


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM telegram_engagement_sampling_jobs",
        "TRUNCATE telegram_engagement_sampling_jobs CASCADE",
        "UPDATE incoming_posts SET telegram_message_id = 8 WHERE id = 1",
    ],
)
def test_postgres_retained_sampling_rows_and_identity_cannot_be_erased(postgres, statement):
    factory, _ = postgres
    runner(factory).enqueue_window(now=NOW)
    with factory() as session, pytest.raises(DBAPIError):
        session.execute(text(statement))
    assert job_after(factory).incoming_post_id == 1


def test_postgres_populated_downgrade_retains_job_and_version(postgres):
    factory, config = postgres
    runner(factory).enqueue_window(now=NOW)
    with factory() as session:
        before_version = session.scalar(text("SELECT version_num FROM alembic_version"))
    with pytest.raises(RuntimeError, match="sampling"):
        command.downgrade(config, "a7e239bc5180")
    with factory() as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == before_version
    assert job_after(factory).state == "QUEUED"
