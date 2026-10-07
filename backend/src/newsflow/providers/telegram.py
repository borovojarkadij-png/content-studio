"""Telegram provider contract and offline fake implementation."""

import asyncio
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


class FloodWait(RuntimeError):
    def __init__(self, seconds: int) -> None:
        super().__init__(f"FloodWait: {seconds}s")
        self.seconds = seconds


class SessionUnavailable(RuntimeError):
    """Raised before a live connection when no decrypted session was supplied."""


@dataclass(frozen=True, slots=True)
class TelegramChannelPeer:
    account_id: str
    channel_id: int
    access_hash: int = field(repr=False)

    def __post_init__(self):
        if (
            not isinstance(self.account_id, str)
            or not self.account_id
            or isinstance(self.channel_id, bool)
            or not isinstance(self.channel_id, int)
            or not -(2**63) <= self.channel_id < -1000000000000
            or isinstance(self.access_hash, bool)
            or not isinstance(self.access_hash, int)
            or not -(2**63) <= self.access_hash < 2**63
            or self.access_hash == 0
        ):
            raise ValueError("Invalid Telegram channel peer identity")


@dataclass(frozen=True, slots=True)
class TelegramChannelResolution:
    identifier: str
    peer: TelegramChannelPeer
    title: str

    def __post_init__(self):
        if not isinstance(self.peer, TelegramChannelPeer):
            raise TypeError("Resolution requires a validated immutable Telegram peer")
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 255:
            raise ValueError("Invalid Telegram channel title")


@dataclass(frozen=True, slots=True)
class TelegramMessage:
    account_id: str
    donor_identifier: str
    message_id: int
    text: str
    is_edit: bool = False
    media_type: str = "text"
    album_id: str | None = None
    source_updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class TelegramAlbumObservation:
    """Observed members, not proof of a complete album or permission to rewrite.

    Telegram history windows may omit members. Keeping that uncertainty explicit
    prevents a truncated photo/video group from becoming an approved text post.
    """

    account_id: str
    donor_identifier: str
    album_id: str
    members: tuple[TelegramMessage, ...]
    lower_id: int
    upper_id: int

    @property
    def message_ids(self) -> tuple[int, ...]:
        return tuple(member.message_id for member in self.members)

    @property
    def text(self) -> str:
        return "\n\n".join(member.text for member in self.members if member.text.strip())

    @property
    def media_types(self) -> tuple[str, ...]:
        return tuple(member.media_type for member in self.members)

    @property
    def membership_complete(self) -> bool:
        return False

    @property
    def rewrite_allowed(self) -> bool:
        return False


def observe_album_window(
    messages: tuple[TelegramMessage, ...],
    *,
    account_id: str,
    donor_identifier: str,
    anchor_id: int,
    lower_id: int,
    upper_id: int,
) -> TelegramAlbumObservation:
    if (
        not isinstance(messages, tuple)
        or len(messages) > 100
        or not isinstance(account_id, str)
        or not account_id
        or not isinstance(donor_identifier, str)
        or not donor_identifier
        or any(type(value) is not int for value in (anchor_id, lower_id, upper_id))
        or not 1 <= lower_id <= anchor_id <= upper_id <= 2**31 - 1
        or upper_id - lower_id >= 100
    ):
        raise ValueError("Invalid bounded Telegram album window")
    by_id: dict[int, TelegramMessage] = {}
    for message in messages:
        if (
            not isinstance(message, TelegramMessage)
            or message.account_id != account_id
            or message.donor_identifier != donor_identifier
            or type(message.message_id) is not int
            or not lower_id <= message.message_id <= upper_id
            or not isinstance(message.text, str)
            or message.media_type not in {"text", "photo", "video", "unsupported"}
            or (
                message.source_updated_at is not None
                and (
                    not isinstance(message.source_updated_at, datetime)
                    or message.source_updated_at.tzinfo is None
                    or message.source_updated_at.utcoffset() is None
                )
            )
            or (
                message.album_id is not None
                and (
                    not isinstance(message.album_id, str)
                    or re.fullmatch(r"-?(?:0|[1-9][0-9]{0,18})", message.album_id) is None
                    or str(int(message.album_id)) != message.album_id
                    or not -(2**63) <= int(message.album_id) < 2**63
                    or message.media_type == "text"
                )
            )
        ):
            raise ValueError("Malformed or foreign Telegram album observation")
        previous = by_id.get(message.message_id)
        if previous is not None and previous != message:
            raise ValueError("Conflicting Telegram album member observations")
        by_id[message.message_id] = message
    anchor = by_id.get(anchor_id)
    if anchor is None:
        raise LookupError("Telegram album anchor no longer exists")
    if anchor.album_id is None:
        raise ValueError("Telegram message is not an album anchor")
    members = tuple(
        message for _, message in sorted(by_id.items()) if message.album_id == anchor.album_id
    )
    if len(members) > 10:
        raise ValueError("Telegram album exceeds its member bound")
    return TelegramAlbumObservation(
        account_id, donor_identifier, anchor.album_id, members, lower_id, upper_id
    )


