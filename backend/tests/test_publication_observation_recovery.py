from datetime import timedelta

import pytest
from sqlalchemy import select, text
from test_configured_text_publication import CIPHER
from test_publication_preflight import seed_plan
from test_publication_runner import Publisher
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store

from newsflow import worker
from newsflow.persistence import models
from newsflow.services.durable_publication_runner import DurablePublicationRunner
from newsflow.services.publication_observations import PublicationObservations, PublicationReceipt

source_store = _source_store


def runner(store, sender, now=NOW):
    return DurablePublicationRunner(*store, publisher=sender, cipher=CIPHER, clock=lambda: now)


def interrupt_after_receipt(execution, monkeypatch):
    def process_exit(*_args):
        raise SystemExit("synthetic crash after durable acknowledgement observation")

    monkeypatch.setattr(execution, "_complete", process_exit)


def test_restart_reconciles_persisted_exact_ack_without_second_send(source_store, monkeypatch):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    interrupt_after_receipt(execution, monkeypatch)
    with pytest.raises(SystemExit):
        execution.run_next(now=NOW)
    with source_store[0]() as session:
        assert session.get(models.PublicationJobModel, job_id).state == "SENDING"
    late = NOW + timedelta(seconds=61)
    assert runner(source_store, sender, late).run_next(now=late) == "RECONCILED"
    assert len(sender.calls) == 1


@pytest.mark.parametrize("failure_point", ["observation", "completion"])
def test_actual_storage_failure_after_send_never_resends(source_store, failure_point):
    seed_plan(source_store)
    with source_store[0].begin() as session:
        if failure_point == "observation":
            session.execute(
                text(
                    "CREATE TRIGGER synthetic_storage_fault BEFORE INSERT ON publication_delivery_observations BEGIN SELECT RAISE(ABORT, 'synthetic disk failure'); END"
                )
            )
        else:
            session.execute(
                text(
                    "CREATE TRIGGER synthetic_storage_fault BEFORE INSERT ON outbox_events WHEN NEW.event_type='publication.delivered' BEGIN SELECT RAISE(ABORT, 'synthetic disk failure'); END"
                )
            )
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    with source_store[0].begin() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.sent_message_id is None and job.attempts == 1
        observation = session.get(models.PublicationDeliveryObservationModel, job_id)
        assert (observation is not None) == (failure_point == "completion")
        session.execute(text("DROP TRIGGER synthetic_storage_fault"))
    late = NOW + timedelta(seconds=61)
    outcome = runner(source_store, sender, late).run_next(now=late)
    assert outcome == ("RECONCILED" if failure_point == "completion" else "IDLE")
    assert len(sender.calls) == 1
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == (
            "SUCCEEDED" if failure_point == "completion" else "NEEDS_RECONCILIATION"
        )
        assert job.sent_message_id == (101 if failure_point == "completion" else None)
        assert job.attempts == 1
        assert len(
            session.scalars(
                select(models.OutboxEventModel).where(
                    models.OutboxEventModel.event_type == "publication.delivered"
                )
            ).all()
        ) == (1 if failure_point == "completion" else 0)
    assert runner(source_store, sender, late).run_next(now=late) == "IDLE"


def test_historical_ack_after_reject_and_edit_does_not_rewrite_or_resend(source_store, monkeypatch):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    interrupt_after_receipt(execution, monkeypatch)
    with pytest.raises(SystemExit):
        execution.run_next(now=NOW)
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.scalar(select(models.RewriteOutputModel)).rewritten_text = "Edited later"
        session.get(models.PublicationJobModel, job_id).state = "NEEDS_RECONCILIATION"
        job = session.get(models.PublicationJobModel, job_id)
        job.claim_token, job.lease_expires_at = None, None
        job.last_error_code = "PUBLICATION_SEND_OUTCOME_UNKNOWN"
    late = NOW + timedelta(seconds=61)
    assert runner(source_store, sender, late).run_next(now=late) == "RECONCILED"
    assert len(sender.calls) == 1
    with source_store[0]() as session:
        assert session.scalar(select(models.EditorialDecisionModel)).rewrite_allowed is False
        assert session.get(models.PublicationJobModel, job_id).sent_message_id == 101


def test_lost_response_without_trusted_observation_stays_ambiguous(source_store):
    seed_plan(source_store)
    sender = Publisher(failure=TimeoutError("synthetic response loss"))
    execution = runner(source_store, sender)
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    late = NOW + timedelta(seconds=61)
    assert runner(source_store, sender, late).run_next(now=late) == "IDLE"
    assert len(sender.calls) == 1
    with source_store[0]() as session:
        assert not session.scalars(select(models.PublicationDeliveryObservationModel)).all()


