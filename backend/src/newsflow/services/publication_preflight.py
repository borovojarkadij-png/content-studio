"""Fresh local publication constraints. No transport, job mutation or provider calls.

This is not Telegram authorization: a future authenticated transport must still
validate the provisioned user, destination permissions and bound request before
sending. Legacy unmapped planning prototypes never qualify for execution.
"""

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from hashlib import sha256

from sqlalchemy import select

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    ChannelMappingModel,
    DonorChannel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutputChannel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    RewriteOutputModel,
    TelegramAccount,
    TelegramPeerModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.automatic_approval import approval_is_current
from newsflow.services.durable_semantic_runner import _aware, _utc
from newsflow.services.fact_guard import FactGuard, FactPreservationBlocked
from newsflow.services.mapping_filters import candidate_technical_allowed, mapping_filter
from newsflow.services.media_job_read import LIBRARY_PUBLICATION_HOLD_CODE, MediaJobReader
from newsflow.services.media_selection import MediaSelectionBlocked, MediaUnavailable
from newsflow.services.publication import PublicationBlocked
from newsflow.services.source_revisions import source_is_current, source_revision


@dataclass(frozen=True, slots=True)
class PublicationEnvelope:
    planned_id: int
    candidate_id: int
    account_id: int
    user_id: int
    output_channel_id: int
    telegram_channel_id: int
    content_key: str
    rewrite_output_id: int
    text: str
    scheduled_for: datetime
    expires_at: datetime
    media_asset_id: int | None
    media_sha256: str | None
    binding_sha256: str


def _hash(value):
    return sha256(value.encode()).hexdigest()


