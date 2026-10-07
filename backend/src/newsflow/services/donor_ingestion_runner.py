"""Bounded at-least-once new-message polling; never classifies unknown text neutral.

No network operation runs inside a DB transaction. Leased progress advances only
after all current mappings commit. Old-message edit catch-up is a separate contract.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import (
    ChannelMappingModel,
    DonorChannel,
    DonorIngestionCursorModel,
    TelegramAccount,
)
from newsflow.providers.telegram import (
    FloodWait,
    SessionUnavailable,
    TelegramMessage,
    TelegramProvider,
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class DonorPollClaim:
    donor_id: int
    account_id: int
    telegram_channel_id: int
    after_id: int
    token: str


class DonorIngestionRunner:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        provider: TelegramProvider,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        page_size: int = 50,
    ):
        if not 1 <= page_size <= 100:
            raise ValueError("History page size must be between 1 and 100")
        self._sessions = session_factory
        self._provider = provider
        self._clock = clock
        self._page_size = page_size

    @staticmethod
    def _validate_time(now):
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Polling time must be timezone-aware")
        return now.astimezone(UTC)

    def claim(self, donor_id: int, *, now: datetime) -> DonorPollClaim | None:
        now = self._validate_time(now)
        with self._sessions() as session, session.begin():
            # The donor row serializes cursor initialization as well as claims.
            donor = session.scalar(
                select(DonorChannel)
                .where(DonorChannel.id == donor_id)
                .with_for_update(skip_locked=True)
            )
            if donor is None:
                return None
            if (
                session.scalar(
                    select(ChannelMappingModel.id)
                    .where(ChannelMappingModel.donor_channel_id == donor_id)
                    .limit(1)
                )
                is None
            ):
                return None
            account = session.get(TelegramAccount, donor.telegram_account_id)
            if account is None or account.health_status == "SESSION_INVALID":
                return None
            if account.cooldown_until is not None and _utc(account.cooldown_until) > now:
                return None
            cursor = session.scalar(
                select(DonorIngestionCursorModel)
                .where(DonorIngestionCursorModel.donor_channel_id == donor_id)
                .with_for_update()
            )
            if cursor is None:
                cursor = DonorIngestionCursorModel(
                    donor_channel_id=donor_id, last_message_id=0, available_at=now
                )
                session.add(cursor)
            if _utc(cursor.available_at) > now:
                return None
            if cursor.lease_expires_at is not None and _utc(cursor.lease_expires_at) > now:
                return None
            cursor.claim_token = str(uuid4())
            cursor.lease_expires_at = now + timedelta(seconds=60)
            cursor.last_error_code = None
            return DonorPollClaim(
                donor_id,
                donor.telegram_account_id,
                donor.telegram_channel_id,
                cursor.last_message_id,
                cursor.claim_token,
            )

    def run_donor(self, donor_id: int, *, now: datetime) -> str:
        claim = self.claim(donor_id, now=now)
        return "IDLE" if claim is None else self.execute(claim)

    def _owned(self, session: Session, claim: DonorPollClaim) -> DonorIngestionCursorModel | None:
        cursor = session.scalar(
            select(DonorIngestionCursorModel)
            .where(DonorIngestionCursorModel.donor_channel_id == claim.donor_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        now = self._validate_time(self._clock())
        if (
            cursor is None
            or cursor.claim_token != claim.token
            or cursor.lease_expires_at is None
            or _utc(cursor.lease_expires_at) <= now
        ):
            return None
        return cursor

    def execute(self, claim: DonorPollClaim) -> str:
        with self._sessions() as session, session.begin():
            if self._owned(session, claim) is None:
                return "STALE_CLAIM"
        try:
            messages = self._provider.history(
                str(claim.account_id),
                str(claim.telegram_channel_id),
                after_id=claim.after_id,
                limit=self._page_size,
            )
        except FloodWait as exc:
            return self._failure(claim, "COOLDOWN", delay=max(1, exc.seconds), health="COOLDOWN")
        except SessionUnavailable:
            return self._failure(claim, "SESSION_INVALID", health="SESSION_INVALID")
        except (TimeoutError, ConnectionError, OSError):
            return self._failure(claim, "RETRY_PROVIDER", delay=30)
        except (ValueError, TypeError, LookupError):
            return self._failure(claim, "FAILED_PROVIDER_CONTRACT", delay=30)
        if not self._valid_history(messages, claim):
            return self._failure(claim, "FAILED_PROVIDER_CONTRACT", delay=30)
        try:
            for event in messages:
                with self._sessions() as session:
                    mappings = list(
                        session.scalars(
                            select(ChannelMappingModel.id)
                            .where(ChannelMappingModel.donor_channel_id == claim.donor_id)
                            .order_by(ChannelMappingModel.id)
                        )
                    )
                if not mappings:
                    return self._failure(claim, "MAPPING_REMOVED", delay=30)
                for mapping_id in mappings:
                    with self._sessions() as session:
                        result = DurableIngestionWorkflow(
                            session,
                            configured_mapping_id=mapping_id,
                            transaction_guard=lambda current: (
                                self._owned(current, claim) is not None
                            ),
                        ).ingest(event, observed_at=self._validate_time(self._clock()))
                        if result.status == "STALE_CLAIM":
                            return "STALE_CLAIM"
                with self._sessions() as session, session.begin():
                    cursor = self._owned(session, claim)
                    if cursor is None:
                        return "STALE_CLAIM"
                    cursor.last_message_id = max(cursor.last_message_id, event.message_id)
                    cursor.lease_expires_at = self._validate_time(self._clock()) + timedelta(
                        seconds=60
                    )
            with self._sessions() as session, session.begin():
                cursor = self._owned(session, claim)
                if cursor is None:
                    return "STALE_CLAIM"
                cursor.claim_token = None
                cursor.lease_expires_at = None
                cursor.available_at = self._validate_time(self._clock())
            return "POLL_COMPLETE"
        except (SQLAlchemyError, ValueError, LookupError):
            return self._failure(claim, "RETRY_PIPELINE", delay=30)

    def _valid_history(self, messages, claim) -> bool:
        if not isinstance(messages, tuple) or len(messages) > self._page_size:
            return False
        previous = claim.after_id
        for event in messages:
            if (
                not isinstance(event, TelegramMessage)
                or event.account_id != str(claim.account_id)
                or event.donor_identifier != str(claim.telegram_channel_id)
                or isinstance(event.message_id, bool)
                or not isinstance(event.message_id, int)
                or event.message_id <= previous
            ):
                return False
            previous = event.message_id
        return True

    def _failure(self, claim, code, *, delay=30, health=None):
        now = self._validate_time(self._clock())
        with self._sessions() as session, session.begin():
            cursor = self._owned(session, claim)
            if cursor is None:
                return "STALE_CLAIM"
            cursor.last_error_code = code
            cursor.available_at = now + timedelta(seconds=delay)
            cursor.claim_token = None
            cursor.lease_expires_at = None
            if health is not None:
                account = session.get(TelegramAccount, claim.account_id)
                account.health_status = health
                account.health_checked_at = now
                account.cooldown_until = (
                    now + timedelta(seconds=delay) if health == "COOLDOWN" else None
                )
        return code
