"""Create-only authenticated channel baseline, before any source history poll.

This is not a recovery/reset API: an existing poll, source or tombstone requires
an explicit resynchronization policy. No network call holds database locks.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.models import (
    ChannelDifferenceCursorModel,
    ChannelMappingModel,
    DonorChannel,
    DonorIngestionCursorModel,
    IncomingPostModel,
    OutboxEventModel,
    SourceDeletionModel,
    TelegramAccount,
)
from newsflow.providers.telegram import (
    FloodWait,
    SessionUnavailable,
    TelegramChannelCheckpoint,
    validate_difference_request,
)
from newsflow.services.channel_difference_runner import _clock, _utc


@dataclass(frozen=True, slots=True)
class _Context:
    account_id: int
    user_id: int
    channel_id: int
    mappings: tuple
    session_digest: str = field(repr=False)


class ChannelBaselineService:
    def __init__(self, session_factory, *, provider, clock=lambda: datetime.now(UTC)):
        self._sessions, self._provider, self._clock = session_factory, provider, clock

    def _inspect(self, session, donor_id):
        now = _clock(self._clock())
        donor = session.get(DonorChannel, donor_id, populate_existing=True, with_for_update=True)
        if donor is None:
            return "DONOR_UNAVAILABLE", None
        cursor = session.get(
            ChannelDifferenceCursorModel, donor_id, populate_existing=True, with_for_update=True
        )
        account = session.get(
            TelegramAccount, donor.telegram_account_id, populate_existing=True, with_for_update=True
        )
        if cursor is not None:
            binding = (
                donor.telegram_account_id,
                None if account is None else account.telegram_user_id,
                donor.telegram_channel_id,
            )
            actual = (
                cursor.telegram_account_id,
                cursor.telegram_user_id,
                cursor.telegram_channel_id,
            )
            return ("ALREADY_INITIALIZED" if actual == binding else "BASELINE_CONFLICT"), None
        if (
            account is None
            or account.health_status != "CONNECTED"
            or not account.encrypted_session
            or (account.cooldown_until is not None and _utc(account.cooldown_until) > now)
        ):
            return "ACCOUNT_UNAVAILABLE", None
        if type(account.telegram_user_id) is not int or not 0 < account.telegram_user_id < 2**63:
            return "ACCOUNT_UNAVAILABLE", None
        validate_difference_request(str(account.id), str(donor.telegram_channel_id), 1, 10)
        # Even an empty completed poll is legacy evidence, not proof of a new donor.
        poll = session.get(
            DonorIngestionCursorModel, donor_id, populate_existing=True, with_for_update=True
        )
        identity = (str(account.id), str(donor.telegram_channel_id))
        source = session.scalar(
            select(IncomingPostModel.id)
            .where(
                IncomingPostModel.telegram_account_id == identity[0],
                IncomingPostModel.donor_channel_id == identity[1],
            )
            .limit(1)
        )
        deleted = session.scalar(
            select(SourceDeletionModel.telegram_message_id)
            .where(
                SourceDeletionModel.telegram_account_id == identity[0],
                SourceDeletionModel.donor_channel_id == identity[1],
            )
            .limit(1)
        )
        aggregate = f"{donor_id}:{account.id}:{donor.telegram_channel_id}"
        recorded = session.scalar(
            select(OutboxEventModel.id)
            .where(OutboxEventModel.idempotency_key == f"channel.baseline_recorded:{aggregate}")
            .limit(1)
        )
        if poll is not None or source is not None or deleted is not None or recorded is not None:
            return "LEGACY_SYNC_REQUIRED", None
        mappings = tuple(
            session.execute(
                select(ChannelMappingModel.id, ChannelMappingModel.output_channel_id)
                .where(ChannelMappingModel.donor_channel_id == donor_id)
                .order_by(ChannelMappingModel.id)
                .limit(101)
                .with_for_update()
            ).all()
        )
        if not mappings or len(mappings) > 100:
            return "MAPPING_UNAVAILABLE", None
        return "READY", _Context(
            account.id,
            account.telegram_user_id,
            donor.telegram_channel_id,
            mappings,
            sha256(account.encrypted_session.encode()).hexdigest(),
        )

    def bootstrap(self, donor_id):
        if type(donor_id) is not int or not 0 < donor_id <= 2147483647:
            raise ValueError("Canonical donor identity required")
        _clock(self._clock())
        try:
            with self._sessions.begin() as session:
                status, context = self._inspect(session, donor_id)
            if status != "READY":
                return status
            try:
                checkpoint = self._provider.channel_checkpoint(
                    str(context.account_id), str(context.channel_id)
                )
                if not isinstance(checkpoint, TelegramChannelCheckpoint):
                    raise TypeError("Authenticated immutable checkpoint required")
                checkpoint.__post_init__()
                if (checkpoint.account_id, checkpoint.user_id, checkpoint.donor_identifier) != (
                    str(context.account_id),
                    context.user_id,
                    str(context.channel_id),
                ):
                    raise ValueError("Foreign checkpoint")
            except FloodWait as exc:
                if type(exc.seconds) is not int or not 1 <= exc.seconds <= 2147483647:
                    return "FAILED_PROVIDER_CONTRACT"
                return self._health_failure(donor_id, context, "COOLDOWN", exc.seconds)
            except SessionUnavailable:
                return self._health_failure(donor_id, context, "SESSION_INVALID")
            except (TimeoutError, ConnectionError, OSError):
                return "RETRY_PROVIDER"
            except (TypeError, ValueError, LookupError):
                return "FAILED_PROVIDER_CONTRACT"
            with self._sessions.begin() as session:
                status, fresh = self._inspect(session, donor_id)
                if status == "ALREADY_INITIALIZED" or status == "BASELINE_CONFLICT":
                    return status
                if status == "LEGACY_SYNC_REQUIRED":
                    return status
                if status != "READY" or fresh != context:
                    return "STALE_CONTEXT"
                now = _clock(self._clock())
                session.add(
                    ChannelDifferenceCursorModel(
                        donor_channel_id=donor_id,
                        telegram_account_id=context.account_id,
                        telegram_user_id=context.user_id,
                        telegram_channel_id=context.channel_id,
                        pts=checkpoint.pts,
                        available_at=now,
                    )
                )
                aggregate = f"{donor_id}:{context.account_id}:{context.channel_id}"
                session.add(
                    OutboxEventModel(
                        event_type="channel.baseline_recorded",
                        aggregate_key=aggregate,
                        idempotency_key=f"channel.baseline_recorded:{aggregate}",
                        created_at=now,
                    )
                )
                session.flush()
            return "BASELINE_RECORDED"
        except SQLAlchemyError:
            return "RETRY_STORAGE"

    def _health_failure(self, donor_id, context, code, seconds=0):
        with self._sessions.begin() as session:
            status, fresh = self._inspect(session, donor_id)
            if status != "READY" or fresh != context:
                return "STALE_CONTEXT"
            account = session.get(TelegramAccount, context.account_id)
            now = _clock(self._clock())
            account.health_status = code
            account.health_checked_at = max(
                _utc(account.health_checked_at) if account.health_checked_at else now, now
            )
            if code == "COOLDOWN":
                account.cooldown_until = max(
                    _utc(account.cooldown_until) if account.cooldown_until else now,
                    now + timedelta(seconds=seconds),
                )
        return code
