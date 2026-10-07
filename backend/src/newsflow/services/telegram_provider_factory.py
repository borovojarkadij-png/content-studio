"""Current encrypted sessions into read-only Telegram RPCs; no login or send API."""

import json
import re
from pathlib import Path

from sqlalchemy import select

from newsflow.persistence.models import TelegramAccount
from newsflow.providers.telegram import SessionUnavailable, TelethonTelegramProvider
from newsflow.security.session_cipher import SessionDecryptionUnavailable


class TelegramCredentialsUnavailable(ValueError):
    pass


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TelegramCredentialsUnavailable("Duplicate credential field")
        result[key] = value
    return result


def load_telegram_credentials(path: Path) -> tuple[int, str]:
    try:
        if path.is_symlink() or not path.is_file():
            raise TelegramCredentialsUnavailable("Telegram credentials file is unavailable")
        with path.open("rb") as file:
            raw = file.read(4097)
        if len(raw) > 4096:
            raise TelegramCredentialsUnavailable("Telegram credentials file is invalid")
        value = json.loads(raw, object_pairs_hook=_unique_fields)
        if not isinstance(value, dict) or set(value) != {"api_id", "api_hash"}:
            raise TelegramCredentialsUnavailable("Telegram credentials file is invalid")
        _validate_credentials(value["api_id"], value["api_hash"])
        return value["api_id"], value["api_hash"]
    except (OSError, ValueError, TypeError):
        raise TelegramCredentialsUnavailable(
            "Provision an existing valid Telegram credentials file"
        ) from None


def _validate_credentials(api_id, api_hash):
    if (
        isinstance(api_id, bool)
        or not isinstance(api_id, int)
        or not 0 < api_id <= 2147483647
        or not isinstance(api_hash, str)
        or re.fullmatch(r"[a-fA-F0-9]{32}", api_hash) is None
    ):
        raise TelegramCredentialsUnavailable("Telegram api_id/api_hash configuration is invalid")


class ConfiguredTelegramProvider:
    def __init__(self, session_factory, *, cipher, api_id, api_hash, client_factory=None):
        _validate_credentials(api_id, api_hash)
        self._sessions = session_factory
        self._cipher = cipher
        self._api_id = api_id
        self._api_hash = api_hash
        self._clients = client_factory

    def _adapter(self, account_id):
        try:
            numeric = int(account_id)
        except (TypeError, ValueError):
            raise SessionUnavailable("Invalid Telegram account identity") from None
        if numeric <= 0 or str(numeric) != account_id:
            raise SessionUnavailable("Invalid Telegram account identity")
        with self._sessions() as session:
            account = session.get(TelegramAccount, numeric)
            if account is None or not account.encrypted_session:
                raise SessionUnavailable("Telegram session is not provisioned")
            encrypted = account.encrypted_session
        try:
            plaintext = self._cipher.decrypt(encrypted)
        except SessionDecryptionUnavailable:
            raise SessionUnavailable(
                "Telegram session cannot be decrypted with the supplied stable key"
            ) from None
        if not plaintext:
            raise SessionUnavailable("Telegram session is not provisioned")

        def preserve(account_id, updated):
            nonlocal encrypted
            with self._sessions() as session, session.begin():
                current = session.scalar(
                    select(TelegramAccount).where(TelegramAccount.id == numeric).with_for_update()
                )
                if current is None or current.encrypted_session != encrypted:
                    raise ConnectionError(
                        "Telegram session changed concurrently; retry with current configuration"
                    )
                current.encrypted_session = self._cipher.encrypt(updated)
                encrypted = current.encrypted_session

        return TelethonTelegramProvider(
            api_id=self._api_id,
            api_hash=self._api_hash,
            sessions={account_id: plaintext},
            client_factory=self._clients,
            on_session_updated=preserve,
        )

    def verify_session(self, account_id):
        return self._adapter(account_id).verify_session(account_id)

    def history(self, account_id, donor_identifier, *, after_id, limit):
        return self._adapter(account_id).history(
            account_id, donor_identifier, after_id=after_id, limit=limit
        )

    def fetch_message(self, account_id, donor_identifier, message_id):
        return self._adapter(account_id).fetch_message(account_id, donor_identifier, message_id)