@pytest.mark.parametrize("change", ["ciphertext", "nonce", "candidate"])
def test_corrupted_or_rebound_observation_never_claims_success_or_sends(
    source_store, monkeypatch, change
):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    interrupt_after_receipt(execution, monkeypatch)
    with pytest.raises(SystemExit):
        execution.run_next(now=NOW)
    with source_store[0].begin() as session:
        if change == "ciphertext":
            session.get(
                models.PublicationDeliveryObservationModel, job_id
            ).encrypted_receipt = "invalid"
        elif change == "nonce":
            session.get(models.PublicationJobModel, job_id).request_nonce += 1
        else:
            session.get(models.PlannedPublicationModel, 1).candidate_id = 999
    late = NOW + timedelta(seconds=61)
    assert runner(source_store, sender, late).run_next(now=late) == "IDLE"
    assert len(sender.calls) == 1
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "NEEDS_RECONCILIATION" and job.sent_message_id is None


def test_tick_advances_recovery_cursor_past_bounded_corrupt_history(source_store, monkeypatch):
    seed_plan(source_store)
    with source_store[0].begin() as session:
        # Synthetic damaged/legacy history has no request snapshot. It must not
        # monopolize every bounded restart-recovery batch.
        for job_id in range(1, 17):
            session.add(
                models.PublicationJobModel(
                    id=job_id,
                    planned_id=100 + job_id,
                    telegram_account_id=1,
                    telegram_channel_id=-1001234567891,
                    request_nonce=job_id,
                    binding_sha256="a" * 64,
                    state="NEEDS_RECONCILIATION",
                    attempts=1,
                    available_at=NOW,
                    last_error_code="PUBLICATION_SEND_OUTCOME_UNKNOWN",
                )
            )
        session.flush()
        for job_id in range(1, 17):
            session.add(
                models.PublicationDeliveryObservationModel(
                    job_id=job_id, encrypted_receipt="invalid"
                )
            )
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    assert job_id == 17
    interrupt_after_receipt(execution, monkeypatch)
    with pytest.raises(SystemExit):
        execution.run_next(now=NOW)
    late = NOW + timedelta(seconds=61)
    kwargs = {
        "enabled": True,
        "cipher": CIPHER,
        "media_root": source_store[1],
        "now": late,
        "publisher": sender,
        "clock": lambda: late,
    }
    first = worker.run_publication_tick(source_store[0], **kwargs)
    assert first.outcome == "IDLE" and first.recovery_cursor == 16
    second = worker.run_publication_tick(
        source_store[0], recovery_cursor=first.recovery_cursor, **kwargs
    )
    assert second.outcome == "RECONCILED" and second.recovery_cursor == 17
    assert len(sender.calls) == 1


def test_active_sender_lease_is_not_reconciled_by_second_worker(source_store, monkeypatch):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    execution.enqueue(1, now=NOW)
    interrupt_after_receipt(execution, monkeypatch)
    with pytest.raises(SystemExit):
        execution.run_next(now=NOW)
    early = NOW + timedelta(seconds=59)
    assert runner(source_store, sender, early).run_next(now=early) == "IDLE"
    assert len(sender.calls) == 1


def test_conflicting_trusted_receipts_preserve_evidence_and_quarantine(source_store, monkeypatch):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    claim = execution.claim_next(now=NOW)
    interrupt_after_receipt(execution, monkeypatch)
    with pytest.raises(SystemExit):
        execution.execute(claim)
    observations = PublicationObservations(source_store[0], cipher=CIPHER)
    snapshot, observed = observations.read(job_id)
    observations.record(claim, observed.receipt, snapshot.envelope, snapshot.request_nonce)
    with source_store[0]() as session:
        original = session.get(models.PublicationDeliveryObservationModel, job_id).encrypted_receipt
    conflict = PublicationReceipt(1, -1001234567891, snapshot.request_nonce, 102)
    with pytest.raises(PermissionError):
        observations.record(claim, conflict, snapshot.envelope, snapshot.request_nonce)
    with source_store[0]() as session:
        assert (
            session.get(models.PublicationDeliveryObservationModel, job_id).encrypted_receipt
            == original
        )
        job = session.get(models.PublicationJobModel, job_id)
        assert (
            job.state == "NEEDS_RECONCILIATION"
            and job.last_error_code == "PUBLICATION_OBSERVATION_CONFLICT"
        )
    late = NOW + timedelta(seconds=61)
    assert runner(source_store, sender, late).run_next(now=late) == "IDLE"
    assert len(sender.calls) == 1
