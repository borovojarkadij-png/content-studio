from datetime import timedelta

import pytest
from sqlalchemy import select
from test_publication_preflight import seed_plan
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store

from newsflow.persistence import models
from newsflow.services.publication import PublicationBlocked

source_store = _source_store


class Publisher:
    def __init__(self, *, failure=None, change=None):
        self.calls, self.failure, self.change = [], failure, change

    def publish(self, envelope, nonce, *, execution_guard):
        from newsflow.services.durable_publication_runner import PublicationReceipt

        if self.change:
            self.change()
        execution_guard()
        self.calls.append((envelope, nonce))
        if self.failure:
            raise self.failure
        return PublicationReceipt(envelope.account_id, envelope.telegram_channel_id, nonce, 101)


def runner(store, publisher, clock=lambda: NOW):
    from newsflow.services.durable_publication_runner import DurablePublicationRunner

    return DurablePublicationRunner(store[0], store[1], publisher=publisher, clock=clock)


def test_publication_job_is_idempotent_and_completion_is_durable(source_store):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.enqueue(1, now=NOW) == job_id
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    assert runner(source_store, sender).run_next(now=NOW) == "IDLE"
    assert len(sender.calls) == 1 and sender.calls[0][1] > 0
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "SUCCEEDED" and job.sent_message_id == 101 and job.attempts == 1
        assert session.get(models.PlannedPublicationModel, 1).state == "PUBLISHED"
        assert session.get(models.PublicationCandidateModel, 1).state == "PUBLISHED"
        events = session.scalars(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.event_type == "publication.delivered"
            )
        ).all()
        assert len(events) == 1


def test_rejected_publication_never_queues_and_stale_job_never_sends(source_store):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    execution.enqueue(1, now=NOW)
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    with pytest.raises(PublicationBlocked):
        execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert sender.calls == []


def test_publication_expired_claim_can_recover_before_send_but_old_owner_is_fenced(source_store):
    seed_plan(source_store)
    sender = Publisher()
    first = runner(source_store, sender)
    first.enqueue(1, now=NOW)
    old = first.claim_next(now=NOW)
    recovered = runner(source_store, sender, clock=lambda: NOW + timedelta(seconds=61))
    current = recovered.claim_next(now=NOW + timedelta(seconds=61))
    assert current.attempt == 2 and current.token != old.token
    assert first.execute(old) == "LOST_LEASE" and sender.calls == []
    assert recovered.execute(current) == "SUCCEEDED" and len(sender.calls) == 1


def test_ambiguous_timeout_is_quarantined_and_never_blindly_retried(source_store):
    seed_plan(source_store)
    sender = Publisher(failure=TimeoutError("Synthetic response lost after sending"))
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    assert (
        runner(source_store, sender, clock=lambda: NOW + timedelta(minutes=2)).run_next(
            now=NOW + timedelta(minutes=2)
        )
        == "IDLE"
    )
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "NEEDS_RECONCILIATION" and job.sent_message_id is None
        assert session.get(models.PlannedPublicationModel, 1).state == "PLANNED"
    assert len(sender.calls) == 1


def test_abandoned_sending_intent_is_not_claimed_by_a_replacement_worker(source_store):
    seed_plan(source_store)
    sender = Publisher()
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    claim = execution.claim_next(now=NOW)
    with source_store[0].begin() as session:
        session.get(models.PublicationJobModel, job_id).state = "SENDING"
    replacement = runner(source_store, sender, clock=lambda: NOW + timedelta(seconds=61))
    assert replacement.claim_next(now=NOW + timedelta(seconds=61)) is None
    assert execution.execute(claim) == "LOST_LEASE" and sender.calls == []
    with source_store[0]() as session:
        assert session.get(models.PublicationJobModel, job_id).state == "NEEDS_RECONCILIATION"


def test_revocation_during_transport_preparation_blocks_before_remote_send(source_store):
    seed_plan(source_store)

    def revoke():
        with source_store[0].begin() as session:
            decision = session.scalar(select(models.EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False

    sender = Publisher(change=revoke)
    execution = runner(source_store, sender)
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED" and sender.calls == []


def test_provider_callback_sees_committed_sending_intent_without_held_database_locks(source_store):
    seed_plan(source_store)
    saw_sending = []

    def check():
        with source_store[0].begin() as session:
            job = session.scalar(select(models.PublicationJobModel))
            saw_sending.append(job.state)
            session.get(models.TelegramAccount, 1).name = "Changed while provider prepares"

    sender = Publisher(change=check)
    execution = runner(source_store, sender)
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    assert saw_sending == ["SENDING"] and len(sender.calls) == 1


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("malformed remote response"),
        LookupError("ack missing"),
        PublicationBlocked("raised after remote send"),
    ],
)
def test_post_send_validation_exception_is_unknown_not_a_zero_send_block(source_store, failure):
    seed_plan(source_store)
    sender = Publisher(failure=failure)
    execution = runner(source_store, sender)
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    assert len(sender.calls) == 1


