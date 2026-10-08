from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_configured_text_publication import CIPHER
from test_publication_preflight import seed_plan
from test_publication_runner import Publisher
from test_source_photo_acquisition import CHANNEL, KEY, NOW, Photos, acquisition
from test_source_photo_acquisition import source_store as _source_store
from test_source_rights_configuration import mapped_store

from newsflow.app import app
from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.editorial import EditorialGate
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.persistence import models
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.durable_publication_runner import DurablePublicationRunner
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.publication_planning import CandidateBlocked, PublicationPlanningService
from newsflow.services.rewrite_outputs import RewriteOutputBlocked, RewriteOutputService
from newsflow.services.source_revisions import source_is_current

source_store = _source_store


def mark_gap(factory):
    with factory() as session:
        donor_id = session.scalar(select(models.DonorChannel.id))
    if donor_id is None:
        mapped_store(factory)
        donor_id = 1
    with factory.begin() as session:
        session.add(
            models.ChannelDifferenceCursorModel(
                donor_channel_id=donor_id,
                telegram_account_id=1,
                telegram_user_id=1001,
                telegram_channel_id=int(CHANNEL),
                pts=10,
                available_at=NOW,
                last_error_code="GAP_UNRESOLVED",
            )
        )


def test_sync_gap_freshness_is_reloaded_and_history_is_not_deleted(source_store):
    factory, _ = source_store
    with factory() as session:
        assert source_is_current(session, KEY) is True
        mark_gap(factory)
        assert source_is_current(session, KEY) is False
        assert session.get(models.ContentRevisionModel, 1).source_text == "Photo caption"
        assert session.scalar(select(models.EditorialDecisionModel)).status == "PASS"
        assert session.get(models.RewriteJobModel, 1).state == "SUCCEEDED"


def test_cached_pass_cannot_fanout_new_rewrite_into_unresolved_gap(source_store):
    mark_gap(source_store[0])
    with source_store[0]() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert (
            DurableEditorialService(session, EditorialGate()).create_rewrite_job(
                decision, output_channel_id=None
            )
            is None
        )
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1


