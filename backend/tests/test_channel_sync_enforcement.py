from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_source_photo_acquisition import KEY, NOW
from test_source_photo_acquisition import source_store as _source_store
from test_source_rights_configuration import mapped_store

from newsflow.domain.editorial import EditorialGate
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.persistence import models
from newsflow.services.channel_sync_enforcement import ChannelSyncEnforcement
from newsflow.services.source_revisions import source_is_current

source_store = _source_store


def enable(factory):
    ChannelSyncEnforcement(factory).enable(now=NOW)


def baseline(factory):
    mapped_store(factory)
    with factory.begin() as session:
        session.add(
            models.ChannelDifferenceCursorModel(
                donor_channel_id=1,
                telegram_account_id=1,
                telegram_user_id=1001,
                telegram_channel_id=-1001234567890,
                pts=10,
                available_at=NOW,
            )
        )


def test_persistent_enforcement_blocks_legacy_source_after_reopen_and_flag_off(
    source_store, monkeypatch
):
    factory, _ = source_store
    enable(factory)
    enable(factory)
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED", "0")
    reopened = create_engine(str(factory.kw["bind"].url))
    try:
        with sessionmaker(reopened)() as session:
            assert source_is_current(session, KEY) is False
            assert session.get(models.ContentRevisionModel, 1).source_text == "Photo caption"
            decision = session.scalar(select(models.EditorialDecisionModel))
            assert decision.status == "PASS" and decision.rewrite_allowed is True
            assert (
                DurableEditorialService(session, EditorialGate()).create_rewrite_job(decision)
                is None
            )
            rows = session.scalars(
                select(models.OutboxEventModel).where(
                    models.OutboxEventModel.event_type == "channel.sync_enforcement_enabled"
                )
            ).all()
            assert len(rows) == 1
    finally:
        reopened.dispose()


@pytest.mark.parametrize("state", ["missing", "error", "nonfinal", "active", "invalid_account"])
def test_enforced_source_needs_current_complete_idle_healthy_baseline(source_store, state):
    factory, _ = source_store
    if state != "missing":
        baseline(factory)
        with factory.begin() as session:
            cursor = session.get(models.ChannelDifferenceCursorModel, 1)
            if state == "error":
                cursor.last_error_code = "RETRY_PROVIDER"
            elif state == "nonfinal":
                cursor.last_error_code = "DIFFERENCE_INCOMPLETE"
            elif state == "active":
                cursor.claim_token, cursor.lease_expires_at = (
                    "synthetic",
                    NOW + timedelta(seconds=60),
                )
            else:
                session.get(models.TelegramAccount, 1).health_status = "SESSION_INVALID"
    enable(factory)
    with factory() as session:
        assert source_is_current(session, KEY) is False


def test_verified_bound_baseline_is_current_under_enforcement(source_store):
    factory, _ = source_store
    baseline(factory)
    enable(factory)
    with factory() as session:
        assert source_is_current(session, KEY) is True


def test_enforcement_denies_prototype_key_without_persisted_source(source_store):
    factory, _ = source_store
    enable(factory)
    with factory() as session:
        service = DurableEditorialService(session, EditorialGate())
        decision = service.evaluate("unbound-prototype-key", (), "neutral", "neutral")
        assert service.create_rewrite_job(decision) is None


@pytest.mark.parametrize("state", ["DISPATCHED", "RETRY", "RUNNING"])
def test_unscanned_legacy_rewrite_is_blocked_before_ai_provider(source_store, state):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    factory, _ = source_store
    with factory.begin() as session:
        job = session.get(models.RewriteJobModel, 1)
        job.state, job.available_at = state, NOW
        job.claim_token, job.lease_expires_at = "expired", NOW - timedelta(seconds=1)
        session.get(models.PublicationCandidateModel, 1).state = "AWAITING_REWRITE"
        session.delete(session.scalar(select(models.RewriteOutputModel)))
    enable(factory)

    def forbidden(_channel):
        raise AssertionError("Unscanned legacy donor reached rewrite provider")

    assert (
        DurableRewriteRunner(factory, provider_for_channel=forbidden).run_next(now=NOW)
        == "SUPERSEDED"
    )
    with factory() as session:
        assert session.scalar(select(models.RewriteOutputModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None


def test_real_api_cannot_approve_legacy_source_after_enforcement(source_store, monkeypatch):
    from fastapi.testclient import TestClient

    from newsflow.app import app

    enable(source_store[0])
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    with TestClient(app) as client:
        item = client.get("/api/telegram/incoming-posts").json()["items"][0]
        assert item["state"] == "SOURCE_SYNC_REQUIRED" and item["editorial_status"] == "PASS"
        assert item["rewrite_allowed"] is False
        assert client.post("/api/telegram/rewrite-outputs/1:approve", json={}).status_code == 409
