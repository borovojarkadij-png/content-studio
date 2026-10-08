from datetime import timedelta

import pytest
from sqlalchemy import select
from test_source_photo_acquisition import NOW, Photos
from test_source_photo_acquisition import source_store as _source_store
from test_source_rights_configuration import mapped_store

from newsflow.persistence import models
from newsflow.services.publication import PublicationBlocked

source_store = _source_store


def seed_plan(store, *, media_type="text"):
    factory, _ = store
    mapping_id = mapped_store(factory)
    with factory.begin() as session:
        source = session.scalar(select(models.ContentRevisionModel))
        source.media_type = media_type
        candidate = session.get(models.PublicationCandidateModel, 1)
        candidate.state, candidate.eligible_at = "SCHEDULED", NOW - timedelta(minutes=1)
        session.add(
            models.TelegramPeerModel(
                telegram_account_id=1,
                telegram_channel_id=-1001234567891,
                encrypted_peer="synthetic encrypted output peer",
            )
        )
        session.add(
            models.PlannedPublicationModel(
                id=1, candidate_id=1, output_channel_id=1, scheduled_for=NOW, state="PLANNED"
            )
        )
    return mapping_id


def guard(store):
    from newsflow.services.publication_preflight import PublicationPreflight

    return PublicationPreflight(store[0], store[1])


def test_publication_preflight_reads_current_approved_output_without_send(source_store):
    seed_plan(source_store)
    envelope = guard(source_store).prepare(1, now=NOW)
    assert envelope.planned_id == 1 and envelope.candidate_id == 1
    assert envelope.text == "Photo caption" and envelope.telegram_channel_id == -1001234567891
    assert envelope.account_id == 1 and envelope.user_id == 1001
    assert envelope.media_asset_id is None and len(envelope.binding_sha256) == 64
    with source_store[0]() as session:
        assert session.get(models.PlannedPublicationModel, 1).state == "PLANNED"


@pytest.mark.parametrize(
    "mutation",
    [
        "reject",
        "rewrite_disabled",
        "review",
        "job",
        "source",
        "candidate",
        "unmapped",
        "session",
        "peer",
        "cooldown",
        "expired",
        "future",
        "protected",
        "album",
        "video",
        "unknown",
        "source_filter",
        "draft_filter",
    ],
)
def test_stale_or_unsafe_publication_is_blocked_at_last_local_boundary(source_store, mutation):
    mapping_id = seed_plan(source_store)
    with source_store[0].begin() as session:
        if mutation in {"reject", "rewrite_disabled"}:
            decision = session.scalar(select(models.EditorialDecisionModel))
            decision.rewrite_allowed = False
            if mutation == "reject":
                decision.status = "REJECT"
        elif mutation == "review":
            session.scalar(select(models.RewriteOutputModel)).approval_state = "REJECTED"
        elif mutation == "job":
            session.get(models.RewriteJobModel, 1).state = "QUEUED"
        elif mutation == "source":
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=1, revision_number=2, source_text="Edited"
                )
            )
        elif mutation == "candidate":
            session.get(models.PublicationCandidateModel, 1).state = "READY"
        elif mutation == "unmapped":
            session.get(models.PublicationCandidateModel, 1).mapping_id = None
        elif mutation == "session":
            session.get(models.TelegramAccount, 1).encrypted_session = ""
        elif mutation == "peer":
            session.get(models.TelegramPeerModel, (1, -1001234567891)).encrypted_peer = ""
        elif mutation == "cooldown":
            session.get(models.TelegramAccount, 1).cooldown_until = NOW + timedelta(minutes=1)
        elif mutation == "expired":
            session.get(models.PlannedPublicationModel, 1).scheduled_for = NOW - timedelta(hours=7)
        elif mutation == "future":
            session.get(models.PlannedPublicationModel, 1).scheduled_for = NOW + timedelta(
                minutes=1
            )
        elif mutation == "protected":
            session.scalar(select(models.ContentRevisionModel)).media_protected = True
        elif mutation == "album":
            session.scalar(select(models.ContentRevisionModel)).album_id = "123"
        elif mutation in {"video", "unknown"}:
            session.scalar(select(models.ContentRevisionModel)).media_type = mutation
        elif mutation == "source_filter":
            session.add(
                models.MappingFilterPolicyModel(
                    mapping_id=mapping_id, allowed_media_types=[], blocked_domains=[], ad_markers=[]
                )
            )
        elif mutation == "draft_filter":
            session.add(
                models.MappingFilterPolicyModel(
                    mapping_id=mapping_id,
                    allowed_media_types=["text", "photo"],
                    blocked_domains=[],
                    ad_markers=["реклама"],
                )
            )
            session.scalar(
                select(models.RewriteOutputModel)
            ).rewritten_text = "Реклама: купи сейчас"
    with pytest.raises(PublicationBlocked):
        guard(source_store).prepare(1, now=NOW)


