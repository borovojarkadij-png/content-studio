import asyncio
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from telethon.errors import FloodWaitError, UnauthorizedError
from telethon.tl.types import MessageReactions, ReactionCount, ReactionEmoji
from test_telethon_rpc import Client

from newsflow.providers.telegram import FloodWait, SessionUnavailable, TelethonTelegramProvider

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)
CHANNEL = "-1001234567890"


class EngagementClient(Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.raw.date = datetime(2026, 10, 13, 11, tzinfo=UTC)
        self.raw.views = 100
        self.raw.forwards = 5
        self.raw.reactions = MessageReactions([ReactionCount(ReactionEmoji("👍"), 2)])
        self.reads = []

    async def get_messages(self, peer, *, ids):
        self.reads.append((peer.channel_id, ids))
        return self.raw


def adapter(client, **kwargs):
    return TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic"},
        client_factory=lambda _: client,
        expected_user_id=1001,
        **kwargs,
    )


def test_fetch_is_separate_from_content_identity():
    client = EngagementClient()
    provider = adapter(client)
    before = provider.fetch_message("1", CHANNEL, 1)
    assert callable(getattr(provider, "fetch_engagement", None)), "Missing engagement reader"
    measured = provider.fetch_engagement("1", CHANNEL, 1, observed_at=NOW)
    assert measured.views == 100
    client.raw.views = 200
    assert provider.fetch_message("1", CHANNEL, 1) == before
    assert client.reads == [(1234567890, 1)] * 3


def read(provider, account="1", channel=CHANNEL, message=1, observed_at=NOW):
    return provider.fetch_engagement(account, channel, message, observed_at=observed_at)


def test_aggregate_uses_original_date_utc_and_exact_bounded_read():
    client = EngagementClient()
    client.raw.edit_date = NOW
    client.raw.date = NOW.astimezone(timezone(timedelta(hours=3))) - timedelta(hours=1)
    client.raw.reactions.results.append(ReactionCount(ReactionEmoji("❤️"), 3))
    result = read(adapter(client), observed_at=NOW.astimezone(timezone(timedelta(hours=-4))))
    assert (result.views, result.forwards, result.reactions) == (100, 5, 5)
    assert result.published_at == NOW - timedelta(hours=1)
    assert result.published_at.tzinfo is UTC and result.observed_at.tzinfo is UTC
    assert client.reads == [(1234567890, 1)]
    assert client.history_args is None and client.connected == client.disconnected == 1
    assert not hasattr(result, "text") and not hasattr(result, "users")
    with pytest.raises(FrozenInstanceError):
        result.views = 999


@pytest.mark.parametrize(
    "account,channel,message,when",
    [
        ("01", CHANNEL, 1, NOW),
        (1, CHANNEL, 1, NOW),
        ("0", CHANNEL, 1, NOW),
        (str(2**63), CHANNEL, 1, NOW),
        ("+1", CHANNEL, 1, NOW),
        ("1", "@donor", 1, NOW),
        ("1", "-1000000000000", 1, NOW),
        ("1", str(-(2**63) - 1), 1, NOW),
        ("1", "-01001234567890", 1, NOW),
        ("1", CHANNEL, True, NOW),
        ("1", CHANNEL, 1.0, NOW),
        ("1", CHANNEL, 0, NOW),
        ("1", CHANNEL, 2**31, NOW),
        ("1", CHANNEL, 1, NOW.replace(tzinfo=None)),
        ("1", CHANNEL, 1, None),
    ],
)
def test_invalid_request_never_constructs_or_connects(account, channel, message, when):
    client = EngagementClient()
    provider = adapter(client)
    provider._client_factory = lambda _: pytest.fail("invalid request constructed client")
    with pytest.raises(ValueError):
        read(provider, account, channel, message, when)
    assert client.connected == 0 and client.reads == []


@pytest.mark.parametrize("field", ["views", "forwards"])
@pytest.mark.parametrize("value", [True, 1.0, -1, 2**63, "1"])
def test_malformed_counters_fail_and_disconnect(field, value):
    client = EngagementClient()
    setattr(client.raw, field, value)
    with pytest.raises(ValueError):
        read(adapter(client))
    assert client.disconnected == 1


@pytest.mark.parametrize(
    "change",
    [
        {"id": True},
        {"id": 2},
        {"chat_id": -1009876543210},
        {"chat_id": True},
        {"date": None},
        {"date": NOW.replace(tzinfo=None)},
        {"date": NOW + timedelta(seconds=1)},
    ],
)
def test_foreign_identity_or_invalid_publication_cannot_be_relabelled(change):
    client = EngagementClient()
    for key, value in change.items():
        setattr(client.raw, key, value)
    with pytest.raises(ValueError):
        read(adapter(client))
    assert client.disconnected == 1


def test_deleted_message_fails_without_fabricating_observation():
    client = EngagementClient()
    client.raw = None
    with pytest.raises(LookupError):
        read(adapter(client))
    assert client.disconnected == 1


@pytest.mark.parametrize("aggregate", [None, MessageReactions([], min=True)])
def test_missing_or_partial_metrics_stay_unknown(aggregate):
    client = EngagementClient()
    del client.raw.views
    client.raw.forwards = None
    client.raw.reactions = aggregate
    result = read(adapter(client))
    assert (result.views, result.forwards, result.reactions) == (None, None, None)


