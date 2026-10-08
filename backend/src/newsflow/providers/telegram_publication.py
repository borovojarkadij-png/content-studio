"""Explicitly injected text-only sender; never constructed by the runtime worker.

No hidden retries, scheduling, forwarding, Markdown parsing or paid sending.
Only a nonce-correlated, exact output-channel message is a delivery receipt.
"""

from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.types import (
    Channel,
    Message,
    UpdateMessageID,
    UpdateNewChannelMessage,
    Updates,
    UpdatesCombined,
)
from telethon.utils import get_peer_id

from newsflow.providers.telegram import SessionUnavailable, TelethonTelegramProvider
from newsflow.services.durable_publication_runner import PublicationNotSentRetry, PublicationReceipt
from newsflow.services.publication import PublicationBlocked
from newsflow.services.publication_preflight import PublicationEnvelope


class TelethonTextPublisher:
    def __init__(self, adapter_for_envelope):
        if not callable(adapter_for_envelope):
            raise TypeError("An explicit bound Telegram adapter factory is required")
        self._adapter_for = adapter_for_envelope

    def publish(self, envelope, nonce, *, execution_guard):
        if (
            not isinstance(envelope, PublicationEnvelope)
            or not callable(execution_guard)
            or any(
                type(value) is not int or value <= 0
                for value in (
                    envelope.planned_id,
                    envelope.candidate_id,
                    envelope.account_id,
                    envelope.user_id,
                    envelope.output_channel_id,
                    envelope.rewrite_output_id,
                )
            )
            or type(nonce) is not int
            or not 0 < nonce < 2**63
            or type(envelope.telegram_channel_id) is not int
            or envelope.telegram_channel_id >= -1000000000000
            or not isinstance(envelope.text, str)
            or not envelope.text.strip()
            or len(envelope.text.encode("utf-16-le")) // 2 > 4096
        ):
            raise ValueError("Invalid bound text publication request")
        if envelope.media_asset_id is not None or envelope.media_sha256 is not None:
            raise PublicationBlocked("TEXT_TRANSPORT_DOES_NOT_SUPPORT_MEDIA")
        adapter = self._adapter_for(envelope)
        if (
            not isinstance(adapter, TelethonTelegramProvider)
            or type(adapter._expected_user_id) is not int
            or adapter._expected_user_id != envelope.user_id
        ):
            raise SessionUnavailable("Publication requires an account-bound provisioned session")

        async def send(client):
            peer = await adapter._input_channel(
                client, str(envelope.account_id), envelope.telegram_channel_id
            )
            entity = await client.get_entity(peer)
            if (
                not isinstance(entity, Channel)
                or get_peer_id(entity) != envelope.telegram_channel_id
                or entity.broadcast is not True
                or entity.megagroup
                or entity.left
                or entity.min
                or not (
                    entity.creator is True
                    or (
                        entity.admin_rights is not None
                        and entity.admin_rights.post_messages is True
                    )
                )
            ):
                raise PublicationBlocked("CURRENT_DESTINATION_POST_PERMISSION_REQUIRED")
            request = SendMessageRequest(
                peer=peer,
                message=envelope.text,
                random_id=nonce,
                no_webpage=True,
                entities=[],
                allow_paid_stars=0,
                allow_paid_floodskip=False,
            )
            # Final local fresh decision/lease validation after all read-only RPCs.
            # No await, database lock or media/network preparation between this
            # callback and the one send RPC. The runner already committed SENDING.
            execution_guard()
            try:
                result = await client(request)
            except FloodWaitError as exc:
                # Only this send-RPC rejection is proof of non-delivery. Auth,
                # permissions, timeout and malformed response never become retry.
                raise PublicationNotSentRetry(max(1, exc.seconds)) from None
            return _exact_receipt(result, envelope, nonce)

        return adapter._run(str(envelope.account_id), send)


def _exact_receipt(result, envelope, nonce):
    if not isinstance(result, (Updates, UpdatesCombined)):
        raise TypeError("Publication response has no exact channel acknowledgement")
    mappings = [
        item
        for item in result.updates
        if isinstance(item, UpdateMessageID) and item.random_id == nonce
    ]
    if len(mappings) != 1 or type(mappings[0].id) is not int or not 0 < mappings[0].id <= 2**31 - 1:
        raise ValueError("Publication response has no unambiguous nonce mapping")
    messages = [
        item.message
        for item in result.updates
        if isinstance(item, UpdateNewChannelMessage)
        and isinstance(item.message, Message)
        and item.message.id == mappings[0].id
    ]
    if len(messages) != 1:
        raise ValueError("Publication response has no unambiguous channel message")
    message = messages[0]
    if (
        get_peer_id(message.peer_id) != envelope.telegram_channel_id
        or message.out is not True
        or message.post is not True
        or message.message != envelope.text
        or message.media is not None
        or message.fwd_from is not None
        or message.from_scheduled
        or message.grouped_id is not None
    ):
        raise ValueError("Publication response does not match the exact sent request")
    return PublicationReceipt(envelope.account_id, envelope.telegram_channel_id, nonce, message.id)
