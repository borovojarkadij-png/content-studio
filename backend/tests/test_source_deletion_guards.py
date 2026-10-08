from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_configured_text_publication import CIPHER
from test_publication_preflight import seed_plan
from test_publication_runner import Publisher
from test_source_photo_acquisition import CHANNEL, KEY, NOW, Photos, acquisition
from test_source_photo_acquisition import source_store as _source_store

from newsflow.app import app
from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.editorial import EditorialGate
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.persistence import models
from newsflow.providers.telegram import TelegramChannelDifference, TelegramMessage
from newsflow.services.durable_publication_runner import DurablePublicationRunner
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.publication_observations import PublicationObservations
from newsflow.services.publication_planning import CandidateBlocked, PublicationPlanningService
from newsflow.services.rewrite_outputs import RewriteOutputBlocked, RewriteOutputService
from newsflow.services.source_deletions import SourceDeletionClaimLost, SourceDeletionService
from newsflow.services.source_revisions import source_is_current

source_store = _source_store


def record(factory, ids=(20,), *, pts=11):
    service = SourceDeletionService(factory)
    difference = TelegramChannelDifference("1", CHANNEL, 10, pts, True, 0, (), ids)
    return service.record(difference, observed_at=NOW)


def test_deletion_is_durable_idempotent_and_never_erases_source_history(source_store):
    factory, _ = source_store
    assert record(factory) == (20,)
    assert record(factory) == ()
    assert record(factory, pts=12) == ()
    with factory() as session:
        assert source_is_current(session, KEY) is False
        assert session.get(models.ContentRevisionModel, 1).source_text == "Photo caption"
        assert session.get(models.RewriteJobModel, 1).state == "SUCCEEDED"
        tombstone = session.get(models.SourceDeletionModel, ("1", CHANNEL, 20))
        assert tombstone.latest_pts == 12
        assert (
            len(
                session.scalars(
                    select(models.OutboxEventModel).where(
                        models.OutboxEventModel.event_type == "source.deleted"
                    )
                ).all()
            )
            == 1
        )


