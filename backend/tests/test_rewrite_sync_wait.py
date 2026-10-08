from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_channel_sync_enforcement import baseline, enable
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store

from newsflow.persistence import models
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

source_store = _source_store


def pending(factory, error="DIFFERENCE_INCOMPLETE", attempts=0):
    baseline(factory)
    enable(factory)
    with factory.begin() as session:
        session.get(models.ChannelDifferenceCursorModel, 1).last_error_code = error
        job = session.get(models.RewriteJobModel, 1)
        job.state, job.available_at, job.attempts = "DISPATCHED", NOW, attempts
        session.get(models.PublicationCandidateModel, 1).state = "AWAITING_REWRITE"
        session.delete(session.scalar(select(models.RewriteOutputModel)))


def forbidden(_channel):
    raise AssertionError("Synchronization wait constructed an AI provider")


@pytest.mark.parametrize(
    "state", ["active", "RETRY_PROVIDER", "RETRY_PIPELINE", "DIFFERENCE_INCOMPLETE"]
)
def test_temporary_sync_wait_retains_job_without_using_ai_attempt_budget(source_store, state):
    factory, _ = source_store
    pending(factory, None if state == "active" else state)
    if state == "active":
        with factory.begin() as session:
            cursor = session.get(models.ChannelDifferenceCursorModel, 1)
            cursor.claim_token, cursor.lease_expires_at = "synthetic", NOW + timedelta(seconds=60)
    runner = DurableRewriteRunner(
        factory, provider_for_channel=forbidden, clock=lambda: NOW, max_attempts=2
    )
    assert runner.run_next(now=NOW) == "RETRY"
    with factory() as session:
        job = session.get(models.RewriteJobModel, 1)
        assert job.attempts == 0 and job.last_error_code == "SOURCE_SYNC_REQUIRED"
        assert job.available_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(seconds=30)
        assert job.claim_token is None and job.lease_expires_at is None
        assert session.scalar(select(models.RewriteOutputModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None
    assert runner.run_next(now=NOW + timedelta(seconds=29)) == "IDLE"
    assert runner.run_next(now=NOW + timedelta(seconds=30)) == "RETRY"
    with factory() as session:
        assert session.get(models.RewriteJobModel, 1).attempts == 0


def test_sync_wait_recovers_after_sql_reopen_and_fresh_source_without_fake_approval(source_store):
    factory, _ = source_store
    pending(factory)
    assert (
        DurableRewriteRunner(factory, provider_for_channel=forbidden).run_next(now=NOW) == "RETRY"
    )
    with factory.begin() as session:
        session.get(models.ChannelDifferenceCursorModel, 1).last_error_code = None
    reopened = create_engine(str(factory.kw["bind"].url))
    try:
        sessions = sessionmaker(reopened)

        class Provider:
            def rewrite(self, text):
                return text

        assert (
            DurableRewriteRunner(
                sessions,
                provider_for_channel=lambda _: Provider(),
                clock=lambda: NOW + timedelta(seconds=30),
            ).run_next(now=NOW + timedelta(seconds=30))
            == "SUCCEEDED"
        )
        with sessions() as session:
            assert session.get(models.RewriteJobModel, 1).attempts == 1
            assert session.scalar(select(models.RewriteOutputModel)).approval_state == "PENDING"
    finally:
        reopened.dispose()


def test_sync_wait_cannot_reset_an_exhausted_ai_attempt_budget(source_store):
    factory, _ = source_store
    pending(factory, attempts=2)
    runner = DurableRewriteRunner(
        factory, provider_for_channel=forbidden, clock=lambda: NOW, max_attempts=2
    )
    assert runner.run_next(now=NOW) == "RETRY"
    with factory.begin() as session:
        assert session.get(models.RewriteJobModel, 1).attempts == 2
        session.get(models.ChannelDifferenceCursorModel, 1).last_error_code = None
    assert runner.run_next(now=NOW + timedelta(seconds=30)) == "FAILED"


def test_reject_during_sync_wait_remains_terminal_and_zero_provider(source_store):
    factory, _ = source_store
    pending(factory)
    runner = DurableRewriteRunner(factory, provider_for_channel=forbidden, clock=lambda: NOW)
    assert runner.run_next(now=NOW) == "RETRY"
    with factory.begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    assert runner.run_next(now=NOW + timedelta(seconds=30)) == "BLOCKED_EDITORIAL"
    with factory() as session:
        assert session.get(models.RewriteJobModel, 1).attempts == 1
        assert session.scalar(select(models.RewriteUsageModel)) is None


@pytest.mark.parametrize(
    "permanent", ["deleted", "stale", "gap", "foreign", "missing", "invalid_session"]
)
def test_temporary_wait_does_not_bypass_permanent_source_block(source_store, permanent):
    factory, _ = source_store
    pending(factory)
    runner = DurableRewriteRunner(factory, provider_for_channel=forbidden, clock=lambda: NOW)
    assert runner.run_next(now=NOW) == "RETRY"
    with factory.begin() as session:
        cursor = session.get(models.ChannelDifferenceCursorModel, 1)
        if permanent == "deleted":
            session.add(
                models.SourceDeletionModel(
                    telegram_account_id="1",
                    donor_channel_id="-1001234567890",
                    telegram_message_id=20,
                    latest_pts=11,
                    observed_at=NOW,
                )
            )
        elif permanent == "stale":
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=1,
                    revision_number=2,
                    source_text="Newer source",
                    media_type="text",
                    source_updated_at=NOW + timedelta(seconds=1),
                )
            )
        elif permanent == "gap":
            cursor.last_error_code = "GAP_UNRESOLVED"
        elif permanent == "foreign":
            cursor.telegram_user_id = 9999
        elif permanent == "missing":
            session.delete(cursor)
        else:
            session.get(models.TelegramAccount, 1).health_status = "SESSION_INVALID"
    assert runner.run_next(now=NOW + timedelta(seconds=30)) == "SUPERSEDED"
    assert runner.run_next(now=NOW + timedelta(seconds=60)) == "IDLE"
    with factory() as session:
        assert session.scalar(select(models.RewriteOutputModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None


def test_sync_changed_after_ai_retains_consumed_attempt_without_creating_draft(source_store):
    factory, _ = source_store
    pending(factory, None)

    class Provider:
        def rewrite(self, text):
            with factory.begin() as session:
                session.get(
                    models.ChannelDifferenceCursorModel, 1
                ).last_error_code = "RETRY_PROVIDER"
            return text

    runner = DurableRewriteRunner(
        factory, provider_for_channel=lambda _: Provider(), clock=lambda: NOW
    )
    assert runner.run_next(now=NOW) == "RETRY"
    with factory() as session:
        job = session.get(models.RewriteJobModel, 1)
        assert job.attempts == 1 and job.last_error_code == "SOURCE_SYNC_REQUIRED"
        assert session.scalar(select(models.RewriteOutputModel)) is None


def test_expired_running_claim_waits_without_erasing_previous_attempt_or_job_identity(source_store):
    factory, _ = source_store
    pending(factory, attempts=1)
    with factory.begin() as session:
        job = session.get(models.RewriteJobModel, 1)
        job.state, job.claim_token, job.lease_expires_at = (
            "RUNNING",
            "old-owner",
            NOW - timedelta(seconds=1),
        )
    assert (
        DurableRewriteRunner(factory, provider_for_channel=forbidden, clock=lambda: NOW).run_next(
            now=NOW
        )
        == "RETRY"
    )
    with factory() as session:
        job = session.get(models.RewriteJobModel, 1)
        assert job.attempts == 1 and job.idempotency_key == "synthetic-source-photo"
        assert job.content_key == "1:-1001234567890:20:revision:1"
        assert session.scalar(select(models.RewriteUsageModel)) is None


def test_current_account_cooldown_can_wait_but_never_call_ai(source_store):
    factory, _ = source_store
    pending(factory, "COOLDOWN")
    with factory.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.health_status, account.cooldown_until = "COOLDOWN", NOW + timedelta(seconds=600)
    assert (
        DurableRewriteRunner(factory, provider_for_channel=forbidden, clock=lambda: NOW).run_next(
            now=NOW
        )
        == "RETRY"
    )
    with factory() as session:
        assert session.get(models.RewriteJobModel, 1).attempts == 0
        assert session.scalar(select(models.RewriteUsageModel)) is None
