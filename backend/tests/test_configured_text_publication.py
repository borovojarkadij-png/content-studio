import json
from datetime import timedelta
from importlib import import_module
from importlib.util import find_spec

import pytest
from sqlalchemy import select
from telethon.errors import FloodWaitError
from test_publication_preflight import seed_plan
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store
from test_telegram_text_publication import Client, reply

from newsflow.persistence import models
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_publication_runner import DurablePublicationRunner

source_store = _source_store
CIPHER = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
OUTPUT = -1001234567891


def configured(store, client):
    module = "newsflow.services.telegram_publication_factory"
    assert find_spec(module) is not None, "Encrypted publication factory is missing"
    return import_module(module).ConfiguredTelegramTextPublisher(
        store[0],
        cipher=CIPHER,
        api_id=123,
        api_hash="a" * 32,
        client_factory=lambda _: client,
    )


def setup(store, client=None):
    seed_plan(store)
    with store[0].begin() as session:
        session.get(models.TelegramAccount, 1).encrypted_session = CIPHER.encrypt("synthetic")
        session.get(models.TelegramPeerModel, (1, OUTPUT)).encrypted_peer = CIPHER.encrypt(
            json.dumps(
                {
                    "version": 1,
                    "account_id": "1",
                    "user_id": 1001,
                    "channel_id": OUTPUT,
                    "access_hash": 999,
                }
            )
        )
    client = client or Client()
    client.channel.id = 1234567891

    async def permission(peer):
        assert (peer.channel_id, peer.access_hash) == (1234567891, 999)
        client.events.append("permissions")
        if client.during_permissions:
            client.during_permissions()
        return client.channel

    client.get_entity = permission
    return client


class ReceiptClient(Client):
    async def __call__(self, request):
        # Observe the committed real state from a separate database connection;
        # this is not a mocked runner or a fabricated completed job.
        with self.factory.begin() as session:
            job = session.scalar(select(models.PublicationJobModel))
            assert job.state == "SENDING" and job.request_nonce == request.random_id
        self.response = reply(nonce=request.random_id, channel=1234567891, text="Photo caption")
        return await super().__call__(request)


def test_encrypted_factory_real_runner_commits_exact_receipt_once(source_store):
    client = setup(source_store, ReceiptClient())
    client.factory = source_store[0]
    execution = DurablePublicationRunner(
        *source_store, publisher=configured(source_store, client), clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    assert execution.run_next(now=NOW) == "IDLE"
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "SUCCEEDED" and job.sent_message_id == 501 and job.attempts == 1
        assert session.get(models.PlannedPublicationModel, 1).state == "PUBLISHED"
    assert len(client.requests) == 1


def test_revocation_during_permission_rpc_blocks_real_runner_with_zero_send(source_store):
    client = setup(source_store)

    def revoke():
        with source_store[0].begin() as session:
            decision = session.scalar(select(models.EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False

    client.during_permissions = revoke
    execution = DurablePublicationRunner(
        *source_store, publisher=configured(source_store, client), clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert not client.requests
    with source_store[0]() as session:
        assert session.get(models.PublicationJobModel, job_id).state == "BLOCKED"
        assert session.get(models.PlannedPublicationModel, 1).state == "PLANNED"


@pytest.mark.parametrize("corrupt", ["session", "peer"])
def test_undecryptable_configuration_never_connects_or_sends(source_store, corrupt):
    from newsflow.providers.telegram import SessionUnavailable
    from newsflow.services.publication_preflight import PublicationPreflight

    client = setup(source_store)
    with source_store[0].begin() as session:
        if corrupt == "session":
            session.get(models.TelegramAccount, 1).encrypted_session = "corrupted"
        else:
            session.get(models.TelegramPeerModel, (1, OUTPUT)).encrypted_peer = "corrupted"
    current = PublicationPreflight(*source_store).prepare(1, now=NOW)
    with pytest.raises(SessionUnavailable):
        configured(source_store, client).publish(current, 123, execution_guard=lambda: None)
    assert not client.events and not client.requests


@pytest.mark.parametrize("mutation", ["session", "user", "source", "review", "cancel"])
def test_permission_time_state_changes_are_fenced_before_send(source_store, mutation):
    client = setup(source_store)

    def change():
        with source_store[0].begin() as session:
            if mutation == "session":
                session.get(models.TelegramAccount, 1).encrypted_session = CIPHER.encrypt(
                    "replacement"
                )
            elif mutation == "user":
                session.get(models.TelegramAccount, 1).telegram_user_id = 9999
            elif mutation == "source":
                session.add(
                    models.ContentRevisionModel(
                        incoming_post_id=1, revision_number=2, source_text="Edited source"
                    )
                )
            elif mutation == "review":
                session.scalar(select(models.RewriteOutputModel)).approval_state = "REJECTED"
            else:
                session.get(models.PlannedPublicationModel, 1).state = "CANCELLED"

    client.during_permissions = change
    execution = DurablePublicationRunner(
        *source_store, publisher=configured(source_store, client), clock=lambda: NOW
    )
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert not client.requests


def test_send_timeout_quarantines_persisted_nonce_and_restart_does_not_resend(source_store):
    client = setup(source_store)
    client.failure = TimeoutError("Synthetic response lost")
    sender = configured(source_store, client)
    execution = DurablePublicationRunner(*source_store, publisher=sender, clock=lambda: NOW)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    restarted = DurablePublicationRunner(
        *source_store, publisher=sender, clock=lambda: NOW + timedelta(minutes=2)
    )
    assert restarted.run_next(now=NOW + timedelta(minutes=2)) == "IDLE"
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "NEEDS_RECONCILIATION" and job.sent_message_id is None
        assert [request.random_id for request in client.requests] == [job.request_nonce]


def test_send_floodwait_delays_durable_retry_and_keeps_nonce_until_budget_exhaustion(source_store):
    client = setup(source_store)
    client.failure = FloodWaitError(None, capture=120)
    sender = configured(source_store, client)
    execution = DurablePublicationRunner(*source_store, publisher=sender, clock=lambda: NOW)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "RETRY"
    assert execution.run_next(now=NOW + timedelta(seconds=119)) == "IDLE"
    retried = DurablePublicationRunner(
        *source_store, publisher=sender, clock=lambda: NOW + timedelta(seconds=120)
    )
    assert retried.run_next(now=NOW + timedelta(seconds=120)) == "FAILED"
    assert retried.run_next(now=NOW + timedelta(seconds=240)) == "IDLE"
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "FAILED" and job.attempts == 2
        assert [request.random_id for request in client.requests] == [job.request_nonce] * 2