def test_deleted_source_replay_stops_before_editorial_or_rewrite_creation(source_store):
    record(source_store[0], ids=(99,))

    class ForbiddenGate(EditorialGate):
        def evaluate(self, **_kwargs):
            raise AssertionError("Deleted source must never reach classifier/rewrite")

    with source_store[0]() as session:
        result = DurableIngestionWorkflow(session, editorial_gate=ForbiddenGate()).ingest(
            TelegramMessage("1", CHANNEL, 99, "A new replayed caption", source_updated_at=NOW),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert result.status == "REJECTED_TECHNICAL" and result.reason_code == "SOURCE_DELETED"
    with source_store[0]() as session:
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1
        assert len(session.scalars(select(models.EditorialDecisionModel)).all()) == 1


def test_cached_decision_cannot_create_new_channel_rewrite_after_deletion(source_store):
    record(source_store[0])
    with source_store[0]() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        result = DurableEditorialService(session, EditorialGate()).create_rewrite_job(
            decision, output_channel_id=None
        )
        assert result is None
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1


def test_stale_publication_job_never_sends_after_deletion(source_store):
    seed_plan(source_store)
    publisher = Publisher()
    execution = DurablePublicationRunner(*source_store, publisher=publisher, clock=lambda: NOW)
    execution.enqueue(1, now=NOW)
    record(source_store[0])
    assert execution.run_next(now=NOW) == "BLOCKED" and not publisher.calls


def test_freshness_rechecks_tombstone_insert_from_separate_writer(source_store):
    with source_store[0]() as session:
        assert source_is_current(session, KEY) is True
        record(source_store[0])
        assert source_is_current(session, KEY) is False


@pytest.mark.parametrize("state", ["DISPATCHED", "RETRY", "RUNNING"])
def test_deleted_source_stale_rewrite_and_retry_construct_no_ai_provider(source_store, state):
    with source_store[0].begin() as session:
        job = session.get(models.RewriteJobModel, 1)
        job.state, job.available_at = state, NOW
        job.claim_token, job.lease_expires_at = "expired-owner", NOW - timedelta(seconds=1)
        session.get(models.PublicationCandidateModel, 1).state = "AWAITING_REWRITE"
        session.delete(session.scalar(select(models.RewriteOutputModel)))
    record(source_store[0])

    def forbidden_provider(_channel):
        raise AssertionError("Deleted source reached AI provider")

    runner = DurableRewriteRunner(source_store[0], provider_for_channel=forbidden_provider)
    assert runner.run_next(now=NOW) == "SUPERSEDED"
    with source_store[0]() as session:
        assert session.scalar(select(models.RewriteOutputModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None


def test_deleted_source_blocks_manual_approval_planning_and_source_download(source_store):
    record(source_store[0])
    with source_store[0]() as session:
        assert RewriteOutputService(session).list_outputs()[0]["approve_allowed"] is False
        with pytest.raises(RewriteOutputBlocked):
            RewriteOutputService(session).approve(1, activate_candidate=True)
        with pytest.raises(CandidateBlocked):
            PublicationPlanningService(session).register_candidate(1, KEY, priority=1)
    photos = Photos()
    with pytest.raises(PermissionError):
        acquisition(source_store, photos).acquire(
            1, license_code="PERMISSION", attribution="Synthetic owner"
        )
    assert photos.calls == []


def test_deletion_fences_final_pre_send_guard(source_store):
    seed_plan(source_store)
    sender = Publisher(change=lambda: record(source_store[0]))
    execution = DurablePublicationRunner(*source_store, publisher=sender, clock=lambda: NOW)
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert sender.calls == []


def test_already_observed_exact_receipt_remains_delivery_truth_after_deletion(
    source_store, monkeypatch
):
    seed_plan(source_store)
    sender = Publisher()
    execution = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)

    def crash(*_args):
        raise SystemExit("Synthetic crash after persisted receipt")

    monkeypatch.setattr(execution, "_complete", crash)
    with pytest.raises(SystemExit):
        execution.run_next(now=NOW)
    record(source_store[0])
    late = NOW + timedelta(seconds=61)
    restarted = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: late
    )
    assert restarted.run_next(now=late) == "RECONCILED"
    assert restarted.run_next(now=late) == "IDLE"
    assert len(sender.calls) == 1
    _snapshot, observed = PublicationObservations(source_store[0], cipher=CIPHER).read(job_id)
    assert observed.receipt.message_id == 101


def test_real_review_http_after_deletion_never_approves_or_creates_jobs(source_store, monkeypatch):
    record(source_store[0])
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    with TestClient(app) as client:
        response = client.get("/api/telegram/rewrite-outputs?output_channel_id=1")
        assert response.status_code == 200
        assert response.json()["items"][0]["approve_allowed"] is False
        assert client.post("/api/telegram/rewrite-outputs/1:approve", json={}).status_code == 409
    with source_store[0]() as session:
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1
        assert session.scalar(select(models.PublicationJobModel)) is None


def test_chunk_outbox_failure_rolls_back_every_tombstone(source_store):
    with source_store[0].begin() as session:
        session.execute(
            text(
                "CREATE TRIGGER synthetic_deletion_fault BEFORE INSERT ON outbox_events WHEN NEW.event_type='source.deleted' BEGIN SELECT RAISE(ABORT, 'synthetic storage failure'); END"
            )
        )
    with pytest.raises(IntegrityError):
        record(source_store[0], ids=(20, 21))
    with source_store[0]() as session:
        assert session.scalar(select(models.SourceDeletionModel)) is None
        assert source_is_current(session, KEY) is True


def test_lost_owner_cannot_record_even_unknown_deletions(source_store):
    chunk = TelegramChannelDifference("1", CHANNEL, 10, 11, True, 0, (), (20, 99))
    with pytest.raises(SourceDeletionClaimLost):
        SourceDeletionService(source_store[0]).record(
            chunk, observed_at=NOW, transaction_guard=lambda _session: False
        )
    with source_store[0]() as session:
        assert session.scalar(select(models.SourceDeletionModel)) is None


@pytest.mark.parametrize("account", ["01", "0", "-1", "true", "١", "2147483648"])
def test_invalid_local_account_binding_cannot_record_deletion(source_store, account):
    chunk = TelegramChannelDifference(account, CHANNEL, 10, 11, True, 0, (), (20,))
    with pytest.raises(ValueError):
        SourceDeletionService(source_store[0]).record(chunk, observed_at=NOW)
    with source_store[0]() as session:
        assert session.scalar(select(models.SourceDeletionModel)) is None


def test_naive_observation_cannot_write_deletion(source_store):
    chunk = TelegramChannelDifference("1", CHANNEL, 10, 11, True, 0, (), (20,))
    with pytest.raises(ValueError):
        SourceDeletionService(source_store[0]).record(chunk, observed_at=NOW.replace(tzinfo=None))
    with source_store[0]() as session:
        assert session.scalar(select(models.SourceDeletionModel)) is None
