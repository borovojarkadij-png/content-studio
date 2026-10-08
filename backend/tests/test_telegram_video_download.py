"""Read-only bounded raw video bytes are not validated/publishable media."""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from test_telegram_albums import raw
from test_telegram_peers import CHANNEL, PeerClient
from test_telegram_photo_download import DownloadStream

from newsflow.providers import telegram

PAYLOAD = b"synthetic raw video bytes, not a playable/validated MP4"


class VideoClient(PeerClient):
    def __init__(self, *, chunks=None):
        super().__init__()
        self.source = video_source()
        self.next_source = None
        self.stream = DownloadStream(chunks if chunks is not None else [PAYLOAD])
        self.downloads = 0
        self.reads = 0

    async def get_messages(self, entity, *, ids):
        assert ids == 20 and entity.channel_id == 1234567890
        self.reads += 1
        return self.next_source if self.reads > 1 and self.next_source is not None else self.source

    def iter_download(self, media, *, request_size, limit):
        assert media is self.source.media
        assert request_size == 64 * 1024 and limit <= 257
        self.downloads += 1
        return self.stream


def video_source():
    source = raw(20, caption="Private video caption", grouped_id=None)
    source.photo = None
    source.document = SimpleNamespace(id=123, size=len(PAYLOAD), mime_type="video/mp4")
    source.video = source.document
    source.media = object()
    source.noforwards = False
    return source


def provider(client):
    return telegram.TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
        expected_user_id=1001,
    )


def test_video_download_preserves_exact_source_bytes_without_validation_or_publication_permission():
    client = VideoClient(chunks=[PAYLOAD[:10], memoryview(PAYLOAD[10:])])
    result = provider(client).download_video("1", str(CHANNEL), 20)
    assert result.content == PAYLOAD
    assert result.message.media_type == "video" and result.message.media_id == "123"
    assert result.message.text == "Private video caption" and result.message.album_id is None
    assert result.media_validated is False and result.publication_allowed is False
    assert client.reads == 2 and client.stream.closed and client.disconnected == 1
    assert "Private video caption" not in repr(result) and "synthetic raw video" not in repr(result)


def test_grouped_video_cannot_start_a_download_or_claim_complete_membership():
    client = VideoClient()
    client.source.grouped_id = 77
    with pytest.raises(ValueError):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.downloads == 0 and client.disconnected == 1


def test_fake_video_download_uses_the_same_strict_unvalidated_contract():
    fake = telegram.FakeTelegramProvider()
    source = telegram.TelethonTelegramProvider.normalize_message("1", str(CHANNEL), video_source())
    fake._messages[("1", str(CHANNEL), 20)] = source
    fake._videos = {("1", str(CHANNEL), 20): PAYLOAD}
    result = fake.download_video("1", str(CHANNEL), 20)
    assert result.content == PAYLOAD
    assert result.media_validated is False and result.publication_allowed is False
    fake._messages[("1", str(CHANNEL), 20)] = replace(source, media_protected=True)
    with pytest.raises(ValueError):
        fake.download_video("1", str(CHANNEL), 20)


@pytest.mark.parametrize(
    "identity",
    [
        ("1", str(CHANNEL), True),
        ("1", str(CHANNEL), 0),
        ("1", str(CHANNEL), 2**31),
        ("", str(CHANNEL), 20),
        (1, str(CHANNEL), 20),
        ("1", "@unresolved", 20),
        ("1", "-1", 20),
    ],
)
def test_invalid_video_request_is_refused_before_session_or_network(identity):
    client = VideoClient()
    with pytest.raises(ValueError):
        provider(client).download_video(*identity)
    assert client.reads == 0 and client.disconnected == 0
    fake = telegram.FakeTelegramProvider()
    with pytest.raises(ValueError):
        fake.download_video(*identity)
    assert fake.session_probe_count("1") == 0


