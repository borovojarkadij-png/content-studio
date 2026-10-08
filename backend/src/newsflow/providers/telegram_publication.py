"""Explicitly injected text/photo sender; never constructed by the runtime worker.

No hidden retries, scheduling, forwarding, Markdown parsing or paid sending.
Only a nonce-correlated, exact output-channel message is a delivery receipt.
"""

import re
from hashlib import sha256

from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import SendMediaRequest, SendMessageRequest
from telethon.tl.types import (
    Channel,
    InputFile,
    InputFileBig,
    InputMediaUploadedPhoto,
    Message,
    MessageMediaPhoto,
    Photo,
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
    _text_limit = 4096

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
            or len(envelope.text.encode("utf-16-le")) // 2 > self._text_limit
        ):
            raise ValueError("Invalid bound text publication request")
        self._validate_media(envelope)
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
            request = await self._prepare_request(client, envelope, peer, nonce)
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

    def _validate_media(self, envelope):
        if envelope.media_asset_id is not None or envelope.media_sha256 is not None:
            raise PublicationBlocked("TEXT_TRANSPORT_DOES_NOT_SUPPORT_MEDIA")

    async def _prepare_request(self, client, envelope, peer, nonce):
        return SendMessageRequest(
            peer=peer,
            message=envelope.text,
            random_id=nonce,
            no_webpage=True,
            entities=[],
            allow_paid_stars=0,
            allow_paid_floodskip=False,
        )


class TelethonPhotoPublisher(TelethonTextPublisher):
    _text_limit = 1024

    def __init__(self, adapter_for_envelope, *, photo_for_envelope):
        super().__init__(adapter_for_envelope)
        if not callable(photo_for_envelope):
            raise TypeError("An explicit bound source-photo reader is required")
        self._photo_for = photo_for_envelope

    def _validate_media(self, envelope):
        if (
            type(envelope.media_asset_id) is not int
            or envelope.media_asset_id <= 0
            or not isinstance(envelope.media_sha256, str)
            or re.fullmatch(r"[a-f0-9]{64}", envelope.media_sha256) is None
        ):
            raise ValueError("An exact bound source photo is required")

    async def _prepare_request(self, client, envelope, peer, nonce):
        content = self._photo_for(envelope)
        if (
            type(content) is not bytes
            or not 0 < len(content) <= 16 * 1024 * 1024
            or sha256(content).hexdigest() != envelope.media_sha256
        ):
            raise PublicationBlocked("CURRENT_PHOTO_BYTE_IDENTITY_REQUIRED")
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            file_name = "source.png"
        elif content.startswith(b"\xff\xd8\xff"):
            file_name = "source.jpg"
        else:
            raise PublicationBlocked("SUPPORTED_PHOTO_SIGNATURE_REQUIRED")
        # Configured reader has already bounded/decoded bytes and checked current
        # rights. Upload is preparation, not channel publication. Guard runs later.
        uploaded = await client.upload_file(content, file_name=file_name)
        if not isinstance(uploaded, (InputFile, InputFileBig)):
            raise TypeError("Photo upload returned no usable file handle")
        return SendMediaRequest(
            peer=peer,
            media=InputMediaUploadedPhoto(file=uploaded),
            message=envelope.text,
            random_id=nonce,
            entities=[],
            allow_paid_stars=0,
            allow_paid_floodskip=False,
        )


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
    media_matches = message.media is None
    if envelope.media_asset_id is not None:
        media_matches = (
            isinstance(message.media, MessageMediaPhoto)
            and isinstance(message.media.photo, Photo)
            and type(message.media.photo.id) is int
            and message.media.photo.id > 0
            and not message.media.video
            and not message.media.live_photo
        )
    if (
        get_peer_id(message.peer_id) != envelope.telegram_channel_id
        or message.out is not True
        or message.post is not True
        or message.message != envelope.text
        or not media_matches
        or message.fwd_from is not None
        or message.from_scheduled
        or message.grouped_id is not None
    ):
        raise ValueError("Publication response does not match the exact sent request")
    return PublicationReceipt(envelope.account_id, envelope.telegram_channel_id, nonce, message.id)
