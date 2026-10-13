"""Migrated synthetic engagement history; no Telegram or rewrite execution."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from alembic.config import Config
from sqlalchemy import Connection, create_engine, func, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from alembic import command
from newsflow.domain.engagement import TelegramEngagementObservation
from newsflow.persistence import models

NOW = datetime(2030, 1, 1, tzinfo=UTC)
KEY = "1:-1000000000001:7:revision:1"


def seed(factory):
    with factory.begin() as session:
        session.add(
            models.TelegramAccount(
                id=1, name="engagement-synthetic", telegram_user_id=41, encrypted_session=""
            )
        )
        session.flush()
        session.add(
            models.DonorChannel(
                telegram_account_id=1, telegram_channel_id=-1000000000001, title="Synthetic donor"
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
                content_key=KEY,
                status="REJECT",
                rewrite_allowed=False,
                sentiment="neutral",
                framing="neutral",
            )
        )


def observation(**changes):
    return replace(
        TelegramEngagementObservation(
            "1", "-1000000000001", 7, NOW, NOW + timedelta(minutes=1), 10, 0, None
        ),
        **changes,
    )


@pytest.fixture
def store(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'engagement.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    seed(factory)
    yield factory, config
    engine.dispose()


@pytest.fixture(autouse=True)
def zero_rewrite_calls(monkeypatch):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter import OpenRouterRewriteProvider

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("Engagement history invoked a rewrite provider")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(OpenRouterRewriteProvider, "rewrite", forbidden)
    yield
    assert calls == []


def history(session):
    from newsflow.services.telegram_engagement_history import TelegramEngagementHistory

    return TelegramEngagementHistory(session)


def assert_preserved(factory):
    with factory() as session:
        revision = session.scalar(select(models.ContentRevisionModel))
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert (revision.source_text, revision.revision_number) == ("Synthetic unchanged source", 1)
        assert (decision.status, decision.rewrite_allowed) == ("REJECT", False)
        assert session.scalar(select(func.count()).select_from(models.ContentRevisionModel)) == 1
        for model in (models.RewriteJobModel, models.RewriteUsageModel):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_record_replay_survives_reopen_without_editorial_side_effects(store):
    factory, _ = store
    value = observation()
    with factory() as session, session.begin():
        service = history(session)
        assert service.record(value) is True
        assert service.record(value) is False
    factory.kw["bind"].dispose()
    with factory() as session:
        assert history(session).history(1) == (value,)
    assert_preserved(factory)


def test_caller_rollback_removes_both_source_and_snapshot(store):
    factory, _ = store
    with factory() as session:
        assert history(session).record(observation()) is True
        session.rollback()
    with factory() as session:
        assert history(session).history(1) == ()
        assert session.scalar(text("SELECT count(*) FROM telegram_engagement_sources")) == 0
    assert_preserved(factory)


def test_latest_limit_is_chronological_and_out_of_order_is_retained(store):
    factory, _ = store
    values = [observation(observed_at=NOW + timedelta(minutes=n), views=n) for n in (3, 1, 2)]
    with factory.begin() as session:
        for value in values:
            assert history(session).record(value)
    with factory() as session:
        assert history(session).history(1, limit=2) == (values[2], values[0])
        assert history(session).history(1) == (values[1], values[2], values[0])


@pytest.mark.parametrize(
    "changes",
    [
        {"views": 11},
        {"forwards": None},
        {"reactions": 0},
        {"published_at": NOW - timedelta(seconds=1)},
    ],
)
def test_conflict_refuses_changes_without_ending_callers_transaction(store, changes):
    factory, _ = store
    with factory.begin() as session:
        service = history(session)
        assert service.record(observation())
        with pytest.raises(ValueError):
            service.record(observation(**changes))
        assert service.record(observation(observed_at=NOW + timedelta(minutes=2)))
    with factory() as session:
        assert len(history(session).history(1)) == 2
    assert_preserved(factory)


@pytest.mark.parametrize(
    "changes", [{"account_id": "2"}, {"donor_identifier": "-1000000000002"}, {"message_id": 8}]
)
def test_unknown_canonical_identity_never_fabricates_source(store, changes):
    factory, _ = store
    with factory.begin() as session:
        with pytest.raises(LookupError):
            history(session).record(observation(**changes))
        assert history(session).history(1) == ()


@pytest.mark.parametrize("missing", ["account", "donor"])
def test_incoming_identity_requires_real_configured_account_and_donor(store, missing):
    factory, _ = store
    with factory.begin() as session:
        session.execute(text("DELETE FROM donor_channels"))
        if missing == "account":
            session.execute(text("DELETE FROM telegram_accounts"))
        with pytest.raises(LookupError):
            history(session).record(observation())


def test_locked_canonical_source_refreshes_stale_session_identity(store):
    factory, _ = store
    with factory() as session:
        cached = session.get(models.IncomingPostModel, 1)
        assert cached.donor_channel_id == "-1000000000001"
        with factory.begin() as writer:
            writer.execute(
                text("UPDATE incoming_posts SET donor_channel_id = '-1000000000002' WHERE id = 1")
            )
        with pytest.raises(LookupError):
            history(session).record(observation(donor_identifier="-1000000000002"))
        session.rollback()
    with factory() as session:
        assert session.scalar(text("SELECT count(*) FROM telegram_engagement_sources")) == 0


def test_history_refreshes_cached_identity_before_labeling_observations(store):
    factory, _ = store
    value = observation(donor_identifier="-1000000000002")
    with factory() as session:
        cached = session.get(models.IncomingPostModel, 1)
        assert cached.donor_channel_id == "-1000000000001"
        with factory.begin() as writer:
            writer.add(
                models.DonorChannel(
                    telegram_account_id=1,
                    telegram_channel_id=-1000000000002,
                    title="Second synthetic donor",
                )
            )
            writer.execute(
                text("UPDATE incoming_posts SET donor_channel_id = '-1000000000002' WHERE id = 1")
            )
            assert history(writer).record(value)
        assert history(session).history(1) == (value,)


def test_retained_history_remains_readable_after_synthetic_donor_configuration_removal(store):
    factory, _ = store
    with factory.begin() as session:
        assert history(session).record(observation())
    with factory.begin() as session:
        session.execute(text("DELETE FROM donor_channels"))
    with factory() as session:
        assert history(session).history(1) == (observation(),)
        with pytest.raises(LookupError):
            history(session).record(observation(observed_at=NOW + timedelta(minutes=2)))
    assert_preserved(factory)


@pytest.mark.parametrize(
    "field,value",
    [
        ("views", True),
        ("views", -1),
        ("views", 2**63),
        ("account_id", "01"),
        ("observed_at", NOW.replace(tzinfo=None)),
        ("published_at", NOW + timedelta(days=1)),
    ],
)
def test_record_revalidates_even_forged_frozen_contract(store, field, value):
    factory, _ = store
    forged = observation()
    object.__setattr__(forged, field, value)
    with factory.begin() as session:
        with pytest.raises(ValueError):
            history(session).record(forged)
        assert history(session).history(1) == ()


@pytest.mark.parametrize("value", [None, {}, "observation"])
def test_record_requires_observation_contract(store, value):
    factory, _ = store
    with factory.begin() as session, pytest.raises(TypeError):
        history(session).record(value)


@pytest.mark.parametrize("metric", ["views", "forwards", "reactions"])
@pytest.mark.parametrize("value", ["-1", "9223372036854775808", "1.5", "'invalid'"])
def test_each_raw_counter_rejects_negative_overflow_and_noninteger(store, metric, value):
    factory, _ = store
    with factory.begin() as session:
        history(session).record(observation())
    with factory() as session, pytest.raises(DBAPIError):
        session.execute(
            text(
                f"INSERT INTO telegram_engagement_snapshots (incoming_post_id,observed_at,{metric}) VALUES (1,'2030-01-02 00:00:00.000000',{value})"
            )
        )
    with factory() as session:
        assert history(session).history(1) == (observation(),)


@pytest.mark.parametrize(
    "published,observed",
    [
        (datetime(1, 1, 1, tzinfo=UTC), datetime(1, 1, 1, tzinfo=UTC)),
        (
            datetime(9999, 12, 31, 23, 59, 59, 999998, tzinfo=UTC),
            datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
        ),
    ],
)
def test_timestamp_extremes_remain_roundtrippable(store, published, observed):
    factory, _ = store
    value = observation(published_at=published, observed_at=observed)
    with factory.begin() as session:
        assert history(session).record(value)
    with factory() as session:
        assert history(session).history(1) == (value,)


@pytest.mark.parametrize(
    "identity,limit",
    [(True, 1), (0, 1), (-1, 1), (2**63, 1), ("1", 1), (1, True), (1, 0), (1, 1001), (1, 1.0)],
)
def test_history_rejects_unbounded_or_noninteger_request(store, identity, limit):
    factory, _ = store
    with factory() as session, pytest.raises(ValueError):
        history(session).history(identity, limit=limit)


def test_unknown_post_history_fails_and_known_empty_history_is_empty(store):
    factory, _ = store
    with factory() as session:
        assert history(session).history(1, limit=1000) == ()
        with pytest.raises(LookupError):
            history(session).history(999)


def test_utc_storage_roundtrip_preserves_null_zero_and_signed64_max(store):
    factory, _ = store
    offset = timezone(timedelta(hours=3))
    value = observation(
        published_at=NOW.astimezone(offset),
        observed_at=(NOW + timedelta(minutes=1)).astimezone(offset),
        views=2**63 - 1,
        forwards=None,
        reactions=0,
    )
    with factory.begin() as session:
        assert history(session).record(value)
    with factory() as session:
        assert history(session).history(1) == (value,)
        assert history(session).history(1)[0].published_at.tzinfo is UTC


@pytest.mark.parametrize("table", ["telegram_engagement_sources", "telegram_engagement_snapshots"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "REPLACE"])
def test_append_only_sql_and_native_replace_refuse_even_without_sqlite_foreign_keys(
    store, table, operation
):
    factory, _ = store
    with factory.begin() as session:
        history(session).record(observation())
    with factory() as session:
        assert session.scalar(text("PRAGMA foreign_keys")) == 0
        statement = {
            "UPDATE": f"UPDATE {table} SET incoming_post_id = incoming_post_id",
            "DELETE": f"DELETE FROM {table}",
            "REPLACE": f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
        }[operation]
        with pytest.raises(DBAPIError):
            session.execute(text(statement))
        session.rollback()
    with factory() as session:
        assert history(session).history(1) == (observation(),)


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM incoming_posts WHERE id = 1",
        "UPDATE incoming_posts SET id = 2 WHERE id = 1",
        "UPDATE incoming_posts SET telegram_message_id = 8 WHERE id = 1",
        "INSERT OR REPLACE INTO incoming_posts SELECT * FROM incoming_posts WHERE id = 1",
    ],
)
def test_sqlite_parent_mutation_cannot_orphan_or_rebind_history(store, statement):
    factory, _ = store
    with factory.begin() as session:
        history(session).record(observation())
    with factory() as session, pytest.raises(DBAPIError):
        session.execute(text(statement))
    with factory() as session:
        assert history(session).history(1) == (observation(),)


@pytest.mark.parametrize(
    "table,columns,values",
    [
        ("sources", "incoming_post_id,published_at", "999,'2030-01-01 00:00:00.000000'"),
        ("sources", "incoming_post_id,published_at", "1,'invalid'"),
        ("sources", "incoming_post_id,published_at", "1,'0000-01-01 00:00:00.000000'"),
        ("sources", "incoming_post_id,published_at", "1,'2030-02-30 00:00:00.000000'"),
        ("snapshots", "incoming_post_id,observed_at,views", "999,'2030-01-01 00:01:00.000000',1"),
        ("snapshots", "incoming_post_id,observed_at,views", "1,'2029-12-31 23:59:59.000000',1"),
        ("snapshots", "incoming_post_id,observed_at,views", "1,'invalid',1"),
        ("snapshots", "incoming_post_id,observed_at,views", "1,'2030-01-01 00:01:00.000000',-1"),
        (
            "snapshots",
            "incoming_post_id,observed_at,views",
            "1,'2030-01-01 00:01:00.000000',9223372036854775808",
        ),
        ("snapshots", "incoming_post_id,observed_at,views", "1,'2030-01-01 00:01:00.000000',1.5"),
        ("snapshots", "incoming_post_id,observed_at,views", "1,'2030-01-01 00:01:00.000000','bad'"),
    ],
)
def test_raw_sql_rejects_invalid_parent_time_or_counter(store, table, columns, values):
    factory, _ = store
    if table == "snapshots":
        with factory.begin() as session:
            session.execute(
                text(
                    "INSERT INTO telegram_engagement_sources VALUES (1,'2030-01-01 00:00:00.000000')"
                )
            )
    with factory() as session, pytest.raises(DBAPIError):
        session.execute(
            text(f"INSERT INTO telegram_engagement_{table} ({columns}) VALUES ({values})")
        )


def test_sqlite_temporal_guard_preserves_microsecond_order(store):
    factory, _ = store
    with factory.begin() as session:
        session.execute(
            text("INSERT INTO telegram_engagement_sources VALUES (1,'2030-01-01 00:00:00.000002')")
        )
    with factory() as session, pytest.raises(DBAPIError):
        session.execute(
            text(
                "INSERT INTO telegram_engagement_snapshots (incoming_post_id,observed_at) VALUES (1,'2030-01-01 00:00:00.000001')"
            )
        )


def test_migration_drift_empty_downgrade_and_upgrade_preserve_original_rows(store):
    factory, config = store
    command.check(config)
    command.downgrade(config, "f6a42c91b805")
    assert "telegram_engagement_sources" not in inspect(factory.kw["bind"]).get_table_names()
    assert_preserved(factory)
    command.upgrade(config, "head")
    with factory() as session:
        assert history(session).history(1) == ()


def test_empty_downgrade_blocks_new_history_between_count_and_drop(store, monkeypatch):
    factory, config = store
    original = Connection.scalar
    outcomes = []

    def after_count(connection, statement, *args, **kwargs):
        result = original(connection, statement, *args, **kwargs)
        if str(statement) == "SELECT count(*) FROM telegram_engagement_snapshots":
            assert result == 0
            with factory() as writer:
                writer.execute(text("PRAGMA busy_timeout=0"))
                with pytest.raises(DBAPIError):
                    history(writer).record(observation())
                writer.rollback()
                outcomes.append("blocked")
        return result

    monkeypatch.setattr(Connection, "scalar", after_count)
    command.downgrade(config, "f6a42c91b805")
    assert outcomes == ["blocked"]
    assert "telegram_engagement_sources" not in inspect(factory.kw["bind"]).get_table_names()
    assert_preserved(factory)


@pytest.mark.parametrize("snapshot", [False, True])
def test_downgrade_refuses_even_source_only_retained_history(store, snapshot):
    factory, config = store
    with factory.begin() as session:
        if snapshot:
            history(session).record(observation())
        else:
            session.execute(
                text(
                    "INSERT INTO telegram_engagement_sources VALUES (1,'2030-01-01 00:00:00.000000')"
                )
            )
    with pytest.raises(RuntimeError, match="engagement history"):
        command.downgrade(config, "f6a42c91b805")
    with factory() as session:
        assert session.scalar(text("SELECT count(*) FROM telegram_engagement_sources")) == 1
