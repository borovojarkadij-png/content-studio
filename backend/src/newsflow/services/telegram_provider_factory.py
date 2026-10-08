"""Current encrypted sessions into read-only Telegram RPCs; no login or send API."""

import json
import re
from pathlib import Path

from sqlalchemy import func, select

from newsflow.persistence.models import TelegramAccount, TelegramPeerModel
from newsflow.providers.telegram import (
    SessionUnavailable,
    TelegramChannelPeer,
    TelethonTelegramProvider,
)
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

    def _adapter(self, account_id, donor_identifier=None, *, resolving=False):
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
            user_id = account.telegram_user_id
            channel_id = (
                None
                if donor_identifier is None
                else TelethonTelegramProvider._channel_id(donor_identifier)
            )
            stored_peer = (
                None
                if channel_id is None
                else session.get(TelegramPeerModel, (numeric, channel_id))
            )
            encrypted_peer = None if stored_peer is None else stored_peer.encrypted_peer
        try:
            plaintext = self._cipher.decrypt(encrypted)
        except SessionDecryptionUnavailable:
            raise SessionUnavailable(
                "Telegram session cannot be decrypted with the supplied stable key"
            ) from None
        if not plaintext:
            raise SessionUnavailable("Telegram session is not provisioned")
        peers = ()
        if encrypted_peer is not None:
            try:
                value = json.loads(
                    self._cipher.decrypt(encrypted_peer), object_pairs_hook=_unique_fields
                )
                if not isinstance(value, dict) or set(value) != {
                    "version",
                    "account_id",
                    "user_id",
                    "channel_id",
                    "access_hash",
                }:
                    raise ValueError("Invalid peer")
                if (
                    type(value["version"]) is not int
                    or value["version"] != 1
                    or value["account_id"] != account_id
                    or type(value["user_id"]) is not int
                    or value["user_id"] != user_id
                    or type(value["channel_id"]) is not int
                    or value["channel_id"] != channel_id
                ):
                    raise ValueError("Invalid peer binding")
                peers = (TelegramChannelPeer(account_id, channel_id, value["access_hash"]),)
            except (SessionDecryptionUnavailable, ValueError, TypeError):
                raise SessionUnavailable(
                    "Persisted Telegram peer identity cannot be verified"
                ) from None

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

        def preserve_peer(peer):
            if peer.account_id != account_id or (not resolving and peer.channel_id != channel_id):
                raise ValueError("Telegram peer account identity mismatch")
            with self._sessions() as session, session.begin():
                current = session.scalar(
                    select(TelegramAccount).where(TelegramAccount.id == numeric).with_for_update()
                )
                if (
                    current is None
                    or current.encrypted_session != encrypted
                    or current.telegram_user_id != user_id
                ):
                    raise ConnectionError("Telegram session changed during peer resolution")
                row = session.get(
                    TelegramPeerModel, (numeric, peer.channel_id), with_for_update=True
                )
                if row is None:
                    row = TelegramPeerModel(
                        telegram_account_id=numeric, telegram_channel_id=peer.channel_id
                    )
                    session.add(row)
                row.encrypted_peer = self._cipher.encrypt(
                    json.dumps(
                        {
                            "version": 1,
                            "account_id": account_id,
                            "user_id": user_id,
                            "channel_id": peer.channel_id,
                            "access_hash": peer.access_hash,
                        },
                        sort_keys=True,
                    )
                )
                row.updated_at = func.now()

        return TelethonTelegramProvider(
            api_id=self._api_id,
            api_hash=self._api_hash,
            sessions={account_id: plaintext},
            client_factory=self._clients,
            on_session_updated=preserve,
            peers=peers,
            on_peer_updated=preserve_peer,
            expected_user_id=user_id,
        )

    def verify_session(self, account_id):
        return self._adapter(account_id).verify_session(account_id)

    def resolve_channel(self, account_id, identifier):
        donor = None if isinstance(identifier, str) and identifier.startswith("@") else identifier
        return self._adapter(account_id, donor, resolving=True).resolve_channel(
            account_id, identifier
        )

    def history(self, account_id, donor_identifier, *, after_id, limit):
        return self._adapter(account_id, donor_identifier).history(
            account_id, donor_identifier, after_id=after_id, limit=limit
        )

    def channel_difference(self, account_id, donor_identifier, *, pts, limit):
        from newsflow.providers.telegram import validate_difference_request

        validate_difference_request(account_id, donor_identifier, pts, limit)
        return self._adapter(account_id, donor_identifier).channel_difference(
            account_id, donor_identifier, pts=pts, limit=limit
        )

    def channel_checkpoint(self, account_id, donor_identifier):
        from newsflow.providers.telegram import validate_difference_request

        validate_difference_request(account_id, donor_identifier, 1, 10)
        return self._adapter(account_id, donor_identifier).channel_checkpoint(
            account_id, donor_identifier
        )

    def fetch_message(self, account_id, donor_identifier, message_id):
        return self._adapter(account_id, donor_identifier).fetch_message(
            account_id, donor_identifier, message_id
        )

    def recent(self, account_id, donor_identifier, *, limit):
        return self._adapter(account_id, donor_identifier).recent(
            account_id, donor_identifier, limit=limit
        )

    def album_window(self, account_id, donor_identifier, *, anchor_id):
        return self._adapter(account_id, donor_identifier).album_window(
            account_id, donor_identifier, anchor_id=anchor_id
        )

    def download_photo(self, account_id, donor_identifier, message_id):
        return self._adapter(account_id, donor_identifier).download_photo(
            account_id, donor_identifier, message_id
        )

    def download_video(self, account_id, donor_identifier, message_id):
        from newsflow.providers.telegram import validate_video_request

        validate_video_request(account_id, donor_identifier, message_id)
        return self._adapter(account_id, donor_identifier).download_video(
            account_id, donor_identifier, message_id
        )
