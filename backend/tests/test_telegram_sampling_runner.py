"""Migrated synthetic sampling contracts; provider IO is always fake."""

from dataclasses import replace
from datetime import timedelta

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker
from test_telegram_engagement_history import (
    NOW,
    history,
    observation,
    seed,
    zero_rewrite_calls,
)

from alembic import command
from newsflow.persistence import models
from newsflow.providers.telegram import FloodWait, SessionUnavailable
from newsflow.services.telegram_engagement_sampling import TelegramEngagementSamplingRunner

__all__ = ["zero_rewrite_calls"]


def assert_preserved(factory):
    with factory() as session:
        revision = session.scalar(
            select(models.ContentRevisionModel).where(
                models.ContentRevisionModel.incoming_post_id == 1
            )
        )
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert (revision.source_text, revision.revision_number) == ("Synthetic unchanged source", 1)
        assert (decision.status, decision.rewrite_allowed) == ("REJECT", False)
        assert session.get(models.IncomingPostModel, 1).state == "RECEIVED"
        assert (
            session.scalar(
                select(func.count())
                .select_from(models.ContentRevisionModel)
                .where(models.ContentRevisionModel.incoming_post_id == 1)
            )
            == 1
        )
        for model in (
            models.RewriteJobModel,
            models.RewriteUsageModel,
            models.RewriteOutputModel,
            models.EditorialClassificationJobModel,
            models.MediaAcquisitionJobModel,
            models.PublicationCandidateModel,
            models.PlannedPublicationModel,
            models.PublicationJobModel,
            models.PublicationRequestSnapshotModel,
            models.PublicationDeliveryObservationModel,
            models.OutboxEventModel,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def seed_sampling(factory):
    seed(factory)
    with factory.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.encrypted_session = "synthetic-ciphertext"
        account.health_status = "CONNECTED"
        session.get(models.IncomingPostModel, 1).created_at = NOW
        output = models.OutputChannel(
            telegram_account_id=1, telegram_channel_id=-1000000000002, title="Synthetic output"
        )
        session.add(output)
        session.flush()
        donor = session.scalar(select(models.DonorChannel))
        session.add(
            models.ChannelMappingModel(
                donor_channel_id=donor.id,
                output_channel_id=output.id,
                intake_percent=100,
                target_mix_percent=100,
            )
        )


@pytest.fixture
def store(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'sampling.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    seed_sampling(factory)
    yield factory
    assert_preserved(factory)
    engine.dispose()


class Fake:
    def __init__(self, *, published=NOW, callback=None, error=None):
        self.published = published
        self.callback = callback
        self.error = error
        self.calls = []

    def fetch_engagement(self, account_id, donor_identifier, message_id, *, observed_at):
        self.calls.append((account_id, donor_identifier, message_id, observed_at))
        if self.callback:
            self.callback()
        if self.error:
            raise self.error
        return observation(published_at=self.published, observed_at=observed_at)


def runner(factory, provider=None, now=NOW):
    return TelegramEngagementSamplingRunner(factory, provider=provider or Fake(), clock=lambda: now)


def test_committed_claim_observation_advances_without_rewrite(store):
    provider = Fake()
    service = runner(store, provider)
    admitted = service.enqueue_window(now=NOW)
    assert admitted.queued_ids == (1,)
    claim = service.claim_next(now=NOW)
    assert claim is not None and claim.step == 0
    with store() as session:
        job = session.get(models.TelegramEngagementSamplingJobModel, 1)
        assert (job.state, job.attempts, job.claim_token) == ("RUNNING", 1, claim.token)
    assert service.execute(claim) == "SAMPLED"
    with store() as session:
        assert history(session).history(1)[0].observed_at == NOW
        job = session.get(models.TelegramEngagementSamplingJobModel, 1)
        assert (job.state, job.step, job.attempts) == ("QUEUED", 1, 0)
        assert job.available_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(seconds=60)
    assert provider.calls == [("1", "-1000000000001", 7, NOW)]
    assert_preserved(store)


def job_after(factory):
    with factory() as session:
        return session.get(models.TelegramEngagementSamplingJobModel, 1)


def admitted_claim(factory, *, provider=None, now=NOW):
    service = runner(factory, provider, now)
    service.enqueue_window(now=now)
    return service, service.claim_next(now=now)


def test_unknown_provider_failure_is_private_and_terminal(store):
    service, claim = admitted_claim(store, provider=Fake(error=RuntimeError("secret-session-body")))
    assert service.execute(claim) == "BLOCKED"
    job = job_after(store)
    assert (job.state, job.last_error_code) == ("BLOCKED", "INVALID_OBSERVATION")


def test_final_clock_backwards_from_actual_acquisition_is_stale(store):
    times = iter(
        (NOW + timedelta(seconds=10), NOW + timedelta(seconds=20), NOW + timedelta(seconds=15))
    )
    service, claim = admitted_claim(store)
    service._clock = lambda: next(times)
    assert service.execute(claim) == "STALE_CLAIM"
    with store() as session:
        assert history(session).history(1) == ()
    assert job_after(store).state == "RUNNING"


def test_failed_job_commit_rolls_back_source_and_history(store):
    service, claim = admitted_claim(store)
    engine = store.kw["bind"]

    def fail_job(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE telegram_engagement_sampling_jobs"):
            raise RuntimeError("synthetic SQL interruption")

    event.listen(engine, "before_cursor_execute", fail_job)
    try:
        with pytest.raises(RuntimeError, match="synthetic SQL interruption"):
            service.execute(claim)
    finally:
        event.remove(engine, "before_cursor_execute", fail_job)
    with store() as session:
        assert history(session).history(1) == ()
        assert (
            session.scalar(select(func.count()).select_from(models.TelegramEngagementSourceModel))
            == 0
        )
    assert job_after(store).claim_token == claim.token


def test_complete_six_actual_intervals_survive_double_reopen(store):
    provider = Fake()
    current = [NOW]
    service = TelegramEngagementSamplingRunner(store, provider=provider, clock=lambda: current[0])
    service.enqueue_window(now=NOW)
    for index, seconds in enumerate((0, 60, 300, 600, 1200, 1800, 3600)):
        current[0] = NOW + timedelta(seconds=seconds)
        store.kw["bind"].dispose()
        store.kw["bind"].dispose()
        claim = service.claim_next(now=current[0])
        assert claim.step == index
        assert service.execute(claim) == ("SUCCEEDED" if index == 6 else "SAMPLED")
    assert (job_after(store).step, job_after(store).attempts, job_after(store).missed_windows) == (
        7,
        0,
        0,
    )
    assert service.run_next(now=current[0]) == "IDLE"
    with store() as session:
        assert [
            int((v.observed_at - NOW).total_seconds()) for v in history(session).history(1)
        ] == [0, 60, 300, 600, 1200, 1800, 3600]
    assert len(provider.calls) == 7


@pytest.mark.parametrize("age,step,missed", [(60, 2, 1), (601, 4, 3), (4000, 7, 6)])
def test_original_publication_age_controls_discovery_not_ingestion_time(store, age, step, missed):
    with store.begin() as session:
        session.scalar(select(models.ContentRevisionModel)).source_updated_at = NOW - timedelta(
            seconds=1
        )
    provider = Fake(published=NOW - timedelta(seconds=age))
    service, claim = admitted_claim(store, provider=provider)
    assert service.execute(claim) == ("SUCCEEDED" if step == 7 else "SAMPLED")
    assert (job_after(store).step, job_after(store).missed_windows) == (step, missed)
    with store() as session:
        assert history(session).history(1)[0].published_at == NOW - timedelta(seconds=age)
    assert len(provider.calls) == 1


def test_late_scheduled_step_skips_only_later_thresholds(store):
    service, claim = admitted_claim(store)
    assert service.execute(claim) == "SAMPLED"
    late = runner(store, now=NOW + timedelta(seconds=601))
    assert late.run_next(now=NOW + timedelta(seconds=601)) == "SAMPLED"
    assert (job_after(store).step, job_after(store).missed_windows) == (4, 2)


def test_admission_is_bounded_fair_idempotent_and_wraps_in_same_call(store):
    with store.begin() as session:
        for post_id in range(2, 21):
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
        for post_id in range(2, 21):
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post_id, revision_number=1, source_text="synthetic source"
                )
            )
    service = runner(store)
    assert service.enqueue_window(now=NOW).queued_ids == tuple(range(1, 17))
    tail = service.enqueue_window(now=NOW, after_id=16)
    assert (tail.cursor, tail.queued_ids) == (20, (17, 18, 19, 20))
    wrapped = service.enqueue_window(now=NOW, after_id=20, limit=3)
    assert (wrapped.cursor, wrapped.queued_ids) == (3, ())
    assert service.enqueue_window(now=NOW, after_id=3, limit=3).cursor == 6
    assert job_after(store).attempts == 0


@pytest.mark.parametrize("seconds,admit", [(-3601, False), (-3600, True), (1, False)])
def test_admission_created_time_bounds(store, seconds, admit):
    with store.begin() as session:
        session.get(models.IncomingPostModel, 1).created_at = NOW + timedelta(seconds=seconds)
    assert runner(store).enqueue_window(now=NOW).queued_ids == ((1,) if admit else ())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"after_id": True},
        {"after_id": -1},
        {"after_id": 2**63},
        {"limit": True},
        {"limit": 0},
        {"limit": 17},
        {"now": NOW.replace(tzinfo=None)},
    ],
)
def test_admission_invalid_parameters_fail_before_database(kwargs):
    def forbidden():
        pytest.fail("invalid parameter opened database")

    with pytest.raises(ValueError):
        runner(forbidden).enqueue_window(**({"now": NOW} | kwargs))


