"""Read-only persisted synchronization diagnostics; not a live Telegram check."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    ChannelDifferenceCursorModel,
    DonorChannel,
    DonorIngestionCursorModel,
    IncomingPostModel,
    OutboxEventModel,
    SourceDeletionModel,
    TelegramAccount,
)
from newsflow.services.channel_sync_enforcement import sync_enforced
from newsflow.services.source_revisions import source_identity_sync_blocked


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class DonorSyncStatusReader:
    def __init__(self, session: Session):
        self._session = session

    def read(self, donor_id: int, *, now: datetime) -> dict[str, object]:
        if type(donor_id) is not int or not 0 < donor_id <= 2147483647:
            raise LookupError("Donor not found")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Status time must be timezone-aware")
        session = self._session
        donor = session.get(DonorChannel, donor_id, populate_existing=True)
        if donor is None:
            raise LookupError("Donor not found")
        owner = session.get(TelegramAccount, donor.telegram_account_id, populate_existing=True)
        cursor = session.get(ChannelDifferenceCursorModel, donor_id, populate_existing=True)
        enforced = sync_enforced(session)
        blocked = source_identity_sync_blocked(
            session, str(donor.telegram_account_id), str(donor.telegram_channel_id)
        )
        retry = [
            _utc(value)
            for value in (
                None if cursor is None else cursor.available_at,
                None if owner is None else owner.cooldown_until,
            )
            if value is not None
        ]
        if cursor is not None and (
            owner is None
            or (cursor.telegram_account_id, cursor.telegram_user_id, cursor.telegram_channel_id)
            != (donor.telegram_account_id, owner.telegram_user_id, donor.telegram_channel_id)
        ):
            state = "INVALID_BASELINE"
        elif cursor is not None and cursor.last_error_code == "GAP_UNRESOLVED":
            state = "GAP_UNRESOLVED"
        elif not enforced:
            state = "NOT_ENFORCED"
        elif (
            owner is None
            or not owner.encrypted_session
            or owner.health_status not in {"CONNECTED", "COOLDOWN"}
        ):
            state = "ACCOUNT_UNAVAILABLE"
        elif owner.health_status == "COOLDOWN":
            state = "COOLDOWN"
        elif cursor is None:
            state = "LEGACY_SYNC_REQUIRED" if self._legacy(donor) else "BASELINE_REQUIRED"
        elif (cursor.claim_token is None) != (cursor.lease_expires_at is None):
            state = "INVALID_BASELINE"
        elif cursor.claim_token is not None:
            state = "SYNC_IN_PROGRESS" if _utc(cursor.lease_expires_at) > now else "RECOVERY_DUE"
        elif cursor.last_error_code is not None:
            state = "WAIT_RETRY" if _utc(cursor.available_at) > now else "RECOVERY_DUE"
        else:
            state = "INVALID_BASELINE" if blocked else "READY"
        return {
            "donor_id": donor_id,
            "state": state,
            "enforcement_enabled": enforced,
            "source_processing_blocked": blocked,
            "network_checked": False,
            "pts": None if cursor is None else cursor.pts,
            "retry_at": max(retry).isoformat() if retry else None,
        }

    def _legacy(self, donor: DonorChannel) -> bool:
        session = self._session
        if session.get(DonorIngestionCursorModel, donor.id) is not None:
            return True
        identity = (str(donor.telegram_account_id), str(donor.telegram_channel_id))
        for model, column in (
            (IncomingPostModel, IncomingPostModel.id),
            (SourceDeletionModel, SourceDeletionModel.telegram_message_id),
        ):
            if (
                session.scalar(
                    select(column)
                    .where(
                        model.telegram_account_id == identity[0],
                        model.donor_channel_id == identity[1],
                    )
                    .limit(1)
                )
                is not None
            ):
                return True
        aggregate = f"{donor.id}:{donor.telegram_account_id}:{donor.telegram_channel_id}"
        return (
            session.scalar(
                select(OutboxEventModel.id)
                .where(OutboxEventModel.idempotency_key == f"channel.baseline_recorded:{aggregate}")
                .limit(1)
            )
            is not None
        )
