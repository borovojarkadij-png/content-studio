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

    def reconnect(
        self, account_id: int, *, now: datetime, cooldown_only: bool = False
    ) -> AccountHealthResult:
        """Own the health transaction, including SQLAlchemy's implicit autobegin."""
        if type(account_id) is not int or account_id <= 0 or type(cooldown_only) is not bool:
            raise ValueError("Canonical account identity and explicit automatic mode required")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Account health time must be timezone-aware")
        now = now.astimezone(UTC)
        try:
            result = self._reconnect(account_id, now=now, cooldown_only=cooldown_only)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def _account(self, account_id: int) -> TelegramAccount:
        account = self._session.scalar(
            select(TelegramAccount)
            .where(TelegramAccount.id == account_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if account is None:
            raise LookupError(f"Telegram account {account_id} was not found")
        return account

    @staticmethod
    def _utc(value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value

    def _reconnect(
        self, account_id: int, *, now: datetime, cooldown_only: bool
    ) -> AccountHealthResult:
        account = self._account(account_id)
        cooldown = self._utc(account.cooldown_until)
        if cooldown_only and (
            account.health_status != "COOLDOWN" or not account.encrypted_session or cooldown is None
        ):
            # A bounded scan is not permission to probe a subsequently invalid,
            # replaced or unprovisioned account. Recheck under the actual row lock.
            return AccountHealthResult(
                AccountHealthStatus(account.health_status), reconnect_attempted=False
            )
        if cooldown is not None and now < cooldown:
            account.health_status = AccountHealthStatus.COOLDOWN.value
            account.health_checked_at = now
            return AccountHealthResult(AccountHealthStatus.COOLDOWN, reconnect_attempted=False)
        expected = (
            account.telegram_user_id,
            account.encrypted_session,
            account.health_status,
            self._utc(account.health_checked_at),
        )
        # A real RPC can refresh its encrypted session in another transaction.
        # Release the health row before calling it; holding this lock would
        # deadlock that callback and retain a transaction during network waits.
        self._session.commit()
        outcome = AccountHealthStatus.CONNECTED
        next_cooldown = None
        try:
            self._provider.verify_session(str(account_id))
        except FloodWait as exc:
            outcome = AccountHealthStatus.COOLDOWN
            next_cooldown = now + timedelta(seconds=max(1, exc.seconds))
        except SessionUnavailable:
            outcome = AccountHealthStatus.SESSION_INVALID

        account = self._account(account_id)
        if (account.telegram_user_id, account.encrypted_session) != expected[
            :2
        ] or account.health_status != expected[2]:
            # This RPC verified the old identity only. Even legitimate provider
            # session refresh gets a fresh probe on the next tick; no ciphertext
            # change may be assumed to authorize a concurrently replaced session.
            return AccountHealthResult(
                AccountHealthStatus(account.health_status), reconnect_attempted=True
            )
        concurrent_cooldown = self._utc(account.cooldown_until)
        if concurrent_cooldown is not None and concurrent_cooldown > now:
            outcome = AccountHealthStatus.COOLDOWN
            next_cooldown = max(concurrent_cooldown, next_cooldown or concurrent_cooldown)
        checked = self._utc(account.health_checked_at)
        if checked is not None and (checked > now or (checked != expected[3] and checked >= now)):
            # An older network response must not clobber a newer health probe.
            return AccountHealthResult(
                AccountHealthStatus(account.health_status), reconnect_attempted=True
            )
        account.health_status = outcome.value
        account.health_checked_at = now
        account.cooldown_until = next_cooldown
        return AccountHealthResult(outcome, reconnect_attempted=True)