@pytest.mark.parametrize(
    "field,value",
    [
        ("incoming_post_id", True),
        ("incoming_post_id", 2**63),
        ("account_id", "01"),
        ("donor_identifier", "-1001"),
        ("message_id", True),
        ("step", True),
        ("step", 7),
        ("token", "INVALID"),
        ("session_digest", "X" * 64),
        ("expected_user_id", True),
        ("lease_expires_at", NOW.replace(tzinfo=None)),
    ],
)
def test_forged_frozen_claim_revalidated_before_database(store, field, value):
    _, claim = admitted_claim(store)
    object.__setattr__(claim, field, value)

    def forbidden():
        pytest.fail("invalid claim opened database")

    provider = Fake()
    with pytest.raises(ValueError):
        runner(forbidden, provider).execute(claim)
    assert provider.calls == []


@pytest.mark.parametrize("seconds", [-1, 60, 61])
def test_preclaim_or_expired_clock_never_fetches(store, seconds):
    _service, claim = admitted_claim(store)
    provider = Fake()
    assert runner(store, provider, NOW + timedelta(seconds=seconds)).execute(claim) == "STALE_CLAIM"
    assert provider.calls == []
    assert job_after(store).claim_token == claim.token


def test_fetch_callback_holds_no_session_transaction_or_checked_out_connection(store):
    def callback():
        assert store.kw["bind"].pool.checkedout() == 0
        with store() as session:
            assert session.get(models.TelegramEngagementSamplingJobModel, 1).state == "RUNNING"

    service, claim = admitted_claim(store, provider=Fake(callback=callback))
    assert service.execute(claim) == "SAMPLED"