def _album_bounds(anchor_id: int) -> tuple[int, int]:
    if type(anchor_id) is not int or not 1 <= anchor_id <= 2**31 - 1:
        raise ValueError("Invalid Telegram album anchor identity")
    return max(1, anchor_id - 49), min(2**31 - 1, anchor_id + 50)


class TelegramProvider(Protocol):
    def album_window(
        self, account_id: str, donor_identifier: str, *, anchor_id: int
    ) -> TelegramAlbumObservation: ...

    def resolve_channel(self, account_id: str, identifier: str) -> TelegramChannelResolution: ...

    def verify_session(self, account_id: str) -> None: ...

    def fetch_message(
        self, account_id: str, donor_identifier: str, message_id: int
    ) -> TelegramMessage: ...

    def history(
        self, account_id: str, donor_identifier: str, *, after_id: int, limit: int
    ) -> tuple[TelegramMessage, ...]: ...

    def recent(
        self, account_id: str, donor_identifier: str, *, limit: int
    ) -> tuple[TelegramMessage, ...]: ...


class FakeTelegramProvider:
    """Deterministic fake for offline ingestion and failure-mode tests."""

    def __init__(self) -> None:
        self._events: dict[str, list[TelegramMessage]] = {}
        self._messages: dict[tuple[str, str, int], TelegramMessage] = {}
        self._floodwaits: dict[str, int] = {}
        self._session_unavailable: set[str] = set()
        self._session_probes: dict[str, int] = {}
        self._channels: dict[tuple[str, str], TelegramChannelResolution] = {}

    def seed_channel(self, account_id, identifier, channel_id, title):
        self._channels[(account_id, identifier)] = TelegramChannelResolution(
            identifier, TelegramChannelPeer(account_id, channel_id, 1), title
        )

    def resolve_channel(self, account_id, identifier):
        self.verify_session(account_id)
        return self._channels[(account_id, identifier)]

    def seed_floodwait(self, account_id: str, seconds: int) -> None:
        self._floodwaits[account_id] = seconds

    def seed_session_unavailable(self, account_id: str) -> None:
        self._session_unavailable.add(account_id)

    def session_probe_count(self, account_id: str) -> int:
        return self._session_probes.get(account_id, 0)

    def verify_session(self, account_id: str) -> None:
        self._session_probes[account_id] = self.session_probe_count(account_id) + 1
        if account_id in self._session_unavailable:
            raise SessionUnavailable(f"No provisioned session for {account_id}")
        if seconds := self._floodwaits.get(account_id):
            raise FloodWait(seconds)

    def seed_message(
        self, account_id: str, donor_identifier: str, message_id: int, text: str
    ) -> None:
        message = TelegramMessage(account_id, donor_identifier, message_id, text)
        self._messages[(account_id, donor_identifier, message_id)] = message
        self._events.setdefault(account_id, []).append(message)

    def seed_edit(self, account_id: str, donor_identifier: str, message_id: int, text: str) -> None:
        event = TelegramMessage(account_id, donor_identifier, message_id, text, is_edit=True)
        self._messages[(account_id, donor_identifier, message_id)] = event
        self._events.setdefault(account_id, []).append(event)

    def fetch_message(
        self, account_id: str, donor_identifier: str, message_id: int
    ) -> TelegramMessage:
        self.verify_session(account_id)
        return self._messages[(account_id, donor_identifier, message_id)]

    def album_window(self, account_id, donor_identifier, *, anchor_id):
        lower, upper = _album_bounds(anchor_id)
        self.verify_session(account_id)
        messages = tuple(
            message
            for (account, donor, message_id), message in self._messages.items()
            if account == account_id and donor == donor_identifier and lower <= message_id <= upper
        )
        return observe_album_window(
            messages,
            account_id=account_id,
            donor_identifier=donor_identifier,
            anchor_id=anchor_id,
            lower_id=lower,
            upper_id=upper,
        )

    def iter_events(self, account_id: str) -> Iterator[TelegramMessage]:
        yield from self._events.get(account_id, [])

    def history(
        self, account_id: str, donor_identifier: str, *, after_id: int, limit: int
    ) -> tuple[TelegramMessage, ...]:
        if after_id < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid history bounds")
        self.verify_session(account_id)
        messages = sorted(
            (
                m
                for (account, donor, _), m in self._messages.items()
                if account == account_id and donor == donor_identifier and m.message_id > after_id
            ),
            key=lambda m: m.message_id,
        )
        return tuple(messages[:limit])

    def recent(self, account_id, donor_identifier, *, limit):
        if not 1 <= limit <= 100:
            raise ValueError("Invalid recent history bound")
        self.verify_session(account_id)
        messages = sorted(
            (
                m
                for (account, donor, _), m in self._messages.items()
                if account == account_id and donor == donor_identifier
            ),
            key=lambda m: m.message_id,
            reverse=True,
        )[:limit]
        return tuple(reversed(messages))


