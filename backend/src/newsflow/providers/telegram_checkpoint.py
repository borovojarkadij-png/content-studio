"""Bounded authenticated current channel state, no cursor reset or history proof."""

from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, ChannelFull
from telethon.tl.types.messages import ChatFull
from telethon.utils import get_input_channel

from newsflow.providers.telegram import (
    SessionUnavailable,
    TelegramChannelCheckpoint,
    validate_difference_request,
)


def read_channel_checkpoint(provider, account_id, donor_identifier):
    # Reuse canonical identity validation only; 1 is never persisted as a pts.
    validate_difference_request(account_id, donor_identifier, 1, 10)
    if type(provider._expected_user_id) is not int or not 0 < provider._expected_user_id < 2**63:
        raise SessionUnavailable("Channel checkpoint requires a provisioned Telegram user identity")

    async def read(client):
        peer = await provider._input_channel(client, account_id, int(donor_identifier))
        result = await client(GetFullChannelRequest(get_input_channel(peer)))
        raw_id = -int(donor_identifier) - 1000000000000
        if (
            not isinstance(result, ChatFull)
            or not isinstance(result.full_chat, ChannelFull)
            or type(result.full_chat.id) is not int
            or result.full_chat.id != raw_id
            or not isinstance(result.chats, (list, tuple))
            or not isinstance(result.users, (list, tuple))
            or len(result.chats) + len(result.users) > 100
        ):
            raise ValueError("Malformed or foreign bounded channel checkpoint")
        matches = [
            chat
            for chat in result.chats
            if isinstance(chat, Channel) and type(chat.id) is int and chat.id == raw_id
        ]
        if (
            len(matches) != 1
            or matches[0].broadcast is not True
            or (matches[0].min is not None and matches[0].min is not False)
            or (matches[0].megagroup is not None and matches[0].megagroup is not False)
        ):
            raise ValueError("Checkpoint requires one full broadcast channel")
        return TelegramChannelCheckpoint(
            account_id, donor_identifier, provider._expected_user_id, result.full_chat.pts
        )

    return provider._run(account_id, read)
