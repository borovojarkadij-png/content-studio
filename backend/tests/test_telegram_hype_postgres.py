"""Explicit create-only PostgreSQL Hype contracts; no fallback or namespace deletion."""

from datetime import timedelta
from os import getenv

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from test_telegram_engagement_history import assert_preserved, seed, zero_rewrite_calls
from test_telegram_hype import NOW, add_baseline, add_history, inspect_post
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
        engine.dispose()


def test_postgres_real_aware_time_null_zero_rates_and_reopen(postgres):
    with postgres.begin() as session:
        add_history(session, 1, samples=((10, 100, None, 0), (20, 300, None, 0)))
        add_baseline(session, samples=((10, 100, None, 0), (20, 200, None, 0)))
    postgres.kw["bind"].dispose()
    with postgres() as session:
        observed = session.scalar(select(models.TelegramEngagementSnapshotModel.observed_at))
        assert observed.tzinfo is not None
        result = inspect_post(session)
        assert result.observed_at == NOW
        assert result.observed_at.utcoffset() == timedelta(0)
        assert result.performance.expected_views_per_minute == 10
        assert result.performance.relative_views_velocity == 2
        assert result.performance.expected_forwards_per_minute is None
        assert result.performance.expected_reactions_per_minute == 0
        assert result.performance.relative_reactions_velocity is None
        assert result.assessment.components.view_velocity == 100
        assert result.assessment.coverage == 0.3
        assert result.reason == "INSUFFICIENT_EVIDENCE"
        session.rollback()
    with postgres() as session:
        assert inspect_post(session) == result


def test_postgres_read_only_transaction_preserves_dirty_caller_and_editorial(postgres, monkeypatch):
    with postgres.begin() as session:
        add_history(session, 1)
        add_baseline(session)
    statements = []
    engine = postgres.kw["bind"]

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    with postgres() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        post = session.get(models.IncomingPostModel, 1)
        post.donor_channel_id = "-1000000000002"
        pending = models.IncomingPostModel(
            telegram_account_id="invalid",
            donor_channel_id="invalid",
            telegram_message_id=9,
            state="RECEIVED",
        )
        session.add(pending)

        def forbidden(*args, **kwargs):
            pytest.fail("Projection changed the caller's PostgreSQL transaction")

        event.listen(engine, "before_cursor_execute", capture)
        try:
            with monkeypatch.context() as patch:
                for method in ("flush", "commit", "rollback"):
                    patch.setattr(session, method, forbidden)
                result = inspect_post(session)
                assert result.reason == "READY"
                assert result.performance.relative_views_velocity == 2
                with pytest.raises(LookupError):
                    inspect_post(session, 99999)
            assert post in session.dirty and pending in session.new
            assert statements and all(sql.lstrip().startswith("SELECT") for sql in statements)
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        session.rollback()
    assert_preserved(postgres)


def test_postgres_as_of_and_independent_session_commit_isolation(postgres):
    with postgres.begin() as session:
        add_history(session, 1)
        add_baseline(session)
        add_baseline(session, first_id=10, account="2")
        add_baseline(session, first_id=20, donor="-1000000000002")
    with postgres() as reader, postgres() as writer:
        assert inspect_post(reader).performance.views_samples == 5
        writer.add(
            models.TelegramEngagementSnapshotModel(
                incoming_post_id=1,
                observed_at=NOW + timedelta(minutes=1),
                views=10000,
                forwards=1000,
                reactions=2000,
            )
        )
        writer.flush()
        assert inspect_post(reader, as_of=NOW + timedelta(minutes=1)).observed_at == NOW
        writer.commit()
        assert inspect_post(reader).performance.relative_views_velocity == 2
        assert inspect_post(reader, as_of=NOW + timedelta(minutes=1)).observed_at > NOW
        assert inspect_post(reader, as_of=NOW + timedelta(minutes=7)).reason == "STALE_ENGAGEMENT"


def test_postgres_bounded_projection_reports_processed_prefix(postgres):
    with postgres.begin() as session:
        add_history(session, 1)
        for post_id in range(2, 1002):
            add_history(
                session,
                post_id,
                NOW - timedelta(days=1),
                samples=((10, 100, 10, 20), (20, 200, 20, 40)),
            )
        session.add(
            models.TelegramEngagementSnapshotModel(
                incoming_post_id=1001,
                observed_at=NOW - timedelta(days=1, minutes=-1),
                views=0,
                forwards=0,
                reactions=0,
            )
        )
    with postgres() as session:
        session.execute(text("SET TRANSACTION READ ONLY"))
        result = inspect_post(session)
        assert result.baseline_truncated is True
        assert result.performance.views_samples == 999
        assert result.performance.relative_views_velocity == 2
        assert inspect_post(session) == result