@pytest.mark.parametrize(
    "change",
    [
        {"message_id": True},
        {"message_id": 0},
        {"account_id": ""},
        {"donor_identifier": "-1"},
        {"text": None},
        {"is_edit": 1},
        {"source_updated_at": None},
        {"source_updated_at": datetime(2026, 10, 8, tzinfo=UTC).replace(tzinfo=None)},
        {"media_type": "photo"},
        {"album_id": "77"},
        {"media_id": "01"},
        {"media_protected": None},
        {"media_protected": True},
    ],
)
def test_video_result_cannot_carry_unbound_malformed_unknown_or_protected_source(change):
    message = telegram.TelethonTelegramProvider.normalize_message("1", str(CHANNEL), video_source())
    with pytest.raises((ValueError, TypeError)):
        telegram.TelegramVideoDownload(replace(message, **change), PAYLOAD)


@pytest.mark.parametrize(
    "content",
    [b"", bytearray(PAYLOAD), b"x" * (16 * 1024 * 1024 + 1)],
    ids=["empty", "mutable", "oversized"],
)
def test_video_result_rejects_empty_mutable_and_unbounded_bytes(content):
    message = telegram.TelethonTelegramProvider.normalize_message("1", str(CHANNEL), video_source())
    with pytest.raises(ValueError):
        telegram.TelegramVideoDownload(message, content)


@pytest.mark.parametrize(
    "change",
    [
        {"photo": object()},
        {"video_note": object()},
        {"gif": object()},
        {"noforwards": 0},
        {"noforwards": "false"},
        {"date": None},
    ],
)
def test_ambiguous_video_shape_or_unknown_source_cannot_reach_download(change):
    client = VideoClient()
    for field, value in change.items():
        setattr(client.source, field, value)
    with pytest.raises((ValueError, TypeError)):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.downloads == 0 and client.disconnected == 1


@pytest.mark.parametrize("size", [True, None, 0, -1, 16 * 1024 * 1024 + 1])
def test_declared_video_size_is_checked_before_any_media_rpc(size):
    client = VideoClient()
    client.source.document.size = size
    with pytest.raises(ValueError):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.downloads == 0 and client.disconnected == 1


@pytest.mark.parametrize(
    "chunks",
    [
        [],
        [b""],
        ["private invalid data"],
        [PAYLOAD[:-1]],
        [PAYLOAD, b"x"],
        [b"x" * (64 * 1024 + 1)],
        [memoryview(b"1234").cast("B", shape=[2, 2])],
    ],
)
def test_incomplete_malformed_or_excess_video_stream_never_returns_and_always_closes(chunks):
    client = VideoClient(chunks=chunks)
    with pytest.raises((ValueError, TypeError)):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.stream.closed and client.disconnected == 1


@pytest.mark.parametrize("change", ["caption", "id", "size", "mime", "group", "protected", "date"])
def test_source_change_during_video_download_never_returns_old_bytes_as_current(change):
    client = VideoClient()
    changed = video_source()
    if change == "caption":
        changed.raw_text = "Edited caption"
    elif change == "id":
        changed.document.id = 124
    elif change == "size":
        changed.document.size += 1
    elif change == "mime":
        changed.document.mime_type = "video/webm"
    elif change == "group":
        changed.grouped_id = 77
    elif change == "protected":
        changed.noforwards = True
    else:
        changed.edit_date = datetime(2026, 10, 9, tzinfo=UTC)
    client.next_source = changed
    with pytest.raises((ValueError, PermissionError)):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.stream.closed and client.disconnected == 1


