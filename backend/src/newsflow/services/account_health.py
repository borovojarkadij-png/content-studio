"""Durable Telegram account health and reconnect cooldown policy."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.persistence.models import TelegramAccount
from newsflow.providers.telegram import FloodWait, SessionUnavailable, TelegramProvider


class AccountHealthStatus(StrEnum):
    CONNECTED = "CONNECTED"
    COOLDOWN = "COOLDOWN"
    SESSION_INVALID = "SESSION_INVALID"


@dataclass(frozen=True, slots=True)
class AccountHealthResult:
    status: AccountHealthStatus
    reconnect_attempted: bool


class AccountHealthService:
    """Updates account state without repeatedly reconnecting a blocked account."""

    def __init__(self, session: Session, provider: TelegramProvider) -> None:
        self._session = session
        self._provider = provider

    def reconnect(self, account_id: int, *, now: datetime) -> AccountHealthResult:
        """Own the health transaction, including SQLAlchemy's implicit autobegin."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Account health time must be timezone-aware")
        now = now.astimezone(UTC)
        try:
            result = self._reconnect(account_id, now=now)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def _reconnect(self, account_id: int, *, now: datetime) -> AccountHealthResult:
        account = self._session.scalar(
            select(TelegramAccount)
            .where(TelegramAccount.id == account_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if account is None:
            raise LookupError(f"Telegram account {account_id} was not found")
        cooldown = account.cooldown_until
        if cooldown is not None and cooldown.tzinfo is None:
            cooldown = cooldown.replace(tzinfo=UTC)  # SQLite round-trip of UTC storage.
        if cooldown is not None and now < cooldown:
            account.health_status = AccountHealthStatus.COOLDOWN.value
            account.health_checked_at = now
            return AccountHealthResult(AccountHealthStatus.COOLDOWN, reconnect_attempted=False)
        try:
            self._provider.verify_session(str(account.id))
        except FloodWait as exc:
            account.health_status = AccountHealthStatus.COOLDOWN.value
            account.health_checked_at = now
            account.cooldown_until = now + timedelta(seconds=exc.seconds)
            return AccountHealthResult(AccountHealthStatus.COOLDOWN, reconnect_attempted=True)
        except SessionUnavailable:
            account.health_status = AccountHealthStatus.SESSION_INVALID.value
            account.health_checked_at = now
            account.cooldown_until = None
            return AccountHealthResult(
                AccountHealthStatus.SESSION_INVALID, reconnect_attempted=True
            )
        account.health_status = AccountHealthStatus.CONNECTED.value
        account.health_checked_at = now
        account.cooldown_until = None
        return AccountHealthResult(AccountHealthStatus.CONNECTED, reconnect_attempted=True)