class TelethonTelegramProvider:
    """Live adapter boundary.

    Session loading/encryption belongs to the account repository; this adapter
    refuses to create a client until that repository supplies a session.
    """

    def __init__(
        self,
        *,
        api_id: int,
        api_hash: str,
        sessions: dict[str, str] | None = None,
        client_factory: Callable[[str], object] | None = None,
        on_session_updated: Callable[[str, str], None] | None = None,
        peers: tuple[TelegramChannelPeer, ...] = (),
        on_peer_updated: Callable[[TelegramChannelPeer], None] | None = None,
        expected_user_id: int | None = None,
        request_timeout: float = 15,
    ) -> None:
        if not 0 < request_timeout <= 30:
            raise ValueError("Telegram request deadline must be within 30 seconds")
        self._api_id = api_id
        self._api_hash = api_hash
        self._sessions = dict(sessions or {})
        self._client_factory = client_factory
        self._on_session_updated = on_session_updated
        self._request_timeout = request_timeout
        self._peers = {(peer.account_id, peer.channel_id): peer for peer in peers}
        self._on_peer_updated = on_peer_updated
        self._expected_user_id = expected_user_id

    def require_session(self, account_id: str) -> str:
        try:
            return self._sessions[account_id]
        except KeyError as exc:
            raise SessionUnavailable(f"No provisioned session for {account_id}") from exc

    def verify_session(self, account_id: str) -> None:
        """Check actual authorization; never call start(), sign_in(), or send a code."""

        async def nothing(client):
            return None

        self._run(account_id, nothing)

    def resolve_channel(self, account_id, identifier):
        from telethon.tl.types import Channel, InputPeerChannel
        from telethon.utils import get_input_peer, get_peer_id

        if not isinstance(identifier, str):
            raise TypeError("Invalid channel identifier")
        username = re.fullmatch(r"@[a-z][a-z0-9_]{3,31}", identifier)
        channel_id = None if username else self._channel_id(identifier)

        async def resolve(client):
            target = (
                identifier
                if username
                else await self._input_channel(client, account_id, channel_id)
            )
            entity = await client.get_entity(target)
            if not isinstance(entity, Channel) or not entity.broadcast or entity.megagroup:
                raise ValueError("Donor identifier must resolve to a broadcast channel")
            try:
                peer = get_input_peer(entity)
            except TypeError:
                raise ValueError("Telegram channel has no usable full access hash") from None
            if not isinstance(peer, InputPeerChannel):
                raise TypeError("Resolved Telegram channel identity mismatch")
            marked = get_peer_id(peer)
            if channel_id is not None and marked != channel_id:
                raise ValueError("Resolved Telegram channel identity mismatch")
            if username:
                names = {getattr(entity, "username", None)} | {
                    item.username for item in (entity.usernames or []) if item.active
                }
                if identifier[1:] not in {
                    name.casefold() for name in names if isinstance(name, str)
                }:
                    raise ValueError("Resolved Telegram username identity mismatch")
            result = TelegramChannelResolution(
                identifier, TelegramChannelPeer(account_id, marked, peer.access_hash), entity.title
            )
            if self._on_peer_updated is not None:
                self._on_peer_updated(result.peer)
            self._peers[(account_id, marked)] = result.peer
            return result

        return self._run(account_id, resolve)

    def build_client(self, account_id: str):
        """Build an account-isolated Telethon client without connecting or logging in."""
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        return TelegramClient(
            StringSession(self.require_session(account_id)),
            self._api_id,
            self._api_hash,
            timeout=5,
            request_retries=0,
            connection_retries=0,
            auto_reconnect=False,
            flood_sleep_threshold=0,
            receive_updates=False,
        )

    def _run(self, account_id, operation):
        if not self.require_session(account_id):
            raise SessionUnavailable("No provisioned Telegram session")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Synchronous Telegram adapter must run outside an async event loop")
        return asyncio.run(self._connected(account_id, operation))

    async def _connected(self, account_id, operation):
        from telethon.errors import FloodWaitError, RPCError, UnauthorizedError

        try:
            client = (
                self._client_factory(account_id)
                if self._client_factory
                else self.build_client(account_id)
            )
        except (ValueError, TypeError):
            raise SessionUnavailable("Provisioned Telegram session is malformed") from None
        try:
            async with asyncio.timeout(self._request_timeout):
                await client.connect()
                if not await client.is_user_authorized():
                    raise SessionUnavailable("Telegram session requires manual authorization")
                if self._expected_user_id is not None:
                    me = await client.get_me()
                    if getattr(me, "id", None) != self._expected_user_id:
                        raise SessionUnavailable("Telegram session account identity mismatch")
                self._save_session(account_id, client)
                result = await operation(client)
                self._save_session(account_id, client)
                return result
        except FloodWaitError as exc:
            raise FloodWait(max(1, exc.seconds)) from None
        except UnauthorizedError:
            raise SessionUnavailable("Telegram session requires manual authorization") from None
        except RPCError:
            raise ConnectionError("Telegram RPC temporarily unavailable") from None
        finally:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=3)
            except (TimeoutError, OSError):
                pass  # asyncio.run cancels remaining tasks; preserve the primary failure.

    def _save_session(self, account_id, client):
        if self._on_session_updated is None:
            return
        updated = client.session.save()
        if not updated:
            raise SessionUnavailable("Telegram session cannot be preserved")
        if updated != self._sessions[account_id]:
            self._on_session_updated(account_id, updated)
            self._sessions[account_id] = updated

    @staticmethod
    def _channel_id(donor_identifier):
        try:
            value = int(donor_identifier)
        except (TypeError, ValueError):
            raise ValueError("History requires canonical numeric donor identity") from None
        if value >= 0 or str(value) != donor_identifier:
            raise ValueError("History requires canonical numeric donor identity")
        return value

    def history(self, account_id, donor_identifier, *, after_id, limit):
        if (
            isinstance(after_id, bool)
            or not isinstance(after_id, int)
            or after_id < 0
            or isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 100
        ):
            raise ValueError("Invalid history bounds")
        channel = self._channel_id(donor_identifier)

        async def read(client):
            peer = await self._input_channel(client, account_id, channel)
            result = []
            async for raw in client.iter_messages(
                peer, min_id=after_id, limit=limit, reverse=True, wait_time=0
            ):
                if getattr(raw, "chat_id", None) != channel:
                    raise ValueError("Telegram source identity mismatch")
                result.append(self.normalize_message(account_id, donor_identifier, raw))
                if len(result) > limit:
                    raise ValueError("Telegram history exceeded its bound")
            return tuple(result)

        return self._run(account_id, read)

    def fetch_message(self, account_id, donor_identifier, message_id):
        channel = self._channel_id(donor_identifier)
        if isinstance(message_id, bool) or not isinstance(message_id, int) or message_id <= 0:
            raise ValueError("Invalid message identity")

        async def read(client):
            peer = await self._input_channel(client, account_id, channel)
            raw = await client.get_messages(peer, ids=message_id)
            if raw is None:
                raise LookupError("Telegram message no longer exists")
            if getattr(raw, "chat_id", None) != channel or getattr(raw, "id", None) != message_id:
                raise ValueError("Telegram source identity mismatch")
            return self.normalize_message(account_id, donor_identifier, raw)

        return self._run(account_id, read)

    def album_window(self, account_id, donor_identifier, *, anchor_id):
        lower, upper = _album_bounds(anchor_id)
        channel = self._channel_id(donor_identifier)

        async def read(client):
            peer = await self._input_channel(client, account_id, channel)
            raws = await client.get_messages(peer, ids=list(range(lower, upper + 1)))
            if not isinstance(raws, (list, tuple)) or len(raws) > upper - lower + 1:
                raise ValueError("Telegram album response exceeded its bound")
            messages = []
            for raw in raws:
                if raw is None:
                    continue
                if getattr(raw, "chat_id", None) != channel:
                    raise ValueError("Telegram album source identity mismatch")
                messages.append(self.normalize_message(account_id, donor_identifier, raw))
            return observe_album_window(
                tuple(messages),
                account_id=account_id,
                donor_identifier=donor_identifier,
                anchor_id=anchor_id,
                lower_id=lower,
                upper_id=upper,
            )

        return self._run(account_id, read)

    def recent(self, account_id, donor_identifier, *, limit):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Invalid recent history bound")
        channel = self._channel_id(donor_identifier)

        async def read(client):
            peer = await self._input_channel(client, account_id, channel)
            result = []
            async for raw in client.iter_messages(peer, limit=limit, reverse=False, wait_time=0):
                if getattr(raw, "chat_id", None) != channel:
                    raise ValueError("Telegram source identity mismatch")
                result.append(self.normalize_message(account_id, donor_identifier, raw))
                if len(result) > limit:
                    raise ValueError("Telegram recent history exceeded its bound")
            return tuple(reversed(result))

        return self._run(account_id, read)

    async def _input_channel(self, client, account_id, channel):
        from telethon.tl.types import InputPeerChannel
        from telethon.utils import get_peer_id

        known = self._peers.get((account_id, channel))
        if known is None:
            # StringSession does not preserve entities. Bounded read-only dialogs
            # can recover already-accessible channels; never join or auto-login.
            count = 0
            async for dialog in client.iter_dialogs(limit=100):
                count += 1
                if count > 100:
                    raise ValueError("Telegram dialog resolution exceeded its bound")
                if getattr(dialog, "id", None) != channel:
                    continue
                peer = getattr(dialog, "input_entity", None)
                if not isinstance(peer, InputPeerChannel) or get_peer_id(peer) != channel:
                    raise ValueError("Telegram resolved peer identity mismatch")
                known = TelegramChannelPeer(account_id, channel, peer.access_hash)
                if self._on_peer_updated is not None:
                    self._on_peer_updated(known)
                self._peers[(account_id, channel)] = known
                break
            if known is None:
                raise LookupError("Donor channel is outside the bounded accessible-dialog window")
        return InputPeerChannel(-channel - 1000000000000, known.access_hash)

    @staticmethod
    def normalize_message(
        account_id: str, donor_identifier: str, raw_message: object
    ) -> TelegramMessage:
        """Map Telethon's runtime shape to the provider-neutral event contract."""
        text = getattr(raw_message, "raw_text", None) or getattr(raw_message, "message", "") or ""
        if getattr(raw_message, "video", None) is not None:
            media_type = "video"
        elif getattr(raw_message, "photo", None) is not None:
            media_type = "photo"
        elif getattr(raw_message, "media", None) is not None:
            media_type = "unsupported"
        else:
            media_type = "text"
        grouped_id = getattr(raw_message, "grouped_id", None)
        message_id = getattr(raw_message, "id", None)
        if type(message_id) is not int or not 1 <= message_id <= 2**31 - 1:
            raise TypeError("Telethon message is missing an integer id")
        if grouped_id is not None and (
            type(grouped_id) is not int or not -(2**63) <= grouped_id < 2**63
        ):
            raise ValueError("Telethon album identity is malformed")
        return TelegramMessage(
            account_id=account_id,
            donor_identifier=donor_identifier,
            message_id=message_id,
            text=text,
            is_edit=getattr(raw_message, "edit_date", None) is not None,
            media_type=media_type,
            album_id=str(grouped_id) if grouped_id is not None else None,
            source_updated_at=getattr(raw_message, "edit_date", None)
            or getattr(raw_message, "date", None),
        )