def test_late_valid_receipt_preserves_delivery_truth_after_lease_expiry(source_store):
    seed_plan(source_store)
    ticks = [NOW]

    class SlowPublisher(Publisher):
        def publish(self, *args, **kwargs):
            receipt = super().publish(*args, **kwargs)
            ticks[0] = NOW + timedelta(seconds=61)
            runner(source_store, self, clock=lambda: ticks[0]).claim_next(now=ticks[0])
            return receipt

    sender = SlowPublisher()
    execution = runner(source_store, sender, clock=lambda: ticks[0])
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "SUCCEEDED" and job.sent_message_id == 101
    assert len(sender.calls) == 1


def test_known_not_sent_retry_keeps_nonce_and_has_bounded_budget(source_store):
    from newsflow.services.durable_publication_runner import PublicationNotSentRetry

    seed_plan(source_store)
    ticks = [NOW]
    sender = Publisher(failure=PublicationNotSentRetry(90))
    execution = runner(source_store, sender, clock=lambda: ticks[0])
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "RETRY"
    assert execution.run_next(now=NOW) == "IDLE"
    ticks[0] += timedelta(seconds=90)
    assert execution.run_next(now=ticks[0]) == "FAILED"
    assert sender.calls[0][1] == sender.calls[1][1]
    with source_store[0]() as session:
        assert session.get(models.PublicationJobModel, job_id).attempts == 2


@pytest.mark.parametrize(
    "corruption", ["account", "channel", "nonce", "message", "bool", "untyped"]
)
def test_invalid_receipt_is_quarantined_without_marking_published(source_store, corruption):
    from dataclasses import replace

    seed_plan(source_store)

    class BadReceipt(Publisher):
        def publish(self, *args, **kwargs):
            receipt = super().publish(*args, **kwargs)
            updates = {
                "account": {"account_id": 2},
                "channel": {"telegram_channel_id": -1005555555555},
                "nonce": {"request_nonce": 1 if receipt.request_nonce != 1 else 2},
                "message": {"message_id": 0},
                "bool": {"message_id": True},
            }
            return {} if corruption == "untyped" else replace(receipt, **updates[corruption])

    execution = runner(source_store, BadReceipt())
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    with source_store[0]() as session:
        assert session.get(models.PlannedPublicationModel, 1).state == "PLANNED"


def test_default_sender_is_disabled_without_consuming_claim(source_store):
    seed_plan(source_store)
    execution = runner(source_store, None)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "IDLE"
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "QUEUED" and job.attempts == 0


def test_transport_must_not_acknowledge_without_running_final_guard(source_store):
    from newsflow.services.durable_publication_runner import PublicationReceipt

    seed_plan(source_store)

    class Unguarded:
        def publish(self, envelope, nonce, *, execution_guard):
            return PublicationReceipt(envelope.account_id, envelope.telegram_channel_id, nonce, 101)

    execution = runner(source_store, Unguarded())
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    with source_store[0]() as session:
        assert session.get(models.PlannedPublicationModel, 1).state == "PLANNED"


def test_lease_expiring_during_transport_preparation_prevents_send(source_store):
    seed_plan(source_store)
    ticks = [NOW]
    sender = Publisher(change=lambda: ticks.__setitem__(0, NOW + timedelta(seconds=61)))
    execution = runner(source_store, sender, clock=lambda: ticks[0])
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "LOST_LEASE" and sender.calls == []
    assert execution.claim_next(now=ticks[0]) is None
    with source_store[0]() as session:
        assert session.scalar(select(models.PublicationJobModel)).state == "NEEDS_RECONCILIATION"


@pytest.mark.parametrize("mutation", ["state", "attempts", "nonce", "channel", "lease", "receipt"])
def test_database_rejects_invalid_publication_job_states(source_store, mutation):
    from sqlalchemy.exc import IntegrityError

    seed_plan(source_store)
    job_id = runner(source_store, None).enqueue(1, now=NOW)
    with pytest.raises(IntegrityError), source_store[0].begin() as session:
        job = session.get(models.PublicationJobModel, job_id)
        if mutation == "state":
            job.state = "PUBLISHED"
        elif mutation == "attempts":
            job.attempts = 3
        elif mutation == "nonce":
            job.request_nonce = 0
        elif mutation == "channel":
            job.telegram_channel_id = 123
        elif mutation == "lease":
            job.state = "SENDING"
        else:
            job.state = "SUCCEEDED"
