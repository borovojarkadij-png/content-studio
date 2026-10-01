"""Durable Telegram account health and reconnect cooldown policy."""

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

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
        transaction = nullcontext() if self._session.in_transaction() else self._session.begin()
        with transaction:
            account = self._session.get(TelegramAccount, account_id)
            if account is None:
                raise LookupError(f"Telegram account {account_id} was not found")
            if account.cooldown_until is not None and now < account.cooldown_until:
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
                return AccountHealthResult(AccountHealthStatus.SESSION_INVALID, reconnect_attempted=True)
            account.health_status = AccountHealthStatus.CONNECTED.value
            account.health_checked_at = now
            account.cooldown_until = None
            return AccountHealthResult(AccountHealthStatus.CONNECTED, reconnect_attempted=True)
