"""Telegram provider contract and offline fake implementation."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


class FloodWait(RuntimeError):
    def __init__(self, seconds: int) -> None:
        super().__init__(f"FloodWait: {seconds}s")
        self.seconds = seconds


class SessionUnavailable(RuntimeError):
    """Raised before a live connection when no decrypted session was supplied."""


@dataclass(frozen=True, slots=True)
class TelegramMessage:
    account_id: str
    donor_identifier: str
    message_id: int
    text: str
    is_edit: bool = False
    media_type: str = "text"


class TelegramProvider(Protocol):
    def fetch_message(self, account_id: str, donor_identifier: str, message_id: int) -> TelegramMessage: ...

    def iter_events(self, account_id: str) -> Iterator[TelegramMessage]: ...


class FakeTelegramProvider:
    """Deterministic fake for offline ingestion and failure-mode tests."""

    def __init__(self) -> None:
        self._events: dict[str, list[TelegramMessage]] = {}
        self._messages: dict[tuple[str, str, int], TelegramMessage] = {}
        self._floodwaits: dict[str, int] = {}

    def seed_floodwait(self, account_id: str, seconds: int) -> None:
        self._floodwaits[account_id] = seconds

    def seed_message(self, account_id: str, donor_identifier: str, message_id: int, text: str) -> None:
        message = TelegramMessage(account_id, donor_identifier, message_id, text)
        self._messages[(account_id, donor_identifier, message_id)] = message
        self._events.setdefault(account_id, []).append(message)

    def seed_edit(self, account_id: str, donor_identifier: str, message_id: int, text: str) -> None:
        event = TelegramMessage(account_id, donor_identifier, message_id, text, is_edit=True)
        self._messages[(account_id, donor_identifier, message_id)] = event
        self._events.setdefault(account_id, []).append(event)

    def fetch_message(self, account_id: str, donor_identifier: str, message_id: int) -> TelegramMessage:
        if seconds := self._floodwaits.get(account_id):
            raise FloodWait(seconds)
        return self._messages[(account_id, donor_identifier, message_id)]

    def iter_events(self, account_id: str) -> Iterator[TelegramMessage]:
        yield from self._events.get(account_id, [])


class TelethonTelegramProvider:
    """Live adapter boundary.

    Session loading/encryption belongs to the account repository; this adapter
    refuses to create a client until that repository supplies a session.
    """

    def __init__(self, *, api_id: int, api_hash: str, sessions: dict[str, str] | None = None) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._sessions = sessions or {}

    def require_session(self, account_id: str) -> str:
        try:
            return self._sessions[account_id]
        except KeyError as exc:
            raise SessionUnavailable(f"No provisioned session for {account_id}") from exc

    def build_client(self, account_id: str):
        """Build an account-isolated Telethon client without connecting or logging in."""
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        return TelegramClient(StringSession(self.require_session(account_id)), self._api_id, self._api_hash)
