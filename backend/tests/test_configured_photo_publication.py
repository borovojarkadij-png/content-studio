import json
from dataclasses import replace
from datetime import timedelta
from importlib import import_module

import pytest
from sqlalchemy import select
from telethon.tl.types import MessageMediaPhoto, Photo
from test_configured_text_publication import CIPHER, setup
from test_source_photo_acquisition import NOW, Photos
from test_source_photo_acquisition import source_store as _source_store
from test_telegram_photo_download import png
from test_telegram_photo_publication import PhotoClient
from test_telegram_text_publication import reply

from newsflow.persistence import models
from newsflow.services.durable_publication_runner import DurablePublicationRunner
from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
from newsflow.services.publication_preflight import PublicationPreflight
from newsflow.services.telegram_configuration import TelegramConfigurationService

source_store = _source_store


class ReceiptClient(PhotoClient):
    async def __call__(self, request):
        with self.factory.begin() as session:
            job = session.scalar(select(models.PublicationJobModel))
            assert job.state == "SENDING" and job.request_nonce == request.random_id
        self.response = reply(nonce=request.random_id, channel=1234567891, text=request.message)
        self.response.updates[1].message.media = MessageMediaPhoto(
            photo=Photo(123, 456, b"synthetic", NOW, [], 1)
        )
        return await super().__call__(request)


def photo_setup(store):
    client = setup(store, ReceiptClient())
    client.factory = store[0]
    with store[0].begin() as session:
        session.scalar(select(models.ContentRevisionModel)).media_type = "photo"
        mapping_id = session.get(models.PublicationCandidateModel, 1).mapping_id
    with store[0]() as session:
        TelegramConfigurationService(session).set_source_media_rights(
            mapping_id, "PERMISSION", "Synthetic owner permission"
        )
    acquisition = DurableSourcePhotoRunner(*store, provider=Photos(), clock=lambda: NOW)
    acquisition.enqueue_configured(1, now=NOW)
    assert acquisition.run_next(now=NOW) == "SUCCEEDED"
    return client, mapping_id


def configured(store, client):
    implementation = import_module("newsflow.services.telegram_publication_factory")
    assert hasattr(implementation, "ConfiguredTelegramPhotoPublisher"), (
        "Guarded photo factory is missing"
    )
    return implementation.ConfiguredTelegramPhotoPublisher(
        *store, cipher=CIPHER, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )


def test_real_photo_job_bytes_and_attribution_reach_exact_durable_receipt(source_store):
    client, _ = photo_setup(source_store)
    execution = DurablePublicationRunner(
        *source_store, publisher=configured(source_store, client), clock=lambda: NOW
    )
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    assert client.uploaded == [(png(), "source.png")]
    assert client.requests[0].message == "Photo caption\n\nSynthetic owner permission"
    assert execution.run_next(now=NOW) == "IDLE" and len(client.requests) == 1
    with source_store[0]() as session:
        assert session.get(models.PublicationJobModel, job_id).sent_message_id == 501
        assert session.get(models.PlannedPublicationModel, 1).state == "PUBLISHED"


def test_preupgrade_v1_source_photo_snapshot_survives_restart_without_rebinding(source_store):
    from newsflow.services.publication_request_snapshot import PublicationRequestSnapshots

    client, _ = photo_setup(source_store)
    sender = configured(source_store, client)
    runner = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: NOW
    )
    job_id = runner.enqueue(1, now=NOW)
    original = PublicationRequestSnapshots(source_store[0], cipher=CIPHER).read(job_id)
    with source_store[0].begin() as session:
        row = session.get(models.PublicationRequestSnapshotModel, job_id)
        payload = json.loads(CIPHER.decrypt(row.encrypted_envelope))
        payload["version"] = 1
        payload["envelope"].pop("illustration_review_id")
        payload["envelope"].pop("illustration_binding")
        row.encrypted_envelope = CIPHER.encrypt(json.dumps(payload))
    restarted = DurablePublicationRunner(
        *source_store, publisher=sender, cipher=CIPHER, clock=lambda: NOW
    )
    assert PublicationRequestSnapshots(source_store[0], cipher=CIPHER).read(job_id) == original
    assert restarted.run_next(now=NOW) == "SUCCEEDED"
    assert restarted.run_next(now=NOW) == "IDLE"
    assert len(client.uploaded) == len(client.requests) == 1


@pytest.mark.parametrize("mutation", ["reject", "rights", "file", "session"])
def test_changes_during_upload_block_publication_without_send(source_store, mutation):
    client, mapping_id = photo_setup(source_store)

    def change():
        # Separate writer succeeds while upload is outstanding: no DB lock/transaction
        # in the configured photo reader crosses this synthetic external boundary.
        with source_store[0].begin() as session:
            if mutation == "reject":
                decision = session.scalar(select(models.EditorialDecisionModel))
                decision.status, decision.rewrite_allowed = "REJECT", False
            elif mutation == "session":
                session.get(models.TelegramAccount, 1).encrypted_session = CIPHER.encrypt(
                    "replaced"
                )
            elif mutation == "rights":
                rights = session.get(models.MappingSourceRightsModel, mapping_id)
                rights.license_code, rights.attribution = "UNDECLARED", ""
                rights.revision += 1
            else:
                asset = session.scalar(select(models.MediaAssetModel))
                (source_store[1] / asset.storage_key).write_bytes(b"altered")

    client.during_upload = change
    execution = DurablePublicationRunner(
        *source_store, publisher=configured(source_store, client), clock=lambda: NOW
    )
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert len(client.uploaded) == 1 and not client.requests


def test_foreign_selected_asset_is_not_uploaded_as_current_photo(source_store):
    from newsflow.services.publication import PublicationBlocked

    client, _ = photo_setup(source_store)
    current = PublicationPreflight(*source_store).prepare(1, now=NOW)
    with pytest.raises(PublicationBlocked):
        configured(source_store, client).publish(
            replace(current, media_asset_id=999), 123, execution_guard=lambda: None
        )
    assert not client.uploaded and not client.requests


def test_photo_send_timeout_keeps_unknown_history_and_never_reuploads_on_restart(source_store):
    client, _ = photo_setup(source_store)
    client.failure = TimeoutError("Synthetic photo response lost")
    sender = configured(source_store, client)
    execution = DurablePublicationRunner(*source_store, publisher=sender, clock=lambda: NOW)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    restarted = DurablePublicationRunner(
        *source_store, publisher=sender, clock=lambda: NOW + timedelta(minutes=2)
    )
    assert restarted.run_next(now=NOW + timedelta(minutes=2)) == "IDLE"
    assert len(client.uploaded) == len(client.requests) == 1
    with source_store[0]() as session:
        job = session.get(models.PublicationJobModel, job_id)
        assert job.state == "NEEDS_RECONCILIATION" and job.sent_message_id is None
        assert client.requests[0].random_id == job.request_nonce


def test_rejected_queue_never_authenticates_uploads_or_sends_photo(source_store):
    from newsflow.services.publication import PublicationBlocked

    client, _ = photo_setup(source_store)
    execution = DurablePublicationRunner(
        *source_store, publisher=configured(source_store, client), clock=lambda: NOW
    )
    execution.enqueue(1, now=NOW)
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    with pytest.raises(PublicationBlocked):
        execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert not client.events and not client.uploaded and not client.requests
