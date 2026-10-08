import json
from datetime import timedelta

import pytest
from sqlalchemy import select
from test_configured_text_publication import CIPHER
from test_publication_preflight import seed_plan
from test_publication_runner import Publisher
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store

from newsflow.persistence import models
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_publication_runner import DurablePublicationRunner
from newsflow.services.publication_request_snapshot import PublicationRequestSnapshots

source_store = _source_store


def snapshot_reader(factory, cipher=CIPHER):
    return PublicationRequestSnapshots(factory, cipher=cipher)


def test_worker_style_enqueue_preserves_encrypted_exact_request_across_restart(source_store):
    seed_plan(source_store)
    execution = DurablePublicationRunner(
        *source_store, publisher=Publisher(), cipher=CIPHER, clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)
    first = snapshot_reader(source_store[0]).read(job_id)
    assert (
        first.envelope.text == "Photo caption"
        and first.envelope.telegram_channel_id == -1001234567891
    )
    with source_store[0]() as session:
        row = session.get(models.PublicationRequestSnapshotModel, job_id)
        assert "Photo caption" not in row.encrypted_envelope
        assert CIPHER.decrypt(row.encrypted_envelope).startswith("{")
        assert first.request_nonce == session.get(models.PublicationJobModel, job_id).request_nonce
    assert snapshot_reader(source_store[0]).read(job_id) == first
    assert execution.enqueue(1, now=NOW) == job_id


def test_original_request_remains_readable_after_reject_and_draft_change_without_send(source_store):
    seed_plan(source_store)
    sender = Publisher(failure=TimeoutError("synthetic lost response"))
    execution = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)
    original = snapshot_reader(source_store[0]).read(job_id)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.scalar(select(models.RewriteOutputModel)).rewritten_text = "Changed draft"
    restored = snapshot_reader(source_store[0]).read(job_id)
    assert restored == original and restored.envelope.text == "Photo caption"
    late = NOW + timedelta(minutes=2)
    assert (
        DurablePublicationRunner(
            *source_store, publisher=sender, cipher=CIPHER, clock=lambda: late
        ).run_next(now=late)
        == "IDLE"
    )
    assert len(sender.calls) == 1


def test_legacy_intent_is_not_backfilled_from_mutable_current_data(source_store):
    seed_plan(source_store)
    legacy = DurablePublicationRunner(*source_store, publisher=None, clock=lambda: NOW)
    job_id = legacy.enqueue(1, now=NOW)
    with pytest.raises(PermissionError):
        snapshot_reader(source_store[0]).read(job_id)
    sender = Publisher()
    execution = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: NOW
    )
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert not sender.calls


@pytest.mark.parametrize("mutation", ["encrypted", "nonce", "digest"])
def test_corrupted_or_rebound_request_snapshot_fails_closed_before_provider(source_store, mutation):
    seed_plan(source_store)
    sender = Publisher()
    execution = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)
    with source_store[0].begin() as session:
        if mutation == "encrypted":
            session.get(
                models.PublicationRequestSnapshotModel, job_id
            ).encrypted_envelope = "invalid"
        elif mutation == "nonce":
            session.get(models.PublicationJobModel, job_id).request_nonce += 1
        else:
            session.get(models.PublicationRequestSnapshotModel, job_id).binding_sha256 = "b" * 64
    with pytest.raises(PermissionError):
        snapshot_reader(source_store[0]).read(job_id)
    assert execution.run_next(now=NOW) == "BLOCKED" and not sender.calls


def test_changed_master_key_never_replaces_snapshot_or_contacts_provider(source_store):
    seed_plan(source_store)
    execution = DurablePublicationRunner(*source_store, cipher=CIPHER, clock=lambda: NOW)
    job_id = execution.enqueue(1, now=NOW)
    original = snapshot_reader(source_store[0]).read(job_id)
    other = SessionCipher("AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=")
    with pytest.raises(PermissionError, match="SNAPSHOT_UNAVAILABLE"):
        snapshot_reader(source_store[0], other).read(job_id)
    sender = Publisher()
    assert (
        DurablePublicationRunner(
            *source_store, publisher=sender, cipher=other, clock=lambda: NOW
        ).run_next(now=NOW)
        == "BLOCKED"
    )
    assert not sender.calls
    assert snapshot_reader(source_store[0]).read(job_id) == original


@pytest.mark.parametrize(
    "change", ["version", "unknown", "boolean", "duplicate", "naive", "expiry", "surrogate"]
)
def test_decrypted_snapshot_schema_is_fail_closed(source_store, change):
    seed_plan(source_store)
    sender = Publisher()
    execution = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)
    with source_store[0].begin() as session:
        row = session.get(models.PublicationRequestSnapshotModel, job_id)
        value = json.loads(CIPHER.decrypt(row.encrypted_envelope))
        if change == "version":
            value["version"] = True
        elif change == "unknown":
            value["envelope"]["access_hash"] = "must-not-be-accepted"
        elif change == "boolean":
            value["envelope"]["user_id"] = True
        elif change == "naive":
            value["envelope"]["scheduled_for"] = "2026-10-08T00:00:00"
        elif change == "expiry":
            value["envelope"]["expires_at"] = "2026-10-08T07:00:00+00:00"
        elif change == "surrogate":
            value["envelope"]["text"] = "\ud800"
        payload = json.dumps(value)
        if change == "duplicate":
            payload = '{"version":2,' + payload[1:]
        row.encrypted_envelope = CIPHER.encrypt(payload)
    with pytest.raises(PermissionError):
        snapshot_reader(source_store[0]).read(job_id)
    assert execution.run_next(now=NOW) == "BLOCKED" and not sender.calls


def test_snapshot_encryption_failure_rolls_back_entire_intent_and_outbox(source_store):
    seed_plan(source_store)

    class UnavailableCipher:
        def encrypt(self, _payload):
            raise RuntimeError("synthetic storage cipher failure")

    execution = DurablePublicationRunner(
        *source_store, cipher=UnavailableCipher(), clock=lambda: NOW
    )
    with pytest.raises(RuntimeError):
        execution.enqueue(1, now=NOW)
    with source_store[0]() as session:
        assert not session.scalars(select(models.PublicationJobModel)).all()
        assert not session.scalars(select(models.PublicationRequestSnapshotModel)).all()
        assert not session.scalars(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.event_type == "publication.queued"
            )
        ).all()


def test_editorial_reject_creates_no_request_snapshot_or_publication_intent(source_store):
    seed_plan(source_store)
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    execution = DurablePublicationRunner(*source_store, cipher=CIPHER, clock=lambda: NOW)
    with pytest.raises(PermissionError):
        execution.enqueue(1, now=NOW)
    with source_store[0]() as session:
        assert not session.scalars(select(models.PublicationJobModel)).all()
        assert not session.scalars(select(models.PublicationRequestSnapshotModel)).all()
