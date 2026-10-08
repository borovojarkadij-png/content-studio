from dataclasses import replace
from hashlib import sha256
from importlib import import_module
from types import SimpleNamespace

import pytest
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import InputFile, InputMediaUploadedPhoto, MessageMediaPhoto, Photo
from test_telegram_photo_download import png
from test_telegram_text_publication import NONCE, NOW, Client, envelope, reply

from newsflow.providers.telegram import TelegramChannelPeer, TelethonTelegramProvider
from newsflow.services.publication import PublicationBlocked


class PhotoClient(Client):
    def __init__(self):
        super().__init__()
        self.uploaded = []
        self.during_upload = None
        self.upload_failure = None
        self.upload_result = InputFile(77, 1, "photo.png", "0" * 32)
        self.response = reply()
        self.response.updates[1].message.media = MessageMediaPhoto(
            photo=Photo(123, 456, b"synthetic", NOW, [], 1)
        )

    async def upload_file(self, content, *, file_name):
        self.events.append("upload")
        self.uploaded.append((content, file_name))
        if self.during_upload:
            self.during_upload()
        if self.upload_failure:
            raise self.upload_failure
        return self.upload_result


def photo_envelope(content=None):
    content = png() if content is None else content
    return replace(envelope(), media_asset_id=1, media_sha256=sha256(content).hexdigest())


def publisher(client, *, content=None):
    implementation = import_module("newsflow.providers.telegram_publication")
    assert hasattr(implementation, "TelethonPhotoPublisher"), "Guarded photo publisher is missing"
    adapter = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic"},
        client_factory=lambda _: client,
        expected_user_id=1001,
        peers=(TelegramChannelPeer("1", -1001234567890, 999),),
    )
    return implementation.TelethonPhotoPublisher(
        lambda _: adapter, photo_for_envelope=lambda _: png() if content is None else content
    )


def test_photo_upload_preserves_exact_bytes_caption_and_nonce_guard_runs_after_upload():
    client = PhotoClient()
    receipt = publisher(client).publish(
        photo_envelope(), NONCE, execution_guard=lambda: client.events.append("guard")
    )
    assert receipt.message_id == 501
    assert client.events == ["connect", "permissions", "upload", "guard", "send-rpc", "disconnect"]
    assert client.uploaded == [(png(), "source.png")]
    (request,) = client.requests
    assert isinstance(request, SendMediaRequest)
    assert isinstance(request.media, InputMediaUploadedPhoto)
    assert request.media.file.id == 77
    assert request.message == "Тестовый пост 42" and request.random_id == NONCE
    assert request.allow_paid_stars == 0 and not request.allow_paid_floodskip
    assert not request.entities and not request.schedule_date and not request.send_as


def test_editorial_reject_after_upload_still_means_zero_send_rpc():
    client = PhotoClient()

    def reject():
        raise PublicationBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")

    with pytest.raises(PublicationBlocked):
        publisher(client).publish(photo_envelope(), NONCE, execution_guard=reject)
    assert len(client.uploaded) == 1 and not client.requests


@pytest.mark.parametrize("content", [b"different", b"", bytearray(b"mutable")])
def test_photo_identity_mismatch_never_uploads_or_sends(content):
    client = PhotoClient()
    with pytest.raises((ValueError, TypeError, PublicationBlocked)):
        publisher(client, content=content).publish(
            photo_envelope(), NONCE, execution_guard=lambda: None
        )
    assert not client.uploaded and not client.requests


def test_photo_caption_limit_is_checked_before_connect():
    client = PhotoClient()
    with pytest.raises(ValueError):
        publisher(client).publish(
            replace(photo_envelope(), text="😀" * 513), NONCE, execution_guard=lambda: None
        )
    assert not client.events


def test_upload_timeout_never_calls_send_or_falls_back_to_text():
    client = PhotoClient()
    client.upload_failure = TimeoutError("synthetic upload failed")
    with pytest.raises(TimeoutError):
        publisher(client).publish(photo_envelope(), NONCE, execution_guard=lambda: None)
    assert len(client.uploaded) == 1 and not client.requests


def test_malformed_upload_handle_is_not_a_photo_request():
    client = PhotoClient()
    client.upload_result = SimpleNamespace(id=77)
    with pytest.raises(TypeError):
        publisher(client).publish(photo_envelope(), NONCE, execution_guard=lambda: None)
    assert not client.requests


@pytest.mark.parametrize(
    "media", [None, MessageMediaPhoto(), MessageMediaPhoto(photo=Photo(0, 1, b"", NOW, [], 1))]
)
def test_text_or_empty_photo_acknowledgement_never_confirms_photo(media):
    client = PhotoClient()
    client.response.updates[1].message.media = media
    with pytest.raises(ValueError):
        publisher(client).publish(photo_envelope(), NONCE, execution_guard=lambda: None)
    assert len(client.requests) == 1
