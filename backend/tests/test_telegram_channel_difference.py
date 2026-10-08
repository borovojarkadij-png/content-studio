from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from telethon.errors import FloodWaitError
from telethon.tl.functions.updates import GetChannelDifferenceRequest
from telethon.tl.types import (
    ChannelMessagesFilterEmpty,
    Message,
    PeerChannel,
    UpdateDeleteChannelMessages,
    UpdateDeleteMessages,
    UpdateEditChannelMessage,
)
from telethon.tl.types.updates import (
    ChannelDifference,
    ChannelDifferenceEmpty,
    ChannelDifferenceTooLong,
)
from test_telethon_rpc import Client

from newsflow.providers.telegram import (
    FloodWait,
    SessionUnavailable,
    TelegramChannelPeer,
    TelethonTelegramProvider,
)

CHANNEL = -1001234567890
DATE = datetime(2026, 10, 8, tzinfo=UTC)


class DifferenceClient(Client):
    def __init__(self, result, **kwargs):
        super().__init__(**kwargs)
        self.result, self.requests = result, []

    async def __call__(self, request):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def adapter(client):
    return TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic"},
        client_factory=lambda _: client,
        expected_user_id=1001,
        peers=(TelegramChannelPeer("1", CHANNEL, 999),),
    )


def read(provider, *, pts=10, limit=50):
    return provider.channel_difference("1", str(CHANNEL), pts=pts, limit=limit)


def message(message_id=20, channel_id=1234567890, **kwargs):
    return Message(
        id=message_id,
        peer_id=PeerChannel(channel_id),
        date=DATE,
        message="Synthetic news",
        **kwargs,
    )


def test_difference_read_is_bound_to_channel_cursor_and_never_sends_or_skips_updates():
    client = DifferenceClient(
        ChannelDifference(
            pts=13,
            new_messages=[message()],
            other_updates=[
                UpdateEditChannelMessage(message(21, edit_date=DATE), pts=12, pts_count=1),
                UpdateDeleteChannelMessages(1234567890, [22], pts=13, pts_count=1),
            ],
            chats=[],
            users=[],
            final=False,
            timeout=30,
        )
    )
    result = read(adapter(client))
    assert (
        result.account_id,
        result.donor_identifier,
        result.start_pts,
        result.next_pts,
        result.final,
        result.retry_after_seconds,
    ) == ("1", str(CHANNEL), 10, 13, False, 30)
    assert [(item.message_id, item.is_edit, item.text) for item in result.messages] == [
        (20, False, "Synthetic news"),
        (21, True, "Synthetic news"),
    ]
    assert result.deleted_message_ids == (22,)
    assert client.connected == client.disconnected == 1 and len(client.requests) == 1
    request = client.requests[0]
    assert isinstance(request, GetChannelDifferenceRequest)
    assert (
        request.channel.channel_id,
        request.channel.access_hash,
        request.pts,
        request.limit,
        request.force,
    ) == (1234567890, 999, 10, 50, False)
    assert isinstance(request.filter, ChannelMessagesFilterEmpty)


def test_empty_difference_preserves_explicit_final_and_timeout():
    result = read(adapter(DifferenceClient(ChannelDifferenceEmpty(10, final=True, timeout=45))))
    assert result.final is True and result.messages == () and result.deleted_message_ids == ()
    assert result.next_pts == 10 and result.retry_after_seconds == 45


@pytest.mark.parametrize(
    "response",
    [
        ChannelDifferenceTooLong(dialog=None, messages=[], chats=[], users=[], final=True),
        ChannelDifferenceEmpty(9, final=True),
        ChannelDifferenceEmpty(10, final=False),
        ChannelDifference(11, [], [UpdateDeleteMessages([20], 11, 1)], [], [], final=True),
        ChannelDifference(11, [message(channel_id=9876543210)], [], [], [], final=True),
        ChannelDifference(
            11, [], [UpdateDeleteChannelMessages(9876543210, [20], 11, 1)], [], [], final=True
        ),
    ],
)
def test_gap_regression_unknown_or_foreign_updates_never_become_a_complete_chunk(response):
    client = DifferenceClient(response)
    with pytest.raises((ValueError, RuntimeError)):
        read(adapter(client))
    assert client.disconnected == 1


@pytest.mark.parametrize(
    "pts,limit", [(0, 50), (True, 50), (2**31, 50), (10, 1), (10, 101), (10, True)]
)
def test_invalid_bounds_never_connect_or_consume_channel_updates(pts, limit):
    client = DifferenceClient(ChannelDifferenceEmpty(10, final=True))
    with pytest.raises(ValueError):
        read(adapter(client), pts=pts, limit=limit)
    assert client.connected == 0 and not client.requests