def mutate(factory, change):
    with factory.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        if change == "session":
            account.encrypted_session = "new-synthetic-session"
        elif change == "user":
            account.telegram_user_id = 42
        elif change == "health":
            account.health_status = "SESSION_INVALID"
        elif change == "cooldown":
            account.health_status = "COOLDOWN"
            account.cooldown_until = NOW + timedelta(minutes=10)
        elif change == "mapping":
            session.execute(text("DELETE FROM channel_mappings"))
        elif change == "revision":
            session.execute(text("DELETE FROM incoming_post_revisions"))
        elif change == "deletion":
            session.add(
                models.SourceDeletionModel(
                    telegram_account_id="1",
                    donor_channel_id="-1000000000001",
                    telegram_message_id=7,
                    latest_pts=1,
                    observed_at=NOW,
                )
            )
        elif change == "sync":
            donor = session.scalar(select(models.DonorChannel))
            session.add(
                models.ChannelDifferenceCursorModel(
                    donor_channel_id=donor.id,
                    telegram_account_id=1,
                    telegram_user_id=41,
                    telegram_channel_id=-1000000000001,
                    pts=1,
                    available_at=NOW,
                    last_error_code="GAP_UNRESOLVED",
                )
            )


@pytest.mark.parametrize("when", ["pre", "post"])
@pytest.mark.parametrize(
    "change,outcome",
    [
        ("session", "STALE_CLAIM"),
        ("user", "STALE_CLAIM"),
        ("mapping", "BLOCKED"),
        ("deletion", "BLOCKED"),
        ("health", "BLOCKED"),
        ("sync", "WAIT_SYNC"),
        ("cooldown", "WAIT_COOLDOWN"),
    ],
)
def test_current_permission_drift_fences_pre_and_post_call(store, when, change, outcome):
    provider = Fake(callback=(lambda: mutate(store, change)) if when == "post" else None)
    service, claim = admitted_claim(store, provider=provider)
    if when == "pre":
        mutate(store, change)
    assert service.execute(claim) == outcome
    assert len(provider.calls) == (1 if when == "post" else 0)
    with store() as session:
        assert history(session).history(1) == ()
    assert job_after(store).attempts == 1


