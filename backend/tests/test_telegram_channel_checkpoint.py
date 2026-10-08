from types import SimpleNamespace

import pytest
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel, ChannelFull, ChatPhotoEmpty, PeerNotifySettings, PhotoEmpty
from telethon.tl.types.messages import ChatFull
from test_telegram_channel_difference import DATE, DifferenceClient, adapter

from newsflow.providers.telegram import (
    FakeTelegramProvider,
    FloodWait,
    SessionUnavailable,
    TelegramChannelCheckpoint,
)

CHANNEL = "-1001234567890"


def full(*, pts=10, full_id=1234567890, **flags):
    return ChatFull(
        ChannelFull(full_id, "Synthetic", 0, 0, 0, PhotoEmpty(0), PeerNotifySettings(), [], pts),
        [
            Channel(
                id=1234567890,
                title="Synthetic",
                photo=ChatPhotoEmpty(),
                date=DATE,
                access_hash=999,
                broadcast=True,
                **flags,
            )
        ],
        [],
    )


def read(provider, account="1", channel=CHANNEL):
    return provider.channel_checkpoint(account, channel)


def test_checkpoint_reads_exact_authenticated_channel_pts_without_send_or_history():
    client = DifferenceClient(full())
    checkpoint = read(adapter(client))
    assert (
        checkpoint.account_id,
        checkpoint.donor_identifier,
        checkpoint.user_id,
        checkpoint.pts,
    ) == ("1", CHANNEL, 1001, 10)
    assert len(client.requests) == 1 and isinstance(client.requests[0], GetFullChannelRequest)
    assert client.requests[0].channel.channel_id == 1234567890
    assert client.connected == client.disconnected == 1
    assert client.history_args is None


@pytest.mark.parametrize("pts", [0, -1, True, None, "10", 2147483648])
def test_malformed_current_pts_never_becomes_baseline(pts):
    client = DifferenceClient(full(pts=pts))
    with pytest.raises(ValueError):
        read(adapter(client))
    assert client.disconnected == 1


@pytest.mark.parametrize("flags", [{"min": True}, {"megagroup": True}])
def test_min_or_group_chat_cannot_supply_broadcast_baseline(flags):
    client = DifferenceClient(full(**flags))
    with pytest.raises(ValueError):
        read(adapter(client))


def test_foreign_full_channel_cannot_be_relabeled_as_requested_donor():
    client = DifferenceClient(full(full_id=9876543210))
    with pytest.raises(ValueError):
        read(adapter(client))


def test_unbound_or_unauthorized_user_cannot_observe_baseline():
    client = DifferenceClient(full())
    provider = adapter(client)
    provider._expected_user_id = None
    with pytest.raises(SessionUnavailable):
        read(provider)
    assert client.connected == 0 and client.requests == []
    client = DifferenceClient(full(), authorized=False)
    with pytest.raises(SessionUnavailable):
        read(adapter(client))
    assert client.requests == [] and client.disconnected == 1


def test_checkpoint_floodwait_is_explicit_and_disconnects_without_hidden_retry():
    client = DifferenceClient(FloodWaitError(None, capture=120))
    with pytest.raises(FloodWait) as error:
        read(adapter(client))
    assert error.value.seconds == 120 and len(client.requests) == 1
    assert client.disconnected == 1


def test_fake_checkpoint_never_fabricates_pts_and_preserves_account_binding():
    fake = FakeTelegramProvider()
    checkpoint = TelegramChannelCheckpoint("1", CHANNEL, 1001, 10)
    fake.seed_channel_checkpoint(checkpoint)
    assert read(fake) == checkpoint
    with pytest.raises(KeyError):
        read(fake, account="2")


def test_encrypted_factory_current_session_checkpoint_and_corrupt_session_zero_rpc(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from newsflow.persistence.models import Base, TelegramAccount
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    engine = create_engine(f"sqlite:///{tmp_path / 'checkpoint-session.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with factory.begin() as session:
        session.add(
            TelegramAccount(
                name="Synthetic checkpoint",
                telegram_user_id=1001,
                encrypted_session=cipher.encrypt("initial"),
            )
        )
    client = DifferenceClient(full())
    client.session = SimpleNamespace(save=lambda: "refreshed")
    provider = ConfiguredTelegramProvider(
        factory, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    assert read(provider).pts == 10
    with factory.begin() as session:
        row = session.get(TelegramAccount, 1)
        assert cipher.decrypt(row.encrypted_session) == "refreshed"
        row.encrypted_session = "corrupt"
    with pytest.raises(SessionUnavailable):
        read(provider)
    assert len(client.requests) == 1
    engine.dispose()


@pytest.mark.parametrize("user_id", [True, 0, -1, "1001", 2**63])
def test_invalid_bound_user_identity_fails_before_connection(user_id):
    client = DifferenceClient(full())
    provider = adapter(client)
    provider._expected_user_id = user_id
    with pytest.raises(SessionUnavailable):
        read(provider)
    assert client.connected == 0 and client.requests == []


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "oversized", "bad_vector"])
def test_untrusted_channel_vector_cannot_supply_checkpoint(mutation):
    response = full()
    if mutation == "missing":
        response.chats = []
    elif mutation == "duplicate":
        response.chats *= 2
    elif mutation == "oversized":
        response.users = [SimpleNamespace(id=1)] * 100
    else:
        response.users = None
    client = DifferenceClient(response)
    with pytest.raises(ValueError):
        read(adapter(client))
    assert client.disconnected == 1 and len(client.requests) == 1


@pytest.mark.parametrize("account,channel", [("", CHANNEL), ("1", "@donor"), ("1", "0")])
def test_invalid_checkpoint_request_never_connects(account, channel):
    client = DifferenceClient(full())
    with pytest.raises(ValueError):
        read(adapter(client), account, channel)
    assert client.connected == 0 and client.requests == []
