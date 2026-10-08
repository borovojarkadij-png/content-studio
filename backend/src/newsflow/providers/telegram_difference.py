"""Strict read-only channel difference observation; no cursor writes or sends."""

from dataclasses import replace

from telethon.tl.functions.updates import GetChannelDifferenceRequest
from telethon.tl.types import (
    ChannelMessagesFilterEmpty,
    Message,
    UpdateDeleteChannelMessages,
    UpdateEditChannelMessage,
    UpdateNewChannelMessage,
)
from telethon.tl.types.updates import (
    ChannelDifference,
    ChannelDifferenceEmpty,
    ChannelDifferenceTooLong,
)
from telethon.utils import get_input_channel, get_peer_id

from newsflow.providers.telegram import (
    SessionUnavailable,
    TelegramChannelDifference,
    validate_difference_request,
)


class ChannelDifferenceGapUnresolved(RuntimeError):
    """Do not reset/advance a durable cursor or assume complete deletion history."""


def _normalize(provider, result, account_id, donor_identifier, *, pts, limit):
    if isinstance(result, ChannelDifferenceTooLong):
        raise ChannelDifferenceGapUnresolved("TELEGRAM_CHANNEL_DIFFERENCE_TOO_LONG")
    if not isinstance(result, (ChannelDifference, ChannelDifferenceEmpty)):
        raise TypeError("Unsupported Telegram channel difference response")
    if result.final is not None and type(result.final) is not bool:
        raise ValueError("Malformed channel difference final flag")
    messages, deleted = [], []
    if isinstance(result, ChannelDifference):
        if (
            not isinstance(result.new_messages, (list, tuple))
            or not isinstance(result.other_updates, (list, tuple))
            or len(result.new_messages) + len(result.other_updates) > limit
        ):
            raise ValueError("Channel difference exceeded its update bound")

        def observe(raw, *, edited=False):
            if not isinstance(raw, Message) or get_peer_id(raw.peer_id) != int(donor_identifier):
                raise ValueError("Telegram difference source identity mismatch")
            value = provider.normalize_message(account_id, donor_identifier, raw)
            if edited:
                if raw.edit_date is None:
                    raise ValueError(
                        "Edited difference message has no authoritative edit timestamp"
                    )
                value = replace(value, is_edit=True)
            messages.append(value)

        for raw in result.new_messages:
            observe(raw)
        for update in result.other_updates:
            if not isinstance(
                update,
                (UpdateEditChannelMessage, UpdateDeleteChannelMessages, UpdateNewChannelMessage),
            ):
                raise ChannelDifferenceGapUnresolved("TELEGRAM_CHANNEL_UPDATE_UNSUPPORTED")
            if (
                type(update.pts) is not int
                or type(update.pts_count) is not int
                or not pts < update.pts <= result.pts
                or not 1 <= update.pts_count <= update.pts - pts
            ):
                raise ValueError("Invalid channel update pts")
            if isinstance(update, UpdateDeleteChannelMessages):
                if (
                    type(update.channel_id) is not int
                    or update.channel_id != -int(donor_identifier) - 1000000000000
                    or not isinstance(update.messages, (list, tuple))
                    or not update.messages
                    or len(update.messages) > limit
                ):
                    raise ValueError("Foreign or oversized channel deletion")
                deleted.extend(update.messages)
            else:
                observe(update.message, edited=isinstance(update, UpdateEditChannelMessage))
    if len(messages) + len(deleted) > limit:
        raise ValueError("Channel difference exceeded observation bound")
    return TelegramChannelDifference(
        account_id,
        donor_identifier,
        pts,
        result.pts,
        result.final is True,
        0 if result.timeout is None else result.timeout,
        tuple(messages),
        tuple(deleted),
    )


def read_channel_difference(provider, account_id, donor_identifier, *, pts, limit):
    validate_difference_request(account_id, donor_identifier, pts, limit)
    if type(provider._expected_user_id) is not int or provider._expected_user_id <= 0:
        raise SessionUnavailable("Channel difference requires a provisioned Telegram user identity")

    async def read(client):
        peer = await provider._input_channel(client, account_id, int(donor_identifier))
        result = await client(
            GetChannelDifferenceRequest(
                channel=get_input_channel(peer),
                filter=ChannelMessagesFilterEmpty(),
                pts=pts,
                limit=limit,
                force=False,
            )
        )
        return _normalize(provider, result, account_id, donor_identifier, pts=pts, limit=limit)

    return provider._run(account_id, read)
