"""Fresh canonical human-review context. No writes, providers or publication.

Only successful currently bound library acquisition is eligible for review;
topic tags and client hashes are never evidence of image relevance. This does
not grant relevance approval or remove the independent library publication hold.
"""

import json
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.illustration_relevance import IllustrationBinding
from newsflow.persistence.models import (
    ChannelMappingModel,
    DonorChannel,
    IncomingPostModel,
    MediaAcquisitionJobModel,
    MediaAssetModel,
    OutputChannel,
    RewriteOutputModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.automatic_approval import approval_is_current
from newsflow.services.durable_media_runner import _digest
from newsflow.services.fact_guard import FactGuard, FactPreservationBlocked
from newsflow.services.mapping_filters import candidate_technical_allowed, mapping_filter
from newsflow.services.media_selection import LocalMediaSelectionService, MediaSelectionBlocked
from newsflow.services.semantic_facts import text_digest
from newsflow.services.source_revisions import source_revision


@dataclass(frozen=True, slots=True)
class _Context:
    binding: IllustrationBinding
    storage_key: str
    mime_type: str
    candidate_state: str
    approval_method: str
    approved_at: object
    media_job_id: int
    media_job_binding: str


class IllustrationBindingResolver:
    def __init__(self, session: Session, media_root: Path):
        self._session, self._root = session, media_root

    def _clean(self) -> None:
        if self._session.new or self._session.dirty or self._session.deleted:
            raise ValueError("Illustration context requires a clean session")

    def _snapshot(self, candidate_id: int) -> _Context:
        self._clean()
        session = self._session
        local = LocalMediaSelectionService(session, self._root)
        candidate = local._require_current_candidate(candidate_id)
        if candidate.media_policy != "LICENSED_LIBRARY" or candidate.mapping_id is None:
            raise MediaSelectionBlocked("CURRENT_MAPPED_LIBRARY_CANDIDATE_REQUIRED")
        mapping = session.get(ChannelMappingModel, candidate.mapping_id, populate_existing=True)
        donor = (
            session.get(DonorChannel, mapping.donor_channel_id, populate_existing=True)
            if mapping
            else None
        )
        source = source_revision(session, candidate.content_key)
        post = (
            session.get(IncomingPostModel, source.incoming_post_id, populate_existing=True)
            if source
            else None
        )
        channel = session.get(OutputChannel, candidate.output_channel_id, populate_existing=True)
        if (
            mapping is None
            or donor is None
            or source is None
            or post is None
            or channel is None
            or mapping.output_channel_id != candidate.output_channel_id
            or mapping.media_policy != "LICENSED_LIBRARY"
            or str(donor.telegram_account_id) != post.telegram_account_id
            or str(donor.telegram_channel_id) != post.donor_channel_id
            or source.media_type not in {"text", "photo"}
            or source.album_id is not None
            or source.media_protected is not False
            or source.source_updated_at is None
            or not candidate_technical_allowed(session, candidate)
        ):
            raise MediaSelectionBlocked("CURRENT_CANONICAL_ILLUSTRATION_CONTEXT_REQUIRED")
        outputs = session.scalars(
            select(RewriteOutputModel)
            .where(
                RewriteOutputModel.content_key == candidate.content_key,
                RewriteOutputModel.output_channel_id == candidate.output_channel_id,
            )
            .limit(2)
            .execution_options(populate_existing=True)
        ).all()
        if len(outputs) != 1 or not approval_is_current(session, outputs[0]):
            raise MediaSelectionBlocked("CURRENT_UNAMBIGUOUS_APPROVED_DRAFT_REQUIRED")
        output = outputs[0]
        source_hash, draft_hash = (
            text_digest(source.source_text),
            text_digest(output.rewritten_text),
        )
        job = session.scalar(
            select(MediaAcquisitionJobModel)
            .where(
                MediaAcquisitionJobModel.candidate_id == candidate_id,
            )
            .order_by(MediaAcquisitionJobModel.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        expected_job = _digest(
            (
                candidate.content_key,
                source.id,
                source_hash,
                output.id,
                draft_hash,
                source.source_text,
            )
        )
        if (
            job is None
            or job.state != "SUCCEEDED"
            or job.acquisition_mode != "LICENSED_LIBRARY"
            or job.selected_asset_id is None
            or job.binding_sha256 != expected_job
        ):
            raise MediaSelectionBlocked("CURRENT_LIBRARY_MEDIA_SELECTION_REQUIRED")
        asset = session.get(MediaAssetModel, job.selected_asset_id, populate_existing=True)
        if (
            asset is None
            or asset.origin != "LICENSED_LIBRARY"
            or asset.source_content_key is not None
            or asset.license_code not in {"CC0", "CC-BY"}
            or type(asset.attribution) is not str
            or len(asset.attribution) > 2048
            or "\x00" in asset.attribution
            or (asset.license_code == "CC-BY" and not asset.attribution.strip())
        ):
            raise MediaSelectionBlocked("CURRENT_LIBRARY_RIGHTS_REQUIRED")
        try:
            FactGuard().require_preserved(source.source_text, output.rewritten_text)
            filters = mapping_filter(session, mapping, intake=False)
            draft = TelegramMessage(
                post.telegram_account_id,
                post.donor_channel_id,
                post.telegram_message_id,
                output.rewritten_text,
                media_type=source.media_type,
                media_protected=False,
                media_id=source.media_id,
            )
            final_text = output.rewritten_text + (
                "\n\n" + asset.attribution if asset.attribution else ""
            )
            if (
                not filters.evaluate(draft).accepted
                or not filters.evaluate(replace(draft, text=final_text)).accepted
            ):
                raise MediaSelectionBlocked("CURRENT_ILLUSTRATION_TEXT_OR_CREDIT_FILTER_BLOCKED")
        except (FactPreservationBlocked, ValueError, TypeError):
            raise MediaSelectionBlocked("CURRENT_ILLUSTRATION_FACT_OR_FILTER_BLOCKED") from None
        metadata_hash = text_digest(
            json.dumps(
                {
                    "version": 1,
                    "origin": asset.origin,
                    "storage_key": asset.storage_key,
                    "mime_type": asset.mime_type,
                    "license_code": asset.license_code,
                    "attribution": asset.attribution,
                    "source_content_key": asset.source_content_key,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        binding = IllustrationBinding(
            candidate.id,
            candidate.output_channel_id,
            mapping.id,
            candidate.content_key,
            source.id,
            source_hash,
            output.id,
            draft_hash,
            asset.id,
            asset.sha256,
            metadata_hash,
        )
        return _Context(
            binding,
            asset.storage_key,
            asset.mime_type,
            candidate.state,
            output.approval_method,
            output.approved_at,
            job.id,
            job.binding_sha256,
        )

    def resolve(self, candidate_id: int) -> IllustrationBinding:
        self._clean()
        if type(candidate_id) is not int or not 0 < candidate_id <= 2**63 - 1:
            raise ValueError("Canonical positive illustration candidate identity required")
        first = self._snapshot(candidate_id)
        local = LocalMediaSelectionService(self._session, self._root)
        # Bounded repeated decode plus fresh SQL after each read. A cache, file
        # replacement or concurrent revocation cannot silently reuse context.
        for _ in range(2):
            digest, mime = local._read_photo(first.storage_key)
            if digest != first.binding.media_sha256 or mime != first.mime_type:
                raise MediaSelectionBlocked("ILLUSTRATION_MEDIA_IDENTITY_CHANGED")
            if self._snapshot(candidate_id) != first:
                raise MediaSelectionBlocked("ILLUSTRATION_BINDING_CHANGED_DURING_READ")
        return first.binding