@pytest.mark.parametrize("change", ["session", "user"])
@pytest.mark.parametrize(
    "error", [SessionUnavailable("private"), RuntimeError("private"), FloodWait(100)]
)
def test_stale_provider_error_cannot_change_newer_account(store, change, error):
    provider = Fake(callback=lambda: mutate(store, change), error=error)
    service, claim = admitted_claim(store, provider=provider)
    assert service.execute(claim) == "STALE_CLAIM"
    with store() as session:
        assert session.get(models.TelegramAccount, 1).health_status == "CONNECTED"
    assert job_after(store).state == "RUNNING"


@pytest.mark.parametrize("change", ["mapping", "deletion", "health", "sync", "cooldown"])
def test_claim_rechecks_permission_without_spending_attempt(store, change):
    service = runner(store)
    service.enqueue_window(now=NOW)
    mutate(store, change)
    assert service.claim_next(now=NOW) is None
    job = job_after(store)
    assert job.attempts == 0
    assert job.state == ("QUEUED" if change in {"sync", "cooldown"} else "BLOCKED")
    if change in {"sync", "cooldown"}:
        expected = 600 if change == "cooldown" else 30
        assert job.available_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(seconds=expected)


def test_expired_cooldown_account_claim_is_accepted(store):
    service = runner(store)
    service.enqueue_window(now=NOW)
    with store.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.health_status = "COOLDOWN"
        account.cooldown_until = NOW - timedelta(seconds=1)
    assert service.claim_next(now=NOW) is not None


def test_expired_takeover_and_attempt_exhaustion_never_make_fourth_call(store):
    provider = Fake()
    _service, original = admitted_claim(store, provider=provider)
    for attempt in (2, 3):
        when = NOW + timedelta(seconds=60 * (attempt - 1))
        store.kw["bind"].dispose()
        claim = runner(store, provider, when).claim_next(now=when)
        assert job_after(store).attempts == attempt
        assert claim.token != original.token
        assert runner(store, provider, when).execute(original) == "STALE_CLAIM"
    assert (
        runner(store, provider, NOW + timedelta(seconds=180)).claim_next(
            now=NOW + timedelta(seconds=180)
        )
        is None
    )
    assert (job_after(store).state, job_after(store).attempts) == ("FAILED", 3)
    assert provider.calls == []


@pytest.mark.parametrize(
    "error", [TimeoutError("private"), ConnectionError("private"), OSError("private")]
)
def test_transient_error_retries_three_times_then_fails(store, error):
    provider = Fake(error=error)
    for attempt in (1, 2, 3):
        when = NOW + timedelta(seconds=30 * (attempt - 1))
        service = runner(store, provider, when)
        service.enqueue_window(now=when)
        assert service.run_next(now=when) == ("FAILED" if attempt == 3 else "RETRY_PROVIDER")
        assert job_after(store).attempts == attempt
        assert service.run_next(now=when) == "IDLE"
    assert len(provider.calls) == 3


@pytest.mark.parametrize(
    "seconds,outcome",
    [(0, "FLOOD_WAIT"), (120, "FLOOD_WAIT"), (2**63, "FAILED"), (-1, "FAILED"), (True, "FAILED")],
)
def test_flood_wait_exact_delay_and_overflow_fail_closed(store, seconds, outcome):
    service, claim = admitted_claim(store, provider=Fake(error=FloodWait(seconds)))
    assert service.execute(claim) == outcome
    with store() as session:
        account = session.get(models.TelegramAccount, 1)
        if outcome == "FLOOD_WAIT":
            assert account.health_status == "COOLDOWN"
            assert account.cooldown_until.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(
                seconds=seconds
            )
        else:
            assert account.health_status == "CONNECTED"


@pytest.mark.parametrize("concurrent,required,expected", [(30, 120, 120), (180, 120, 180)])
def test_flood_wait_preserves_full_required_and_longer_concurrent_cooldown(
    store, concurrent, required, expected
):
    def callback():
        with store.begin() as session:
            account = session.get(models.TelegramAccount, 1)
            account.health_status = "COOLDOWN"
            account.cooldown_until = NOW + timedelta(seconds=concurrent)

    service, claim = admitted_claim(
        store, provider=Fake(callback=callback, error=FloodWait(required))
    )
    assert service.execute(claim) == "FLOOD_WAIT"
    with store() as session:
        account = session.get(models.TelegramAccount, 1)
        assert account.cooldown_until.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(
            seconds=expected
        )
    assert job_after(store).available_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(
        seconds=expected
    )


