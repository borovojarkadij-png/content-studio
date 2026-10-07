from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from test_telegram_albums import raw
from test_telegram_peers import CHANNEL, PeerClient

from newsflow.providers import telegram


def png():
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


class DownloadStream:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.closed = False
        self.reads = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            value = next(self.chunks)
        except StopIteration:
            raise StopAsyncIteration from None
        self.reads += 1
        return value

    async def close(self):
        self.closed = True


class PhotoClient(PeerClient):
    def __init__(self, *, source=None, chunks=None):
        super().__init__()
        self.source = (
            source if source is not None else raw(20, caption="Photo caption", grouped_id=None)
        )
        self.source.media = object()
        self.source.photo = SimpleNamespace(id=123)
        self.stream = DownloadStream(chunks if chunks is not None else [png()])
        self.downloads = 0
        self.reads = 0
        self.next_source = None

    async def get_messages(self, entity, *, ids):
        assert ids == 20 and entity.channel_id == 1234567890
        self.reads += 1
        return self.next_source if self.reads > 1 and self.next_source is not None else self.source

    def iter_download(self, media, *, request_size, limit):
        assert media is self.source.media
        assert request_size <= 64 * 1024 and limit <= 257
        self.downloads += 1
        return self.stream


def provider(client):
    return telegram.TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
        expected_user_id=1001,
    )


def test_read_only_photo_download_preserves_source_binding_and_original_bytes():
    data = png()
    client = PhotoClient(chunks=[data[:15], memoryview(data[15:])])
    result = provider(client).download_photo("1", str(CHANNEL), 20)
    assert result.content == data
    assert result.message.text == "Photo caption"
    assert result.message.message_id == 20
    assert result.message.media_type == "photo" and result.message.album_id is None
    assert result.message.media_id == "123"
    assert client.reads == 2
    assert client.stream.closed and client.disconnected == 1
    assert "Photo caption" not in repr(result) and str(data) not in repr(result)


@pytest.mark.parametrize(
    "source",
    [
        raw(20, grouped_id=77),
        raw(21, grouped_id=None),
        raw(20, grouped_id=None, chat_id=CHANNEL - 1),
    ],
)
def test_foreign_missing_or_grouped_photo_cannot_reach_the_download_rpc(source):
    client = PhotoClient(source=source)
    with pytest.raises((ValueError, PermissionError)):
        provider(client).download_photo("1", str(CHANNEL), 20)
    assert client.downloads == 0 and client.disconnected == 1


def test_protected_message_never_downloads_even_with_a_provisioned_authorized_session():
    source = raw(20, grouped_id=None)
    source.noforwards = True
    client = PhotoClient(source=source)
    with pytest.raises(PermissionError):
        provider(client).download_photo("1", str(CHANNEL), 20)
    assert client.downloads == 0 and client.disconnected == 1


@pytest.mark.parametrize(
    "chunks",
    [
        [b"x" * (64 * 1024 + 1)],
        [b""],
        ["invalid"],
        [b"x" * (64 * 1024)] * 257,
    ],
)
def test_photo_stream_bounds_refuse_malformed_empty_or_oversized_data_and_close(chunks):
    client = PhotoClient(chunks=chunks)
    with pytest.raises((ValueError, TypeError)):
        provider(client).download_photo("1", str(CHANNEL), 20)
    assert client.stream.closed and client.disconnected == 1


def test_fake_photo_download_contract_preserves_metadata_and_rejects_albums():
    provider = telegram.FakeTelegramProvider()
    message = telegram.TelegramMessage(
        "1", str(CHANNEL), 20, "Caption", media_type="photo", media_id="123", media_protected=False
    )
    provider._messages[("1", str(CHANNEL), 20)] = message
    provider._photos[("1", str(CHANNEL), 20)] = png()
    assert provider.download_photo("1", str(CHANNEL), 20).content == png()
    provider._messages[("1", str(CHANNEL), 20)] = replace(message, album_id="77")
    with pytest.raises(ValueError):
        provider.download_photo("1", str(CHANNEL), 20)


@pytest.mark.parametrize("change", ["photo", "caption", "protection"])
def test_photo_or_protection_change_during_stream_is_not_returned_as_original_source(change):
    client = PhotoClient()
    changed = raw(20, caption="Photo caption", grouped_id=None)
    changed.photo = SimpleNamespace(id=124 if change == "photo" else 123)
    if change == "caption":
        changed.raw_text = "Edited caption"
    if change == "protection":
        changed.noforwards = True
    client.next_source = changed
    with pytest.raises((ValueError, PermissionError)):
        provider(client).download_photo("1", str(CHANNEL), 20)
    assert client.stream.closed and client.disconnected == 1


def test_photo_without_a_stable_media_id_is_not_downloaded():
    client = PhotoClient()
    client.source.photo = object()
    with pytest.raises(ValueError):
        provider(client).download_photo("1", str(CHANNEL), 20)
    assert client.downloads == 0


def test_empty_stream_is_not_returned_as_a_downloaded_photo():
    client = PhotoClient(chunks=[])
    with pytest.raises(ValueError):
        provider(client).download_photo("1", str(CHANNEL), 20)
    assert client.stream.closed and client.disconnected == 1