def test_publication_preflight_rechecks_not_cached_and_binding_changes_with_session(source_store):
    seed_plan(source_store)
    service = guard(source_store)
    first = service.prepare(1, now=NOW)
    with source_store[0].begin() as session:
        session.get(models.TelegramAccount, 1).encrypted_session = "new synthetic encrypted session"
    second = service.prepare(1, now=NOW)
    assert first.binding_sha256 != second.binding_sha256
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    with pytest.raises(PublicationBlocked):
        service.prepare(1, now=NOW)


def test_photo_publication_requires_completed_current_job_and_preserves_credit(source_store):
    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    mapping_id = seed_plan(source_store, media_type="photo")
    service = guard(source_store)
    with pytest.raises(PublicationBlocked):
        service.prepare(1, now=NOW)
    with source_store[0]() as session:
        TelegramConfigurationService(session).set_source_media_rights(
            mapping_id, "PERMISSION", "Synthetic owner permission"
        )
    execution = DurableSourcePhotoRunner(*source_store, provider=Photos(), clock=lambda: NOW)
    execution.enqueue_configured(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    envelope = service.prepare(1, now=NOW)
    assert envelope.media_asset_id is not None
    assert envelope.text == "Photo caption\n\nSynthetic owner permission"
    with source_store[0]() as session:
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "UNDECLARED", "")
    with pytest.raises(PublicationBlocked):
        service.prepare(1, now=NOW)


def test_photo_credit_cannot_bypass_final_publication_link_filters(source_store):
    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    mapping_id = seed_plan(source_store, media_type="photo")
    with source_store[0]() as session:
        TelegramConfigurationService(session).set_source_media_rights(
            mapping_id, "PERMISSION", "Owner https://forbidden.example/credit"
        )
        session.add(
            models.MappingFilterPolicyModel(
                mapping_id=mapping_id,
                allowed_media_types=["text", "photo"],
                blocked_domains=["forbidden.example"],
                ad_markers=[],
            )
        )
        session.commit()
    execution = DurableSourcePhotoRunner(*source_store, provider=Photos(), clock=lambda: NOW)
    execution.enqueue_configured(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    with pytest.raises(PublicationBlocked, match="TECHNICAL"):
        guard(source_store).prepare(1, now=NOW)


def test_cancellation_during_photo_preflight_cannot_return_a_send_envelope(
    source_store, monkeypatch
):
    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
    from newsflow.services.media_selection import LocalMediaSelectionService
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    mapping_id = seed_plan(source_store, media_type="photo")
    with source_store[0]() as session:
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "OWNED", "")
    execution = DurableSourcePhotoRunner(*source_store, provider=Photos(), clock=lambda: NOW)
    execution.enqueue_configured(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    read = LocalMediaSelectionService._read_photo

    def cancel(self, storage_key):
        value = read(self, storage_key)
        with source_store[0].begin() as session:
            session.get(models.PlannedPublicationModel, 1).state = "CANCELLED"
        return value

    monkeypatch.setattr(LocalMediaSelectionService, "_read_photo", cancel)
    with pytest.raises(PublicationBlocked):
        guard(source_store).prepare(1, now=NOW)


def test_manual_approval_cannot_bypass_current_fact_anchor_check(source_store):
    seed_plan(source_store)
    with source_store[0].begin() as session:
        session.scalar(
            select(models.ContentRevisionModel)
        ).source_text = "Photo caption with 3 facts"
        session.scalar(
            select(models.RewriteOutputModel)
        ).rewritten_text = "Photo caption with 4 facts"
    with pytest.raises(PublicationBlocked, match="FACT"):
        guard(source_store).prepare(1, now=NOW)