@pytest.mark.parametrize("state", ["DISPATCHED", "RETRY", "RUNNING"])
def test_gap_stale_rewrite_creates_no_provider_output_or_usage(source_store, state):
    with source_store[0].begin() as session:
        job = session.get(models.RewriteJobModel, 1)
        job.state, job.available_at = state, NOW
        job.claim_token, job.lease_expires_at = "expired-owner", NOW - timedelta(seconds=1)
        session.get(models.PublicationCandidateModel, 1).state = "AWAITING_REWRITE"
        session.delete(session.scalar(select(models.RewriteOutputModel)))
    mark_gap(source_store[0])

    def forbidden(_channel):
        raise AssertionError("Unresolved gap reached AI provider")

    execution = DurableRewriteRunner(source_store[0], provider_for_channel=forbidden)
    assert execution.run_next(now=NOW) == "SUPERSEDED"
    with source_store[0]() as session:
        assert session.scalar(select(models.RewriteOutputModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None


def test_gap_blocks_manual_review_planning_and_download(source_store):
    mark_gap(source_store[0])
    with source_store[0]() as session:
        assert RewriteOutputService(session).list_outputs()[0]["approve_allowed"] is False
        with pytest.raises(RewriteOutputBlocked):
            RewriteOutputService(session).approve(1, activate_candidate=True)
        with pytest.raises(CandidateBlocked):
            PublicationPlanningService(session).register_candidate(1, KEY, priority=1)
    photos = Photos()
    with pytest.raises(PermissionError):
        acquisition(source_store, photos).acquire(1, license_code="PERMISSION", attribution="Owner")
    assert photos.calls == []


def test_gap_blocks_stale_publication_without_send(source_store):
    seed_plan(source_store)
    publisher = Publisher()
    execution = DurablePublicationRunner(*source_store, publisher=publisher, clock=lambda: NOW)
    execution.enqueue(1, now=NOW)
    mark_gap(source_store[0])
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert publisher.calls == []


def test_gap_observed_at_final_send_guard_prevents_send(source_store):
    seed_plan(source_store)
    publisher = Publisher(change=lambda: mark_gap(source_store[0]))
    execution = DurablePublicationRunner(*source_store, publisher=publisher, clock=lambda: NOW)
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert publisher.calls == []


@pytest.mark.parametrize("change", ["user", "donor_channel", "cursor_channel"])
def test_foreign_persisted_baseline_does_not_assert_current_source(source_store, change):
    mark_gap(source_store[0])
    with source_store[0].begin() as session:
        cursor = session.get(models.ChannelDifferenceCursorModel, 1)
        cursor.last_error_code = None
        if change == "user":
            cursor.telegram_user_id = 1002
        elif change == "donor_channel":
            session.get(models.DonorChannel, 1).telegram_channel_id = -1002222222222
        else:
            cursor.telegram_channel_id = -1002222222222
    with source_store[0]() as session:
        assert source_is_current(session, KEY) is False


def test_exact_observed_receipt_is_reconciled_after_gap_without_resend(source_store, monkeypatch):
    seed_plan(source_store)
    publisher = Publisher()
    execution = DurablePublicationRunner(
        *source_store, publisher=publisher, cipher=CIPHER, clock=lambda: NOW
    )
    execution.enqueue(1, now=NOW)

    def crash(*_args):
        raise SystemExit("Synthetic crash after persisted receipt")

    monkeypatch.setattr(execution, "_complete", crash)
    with pytest.raises(SystemExit):
        execution.run_next(now=NOW)
    mark_gap(source_store[0])
    late = NOW + timedelta(seconds=61)
    restarted = DurablePublicationRunner(
        *source_store, publisher=publisher, cipher=CIPHER, clock=lambda: late
    )
    assert restarted.run_next(now=late) == "RECONCILED"
    assert restarted.run_next(now=late) == "IDLE" and len(publisher.calls) == 1


def test_real_review_http_cannot_bypass_gap(source_store, monkeypatch):
    mark_gap(source_store[0])
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    with TestClient(app) as client:
        response = client.get("/api/telegram/rewrite-outputs?output_channel_id=1")
        assert response.status_code == 200
        assert response.json()["items"][0]["approve_allowed"] is False
        assert client.post("/api/telegram/rewrite-outputs/1:approve", json={}).status_code == 409


def test_gap_ingress_retains_observation_without_classifier_fingerprint_or_new_jobs(source_store):
    mark_gap(source_store[0])

    class ForbiddenGate(EditorialGate):
        def evaluate(self, **_kwargs):
            raise AssertionError("Known gap reached classifier")

    event = TelegramMessage("1", CHANNEL, 99, "Unverified gap observation", source_updated_at=NOW)
    for _ in range(2):
        with source_store[0]() as session:
            result = DurableIngestionWorkflow(
                session, configured_mapping_id=1, editorial_gate=ForbiddenGate()
            ).ingest(event, observed_at=NOW, sentiment="neutral", framing="neutral")
            assert result.status == "SOURCE_SYNC_REQUIRED"
    with source_store[0]() as session:
        assert len(session.scalars(select(models.IncomingPostModel)).all()) == 2
        assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 2
        assert session.scalar(select(models.MappingContentFingerprintModel)) is None
        assert len(session.scalars(select(models.EditorialDecisionModel)).all()) == 1
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1


def test_readonly_inbox_projects_gap_without_fabricating_editorial_reject(
    source_store, monkeypatch
):
    mark_gap(source_store[0])
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    with TestClient(app) as client:
        item = client.get("/api/telegram/incoming-posts").json()["items"][0]
        assert item["state"] == "SOURCE_SYNC_REQUIRED" and item["rewrite_allowed"] is False
        assert item["editorial_status"] == "PASS" and item["source_deleted"] is False
    with source_store[0]() as session:
        assert session.get(models.IncomingPostModel, 1).state == "RECEIVED"
