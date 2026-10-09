"""Fresh authenticated library review through real durable transport boundaries."""

import json
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import select
from telethon.errors import FloodWaitError
from test_configured_photo_publication import ReceiptClient, configured
from test_configured_text_publication import CIPHER, OUTPUT
from test_illustration_binding import DRAFT, NOW, mutate
from test_illustration_binding import library_store as _library_store
from test_illustration_binding import mapping_store as _mapping_store

from newsflow.persistence import models
from newsflow.security.illustration_reviewer import ReviewerPrincipal
from newsflow.services.durable_publication_runner import DurablePublicationRunner
from newsflow.services.illustration_binding import IllustrationBindingResolver
from newsflow.services.illustration_review import IllustrationReviewWriter
from newsflow.services.media_job_read import MediaJobReader
from newsflow.services.publication import PublicationBlocked
from newsflow.services.publication_preflight import PublicationPreflight
from newsflow.services.publication_request_snapshot import PublicationRequestSnapshots

library_store = _library_store
mapping_store = _mapping_store


def review(store, verdict="APPROVED_ILLUSTRATION", key="approval"):
    factory, root, _ = store
    with factory() as session:
        binding = IllustrationBindingResolver(session, root).resolve(1)
    with factory() as session:
        return IllustrationReviewWriter(session, root).review(
            ReviewerPrincipal(17),
            displayed_binding=binding,
            operation_key=key,
            verdict=verdict,
            illustration_acknowledged=True,
            review_note="Synthetic illustration; no event-photo claim",
        )["id"]


def revoke(store, review_id):
    with store[0]() as session:
        IllustrationReviewWriter(session, store[1]).revoke(
            ReviewerPrincipal(17),
            review_id=review_id,
            operation_key="revoke",
            review_note="Synthetic withdrawal",
        )


def publication(store):
    factory, root, _ = store
    with factory.begin() as session:
        candidate = session.get(models.PublicationCandidateModel, 1)
        candidate.state, candidate.eligible_at = "SCHEDULED", NOW - timedelta(minutes=1)
        account = session.get(models.TelegramAccount, 1)
        account.encrypted_session, account.health_status = CIPHER.encrypt("synthetic"), "CONNECTED"
        session.add(
            models.TelegramPeerModel(
                telegram_account_id=1,
                telegram_channel_id=OUTPUT,
                encrypted_peer=CIPHER.encrypt(
                    json.dumps(
                        {
                            "version": 1,
                            "account_id": "1",
                            "user_id": 1001,
                            "channel_id": OUTPUT,
                            "access_hash": 999,
                        }
                    )
                ),
            )
        )
        session.add(
            models.PlannedPublicationModel(
                id=1,
                candidate_id=1,
                output_channel_id=1,
                scheduled_for=NOW,
                state="PLANNED",
            )
        )
    client = ReceiptClient()
    client.factory, client.channel.id = factory, 1234567891

    async def permission(peer):
        assert (peer.channel_id, peer.access_hash) == (1234567891, 999)
        client.events.append("permissions")
        if client.during_permissions:
            client.during_permissions()
        return client.channel

    client.get_entity = permission
    runner = DurablePublicationRunner(
        factory,
        root,
        publisher=configured((factory, root), client),
        cipher=CIPHER,
        clock=lambda: NOW,
    )
    return runner, client


def test_current_review_sends_labeled_exact_library_photo_once_and_snapshots_review(library_store):
    review_id = review(library_store)
    runner, client = publication(library_store)
    job = runner.enqueue(1, now=NOW)
    saved = PublicationRequestSnapshots(library_store[0], cipher=CIPHER).read(job)
    assert saved.envelope.illustration_review_id == review_id
    assert saved.envelope.illustration_binding.candidate_id == 1
    assert runner.run_next(now=NOW) == "SUCCEEDED"
    assert runner.run_next(now=NOW) == "IDLE"
    assert len(client.uploaded) == len(client.requests) == 1
    assert client.requests[0].message.startswith(DRAFT + "\n\nИллюстрация.")
    with library_store[0]() as session:
        credit = session.get(models.MediaAssetModel, 1).attribution
    assert client.requests[0].message == DRAFT + "\n\nИллюстрация.\n\n" + credit


