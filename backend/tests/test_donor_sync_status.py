from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_channel_baseline import healthy
from test_donor_ingestion_runner import NOW
from test_donor_ingestion_runner import donor_store as _donor_store

from newsflow.app import app
from newsflow.persistence import models
from newsflow.services.channel_sync_enforcement import ChannelSyncEnforcement

donor_store = _donor_store


@pytest.mark.parametrize(
    "fixture,want,blocked",
    [
        ("new", "BASELINE_REQUIRED", True),
        ("legacy", "LEGACY_SYNC_REQUIRED", True),
        ("idle", "READY", False),
        ("active", "SYNC_IN_PROGRESS", True),
        ("expired", "RECOVERY_DUE", True),
        ("retry", "WAIT_RETRY", True),
        ("due", "RECOVERY_DUE", True),
        ("gap", "GAP_UNRESOLVED", True),
        ("foreign", "INVALID_BASELINE", True),
        ("invalid_account", "ACCOUNT_UNAVAILABLE", True),
        ("disabled", "NOT_ENFORCED", False),
    ],
)
def test_sync_status_projects_persisted_truth_without_rpc_or_secret(
    donor_store, fixture, want, blocked
):
    from newsflow.services.donor_sync_status import DonorSyncStatusReader

    healthy(donor_store)
    if fixture != "disabled":
        ChannelSyncEnforcement(donor_store).enable(now=NOW)
    if fixture == "legacy":
        with donor_store.begin() as session:
            session.add(
                models.DonorIngestionCursorModel(
                    donor_channel_id=1, last_message_id=10, available_at=NOW
                )
            )
    if fixture not in {"new", "legacy", "disabled"}:
        with donor_store.begin() as session:
            cursor = models.ChannelDifferenceCursorModel(
                donor_channel_id=1,
                telegram_account_id=1,
                telegram_user_id=1001,
                telegram_channel_id=-1001234567890,
                pts=10,
                available_at=NOW,
            )
            session.add(cursor)
            if fixture in {"active", "expired"}:
                cursor.claim_token = "private-claim-token"
                cursor.lease_expires_at = NOW + timedelta(seconds=60 if fixture == "active" else -1)
            elif fixture in {"retry", "due"}:
                cursor.last_error_code = "RETRY_PROVIDER"
                cursor.available_at = NOW + timedelta(seconds=30 if fixture == "retry" else -1)
            elif fixture == "gap":
                cursor.last_error_code = "GAP_UNRESOLVED"
            elif fixture == "foreign":
                cursor.telegram_user_id = 7777
            elif fixture == "invalid_account":
                session.get(models.TelegramAccount, 1).health_status = "SESSION_INVALID"
    with donor_store() as session:
        before = list(session.scalars(select(models.OutboxEventModel.id)))
        status = DonorSyncStatusReader(session).read(1, now=NOW)
        assert status["state"] == want
        assert status["source_processing_blocked"] is blocked
        assert status["network_checked"] is False
        assert status["donor_id"] == 1
        assert not {"claim_token", "encrypted_session", "master_key", "api_hash"} & status.keys()
        assert "private-claim-token" not in str(status)
        assert list(session.scalars(select(models.OutboxEventModel.id))) == before
        assert not session.dirty and not session.new


def test_real_sync_status_api_is_read_only_and_not_a_live_connection_claim(
    donor_store, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", str(donor_store.kw["bind"].url))
    with TestClient(app) as client:
        response = client.get("/api/telegram/donors/1/sync-status")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json()["network_checked"] is False
        assert client.post("/api/telegram/donors/1/sync-status", json={}).status_code == 405
        assert client.get("/api/telegram/donors/999/sync-status").status_code == 404


@pytest.mark.parametrize("evidence", ["poll_zero", "source", "tombstone", "outbox"])
def test_legacy_evidence_survives_reopen_and_status_never_creates_baseline(donor_store, evidence):
    from newsflow.services.donor_sync_status import DonorSyncStatusReader

    healthy(donor_store)
    ChannelSyncEnforcement(donor_store).enable(now=NOW)
    with donor_store.begin() as session:
        if evidence == "poll_zero":
            row = models.DonorIngestionCursorModel(
                donor_channel_id=1, last_message_id=0, available_at=NOW
            )
        elif evidence == "source":
            row = models.IncomingPostModel(
                telegram_account_id="1",
                donor_channel_id="-1001234567890",
                telegram_message_id=2,
                state="RECEIVED",
            )
        elif evidence == "tombstone":
            row = models.SourceDeletionModel(
                telegram_account_id="1",
                donor_channel_id="-1001234567890",
                telegram_message_id=2,
                observed_at=NOW,
                latest_pts=10,
            )
        else:
            row = models.OutboxEventModel(
                event_type="channel.baseline_recorded",
                aggregate_key="1:1:-1001234567890",
                idempotency_key="channel.baseline_recorded:1:1:-1001234567890",
                created_at=NOW,
            )
        session.add(row)
    reopened = create_engine(str(donor_store.kw["bind"].url))
    try:
        with sessionmaker(reopened)() as session:
            status = DonorSyncStatusReader(session).read(1, now=NOW)
            assert status["state"] == "LEGACY_SYNC_REQUIRED"
            assert status["pts"] is None
            assert status["source_processing_blocked"] is True
            assert session.get(models.ChannelDifferenceCursorModel, 1) is None
            assert session.scalar(select(models.RewriteJobModel)) is None
            assert not session.dirty and not session.new
    finally:
        reopened.dispose()


def test_reader_reloads_current_policy_health_and_lease_without_a_live_check(donor_store):
    from newsflow.services.donor_sync_status import DonorSyncStatusReader

    healthy(donor_store)
    ChannelSyncEnforcement(donor_store).enable(now=NOW)
    with donor_store.begin() as session:
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
    with donor_store() as session:
        reader = DonorSyncStatusReader(session)
        assert reader.read(1, now=NOW)["state"] == "READY"
        session.commit()
        with donor_store.begin() as writer:
            owner = writer.get(models.TelegramAccount, 1)
            owner.health_status = "COOLDOWN"
            owner.cooldown_until = NOW + timedelta(seconds=60)
        cooled = reader.read(1, now=NOW)
        assert cooled["state"] == "COOLDOWN"
        assert cooled["source_processing_blocked"] is True
        assert cooled["retry_at"] == "2030-01-01T00:01:00+00:00"
        session.commit()
        with donor_store.begin() as writer:
            writer.get(models.TelegramAccount, 1).encrypted_session = ""
        assert reader.read(1, now=NOW)["state"] == "ACCOUNT_UNAVAILABLE"


def test_status_storage_error_returns_redacted_503_not_empty_success(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'unmigrated.db'}")
    with TestClient(app) as client:
        response = client.get("/api/telegram/donors/1/sync-status")
        assert response.status_code == 503
        assert response.json() == {
            "detail": "Durable database is unavailable or requires migrations"
        }
        assert "SELECT" not in response.text and "unmigrated.db" not in response.text
