"""Explicit first authorization, separate from the read-only provider."""

import asyncio
import logging
import re
import struct
from dataclasses import dataclass, field

from newsflow.services.telegram_provider_factory import (
    TelegramCredentialsUnavailable,
    _validate_credentials,
)


class TelegramLoginError(RuntimeError):
    """A private authorization or provisioning failure."""


class _PrivateLogger(logging.Logger):
    def getChild(self, suffix):
        # Telethon derives child loggers. Keep them on this isolated disabled
        # instance; Logger.getChild otherwise registers children under root.
        return self


@dataclass(frozen=True)
class AuthorizedTelegramSession:
    telegram_user_id: int = field(repr=False)
    phone: str = field(repr=False)
    string_session: str = field(repr=False)


def _positive_id(value):
    return type(value) is int and 0 < value < 2**63


def _validate_phone(phone):
    if not isinstance(phone, str) or re.fullmatch(r"\+[1-9][0-9]{4,14}", phone) is None:
        raise TelegramLoginError("Telegram authorization failed")


def _validate_authorized_session(result, phone, expected_user_id=None):
    """Revalidate the SDK serialization at both RPC and persistence boundaries."""
    from telethon.sessions import StringSession

    if (
        not isinstance(result, AuthorizedTelegramSession)
        or not _positive_id(result.telegram_user_id)
        or result.phone != phone
        or (expected_user_id is not None and result.telegram_user_id != expected_user_id)
        or not isinstance(result.string_session, str)
        or not 1 <= len(result.string_session) <= 4096
    ):
        raise TelegramLoginError("Telegram authorization failed")
    try:
        session = StringSession(result.string_session)
        if session.auth_key is None or len(session.auth_key.key) != 256:
            raise ValueError("Missing authorization key")
    except (ValueError, TypeError, AttributeError, struct.error):
        raise TelegramLoginError("Telegram authorization failed") from None


class TelethonLoginAdapter:
    """One explicit code attempt and optional 2FA; never discovers credentials."""

    def __init__(self, api_id, api_hash, client_factory=None):
        try:
            _validate_credentials(api_id, api_hash)
        except TelegramCredentialsUnavailable:
            raise TelegramLoginError("Telegram authorization failed") from None
        self._api_id = api_id
        self._api_hash = api_hash
        self._clients = client_factory

    async def authorize(self, phone, *, read_code, read_password):
        from telethon import TelegramClient
        from telethon.errors import SessionPasswordNeededError
        from telethon.sessions import StringSession
        from telethon.tl.types import User

        _validate_phone(phone)
        client = None
        failed = True
        try:
            logger = _PrivateLogger("newsflow.telegram_login.private")
            logger.propagate = False
            logger.disabled = True
            logger.addHandler(logging.NullHandler())
            factory = self._clients if self._clients is not None else TelegramClient
            client = factory(
                StringSession(),
                self._api_id,
                self._api_hash,
                request_retries=0,
                connection_retries=0,
                auto_reconnect=False,
                flood_sleep_threshold=0,
                receive_updates=False,
                base_logger=logger,
            )
            await asyncio.wait_for(client.connect(), timeout=15)
            sent = await asyncio.wait_for(client.send_code_request(phone), timeout=15)
            code_hash = getattr(sent, "phone_code_hash", None)
            if not isinstance(code_hash, str) or not 1 <= len(code_hash) <= 4096:
                raise TelegramLoginError("Telegram authorization failed")
            code = read_code()
            if not isinstance(code, str) or re.fullmatch(r"[0-9]{4,8}", code) is None:
                raise TelegramLoginError("Telegram authorization failed")
            try:
                await asyncio.wait_for(
                    client.sign_in(phone=phone, code=code, phone_code_hash=code_hash), timeout=15
                )
            except SessionPasswordNeededError:
                password = read_password()
                if not isinstance(password, str) or not 1 <= len(password) <= 1024:
                    raise TelegramLoginError("Telegram authorization failed")
                await asyncio.wait_for(client.sign_in(password=password), timeout=15)
            if await asyncio.wait_for(client.is_user_authorized(), timeout=15) is not True:
                raise TelegramLoginError("Telegram authorization failed")
            me = await asyncio.wait_for(client.get_me(), timeout=15)
            if (
                not isinstance(me, User)
                or not _positive_id(me.id)
                or (me.bot is not False and me.bot is not None)
                or not isinstance(me.phone, str)
                or "+" + me.phone != phone
            ):
                raise TelegramLoginError("Telegram authorization failed")
            result = AuthorizedTelegramSession(me.id, phone, client.session.save())
            _validate_authorized_session(result, phone)
            failed = False
            return result
        except EOFError:
            raise
        except Exception:  # noqa: BLE001 -- RPC/client failures must never expose provider text.
            raise TelegramLoginError("Telegram authorization failed") from None
        finally:
            if client is not None:
                try:
                    await asyncio.wait_for(client.disconnect(), timeout=3)
                except BaseException:  # noqa: BLE001 -- Preserve primary failure including aborts.
                    # Cleanup must not mask an RPC failure or an operator abort.
                    if not failed:
                        raise TelegramLoginError("Telegram authorization failed") from None
