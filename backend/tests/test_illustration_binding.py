"""Canonical review context from owned migrated SQL and synthetic photo bytes."""

import importlib
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, event, func, null, select
from sqlalchemy.orm import sessionmaker
from test_internet_media import Images
from test_mapping_fanout_dedup import mapping_store as _mapping_store

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.durable_media_runner import DurableMediaRunner
from newsflow.services.media_selection import LocalMediaSelectionService
from newsflow.services.rewrite_outputs import RewriteOutputService

mapping_store = _mapping_store
NOW = datetime(2030, 1, 1, tzinfo=UTC)
SOURCE = "Завод открыл 3 линии."
DRAFT = "Открыты 3 линии на заводе."
KEY = "1:-1001234567890:20:revision:1"


@pytest.fixture
def library_store(mapping_store, tmp_path):
    engine = create_engine(mapping_store[0])
    factory = sessionmaker(engine)
    mapping_id = mapping_store[1][0]
    with factory() as session:
        session.get(models.ChannelMappingModel, mapping_id).media_policy = "LICENSED_LIBRARY"
        session.commit()
        result = DurableIngestionWorkflow(session, configured_mapping_id=mapping_id).ingest(
            TelegramMessage(
                "1",
                "-1001234567890",
                20,
                SOURCE,
                media_type="photo",
                media_id="123",
                media_protected=False,
                source_updated_at=NOW,
            ),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert result.status == "REWRITE_QUEUED"
        session.scalar(select(models.RewriteJobModel)).state = "SUCCEEDED"
        session.commit()
        drafts = RewriteOutputService(session)
        drafts.record_succeeded_output(1, DRAFT)
        drafts.approve(1, activate_candidate=True)
    root = tmp_path / "photos"
    root.mkdir()
    images = Images()
    runner = DurableMediaRunner(factory, root, provider=images, clock=lambda: NOW)
    runner.enqueue_candidate(1, now=NOW)
    assert runner.run_next(now=NOW) == "SUCCEEDED"
    yield factory, root, images
    engine.dispose()


def resolver(session, root):
    module = importlib.import_module("newsflow.services.illustration_binding")
    return module.IllustrationBindingResolver(session, root)


def counts(factory):
    with factory() as session:
        return tuple(
            session.scalar(select(func.count()).select_from(model))
            for model in (
                models.RewriteJobModel,
                models.RewriteOutputModel,
                models.MediaAcquisitionJobModel,
                models.PublicationJobModel,
                models.OutboxEventModel,
                models.RewriteUsageModel,
            )
        )


def test_resolver_returns_exact_binding_from_reopened_sql_without_writes_or_provider(library_store):
    factory, root, images = library_store
    before = counts(factory)
    writes = []

    def observe(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(statement)

    event.listen(factory.kw["bind"], "before_cursor_execute", observe)
    with factory() as session:
        first = resolver(session, root).resolve(1)
        assert first.candidate_id == 1 and first.output_channel_id == 1 and first.mapping_id == 1
        assert first.content_key == KEY and first.source_revision_id == 1
        assert first.rewrite_output_id == 1 and first.media_asset_id == 1
        assert first.source_sha256 == sha256(SOURCE.encode()).hexdigest()
        assert first.draft_sha256 == sha256(DRAFT.encode()).hexdigest()
        asset = session.get(models.MediaAssetModel, 1)
        assert first.media_sha256 == sha256((root / asset.storage_key).read_bytes()).hexdigest()
        assert len(first.asset_metadata_sha256) == 64
        assert not session.new and not session.dirty and not session.deleted
    with factory() as reopened:
        assert resolver(reopened, root).resolve(1) == first
    assert counts(factory) == before
    assert writes == []
    assert images.calls == ["search", "download"]  # Setup only, never the resolver.


@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_resolver_refuses_pending_caller_work_before_implicit_flush(library_store, pending):
    factory, root, _ = library_store
    with factory() as session:
        row = session.get(models.PublicationCandidateModel, 1)
        if pending == "new":
            session.add(
                models.OutboxEventModel(
                    event_type="synthetic",
                    aggregate_key="caller",
                    idempotency_key="caller-owned",
                )
            )
        elif pending == "dirty":
            row.priority = 999
        else:
            session.delete(row)
        with pytest.raises(ValueError, match="clean session"):
            resolver(session, root).resolve(1)
        assert getattr(session, pending)
        session.rollback()
    with factory() as reopened:
        assert reopened.get(models.PublicationCandidateModel, 1).priority != 999
        assert (
            reopened.scalar(
                select(models.OutboxEventModel).where(
                    models.OutboxEventModel.idempotency_key == "caller-owned"
                )
            )
            is None
        )


@pytest.mark.parametrize("invalid", [True, 0, -1, "1", None])
def test_resolver_never_coerces_candidate_identity(library_store, invalid):
    factory, root, _ = library_store
    with factory() as session, pytest.raises(ValueError):
        resolver(session, root).resolve(invalid)


def mutate(session, scenario):
    candidate = session.get(models.PublicationCandidateModel, 1)
    source = session.get(models.ContentRevisionModel, 1)
    output = session.get(models.RewriteOutputModel, 1)
    job = session.get(models.MediaAcquisitionJobModel, 1)
    mapping = session.get(models.ChannelMappingModel, 1)
    asset = session.get(models.MediaAssetModel, 1)
    if scenario == "reject":
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    elif scenario == "protected_negative":
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.sentiment, decision.protected_entities = "negative", "Protected"
    elif scenario == "unreviewed":
        output.approval_state = "PENDING"
    elif scenario == "rewrite_job":
        session.get(models.RewriteJobModel, 1).state = "SUPERSEDED"
    elif scenario == "new_source":
        session.add(
            models.ContentRevisionModel(
                incoming_post_id=1,
                revision_number=2,
                source_text="New version",
            )
        )
    elif scenario == "deleted_source":
        session.add(
            models.SourceDeletionModel(
                telegram_account_id="1",
                donor_channel_id="-1001234567890",
                telegram_message_id=20,
                latest_pts=22,
                observed_at=NOW,
            )
        )
    elif scenario == "missing_mapping":
        candidate.mapping_id = None
    elif scenario == "foreign_channel":
        candidate.mapping_id = 2  # Real foreign-channel mapping, no UNIQUE violation.
    elif scenario == "foreign_donor":
        session.get(
            models.DonorChannel, mapping.donor_channel_id
        ).telegram_channel_id = -1001234567880
    elif scenario == "mapping_policy":
        mapping.media_policy = "REUSE_SOURCE"
    elif scenario == "source_policy":
        candidate.media_policy = "REUSE_SOURCE"
    elif scenario == "candidate_state":
        candidate.state = "AWAITING_REWRITE"
    elif scenario == "video":
        source.media_type = "video"
    elif scenario == "album":
        source.album_id = "99"
    elif scenario == "protected":
        source.media_protected = True
    elif scenario == "unknown_protection":
        source.media_protected = None
    elif scenario == "hidden_youtube":
        source.link_destinations = ["https://youtu.be/synthetic"]
    elif scenario == "unknown_links":
        source.link_destinations = null()
    elif scenario == "draft_youtube":
        output.rewritten_text = "https://youtu.be/synthetic"
    elif scenario == "fact_changed":
        output.rewritten_text = "Открыты 4 линии на заводе."
    elif scenario == "source_filter":
        session.add(
            models.MappingFilterPolicyModel(
                mapping_id=1,
                allowed_media_types=[],
                blocked_domains=[],
                ad_markers=[],
            )
        )
    elif scenario == "credit_filter":
        session.add(
            models.MappingFilterPolicyModel(
                mapping_id=1,
                allowed_media_types=["photo", "text"],
                blocked_domains=["commons.wikimedia.org"],
                ad_markers=[],
            )
        )
    elif scenario == "job_pending":
        job.state, job.selected_asset_id = "QUEUED", None
    elif scenario == "stale_media_binding":
        job.binding_sha256 = "0" * 64
    elif scenario == "asset_not_selected":
        other = models.MediaAssetModel(
            storage_key="unselected.png",
            sha256="a" * 64,
            mime_type="image/png",
            origin="LICENSED_LIBRARY",
            license_code="CC0",
            attribution="",
            tags="[]",
        )
        session.add(other)
        session.flush()
        job.selected_asset_id = other.id
    elif scenario == "blank_credit":
        asset.attribution = " "
    elif scenario == "invalid_provenance":
        asset.origin, asset.source_content_key, asset.license_code = "SOURCE", KEY, "OWNED"
    else:
        raise AssertionError("Unknown synthetic mutation")


UNSAFE = [
    "reject",
    "protected_negative",
    "unreviewed",
    "rewrite_job",
    "new_source",
    "deleted_source",
    "missing_mapping",
    "foreign_channel",
    "foreign_donor",
    "mapping_policy",
    "source_policy",
    "candidate_state",
    "video",
    "album",
    "protected",
    "unknown_protection",
    "hidden_youtube",
    "unknown_links",
    "draft_youtube",
    "fact_changed",
    "source_filter",
    "credit_filter",
    "job_pending",
    "stale_media_binding",
    "asset_not_selected",
    "blank_credit",
    "invalid_provenance",
]


@pytest.mark.parametrize("scenario", UNSAFE)
def test_current_unsafe_context_never_returns_a_review_binding(library_store, scenario):
    factory, root, images = library_store
    with factory.begin() as session:
        mutate(session, scenario)
    before = counts(factory)
    with factory() as session, pytest.raises((PermissionError, ValueError)):
        resolver(session, root).resolve(1)
    assert counts(factory) == before
    assert images.calls == ["search", "download"]


@pytest.mark.parametrize(
    "scenario", ["reject", "new_source", "foreign_donor", "mapping_policy", "unreviewed"]
)
def test_independent_sql_change_during_decode_cannot_return_cached_binding(
    library_store, monkeypatch, scenario
):
    factory, root, _ = library_store
    read = LocalMediaSelectionService._read_photo
    changed = False

    def interleaved(self, key):
        nonlocal changed
        value = read(self, key)
        if not changed:
            changed = True
            with factory.begin() as independent:
                mutate(independent, scenario)
        return value

    monkeypatch.setattr(LocalMediaSelectionService, "_read_photo", interleaved)
    with factory() as session, pytest.raises((PermissionError, ValueError)):
        resolver(session, root).resolve(1)


def test_valid_but_changed_attribution_invalidates_previous_human_review(library_store):
    factory, root, _ = library_store
    from newsflow.domain.illustration_relevance import (
        HumanIllustrationReview,
        IllustrationVerdict,
        assess_illustration_review,
    )

    with factory() as session:
        original = resolver(session, root).resolve(1)
    evidence = HumanIllustrationReview(
        original,
        1,
        IllustrationVerdict.APPROVED_ILLUSTRATION,
        True,
        "Synthetic illustration, not an event photo",
        NOW,
    )
    with factory.begin() as session:
        session.get(models.MediaAssetModel, 1).attribution += "\nSynthetic additional credit"
    with factory() as session:
        current = resolver(session, root).resolve(1)
    assert current == replace(original, asset_metadata_sha256=current.asset_metadata_sha256)
    assert current.asset_metadata_sha256 != original.asset_metadata_sha256
    assert assess_illustration_review(evidence, current=current, now=NOW).allowed is False


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_persisted_job_success_does_not_approve_missing_or_changed_photo_bytes(
    library_store, damage
):
    factory, root, _ = library_store
    with factory() as session:
        asset = session.get(models.MediaAssetModel, 1)
        path = root / asset.storage_key
    if damage == "missing":
        path.unlink()  # Exact decoded synthetic fixture owned by this test only.
    else:
        path.write_bytes(b"changed synthetic bytes")
    with factory() as session, pytest.raises((PermissionError, ValueError)):
        resolver(session, root).resolve(1)


def test_replaced_photo_after_first_decode_is_rechecked_not_trusted_from_returned_hash(
    library_store, monkeypatch
):
    factory, root, _ = library_store
    read = LocalMediaSelectionService._read_photo
    changed = False

    def interleaved(self, key):
        nonlocal changed
        result = read(self, key)
        if not changed:
            changed = True
            (root / key).write_bytes(b"replacement after first decode")
        return result

    monkeypatch.setattr(LocalMediaSelectionService, "_read_photo", interleaved)
    with factory() as session, pytest.raises((PermissionError, ValueError)):
        resolver(session, root).resolve(1)


def test_foreign_job_output_cannot_make_channel_draft_ambiguously_approved(library_store):
    factory, root, _ = library_store
    with factory.begin() as session:
        job = models.RewriteJobModel(
            content_key=KEY + ":foreign",
            output_channel_id=2,
            idempotency_key="another-synthetic-draft",
            state="SUCCEEDED",
        )
        session.add(job)
        session.flush()
        session.add(
            models.RewriteOutputModel(
                rewrite_job_id=job.id,
                output_channel_id=1,
                content_key=KEY,
                rewritten_text=DRAFT,
                approval_state="APPROVED",
                approval_method="MANUAL",
            )
        )
    with factory() as session, pytest.raises(PermissionError, match="UNAMBIGUOUS"):
        resolver(session, root).resolve(1)


def test_reject_first_ingestion_has_no_rewrite_jobs_usage_or_illustration_binding(
    mapping_store, tmp_path
):
    engine = create_engine(mapping_store[0])
    try:
        with sessionmaker(engine)() as session:
            result = DurableIngestionWorkflow(
                session, configured_mapping_id=mapping_store[1][0]
            ).ingest(
                TelegramMessage("1", "-1001234567890", 20, "Synthetic protected report"),
                observed_at=NOW,
                protected_entities=("Protected",),
                sentiment="negative",
                framing="hostile",
            )
            assert result.status == "REJECTED_EDITORIAL"
            assert session.scalar(select(models.EditorialDecisionModel)).rewrite_allowed is False
            assert session.scalar(select(models.RewriteJobModel)) is None
            assert session.scalar(select(models.RewriteUsageModel)) is None
            with pytest.raises(LookupError):
                resolver(session, tmp_path).resolve(1)
    finally:
        engine.dispose()