def test_complete_empty_aggregate_and_explicit_zero_are_known_zero():
    client = EngagementClient()
    client.raw.views = client.raw.forwards = 0
    client.raw.reactions = MessageReactions([])
    result = read(adapter(client))
    assert (result.views, result.forwards, result.reactions) == (0, 0, 0)


@pytest.mark.parametrize(
    "aggregate",
    [
        SimpleNamespace(results=[]),
        MessageReactions(None),
        MessageReactions([object()]),
        MessageReactions([ReactionCount(ReactionEmoji("👍"), True)]),
        MessageReactions([ReactionCount(ReactionEmoji("👍"), -1)]),
        MessageReactions([ReactionCount(ReactionEmoji("👍"), 1.0)]),
        MessageReactions([ReactionCount(ReactionEmoji("👍"), 2**63)]),
        MessageReactions(
            [ReactionCount(ReactionEmoji("👍"), 2**63 - 1), ReactionCount(ReactionEmoji("❤️"), 1)]
        ),
        MessageReactions([ReactionCount(ReactionEmoji("👍"), 1)] * 101),
        MessageReactions([], min=1),
    ],
)
def test_malformed_or_unbounded_reaction_aggregate_never_repairs_to_zero(aggregate):
    client = EngagementClient()
    client.raw.reactions = aggregate
    with pytest.raises(ValueError):
        read(adapter(client))
    assert client.disconnected == 1


def test_missing_session_and_user_binding_never_construct_client():
    for field, value in [
        ("_sessions", {}),
        ("_expected_user_id", None),
        ("_expected_user_id", True),
        ("_expected_user_id", 2**63),
    ]:
        provider = adapter(EngagementClient())
        setattr(provider, field, value)
        provider._client_factory = lambda _: pytest.fail("unprovisioned client constructed")
        with pytest.raises(SessionUnavailable):
            read(provider)


@pytest.mark.parametrize(
    "failure", [FloodWaitError(None, capture=120), UnauthorizedError(None, "synthetic")]
)
def test_rpc_auth_or_flood_failure_disconnects_without_retry(failure):
    class BrokenClient(EngagementClient):
        async def get_messages(self, peer, *, ids):
            self.reads.append((peer.channel_id, ids))
            raise failure

    client = BrokenClient()
    with pytest.raises(FloodWait if isinstance(failure, FloodWaitError) else SessionUnavailable):
        read(adapter(client))
    assert client.disconnected == 1 and len(client.reads) == 1


def test_unauthorized_or_foreign_user_has_zero_reads_and_disconnects():
    client = EngagementClient(authorized=False)
    with pytest.raises(SessionUnavailable):
        read(adapter(client))
    assert client.reads == [] and client.disconnected == 1
    client = EngagementClient()
    provider = adapter(client)
    provider._expected_user_id = 1002
    with pytest.raises(SessionUnavailable):
        read(provider)
    assert client.reads == [] and client.disconnected == 1


def test_deadline_cancels_reader_and_disconnects_without_retry():
    class SlowClient(EngagementClient):
        async def get_messages(self, peer, *, ids):
            self.reads.append((peer.channel_id, ids))
            await asyncio.Event().wait()

    client = SlowClient()
    with pytest.raises(TimeoutError):
        read(adapter(client, request_timeout=0.01))
    assert client.disconnected == 1 and len(client.reads) == 1


def test_fake_only_returns_explicit_exact_observations():
    from newsflow.providers.telegram_engagement import FakeTelegramEngagementProvider

    fake = FakeTelegramEngagementProvider()
    result = read(adapter(EngagementClient()))
    with pytest.raises(KeyError):
        read(fake)
    fake.seed_observation(result)
    assert read(fake) == result
    for account, channel, message, when in [
        ("2", CHANNEL, 1, NOW),
        ("1", CHANNEL, 2, NOW),
        ("1", CHANNEL, 1, NOW + timedelta(seconds=1)),
    ]:
        with pytest.raises(KeyError):
            read(fake, account, channel, message, when)
    with pytest.raises(ValueError):
        fake.seed_observation(replace(result, views=True))
    with pytest.raises(ValueError):
        fake.seed_observation(replace(result, views=101))


def test_fake_rejects_unvalidated_object_type():
    from newsflow.providers.telegram_engagement import FakeTelegramEngagementProvider

    with pytest.raises(TypeError):
        FakeTelegramEngagementProvider().seed_observation(object())


def test_factory_preserves_session_peer_cas_and_rejects_corruption_before_rpc(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from newsflow.persistence.models import Base, TelegramAccount, TelegramPeerModel
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    engine = create_engine(f"sqlite:///{tmp_path / 'engagement.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with sessions.begin() as session:
        session.add(
            TelegramAccount(
                name="synthetic", telegram_user_id=1001, encrypted_session=cipher.encrypt("initial")
            )
        )
    client = EngagementClient()
    client.session = SimpleNamespace(save=lambda: "refreshed")
    provider = ConfiguredTelegramProvider(
        sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    assert read(provider).views == 100
    with sessions.begin() as session:
        row = session.get(TelegramAccount, 1)
        assert cipher.decrypt(row.encrypted_session) == "refreshed"
        assert session.get(TelegramPeerModel, (1, int(CHANNEL))) is not None
        row.encrypted_session = "corrupt"
    with pytest.raises(SessionUnavailable):
        read(provider)
    with pytest.raises(ValueError):
        read(provider, account="01")
    assert len(client.reads) == 1
    engine.dispose()