def test_current_encrypted_factory_download_reopens_with_the_same_key_and_peer(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from newsflow.persistence.models import Base, TelegramAccount, TelegramPeerModel
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    target = f"sqlite:///{tmp_path / 'synthetic-video-session.db'}"
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    engine = create_engine(target)
    sessions = sessionmaker(engine)
    Base.metadata.create_all(engine)
    with sessions.begin() as session:
        session.add(
            TelegramAccount(
                id=1,
                name="Synthetic video",
                telegram_user_id=1001,
                encrypted_session=cipher.encrypt("synthetic session"),
            )
        )
    first = VideoClient()
    result = ConfiguredTelegramProvider(
        sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: first
    ).download_video("1", str(CHANNEL), 20)
    assert result.content == PAYLOAD and result.publication_allowed is False
    with sessions() as session:
        ciphertext = session.get(TelegramAccount, 1).encrypted_session
        peer_ciphertext = session.get(TelegramPeerModel, (1, CHANNEL)).encrypted_peer
    engine.dispose()
    engine = create_engine(target)
    second = VideoClient()
    sessions = sessionmaker(engine)
    try:
        result = ConfiguredTelegramProvider(
            sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: second
        ).download_video("1", str(CHANNEL), 20)
        assert result.content == PAYLOAD and second.dialog_reads == 0
        with sessions() as session:
            assert session.get(TelegramAccount, 1).encrypted_session == ciphertext
            assert session.get(TelegramPeerModel, (1, CHANNEL)).encrypted_peer == peer_ciphertext
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "change",
    [
        {"id": 20.0},
        {"chat_id": float(CHANNEL)},
        {"chat_id": CHANNEL - 1},
        {"id": 21},
        {"document": None},
        {"video": None},
        {"media": None},
    ],
)
def test_nonexact_video_rpc_identity_or_missing_document_is_refused_before_download(change):
    client = VideoClient()
    for field, value in change.items():
        setattr(client.source, field, value)
    with pytest.raises(ValueError):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.downloads == 0 and client.disconnected == 1


@pytest.mark.parametrize(
    "change", [{"account_id": "2"}, {"donor_identifier": str(CHANNEL - 1)}, {"message_id": 21}]
)
def test_fake_video_cannot_return_a_foreign_message_stored_under_the_requested_key(change):
    fake = telegram.FakeTelegramProvider()
    source = telegram.TelethonTelegramProvider.normalize_message("1", str(CHANNEL), video_source())
    fake._messages[("1", str(CHANNEL), 20)] = replace(source, **change)
    fake._videos[("1", str(CHANNEL), 20)] = PAYLOAD
    with pytest.raises(ValueError):
        fake.download_video("1", str(CHANNEL), 20)


def test_exact_video_size_bound_and_excessive_tiny_chunk_count_are_enforced():
    client = VideoClient(chunks=[b"v" * 65536] * 256)
    client.source.document.size = 16 * 1024 * 1024
    result = provider(client).download_video("1", str(CHANNEL), 20)
    assert len(result.content) == 16 * 1024 * 1024 and client.stream.closed
    client = VideoClient(chunks=[b"v"] * 258)
    client.source.document.size = 258
    with pytest.raises(ValueError):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.stream.reads == 258 and client.stream.closed


def test_floodwait_during_video_stream_is_translated_without_a_retry_or_sleep():
    from telethon.errors import FloodWaitError

    class FloodStream(DownloadStream):
        async def __anext__(self):
            self.reads += 1
            raise FloodWaitError(None, capture=90)

    client = VideoClient()
    client.stream = FloodStream([])
    with pytest.raises(telegram.FloodWait) as error:
        provider(client).download_video("1", str(CHANNEL), 20)
    assert error.value.seconds == 90 and client.downloads == 1
    assert client.stream.reads == 1 and client.stream.closed and client.disconnected == 1


def test_stalled_video_stream_obeys_outer_deadline_and_closes_before_disconnect():
    import asyncio

    class StalledStream(DownloadStream):
        async def __anext__(self):
            await asyncio.Event().wait()

    client = VideoClient()
    client.stream = StalledStream([])
    adapter = telegram.TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
        expected_user_id=1001,
        request_timeout=0.02,
    )
    with pytest.raises(TimeoutError):
        adapter.download_video("1", str(CHANNEL), 20)
    assert client.stream.closed and client.disconnected == 1


def test_removed_source_after_download_never_returns_unverifiable_bytes():
    class DeletedDuringDownload(VideoClient):
        async def get_messages(self, entity, *, ids):
            if self.reads:
                return None
            return await super().get_messages(entity, ids=ids)

    client = DeletedDuringDownload()
    with pytest.raises(LookupError):
        provider(client).download_video("1", str(CHANNEL), 20)
    assert client.stream.closed and client.disconnected == 1