class PublicationPreflight:
    def __init__(self, session_factory, media_root=None):
        self._factory, self._root = session_factory, media_root

    def prepare(self, planned_id: int, *, now: datetime) -> PublicationEnvelope:
        _aware(now)
        if type(planned_id) is not int or planned_id <= 0:
            raise ValueError("Publication identity must be a positive integer")
        # Caller receives an immutable value only after every DB transaction closes.
        with self._factory() as session:
            first = self._prepare(session, planned_id, now=now)
            current = self._prepare(session, planned_id, now=now)
            if current.binding_sha256 != first.binding_sha256:
                raise PublicationBlocked("PUBLICATION_BINDING_CHANGED_DURING_PREFLIGHT")
            return current

    def _prepare(self, session, planned_id, *, now):
        item = session.get(PlannedPublicationModel, planned_id, populate_existing=True)
        if item is None:
            raise LookupError("Planned publication was not found")
        scheduled = _utc(item.scheduled_for)
        expires = scheduled + timedelta(hours=6)
        if item.state != "PLANNED" or scheduled > now or expires <= now:
            raise PublicationBlocked("PUBLICATION_NOT_DUE_OR_EXPIRED")
        candidate = session.get(
            PublicationCandidateModel, item.candidate_id, populate_existing=True
        )
        if (
            candidate is None
            or candidate.state != "SCHEDULED"
            or candidate.output_channel_id != item.output_channel_id
            or candidate.mapping_id is None
            or _utc(candidate.eligible_at) > now
        ):
            raise PublicationBlocked("CURRENT_MAPPED_SCHEDULED_CANDIDATE_REQUIRED")
        decision = session.scalar(
            select(EditorialDecisionModel)
            .where(EditorialDecisionModel.content_key == candidate.content_key)
            .execution_options(populate_existing=True)
        )
        if not editorial_allows_rewrite(decision):
            raise PublicationBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")
        if not source_is_current(session, candidate.content_key):
            raise PublicationBlocked("SOURCE_REVISION_NOT_CURRENT_OR_MISSING")
        source = source_revision(session, candidate.content_key)
        if (
            source is None
            or source.media_type not in {"text", "photo"}
            or source.album_id is not None
            or source.media_protected is not False
            or source.source_updated_at is None
        ):
            raise PublicationBlocked("KNOWN_UNPROTECTED_SINGLE_SOURCE_REQUIRED")
        mapping = session.get(ChannelMappingModel, candidate.mapping_id, populate_existing=True)
        donor = (
            session.get(DonorChannel, mapping.donor_channel_id, populate_existing=True)
            if mapping
            else None
        )
        post = session.get(IncomingPostModel, source.incoming_post_id, populate_existing=True)
        if (
            mapping is None
            or donor is None
            or post is None
            or mapping.output_channel_id != candidate.output_channel_id
            or mapping.media_policy != candidate.media_policy
            or str(donor.telegram_account_id) != post.telegram_account_id
            or str(donor.telegram_channel_id) != post.donor_channel_id
        ):
            raise PublicationBlocked("CURRENT_CANONICAL_MAPPING_REQUIRED")
        if not candidate_technical_allowed(session, candidate):
            raise PublicationBlocked("CURRENT_TECHNICAL_FILTER_BLOCKED")
        output = session.scalar(
            select(RewriteOutputModel)
            .where(
                RewriteOutputModel.content_key == candidate.content_key,
                RewriteOutputModel.output_channel_id == candidate.output_channel_id,
            )
            .execution_options(populate_existing=True)
        )
        if output is None or not approval_is_current(session, output):
            raise PublicationBlocked("CURRENT_APPROVED_CHANNEL_REWRITE_REQUIRED")
        try:
            FactGuard().require_preserved(source.source_text, output.rewritten_text)
        except (FactPreservationBlocked, ValueError):
            raise PublicationBlocked("CURRENT_FACT_ANCHORS_NOT_PRESERVED") from None
        try:
            filters = mapping_filter(session, mapping, intake=False)
            draft_event = TelegramMessage(
                post.telegram_account_id,
                post.donor_channel_id,
                post.telegram_message_id,
                output.rewritten_text,
                media_type=source.media_type,
                media_id=source.media_id,
                media_protected=source.media_protected,
            )
            if not filters.evaluate(draft_event).accepted:
                raise PublicationBlocked("REWRITTEN_TECHNICAL_FILTER_BLOCKED")
        except (ValueError, TypeError):
            raise PublicationBlocked("CURRENT_TECHNICAL_FILTER_INVALID") from None
        channel = session.get(OutputChannel, item.output_channel_id, populate_existing=True)
        account = (
            session.get(TelegramAccount, channel.telegram_account_id, populate_existing=True)
            if channel
            else None
        )
        peer = (
            session.get(
                TelegramPeerModel,
                (channel.telegram_account_id, channel.telegram_channel_id),
                populate_existing=True,
            )
            if channel
            else None
        )
        if (
            channel is None
            or channel.telegram_channel_id >= -1000000000000
            or account is None
            or account.telegram_user_id <= 0
            or not account.encrypted_session
            or account.health_status not in {"CONNECTED", "COOLDOWN"}
            or (account.cooldown_until is not None and _utc(account.cooldown_until) > now)
            or peer is None
            or not peer.encrypted_peer
        ):
            raise PublicationBlocked("PROVISIONED_HEALTHY_OUTPUT_AND_PEER_REQUIRED")
        if candidate.media_policy != "REUSE_SOURCE":
            # Topic matching is not sufficient to approve an illustration's relevance.
            raise PublicationBlocked(LIBRARY_PUBLICATION_HOLD_CODE)
        asset = None
        media_job_id = None
        text = output.rewritten_text
        if source.media_type == "photo":
            try:
                status = MediaJobReader(session, self._root).get_status(candidate.id)
            except (MediaSelectionBlocked, MediaUnavailable, ValueError):
                raise PublicationBlocked("CURRENT_SOURCE_MEDIA_REQUIRED") from None
            if not status["selected_allowed"] or status["illustration"] or status["asset"] is None:
                raise PublicationBlocked("CURRENT_SOURCE_MEDIA_REQUIRED")
            asset = status["asset"]
            media_job_id = status["job_id"]
            if asset["attribution"]:
                text += "\n\n" + asset["attribution"]
        try:
            if not filters.evaluate(replace(draft_event, text=text)).accepted:
                raise PublicationBlocked("FINAL_PUBLICATION_TECHNICAL_FILTER_BLOCKED")
        except (ValueError, TypeError):
            raise PublicationBlocked("CURRENT_TECHNICAL_FILTER_INVALID") from None
        if not text.strip() or len(text.encode("utf-16-le")) // 2 > (1024 if asset else 4096):
            raise PublicationBlocked("TELEGRAM_TEXT_OR_CAPTION_LIMIT")
        snapshot = (
            item.id,
            item.candidate_id,
            item.output_channel_id,
            scheduled.isoformat(),
            candidate.content_key,
            candidate.mapping_id,
            candidate.media_policy,
            decision.id,
            decision.status,
            decision.rewrite_allowed,
            decision.protected_entities,
            decision.sentiment,
            decision.framing,
            source.id,
            source.source_text,
            source.media_type,
            source.media_id,
            source.media_protected,
            source.source_updated_at.isoformat(),
            mapping.donor_channel_id,
            mapping.eligibility_mode,
            mapping.delay_minutes,
            mapping.intake_percent,
            mapping.target_mix_percent,
            mapping.priority,
            sorted(filters.allowed_media_types),
            sorted(filters.blocked_domains),
            filters.ad_markers,
            output.id,
            output.rewrite_job_id,
            output.approval_method,
            output.rewritten_text,
            account.id,
            account.telegram_user_id,
            _hash(account.encrypted_session),
            channel.id,
            channel.telegram_channel_id,
            _hash(peer.encrypted_peer),
            media_job_id,
            asset,
        )
        return PublicationEnvelope(
            item.id,
            candidate.id,
            account.id,
            account.telegram_user_id,
            channel.id,
            channel.telegram_channel_id,
            candidate.content_key,
            output.id,
            text,
            scheduled,
            expires,
            asset["id"] if asset else None,
            asset["sha256"] if asset else None,
            _hash(json.dumps(snapshot, ensure_ascii=False, sort_keys=True)),
        )