def test_difference_floodwait_uses_existing_deadline_and_session_health_boundary():
    client = DifferenceClient(FloodWaitError(None, capture=120))
    with pytest.raises(FloodWait) as error:
        read(adapter(client))
    assert error.value.seconds == 120 and client.disconnected == 1
    unauthorized = DifferenceClient(ChannelDifferenceEmpty(10, final=True), authorized=False)
    with pytest.raises(SessionUnavailable):
        read(adapter(unauthorized))
    assert not unauthorized.requests and unauthorized.disconnected == 1


def test_empty_deletion_update_cannot_advance_a_content_cursor():
    client = DifferenceClient(
        ChannelDifference(
            11, [], [UpdateDeleteChannelMessages(1234567890, [], 11, 1)], [], [], final=True
        )
    )
    with pytest.raises(ValueError):
        read(adapter(client))


@pytest.mark.parametrize(
    "response",
    [
        ChannelDifferenceEmpty(True, final=True),
        ChannelDifferenceEmpty(11, final=1),
        ChannelDifferenceEmpty(11, final=True, timeout=True),
        ChannelDifference(11, [message()] * 51, [], [], [], final=True),
        ChannelDifference(
            11, [], [UpdateDeleteChannelMessages(1234567890, [True], 11, 1)], [], [], final=True
        ),
        ChannelDifference(
            11, [], [UpdateDeleteChannelMessages(1234567890, [20, 20], 11, 1)], [], [], final=True
        ),
        ChannelDifference(11, [], [UpdateEditChannelMessage(message(), 11, 1)], [], [], final=True),
    ],
)
def test_malformed_or_oversized_content_observations_fail_closed(response):
    client = DifferenceClient(response)
    with pytest.raises((ValueError, TypeError)):
        read(adapter(client))
    assert client.disconnected == 1


def test_boolean_user_identity_cannot_authorize_a_channel_difference():
    client = DifferenceClient(ChannelDifferenceEmpty(10, final=True))

    async def malformed_user():
        return SimpleNamespace(id=True)

    client.get_me = malformed_user
    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic"},
        client_factory=lambda _: client,
        expected_user_id=1,
        peers=(TelegramChannelPeer("1", CHANNEL, 999),),
    )
    with pytest.raises(SessionUnavailable):
        read(provider)
    assert not client.requests


def test_unbound_user_identity_never_starts_difference_connection():
    client = DifferenceClient(ChannelDifferenceEmpty(10, final=True))
    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic"},
        client_factory=lambda _: client,
    )
    with pytest.raises(SessionUnavailable):
        read(provider)
    assert not client.requests and client.connected == 0


def test_fake_difference_is_replayable_and_never_fabricates_an_unseeded_cursor():
    from newsflow.providers.telegram import FakeTelegramProvider

    observed = read(adapter(DifferenceClient(ChannelDifferenceEmpty(11, final=True))))
    fake = FakeTelegramProvider()
    fake.seed_channel_difference(observed)
    assert read(fake) == observed and read(fake) == observed
    with pytest.raises(KeyError):
        read(fake, pts=11)
    fake.seed_floodwait("1", 120)
    with pytest.raises(FloodWait):
        read(fake)


def test_configured_difference_uses_fresh_encrypted_session_and_persists_refresh(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from newsflow.persistence.models import Base, TelegramAccount
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    engine = create_engine(f"sqlite:///{tmp_path / 'difference-session.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with factory.begin() as session:
        session.add(
            TelegramAccount(
                name="Synthetic difference",
                telegram_user_id=1001,
                encrypted_session=cipher.encrypt("initial"),
            )
        )
    client = DifferenceClient(ChannelDifferenceEmpty(10, final=True))
    client.session = SimpleNamespace(save=lambda: "refreshed")
    provider = ConfiguredTelegramProvider(
        factory, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    assert read(provider).final is True
    with factory() as session:
        row = session.get(TelegramAccount, 1)
        assert (
            row.encrypted_session != "refreshed"
            and cipher.decrypt(row.encrypted_session) == "refreshed"
        )
    with factory.begin() as session:
        session.get(TelegramAccount, 1).encrypted_session = "invalid"
    with pytest.raises(SessionUnavailable):
        read(provider)
    assert len(client.requests) == 1
    engine.dispose()


def test_configured_invalid_difference_never_accesses_storage():
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    def forbidden():
        raise AssertionError("Invalid difference must not load/decrypt sessions")

    provider = ConfiguredTelegramProvider(
        forbidden,
        cipher=SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="),
        api_id=123,
        api_hash="a" * 32,
    )
    with pytest.raises(ValueError):
        read(provider, pts=0)
