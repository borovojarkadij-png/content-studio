"""Replay durable quarantined observations, never network or fabricated PASS.

Each mapping commits independently through normal ingestion. The retained outbox
obligation completes only after all current mappings under the same sync binding.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import String, cast, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import aliased

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import (
    ChannelDifferenceCursorModel,
    ContentRevisionModel,
    DonorChannel,
    IncomingPostModel,
    OutboxEventModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.channel_difference_runner import ChannelDifferenceRunner, _clock, _utc
from newsflow.services.source_revisions import source_identity_deleted, source_revision


@dataclass(frozen=True, slots=True)
class _ReplayContext:
    donor_id: int
    account_id: int
    user_id: int
    channel_id: int
    pts: int
    mappings: tuple
    mapping_binding: str
    session_digest: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReplayBatch:
    cursor: int
    outcomes: tuple[tuple[int, str], ...]


class SourceSyncReplayService:
    def __init__(self, session_factory, *, clock=lambda: datetime.now(UTC)):
        self._sessions, self._clock = session_factory, clock

    def run_batch(self, *, after_id=0, limit=16):
        if (
            type(after_id) is not int
            or after_id < 0
            or type(limit) is not int
            or not 1 <= limit <= 16
        ):
            raise ValueError("Replay scan requires bounded canonical cursor/limit")
        _clock(self._clock())
        completed = aliased(OutboxEventModel)
        with self._sessions() as session:

            def scan(after):
                return tuple(
                    session.scalars(
                        select(OutboxEventModel.id)
                        .where(
                            OutboxEventModel.event_type == "source.sync_quarantined",
                            OutboxEventModel.id > after,
                            ~select(completed.id)
                            .where(
                                completed.idempotency_key
                                == "source.sync_replay_completed:" + OutboxEventModel.aggregate_key
                            )
                            .exists(),
                        )
                        .order_by(OutboxEventModel.id)
                        .limit(limit)
                    )
                )

            ids = scan(after_id)
            if not ids and after_id:
                ids = scan(0)
        return ReplayBatch(
            ids[-1] if ids else 0, tuple((marker_id, self.replay(marker_id)) for marker_id in ids)
        )

    def _inspect(self, session, key):
        now = _clock(self._clock())
        revision = source_revision(session, key)
        if revision is None:
            return "INVALID_OBLIGATION", None, None
        post = session.get(IncomingPostModel, revision.incoming_post_id, populate_existing=True)
        if (
            source_identity_deleted(
                session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
            )
            or session.scalar(
                select(func.max(ContentRevisionModel.revision_number)).where(
                    ContentRevisionModel.incoming_post_id == post.id
                )
            )
            != revision.revision_number
        ):
            return "SUPERSEDED", None, None
        donor = session.scalar(
            select(DonorChannel)
            .where(
                cast(DonorChannel.telegram_account_id, String) == post.telegram_account_id,
                cast(DonorChannel.telegram_channel_id, String) == post.donor_channel_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if donor is None:
            return "WAIT_SYNC", None, None
        cursor = session.get(
            ChannelDifferenceCursorModel, donor.id, populate_existing=True, with_for_update=True
        )
        account = session.get(
            TelegramAccount, donor.telegram_account_id, populate_existing=True, with_for_update=True
        )
        if (
            cursor is None
            or account is None
            or cursor.last_error_code is not None
            or cursor.claim_token is not None
            or cursor.lease_expires_at is not None
            or account.health_status != "CONNECTED"
            or not account.encrypted_session
            or (account.cooldown_until is not None and _utc(account.cooldown_until) > now)
            or (cursor.telegram_account_id, cursor.telegram_user_id, cursor.telegram_channel_id)
            != (account.id, account.telegram_user_id, donor.telegram_channel_id)
        ):
            return "WAIT_SYNC", None, None
        mappings, binding = ChannelDifferenceRunner._mapping_snapshot(session, donor.id, lock=True)
        if not mappings:
            return "WAIT_SYNC", None, None
        # The early max/deletion reads are only a cheap precheck. A separate
        # writer may commit while donor/cursor/account/mapping locks are acquired.
        # Match ordinary ingress lock order (mapping -> post), then re-read the
        # immutable latest revision before classifying or completing an obligation.
        post = session.get(
            IncomingPostModel,
            revision.incoming_post_id,
            populate_existing=True,
            with_for_update=True,
        )
        if post is None:
            return "INVALID_OBLIGATION", None, None
        if (
            source_identity_deleted(
                session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
            )
            or session.scalar(
                select(func.max(ContentRevisionModel.revision_number)).where(
                    ContentRevisionModel.incoming_post_id == post.id
                )
            )
            != revision.revision_number
        ):
            return "SUPERSEDED", None, None
        if (post.telegram_account_id, post.donor_channel_id) != (
            str(account.id),
            str(donor.telegram_channel_id),
        ):
            return "WAIT_SYNC", None, None
        context = _ReplayContext(
            donor.id,
            account.id,
            account.telegram_user_id,
            donor.telegram_channel_id,
            cursor.pts,
            mappings,
            binding,
            sha256(account.encrypted_session.encode()).hexdigest(),
        )
        event = TelegramMessage(
            post.telegram_account_id,
            post.donor_channel_id,
            post.telegram_message_id,
            revision.source_text,
            media_type=revision.media_type,
            album_id=revision.album_id,
            media_id=revision.media_id,
            media_protected=revision.media_protected,
            source_updated_at=_utc(revision.source_updated_at)
            if revision.source_updated_at
            else None,
        )
        return "READY", context, event

    @staticmethod
    def _completed(session, key):
        return (
            session.scalar(
                select(OutboxEventModel.id).where(
                    OutboxEventModel.idempotency_key == f"source.sync_replay_completed:{key}"
                )
            )
            is not None
        )

    def replay(self, marker_id):
        if type(marker_id) is not int or marker_id <= 0:
            raise ValueError("Canonical replay obligation identity required")
        _clock(self._clock())
        try:
            with self._sessions.begin() as session:
                marker = session.get(OutboxEventModel, marker_id, populate_existing=True)
                if marker is None or marker.event_type != "source.sync_quarantined":
                    return "INVALID_OBLIGATION"
                key = marker.aggregate_key
                if marker.idempotency_key != f"source.sync_quarantined:{key}":
                    return "INVALID_OBLIGATION"
                if self._completed(session, key):
                    return "ALREADY_COMPLETED"
                status, context, event = self._inspect(session, key)
            if status not in {"READY", "SUPERSEDED"}:
                return status
            if status == "READY":
                for mapping_id in context.mappings:
                    with self._sessions() as session:
                        result = DurableIngestionWorkflow(
                            session,
                            configured_mapping_id=mapping_id,
                            transaction_guard=lambda current: self._owned(current, key, context),
                        ).ingest(event, observed_at=_clock(self._clock()))
                    if result.status in {"STALE_CLAIM", "MAPPING_REMOVED", "SOURCE_SYNC_REQUIRED"}:
                        return "WAIT_SYNC"
            with self._sessions.begin() as session:
                fresh_status, fresh, _event = self._inspect(session, key)
                if (fresh_status, fresh) != (status, context):
                    return "WAIT_SYNC"
                session.get(
                    OutboxEventModel, marker_id, populate_existing=True, with_for_update=True
                )
                if self._completed(session, key):
                    return "ALREADY_COMPLETED"
                session.add(
                    OutboxEventModel(
                        event_type="source.sync_replay_completed",
                        aggregate_key=key,
                        idempotency_key=f"source.sync_replay_completed:{key}",
                        created_at=_clock(self._clock()),
                    )
                )
                session.flush()
            return "REPLAYED" if status == "READY" else "SUPERSEDED"
        except (SQLAlchemyError, ValueError, TypeError, LookupError):
            return "RETRY_STORAGE"

    def _owned(self, session, key, context):
        status, fresh, _event = self._inspect(session, key)
        return status == "READY" and fresh == context