def test_exact_review_clears_only_read_only_library_hold(library_store):
    with library_store[0]() as session:
        assert (
            MediaJobReader(session, library_store[1]).get_status(1)["publication_hold_reason_code"]
            == "HUMAN_ILLUSTRATION_REVIEW_REQUIRED"
        )
    review(library_store)
    with library_store[0]() as session:
        assert (
            MediaJobReader(session, library_store[1]).get_status(1)["publication_hold_reason_code"]
            is None
        )


@pytest.mark.parametrize("verdict", [None, "REJECTED", "UNCERTAIN", "revoked"])
def test_unapproved_library_never_uploads_or_sends(library_store, verdict):
    if verdict:
        review_id = review(
            library_store, "APPROVED_ILLUSTRATION" if verdict == "revoked" else verdict
        )
        if verdict == "revoked":
            revoke(library_store, review_id)
    runner, client = publication(library_store)
    with pytest.raises(PublicationBlocked):
        runner.enqueue(1, now=NOW)
    assert not client.uploaded and not client.requests


@pytest.mark.parametrize(
    "mutation", ["revoke", "reject", "credit", "rights", "file", "new_reject", "new_uncertain"]
)
def test_library_mutation_during_upload_prevents_send(library_store, mutation):
    review_id = review(library_store)
    runner, client = publication(library_store)
    runner.enqueue(1, now=NOW)

    def change():
        if mutation == "revoke":
            revoke(library_store, review_id)
        elif mutation.startswith("new_"):
            review(library_store, "REJECTED" if mutation == "new_reject" else "UNCERTAIN", "latest")
        else:
            with library_store[0].begin() as session:
                asset = session.get(models.MediaAssetModel, 1)
                if mutation == "credit":
                    asset.attribution = "Changed credit"
                elif mutation == "rights":
                    asset.license_code = "OWNED"
                elif mutation == "file":
                    (library_store[1] / asset.storage_key).write_bytes(b"changed")
                else:
                    decision = session.scalar(select(models.EditorialDecisionModel))
                    decision.status, decision.rewrite_allowed = "REJECT", False

    client.during_upload = change
    assert runner.run_next(now=NOW) == "BLOCKED"
    assert len(client.uploaded) == 1 and not client.requests


@pytest.mark.parametrize(
    "mutation", ["foreign_channel", "new_source", "unreviewed", "blank_credit", "fact_changed"]
)
def test_stale_library_binding_is_blocked_before_any_transport(library_store, mutation):
    review(library_store)
    runner, client = publication(library_store)
    runner.enqueue(1, now=NOW)
    with library_store[0].begin() as session:
        mutate(session, mutation)
    assert runner.run_next(now=NOW) == "BLOCKED"
    assert not client.events and not client.uploaded and not client.requests


def test_new_approval_cannot_rebind_old_queued_library_intent(library_store):
    review(library_store)
    runner, client = publication(library_store)
    runner.enqueue(1, now=NOW)
    review(library_store, key="new-approval")
    assert runner.run_next(now=NOW) == "BLOCKED"
    assert not client.requests and not client.uploaded


def test_revocation_during_permissions_refuses_bytes_before_upload(library_store):
    review_id = review(library_store)
    runner, client = publication(library_store)
    runner.enqueue(1, now=NOW)
    client.during_permissions = lambda: revoke(library_store, review_id)
    # A committed SENDING intent is conservatively quarantined if preparation fails.
    assert runner.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    assert not client.uploaded and not client.requests


def test_known_not_sent_library_retry_refuses_revocation(library_store):
    review_id = review(library_store)
    runner, client = publication(library_store)
    runner.enqueue(1, now=NOW)
    client.failure = FloodWaitError(request=None, capture=1)
    assert runner.run_next(now=NOW) == "RETRY"
    revoke(library_store, review_id)
    client.failure = None
    runner._clock = lambda: NOW + timedelta(seconds=31)
    assert runner.run_next(now=NOW + timedelta(seconds=31)) == "BLOCKED"
    assert len(client.uploaded) == len(client.requests) == 1