def test_flood_wait_with_concurrent_cooldown_and_sync_gap_keeps_sync_fence(store):
    def callback():
        mutate(store, "cooldown")
        mutate(store, "sync")

    service, claim = admitted_claim(store, provider=Fake(callback=callback, error=FloodWait(1200)))
    assert service.execute(claim) == "WAIT_SYNC"
    with store() as session:
        assert session.get(models.TelegramAccount, 1).cooldown_until.replace(
            tzinfo=NOW.tzinfo
        ) == NOW + timedelta(seconds=600)


def test_clock_backwards_between_precheck_and_fetch_never_calls_provider(store):
    times = iter(
        (NOW + timedelta(seconds=20), NOW + timedelta(seconds=10), NOW + timedelta(seconds=20))
    )
    provider = Fake()
    service, claim = admitted_claim(store, provider=provider)
    service._clock = lambda: next(times)
    assert service.execute(claim) == "STALE_CLAIM"
    assert provider.calls == []


def test_session_unavailable_invalidates_only_current_session(store):
    service, claim = admitted_claim(store, provider=Fake(error=SessionUnavailable("private")))
    assert service.execute(claim) == "BLOCKED"
    with store() as session:
        assert session.get(models.TelegramAccount, 1).health_status == "SESSION_INVALID"
    assert job_after(store).last_error_code == "SESSION_UNAVAILABLE"


@pytest.mark.parametrize(
    "changes",
    [
        {"views": True},
        {"views": -1},
        {"views": 2**63},
        {"observed_at": NOW + timedelta(seconds=1)},
        {"account_id": "2"},
        {"message_id": 8},
        {"published_at": NOW + timedelta(seconds=1)},
    ],
)
def test_forged_provider_observation_is_reconstructed_and_identity_fenced(store, changes):
    class Forged(Fake):
        def fetch_engagement(self, *args, **kwargs):
            value = super().fetch_engagement(*args, **kwargs)
            for field, replacement in changes.items():
                object.__setattr__(value, field, replacement)
            return value

    service, claim = admitted_claim(store, provider=Forged())
    assert service.execute(claim) == "BLOCKED"
    assert job_after(store).last_error_code == "INVALID_OBSERVATION"
    with store() as session:
        assert history(session).history(1) == ()


def test_nullable_and_reset_counters_are_stored_honestly(store):
    class Counters(Fake):
        def fetch_engagement(self, *args, **kwargs):
            value = super().fetch_engagement(*args, **kwargs)
            return replace(
                value,
                views=None if len(self.calls) == 1 else 0,
                forwards=2**63 - 1 if len(self.calls) == 1 else 0,
            )

    provider = Counters()
    service, claim = admitted_claim(store, provider=provider)
    assert service.execute(claim) == "SAMPLED"
    assert (
        runner(store, provider, NOW + timedelta(seconds=60)).run_next(
            now=NOW + timedelta(seconds=60)
        )
        == "SAMPLED"
    )
    with store() as session:
        values = history(session).history(1)
        assert [value.views for value in values] == [None, 0]
        assert [value.forwards for value in values] == [2**63 - 1, 0]


def test_immutable_publication_conflict_blocks_without_new_history(store):
    with store.begin() as session:
        history(session).record(
            observation(published_at=NOW - timedelta(seconds=10), observed_at=NOW)
        )
    service, claim = admitted_claim(store)
    assert service.execute(claim) == "BLOCKED"
    with store() as session:
        assert len(history(session).history(1)) == 1
    assert job_after(store).last_error_code == "INVALID_OBSERVATION"


def test_terminal_job_is_retained_without_reset_or_revival(store):
    service, claim = admitted_claim(store, provider=Fake(published=NOW - timedelta(hours=2)))
    assert service.execute(claim) == "SUCCEEDED"
    assert service.enqueue_window(now=NOW).queued_ids == ()
    assert service.claim_next(now=NOW + timedelta(hours=1)) is None
    with store() as session, pytest.raises(DBAPIError):
        session.execute(text("DELETE FROM telegram_engagement_sampling_jobs"))
    assert job_after(store).state == "SUCCEEDED"


