"""Migrated synthetic read-only donor-relative Hype contracts."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.orm import sessionmaker
from test_telegram_engagement_history import assert_preserved, seed, zero_rewrite_calls

from alembic import command
from newsflow.domain.hype import HypeComponents, HypeWeights
from newsflow.persistence import models

__all__ = ["zero_rewrite_calls"]
NOW = datetime(2030, 1, 2, tzinfo=UTC)
PUBLISHED = NOW - timedelta(minutes=20)


@pytest.fixture
def store(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'hype.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    seed(factory)
    try:
        yield factory
        assert_preserved(factory)
    finally:
        engine.dispose()


def add_history(
    session,
    post_id,
    published=PUBLISHED,
    *,
    account="1",
    donor="-1000000000001",
    samples=((10, 100, 10, 20), (20, 300, 30, 60)),
):
    if post_id != 1:
        session.add(
            models.IncomingPostModel(
                id=post_id,
                telegram_account_id=account,
                donor_channel_id=donor,
                telegram_message_id=post_id + 100,
                state="RECEIVED",
            )
        )
        session.flush()
    session.add(
        models.TelegramEngagementSourceModel(
            incoming_post_id=post_id,
            published_at=published,
        )
    )
    session.flush()
    session.add_all(
        [
            models.TelegramEngagementSnapshotModel(
                incoming_post_id=post_id,
                observed_at=published + timedelta(minutes=minute),
                views=views,
                forwards=forwards,
                reactions=reactions,
            )
            for minute, views, forwards, reactions in samples
        ]
    )
    session.flush()


def add_baseline(session, *, count=5, first_id=2, samples=None, **changes):
    for offset in range(count):
        add_history(
            session,
            first_id + offset,
            published=NOW - timedelta(days=1, minutes=offset),
            samples=samples if samples is not None else ((10, 100, 10, 20), (20, 200, 20, 40)),
            **changes,
        )


def inspect_post(session, post_id=1, **kwargs):
    from newsflow.services.telegram_hype import TelegramHypeService

    return TelegramHypeService(session).inspect(post_id, as_of=kwargs.pop("as_of", NOW), **kwargs)


def test_twice_ordinary_donor_interval_is_100_without_rewrite_authority(store):
    with store.begin() as session:
        add_history(session, 1)
        add_baseline(session)
    with store() as session:
        projection = inspect_post(session)
        assert projection.assessment.components.view_velocity == 100
        assert projection.performance.relative_views_velocity == 2
        assert projection.performance.expected_views_per_minute == 10
        assert projection.performance.views_samples == 5
        assert projection.assessment.components.forward_velocity == 100
        assert projection.assessment.components.reaction_velocity == 100
        assert projection.assessment.coverage == 0.5
        assert projection.assessment.score == pytest.approx(92.59921049894874)
        assert projection.reason == "READY"
        assert projection.observed_at == NOW
        assert projection.baseline_truncated is False
        assert session.scalar(select(func.count()).select_from(models.RewriteJobModel)) == 0
        for field in fields(HypeComponents)[4:]:
            assert getattr(projection.assessment.components, field.name) is None
        with pytest.raises(FrozenInstanceError):
            projection.reason = "PERMISSION"
    assert_preserved(store)


@pytest.mark.parametrize(
    "kind,reason,observed,has_freshness",
    [
        ("missing", "NO_ENGAGEMENT", None, False),
        ("empty", "NO_ENGAGEMENT", None, False),
        ("future", "NO_ENGAGEMENT", None, False),
        ("one", "INSUFFICIENT_EVIDENCE", NOW, True),
        ("stale", "STALE_ENGAGEMENT", NOW - timedelta(minutes=6), True),
    ],
)
def test_missing_one_future_and_stale_history_are_honest(
    store, kind, reason, observed, has_freshness
):
    with store.begin() as session:
        if kind == "empty":
            add_history(session, 1, samples=())
        elif kind == "future":
            add_history(session, 1, samples=((21, 1, 1, 1),))
        elif kind == "one":
            add_history(session, 1, samples=((20, 1, 1, 1),))
        elif kind == "stale":
            add_history(session, 1, samples=((4, 1, 1, 1), (14, 2, 2, 2)))
    with store() as session:
        projection = inspect_post(session)
        assert projection.reason == reason
        assert projection.observed_at == observed
        assert projection.performance is None
        assert projection.assessment.score is None
        assert (projection.assessment.components.freshness is not None) == has_freshness
        assert projection.assessment.components.view_velocity is None


def test_as_of_uses_only_latest_two_eligible_snapshots_and_explicit_clock(store):
    with store.begin() as session:
        add_history(
            session,
            1,
            samples=((26, 9000, 9000, 9000), (20, 300, 30, 60), (0, 0, 0, 0), (10, 100, 10, 20)),
        )
        add_baseline(session)
    with store() as session:
        result = inspect_post(session, as_of=NOW + timedelta(minutes=5))
        assert result.reason == "READY"  # Exactly five minutes remains fresh.
        assert result.performance.relative_views_velocity == 2
        assert result.assessment.components.freshness == pytest.approx(56.12310241546865)
        earlier = inspect_post(session, as_of=NOW - timedelta(minutes=10))
        assert earlier.observed_at == NOW - timedelta(minutes=10)
        assert earlier.performance.relative_views_velocity is None
        assert inspect_post(session, as_of=NOW + timedelta(minutes=6)).observed_at > NOW


def test_five_minutes_plus_microsecond_is_stale(store):
    with store.begin() as session:
        add_history(session, 1)
        add_baseline(session)
    with store() as session:
        result = inspect_post(session, as_of=NOW + timedelta(minutes=5, microseconds=1))
        assert result.reason == "STALE_ENGAGEMENT"
        assert result.performance is None


@pytest.mark.parametrize(
    "variant",
    [
        "foreign_account",
        "foreign_donor",
        "same_publication",
        "future_observation",
        "too_old",
        "cold_start",
    ],
)
def test_ineligible_history_cannot_complete_baseline(store, variant):
    with store.begin() as session:
        add_history(session, 1)
        if variant == "cold_start":
            add_baseline(session, count=4)
        elif variant == "foreign_account":
            add_baseline(session, account="2")
        elif variant == "foreign_donor":
            add_baseline(session, donor="-1000000000002")
        else:
            for post_id in range(2, 7):
                if variant == "same_publication":
                    published, samples = PUBLISHED, ((10, 100, 10, 20), (20, 200, 20, 40))
                elif variant == "future_observation":
                    published = PUBLISHED - timedelta(seconds=1)
                    samples = ((10, 100, 10, 20), (21, 200, 20, 40))
                else:
                    published = PUBLISHED - timedelta(days=30, microseconds=1)
                    samples = ((10, 100, 10, 20), (20, 200, 20, 40))
                add_history(session, post_id, published, samples=samples)
    with store() as session:
        result = inspect_post(session)
        assert result.reason == "INSUFFICIENT_EVIDENCE"
        assert result.performance.expected_views_per_minute is None
        assert result.assessment.components.view_velocity is None
        assert result.performance.views_samples == (4 if variant == "cold_start" else 0)


@pytest.mark.parametrize(
    "target_samples,baseline_samples,expected,ratio",
    [
        (((10, 300, None, 1), (20, 100, None, 0)), None, 10, None),
        (((10, None, None, None), (20, None, None, None)), None, 10, None),
        (((10, 100, None, 0), (20, 100, None, 0)), None, 10, 0),
        (None, ((10, 100, None, 0), (20, 100, None, 0)), 0, None),
        (None, ((10, 100, None, 0), (20, 0, None, 0)), None, None),
    ],
)
def test_reset_null_and_zero_rates_are_not_fabricated(
    store, target_samples, baseline_samples, expected, ratio
):
    with store.begin() as session:
        add_history(session, 1, **({"samples": target_samples} if target_samples else {}))
        add_baseline(session, samples=baseline_samples)
    with store() as session:
        performance = inspect_post(session).performance
        assert performance.expected_views_per_minute == expected
        assert performance.relative_views_velocity == ratio
        if baseline_samples:
            assert performance.relative_forwards_velocity is None


def test_historical_read_needs_no_current_donor_configuration_and_survives_reopen(store):
    with store.begin() as session:
        add_history(session, 1)
        add_baseline(session)
        session.execute(text("DELETE FROM donor_channels"))
        session.execute(text("DELETE FROM telegram_accounts"))
    store.kw["bind"].dispose()
    with store() as session:
        assert inspect_post(session).performance.relative_views_velocity == 2
        session.rollback()
    with store() as session:
        assert inspect_post(session).performance.relative_views_velocity == 2


def test_projection_never_flushes_pending_caller_changes_or_writes(store, monkeypatch):
    with store.begin() as session:
        add_history(session, 1)
        add_baseline(session)
    statements = []
    engine = store.kw["bind"]

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    with store() as session:
        session.execute(text("PRAGMA query_only=ON"))
        cached = session.get(models.IncomingPostModel, 1)
        cached.donor_channel_id = "-1000000000002"
        pending = models.IncomingPostModel(
            telegram_account_id="1",
            donor_channel_id="invalid",
            telegram_message_id=8,
            state="RECEIVED",
        )
        session.add(pending)

        def forbidden(*args, **kwargs):
            pytest.fail("Projection changed the caller's transaction")

        event.listen(engine, "before_cursor_execute", capture)
        try:
            with monkeypatch.context() as patch:
                for method in ("flush", "commit", "rollback"):
                    patch.setattr(session, method, forbidden)
                assert inspect_post(session).performance.relative_views_velocity == 2
                with pytest.raises(LookupError):
                    inspect_post(session, post_id=2**63 - 1)
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        assert pending in session.new
        assert cached in session.dirty
        assert statements and all(sql.lstrip().startswith("SELECT") for sql in statements)
        session.rollback()
        session.execute(text("PRAGMA query_only=OFF"))


def test_fresh_sql_identity_overrides_cached_label_without_reusing_other_donor_baseline(store):
    with store() as reader:
        cached = reader.get(models.IncomingPostModel, 1)
        with store.begin() as writer:
            writer.execute(
                text("UPDATE incoming_posts SET donor_channel_id='-1000000000002' WHERE id=1")
            )
            add_history(writer, 1)
            add_baseline(writer)  # Old donor's evidence must not be used.
        assert cached.donor_channel_id == "-1000000000001"
        result = inspect_post(reader)
        assert result.performance.views_samples == 0
        assert result.assessment.components.view_velocity is None


def test_fresh_scalar_reads_do_not_use_cached_missing_history(store):
    with store() as reader:
        assert inspect_post(reader).reason == "NO_ENGAGEMENT"
        with store.begin() as writer:
            add_history(writer, 1)
            add_baseline(writer)
        assert inspect_post(reader).performance.relative_views_velocity == 2


def test_cached_snapshot_edits_do_not_replace_persisted_evidence(store):
    with store.begin() as session:
        add_history(session, 1)
        add_baseline(session)
    with store() as session:
        snapshot = session.scalar(
            select(models.TelegramEngagementSnapshotModel)
            .where(
                models.TelegramEngagementSnapshotModel.incoming_post_id == 1,
            )
            .order_by(models.TelegramEngagementSnapshotModel.observed_at.desc())
        )
        source = session.get(models.TelegramEngagementSourceModel, 1)
        snapshot.views = 100000
        source.published_at = NOW - timedelta(days=10)
        result = inspect_post(session)
        assert result.performance.relative_views_velocity == 2
        assert result.assessment.components.freshness == pytest.approx(62.99605249474366)
        assert snapshot in session.dirty and source in session.dirty
        session.rollback()


def test_adjacent_intervals_count_each_message_once_and_include_thirty_day_boundary(store):
    with store.begin() as session:
        add_history(session, 1)
        for post_id in range(2, 7):
            add_history(
                session,
                post_id,
                PUBLISHED - timedelta(days=30),
                samples=((0, 0, 0, 0), (10, 100, 10, 20), (20, 200, 20, 40)),
            )
    with store() as session:
        result = inspect_post(session)
        assert result.performance.views_samples == 5
        assert result.performance.relative_views_velocity == 2


def test_large_lifetime_counts_do_not_change_interval_ranking(store):
    with store.begin() as session:
        add_history(session, 1, samples=((10, 1000000, 10, 20), (20, 1000200, 30, 60)))
        add_baseline(session, samples=((10, 2000000, 10, 20), (20, 2000100, 20, 40)))
    with store() as session:
        result = inspect_post(session)
        assert result.performance.relative_views_velocity == 2
        assert result.assessment.components.view_velocity == 100


def test_valid_custom_policy_can_score_known_freshness_only(store):
    with store.begin() as session:
        add_history(session, 1, samples=((20, 1, None, None),))
    weights = HypeWeights(
        **{field.name: int(field.name == "freshness") for field in fields(HypeWeights)}
    )
    with store() as session:
        result = inspect_post(session, weights=weights, minimum_coverage=1)
        assert result.reason == "READY"
        assert result.assessment.coverage == 1
        assert result.assessment.score == pytest.approx(62.99605249474366)


@pytest.mark.parametrize("post_id", [True, 0, -1, 2**63, 1.0, "1", None])
def test_invalid_post_id_fails(store, post_id):
    with store() as session, pytest.raises(ValueError):
        inspect_post(session, post_id)


@pytest.mark.parametrize("as_of", [None, datetime(2030, 1, 2), "2030-01-02"])
def test_invalid_clock_fails(store, as_of):
    with store() as session, pytest.raises(ValueError):
        inspect_post(session, as_of=as_of)


@pytest.mark.parametrize(
    "policy",
    [
        {"minimum_coverage": True},
        {"minimum_coverage": -1},
        {"minimum_coverage": float("nan")},
        {"weights": object()},
    ],
)
def test_invalid_policy_fails_even_when_engagement_is_missing(store, policy):
    with store() as session, pytest.raises((TypeError, ValueError)):
        inspect_post(session, **policy)


def test_forged_weights_fail_even_when_engagement_is_missing(store):
    weights = HypeWeights()
    object.__setattr__(weights, "freshness", True)
    with store() as session, pytest.raises(ValueError):
        inspect_post(session, weights=weights)


def test_unknown_post_and_noncanonical_identity_fail(store):
    with store() as session, pytest.raises(LookupError):
        inspect_post(session, 999)
    with store.begin() as session:
        session.execute(text("UPDATE incoming_posts SET telegram_account_id='01' WHERE id=1"))
    with store() as session, pytest.raises(ValueError):
        inspect_post(session)


def test_early_utc_publication_clamps_thirty_day_bound(store):
    published = datetime.min.replace(tzinfo=UTC)
    with store.begin() as session:
        add_history(session, 1, published)
    with store() as session:
        result = inspect_post(session, as_of=published + timedelta(minutes=20))
        assert result.reason == "INSUFFICIENT_EVIDENCE"
        assert result.performance.views_samples == 0


@pytest.mark.parametrize("rows,truncated", [(2000, False), (2001, True)])
def test_baseline_snapshot_bound_order_and_deterministic_truncation(store, rows, truncated):
    with store.begin() as session:
        add_history(session, 1)
        # Equal publications force incoming ID DESC before observation DESC.
        # Each selected message has one independent comparable ordinary interval.
        for post_id in range(2, 1002):
            add_history(
                session,
                post_id,
                NOW - timedelta(days=1),
                samples=((10, 100, 10, 20), (20, 200, 20, 40)),
            )
        if rows == 2001:
            # Newest message's extra old observation pushes the oldest message's
            # first observation past the 2000-row processing limit.
            session.add(
                models.TelegramEngagementSnapshotModel(
                    incoming_post_id=1001,
                    observed_at=NOW - timedelta(days=1, minutes=-1),
                    views=0,
                    forwards=0,
                    reactions=0,
                )
            )
    statements = []

    def capture(_connection, _cursor, statement, _parameters, context, _many):
        if "JOIN telegram_engagement_sources" in statement:
            statements.append((statement, context.compiled_parameters))

    engine = store.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture)
    try:
        with store() as session:
            result = inspect_post(session)
            assert result.baseline_truncated is truncated
            assert result.performance.views_samples == (999 if truncated else 1000)
            assert result.performance.relative_views_velocity == 2
            assert inspect_post(session) == result
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 2
    for sql, parameters in statements:
        assert "LIMIT" in sql and "ORDER BY" in sql
        assert 2001 in parameters[0].values()
