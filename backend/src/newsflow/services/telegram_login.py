"""Create-only encrypted Telegram session provisioning."""

import hashlib
import hmac
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4
from weakref import WeakSet

from sqlalchemy import select, update

from newsflow.persistence.models import OutboxEventModel, TelegramAccount
from newsflow.providers.telegram_login import (
    TelegramLoginError,
    _positive_id,
    _validate_authorized_session,
    _validate_phone,
)
from newsflow.security.session_cipher import SessionCipher


@dataclass(frozen=True, eq=False)
class ProvisioningRequest:
    """Ephemeral preflight capability; no master key or session material."""

    account_name: str = field(repr=False)
    actor_id: int = field(repr=False)
    expected_user_id: int | None = field(repr=False)
    _key_fingerprint: bytes = field(repr=False)
    _account_id: int | None = field(repr=False)
    _user_id: int | None = field(repr=False)
    _empty_session: str | None = field(repr=False)
    _health: str | None = field(repr=False)
    _cooldown: datetime | None = field(repr=False)


class SessionProvisioningService:
    def __init__(self, session_factory, *, master_key_loader, login_adapter):
        self._sessions = session_factory
        self._key_loader = master_key_loader
        self._login = login_adapter
        # Identity-based capabilities reject fabricated/copied/replayed requests.
        # Weak references avoid retaining abandoned interactive preflights.
        self._requests = WeakSet()

    def _key(self):
        key = self._key_loader()
        cipher = SessionCipher(key)
        return cipher, hashlib.sha256(key.encode("ascii")).digest()

    def preflight(self, account_name, actor_id, expected_user_id=None):
        try:
            if (
                not isinstance(account_name, str)
                or any(unicodedata.category(char) in {"Cc", "Cf"} for char in account_name)
                or not 1 <= len(account_name.strip()) <= 100
                or not _positive_id(actor_id)
                or (expected_user_id is not None and not _positive_id(expected_user_id))
            ):
                raise ValueError("Invalid preflight")
            name = account_name.strip()
            _, fingerprint = self._key()
            with self._sessions() as session:
                account = session.scalar(
                    select(TelegramAccount).where(TelegramAccount.name == name)
                )
                if account is not None:
                    if (
                        account.encrypted_session != ""
                        or account.health_status != "DISCONNECTED"
                        or account.cooldown_until is not None
                        or not _positive_id(account.telegram_user_id)
                        or (
                            expected_user_id is not None
                            and account.telegram_user_id != expected_user_id
                        )
                    ):
                        raise ValueError("Account is not provisionable")
                    expected_user_id = account.telegram_user_id
                request = ProvisioningRequest(
                    name,
                    actor_id,
                    expected_user_id,
                    fingerprint,
                    account.id if account else None,
                    account.telegram_user_id if account else None,
                    account.encrypted_session if account else None,
                    account.health_status if account else None,
                    account.cooldown_until if account else None,
                )
            self._requests.add(request)
            return request
        except Exception:  # noqa: BLE001 -- Key-loader and SQL errors are private boundaries.
            raise TelegramLoginError("Telegram session provisioning failed") from None

    async def provision(self, request, *, phone, read_code, read_password):
        try:
            if type(request) is not ProvisioningRequest or request not in self._requests:
                raise ValueError("Invalid preflight capability")
            self._requests.remove(request)
            _validate_phone(phone)
        except (TypeError, ValueError, KeyError, TelegramLoginError):
            raise TelegramLoginError("Telegram session provisioning failed") from None

        # Preflight's SQL transaction is closed before any operator input/RPC.
        authorized = await self._login.authorize(
            phone, read_code=read_code, read_password=read_password
        )
        try:
            _validate_authorized_session(authorized, phone, request.expected_user_id)
            cipher, fingerprint = self._key()
            if not hmac.compare_digest(fingerprint, request._key_fingerprint):
                raise ValueError("Master key changed")
            encrypted = cipher.encrypt(authorized.string_session)
            with self._sessions() as session, session.begin():
                conflict = session.scalar(
                    select(TelegramAccount.id).where(
                        TelegramAccount.telegram_user_id == authorized.telegram_user_id,
                        TelegramAccount.name != request.account_name,
                    )
                )
                if conflict is not None:
                    raise ValueError("Account identity conflict")
                if request._account_id is None:
                    account = TelegramAccount(
                        name=request.account_name,
                        telegram_user_id=authorized.telegram_user_id,
                        encrypted_session=encrypted,
                        health_status="DISCONNECTED",
                    )
                    session.add(account)
                    session.flush()
                    account_id = account.id
                else:
                    result = session.execute(
                        update(TelegramAccount)
                        .where(
                            TelegramAccount.id == request._account_id,
                            TelegramAccount.name == request.account_name,
                            TelegramAccount.telegram_user_id == request._user_id,
                            TelegramAccount.encrypted_session == request._empty_session,
                            TelegramAccount.health_status == request._health,
                            TelegramAccount.cooldown_until == request._cooldown,
                        )
                        .values(encrypted_session=encrypted)
                        .execution_options(synchronize_session=False)
                    )
                    if result.rowcount != 1:
                        raise ValueError("Account changed during authorization")
                    account_id = request._account_id
                    session.flush()
                session.add(
                    OutboxEventModel(
                        event_type="TelegramSessionProvisioned",
                        aggregate_key=f"telegram-session:{request.actor_id}:{account_id}",
                        idempotency_key=f"telegram-session-provision:{uuid4().hex}",
                    )
                )
                session.flush()
            return account_id
        except Exception:  # noqa: BLE001 -- Encryption, SQL and commit errors may contain secrets.
            raise TelegramLoginError("Telegram session provisioning failed") from None