@pytest.mark.parametrize("change", ["mapping", "deletion", "health", "sync", "cooldown"])
def test_admission_requires_current_healthy_configured_source(store, change):
    mutate(store, change)
    provider = Fake()
    assert runner(store, provider).enqueue_window(now=NOW).queued_ids == ()
    assert provider.calls == []


@pytest.mark.parametrize("change", ["revision", "empty_session", "user", "moved_donor"])
def test_claim_blocks_missing_source_revision_session_user_or_donor(store, change):
    service = runner(store)
    service.enqueue_window(now=NOW)
    with store.begin() as session:
        if change == "revision":
            session.execute(text("DELETE FROM incoming_post_revisions"))
        elif change == "empty_session":
            session.get(models.TelegramAccount, 1).encrypted_session = ""
        elif change == "user":
            session.get(models.TelegramAccount, 1).telegram_user_id = 0
        else:
            session.scalar(select(models.DonorChannel)).telegram_channel_id = -1000000000003
    assert service.claim_next(now=NOW) is None
    assert (job_after(store).state, job_after(store).attempts) == ("BLOCKED", 0)
    if change == "revision":
        with store.begin() as session:
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=1, revision_number=1, source_text="Synthetic unchanged source"
                )
            )


def test_provider_lookup_error_is_private_source_block(store):
    service, claim = admitted_claim(store, provider=Fake(error=LookupError("private-source")))
    assert service.execute(claim) == "BLOCKED"
    assert job_after(store).last_error_code == "SOURCE_UNAVAILABLE"


def test_claim_date_overflow_fails_without_io(store):
    service = runner(store)
    service.enqueue_window(now=NOW)
    from datetime import datetime

    future = datetime.max.replace(tzinfo=NOW.tzinfo) - timedelta(seconds=30)
    assert service.claim_next(now=future) is None
    assert (job_after(store).state, job_after(store).last_error_code) == (
        "FAILED",
        "INVALID_SCHEDULE",
    )


def test_early_scheduled_observation_fails_without_new_history(store):
    service, claim = admitted_claim(store)
    assert service.execute(claim) == "SAMPLED"
    with store.begin() as session:
        session.get(models.TelegramEngagementSamplingJobModel, 1).available_at = NOW
    early = NOW + timedelta(seconds=30)
    assert runner(store, now=early).run_next(now=early) == "FAILED"
    assert job_after(store).last_error_code == "INVALID_SCHEDULE"
    with store() as session:
        assert len(history(session).history(1)) == 1


@pytest.mark.parametrize("response", [None, {}, (), "private"])
def test_wrong_observation_type_never_stores_history(store, response):
    class Wrong(Fake):
        def fetch_engagement(self, *args, **kwargs):
            super().fetch_engagement(*args, **kwargs)
            return response

    service, claim = admitted_claim(store, provider=Wrong())
    assert service.execute(claim) == "BLOCKED"
    with store() as session:
        assert history(session).history(1) == ()


def test_flood_wait_third_attempt_retains_full_cooldown_but_never_retries_fourth(store):
    provider = Fake(error=FloodWait(30))
    for attempt in (1, 2, 3):
        when = NOW + timedelta(seconds=30 * (attempt - 1))
        service = runner(store, provider, when)
        service.enqueue_window(now=when)
        assert service.run_next(now=when) == ("FAILED" if attempt == 3 else "FLOOD_WAIT")
    with store() as session:
        assert session.get(models.TelegramAccount, 1).cooldown_until.replace(
            tzinfo=NOW.tzinfo
        ) == NOW + timedelta(seconds=90)
    assert (
        runner(store, provider, NOW + timedelta(seconds=90)).run_next(
            now=NOW + timedelta(seconds=90)
        )
        == "IDLE"
    )
    assert len(provider.calls) == 3


def test_native_sqlite_job_failure_atomically_rolls_back_history_and_keeps_lease(store):
    service, claim = admitted_claim(store)
    with store.kw["bind"].begin() as connection:
        connection.exec_driver_sql("""CREATE TRIGGER synthetic_sampling_failure
            BEFORE UPDATE ON telegram_engagement_sampling_jobs
            BEGIN SELECT RAISE(ABORT, 'synthetic SQL failure'); END""")
    with pytest.raises(DBAPIError, match="synthetic SQL failure"):
        service.execute(claim)
    with store() as session:
        assert history(session).history(1) == ()
        assert (
            session.scalar(select(func.count()).select_from(models.TelegramEngagementSourceModel))
            == 0
        )
    assert (job_after(store).state, job_after(store).claim_token) == ("RUNNING", claim.token)