def test_installed_telethon_message_document_video_shape_keeps_unset_flags_and_source_binding():
    from telethon.tl.types import (
        Document,
        DocumentAttributeVideo,
        Message,
        MessageMediaDocument,
        PeerChannel,
    )

    document = Document(
        id=123,
        access_hash=456,
        file_reference=b"synthetic reference",
        date=datetime(2026, 10, 8, tzinfo=UTC),
        mime_type="video/mp4",
        size=len(PAYLOAD),
        dc_id=1,
        attributes=[DocumentAttributeVideo(duration=1.0, w=32, h=32, supports_streaming=True)],
    )
    client = VideoClient()
    client.source = Message(
        id=20,
        peer_id=PeerChannel(1234567890),
        date=datetime(2026, 10, 8, tzinfo=UTC),
        message="Private SDK video caption",
        media=MessageMediaDocument(document=document),
    )
    assert client.source.noforwards is None
    result = provider(client).download_video("1", str(CHANNEL), 20)
    assert result.message.text == "Private SDK video caption"
    assert result.message.media_id == "123" and result.message.media_protected is False
    assert result.content == PAYLOAD and result.media_validated is False
    assert client.reads == 2 and client.stream.closed and client.disconnected == 1


class SdkIteratorClient(VideoClient):
    """Actual installed iterator; only the external byte RPC is synthetic."""

    def __init__(self, size=65536, *, initialization_failure=None):
        super().__init__()
        self.source.document.size = size
        self.session.dc_id = 1
        self._sender = object()
        self.byte_requests = 0
        self.initialization_failure = initialization_failure

    def iter_download(self, media, *, request_size, limit):
        from telethon.client.downloads import _DirectDownloadIter
        from telethon.tl.types import InputDocumentFileLocation

        assert media is self.source.media
        self.downloads += 1
        self.stream = _DirectDownloadIter(
            self,
            limit=limit,
            file=InputDocumentFileLocation(123, 456, b"synthetic", ""),
            dc_id=2 if self.initialization_failure else 1,
            offset=0,
            stride=request_size,
            chunk_size=request_size,
            request_size=request_size,
            file_size=self.source.document.size,
            msg_data=None,
        )
        return self.stream

    async def _call(self, sender, request):
        assert sender is self._sender and request.location.id == 123
        self.byte_requests += 1
        length = min(request.limit, max(0, self.source.document.size - request.offset))
        return SimpleNamespace(bytes=b"v" * length)

    async def _borrow_exported_sender(self, dc_id):
        assert dc_id == 2
        if self.initialization_failure == "flood":
            from telethon.errors import FloodWaitError

            raise FloodWaitError(None, capture=90)
        import asyncio

        await asyncio.Event().wait()


@pytest.mark.parametrize("size,requests", [(65536, 1), (16 * 1024 * 1024, 256)])
def test_actual_sdk_iterator_does_not_fetch_or_reject_empty_eof_after_exact_full_chunks(
    size, requests
):
    client = SdkIteratorClient(size)
    result = provider(client).download_video("1", str(CHANNEL), 20)
    assert result.content == b"v" * size and client.byte_requests == requests
    assert client.stream._sender is None and client.disconnected == 1


@pytest.mark.parametrize("failure", ["flood", "timeout"])
def test_actual_sdk_iterator_initialization_failure_keeps_primary_error_despite_broken_close(
    failure,
):
    client = SdkIteratorClient(initialization_failure=failure)
    adapter = telegram.TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
        expected_user_id=1001,
        request_timeout=0.02,
    )
    expected = telegram.FloodWait if failure == "flood" else TimeoutError
    with pytest.raises(expected) as error:
        adapter.download_video("1", str(CHANNEL), 20)
    if failure == "flood":
        assert error.value.seconds == 90
    assert client.byte_requests == 0 and client.disconnected == 1