def test_library_unknown_delivery_restart_never_reuploads_or_resends(library_store):
    review(library_store)
    runner, client = publication(library_store)
    runner.enqueue(1, now=NOW)
    client.failure = TimeoutError("synthetic lost receipt")
    assert runner.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    restarted = DurablePublicationRunner(
        *library_store[:2],
        publisher=configured(library_store[:2], client),
        cipher=CIPHER,
        clock=lambda: NOW + timedelta(minutes=2),
    )
    assert restarted.run_next(now=NOW + timedelta(minutes=2)) == "IDLE"
    assert len(client.uploaded) == len(client.requests) == 1


@pytest.mark.parametrize(
    "damage",
    ["bool", "unknown", "missing", "null_binding", "wrong_channel", "duplicate", "v1_extra"],
)
def test_library_snapshot_review_schema_never_authorizes_corrupt_intent(library_store, damage):
    review(library_store)
    runner, client = publication(library_store)
    job_id = runner.enqueue(1, now=NOW)
    with library_store[0].begin() as session:
        row = session.get(models.PublicationRequestSnapshotModel, job_id)
        value = json.loads(CIPHER.decrypt(row.encrypted_envelope))
        assert value["version"] == 2
        envelope = value["envelope"]
        if damage == "bool":
            envelope["illustration_review_id"] = True
        elif damage == "unknown":
            envelope["illustration_binding"]["provenance"] = "forged"
        elif damage == "missing":
            del envelope["illustration_review_id"]
        elif damage == "null_binding":
            envelope["illustration_binding"] = None
        elif damage == "wrong_channel":
            envelope["illustration_binding"]["output_channel_id"] = 2
        elif damage == "v1_extra":
            value["version"] = 1
        payload = json.dumps(value)
        if damage == "duplicate":
            payload = payload.replace(
                '"illustration_review_id": 1',
                '"illustration_review_id": 1, "illustration_review_id": 1',
            )
        row.encrypted_envelope = CIPHER.encrypt(payload)
    with pytest.raises(PublicationBlocked):
        PublicationRequestSnapshots(library_store[0], cipher=CIPHER).read(job_id)
    assert runner.run_next(now=NOW) == "BLOCKED"
    assert not client.uploaded and not client.requests


@pytest.mark.parametrize("gate", ["actual_photo", "label_filter", "caption_limit"])
def test_complete_labeled_library_caption_and_actual_photo_type_obey_filters(library_store, gate):
    with library_store[0].begin() as session:
        if gate == "actual_photo":
            session.get(models.ContentRevisionModel, 1).media_type = "text"
        if gate == "caption_limit":
            session.get(models.MediaAssetModel, 1).attribution = "Synthetic credit " + "a" * 1024
        else:
            session.add(
                models.MappingFilterPolicyModel(
                    mapping_id=1,
                    allowed_media_types=["text"] if gate == "actual_photo" else ["text", "photo"],
                    blocked_domains=[],
                    ad_markers=["Иллюстрация."] if gate == "label_filter" else [],
                )
            )
    review(library_store)
    runner, client = publication(library_store)
    with pytest.raises(PublicationBlocked):
        runner.enqueue(1, now=NOW)
    assert not client.requests and not client.uploaded


def test_configured_library_reader_refuses_removed_label_or_credit_before_upload(library_store):
    review(library_store)
    _, client = publication(library_store)
    envelope = PublicationPreflight(*library_store[:2]).prepare(1, now=NOW)
    with pytest.raises(PublicationBlocked):
        configured(library_store[:2], client)._bound_photo(replace(envelope, text=DRAFT))
    assert not client.uploaded and not client.requests


def test_abandoned_library_sending_intent_never_reuploads_after_restart(library_store):
    review_id = review(library_store)
    runner, client = publication(library_store)
    job_id = runner.enqueue(1, now=NOW)
    claim = runner.claim_next(now=NOW)
    assert claim.job_id == job_id
    with library_store[0].begin() as session:
        session.get(models.PublicationJobModel, job_id).state = "SENDING"
    revoke(library_store, review_id)
    restarted = DurablePublicationRunner(
        *library_store[:2],
        publisher=configured(library_store[:2], client),
        cipher=CIPHER,
        clock=lambda: NOW + timedelta(minutes=2),
    )
    assert restarted.run_next(now=NOW + timedelta(minutes=2)) == "IDLE"
    with library_store[0]() as session:
        assert session.get(models.PublicationJobModel, job_id).state == "NEEDS_RECONCILIATION"
    assert not client.uploaded and not client.requests
