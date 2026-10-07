import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from telethon.tl.types import InputPeerChannel, InputPeerUser

from newsflow.persistence.models import Base, TelegramAccount
from newsflow.providers.telegram import SessionUnavailable, TelethonTelegramProvider
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
CHANNEL = -1001234567890


class PeerClient:
    def __init__(self, *, peer=None, user_id=1001):
        self.peer = peer or InputPeerChannel(1234567890, 987654321)
        self.user_id = user_id
        self.session = SimpleNamespace(save=lambda: "synthetic session")
        self.disconnected = 0
        self.entities = []
        self.dialog_reads = 0

    async def connect(self):
        pass

    async def disconnect(self):
        self.disconnected += 1

    async def is_user_authorized(self):
        return True

    async def get_me(self):
        return SimpleNamespace(id=self.user_id)

    def iter_dialogs(self, *, limit):
        self.dialog_reads += 1
        assert limit <= 100

        async def rows():
            yield SimpleNamespace(id=CHANNEL, input_entity=self.peer, title="Synthetic donor")

        return rows()

    def iter_messages(self, entity, **kwargs):
        self.entities.append(entity)

        async def rows():
            yield SimpleNamespace(id=1, chat_id=CHANNEL, raw_text="Synthetic source", media=None)

        return rows()


def test_missing_peer_resolves_bounded_dialogs_and_reads_with_account_scoped_hash():
    client = PeerClient()
    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
    )
    assert provider.history("1", str(CHANNEL), after_id=0, limit=5)[0].text == "Synthetic source"
    assert isinstance(client.entities[0], InputPeerChannel)
    assert client.entities[0].channel_id == 1234567890
    assert client.entities[0].access_hash == 987654321
    assert client.dialog_reads == 1


def test_foreign_peer_from_resolver_never_reads_messages():
    client = PeerClient(peer=InputPeerUser(1234567890, 987654321))
    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
    )
    with pytest.raises(ValueError, match="identity"):
        provider.history("1", str(CHANNEL), after_id=0, limit=5)
    assert client.entities == []
    assert client.disconnected == 1


def test_factory_persists_encrypted_peer_and_reuses_it_after_recreation(tmp_path):
    from newsflow.persistence.models import TelegramPeerModel

    engine = create_engine(f"sqlite:///{tmp_path / 'peers.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cipher = SessionCipher(KEY)
    with sessions.begin() as session:
        session.add(
            TelegramAccount(
                name="synthetic",
                telegram_user_id=1001,
                encrypted_session=cipher.encrypt("synthetic session"),
            )
        )
    first = PeerClient()
    ConfiguredTelegramProvider(
        sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: first
    ).history("1", str(CHANNEL), after_id=0, limit=5)
    with sessions() as session:
        peer = session.scalar(select(TelegramPeerModel))
        assert peer.telegram_account_id == 1
        assert peer.telegram_channel_id == CHANNEL
        assert "987654321" not in peer.encrypted_peer
    second = PeerClient()
    ConfiguredTelegramProvider(
        sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: second
    ).history("1", str(CHANNEL), after_id=0, limit=5)
    assert second.dialog_reads == 0
    assert second.entities[0].access_hash == 987654321
    engine.dispose()


def test_factory_rejects_authorized_session_of_another_user_before_reading(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cipher = SessionCipher(KEY)
    with sessions.begin() as session:
        session.add(
            TelegramAccount(
                name="synthetic",
                telegram_user_id=1001,
                encrypted_session=cipher.encrypt("synthetic session"),
            )
        )
    client = PeerClient(user_id=2002)
    with pytest.raises(SessionUnavailable, match="account identity"):
        ConfiguredTelegramProvider(
            sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
        ).history("1", str(CHANNEL), after_id=0, limit=5)
    assert client.entities == []
    assert client.dialog_reads == 0
    engine.dispose()


@pytest.mark.parametrize(
    "corruption", ["foreign_account", "foreign_channel", "boolean_version", "malformed"]
)
def test_corrupt_or_misbound_peer_is_not_replaced_with_empty_cache(corruption):
    from newsflow.persistence.models import TelegramPeerModel

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cipher = SessionCipher(KEY)
    value = {
        "version": 1,
        "account_id": "1",
        "user_id": 1001,
        "channel_id": CHANNEL,
        "access_hash": 987654321,
    }
    if corruption == "foreign_account":
        value["account_id"] = "2"
    elif corruption == "foreign_channel":
        value["channel_id"] = -1001234567891
    elif corruption == "boolean_version":
        value["version"] = True
    stored = cipher.encrypt(json.dumps(value)) if corruption != "malformed" else "corrupt"
    with sessions.begin() as session:
        session.add(
            TelegramAccount(
                id=1,
                name="synthetic",
                telegram_user_id=1001,
                encrypted_session=cipher.encrypt("synthetic session"),
            )
        )
        session.flush()
        session.add(
            TelegramPeerModel(
                telegram_account_id=1, telegram_channel_id=CHANNEL, encrypted_peer=stored
            )
        )
    client = PeerClient()
    with pytest.raises(SessionUnavailable, match="peer identity"):
        ConfiguredTelegramProvider(
            sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
        ).history("1", str(CHANNEL), after_id=0, limit=5)
    assert client.entities == []
    assert client.dialog_reads == 0
    with sessions() as session:
        assert session.get(TelegramPeerModel, (1, CHANNEL)).encrypted_peer == stored
    engine.dispose()


def test_peer_saved_by_old_session_is_fenced_after_concurrent_replacement():
    from newsflow.persistence.models import TelegramPeerModel

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cipher = SessionCipher(KEY)
    with sessions.begin() as session:
        session.add(
            TelegramAccount(
                name="synthetic",
                telegram_user_id=1001,
                encrypted_session=cipher.encrypt("synthetic session"),
            )
        )

    class ReplacedDuringResolution(PeerClient):
        def iter_dialogs(self, *, limit):
            with sessions.begin() as session:
                session.get(TelegramAccount, 1).encrypted_session = cipher.encrypt(
                    "manual replacement"
                )
            return super().iter_dialogs(limit=limit)

    client = ReplacedDuringResolution()
    with pytest.raises(ConnectionError, match="changed during peer"):
        ConfiguredTelegramProvider(
            sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
        ).history("1", str(CHANNEL), after_id=0, limit=5)
    with sessions() as session:
        assert session.scalar(select(TelegramPeerModel)) is None
    assert client.entities == []
    assert client.disconnected == 1
    engine.dispose()


def test_resolution_floodwait_propagates_before_any_history_read():
    from telethon.errors import FloodWaitError

    from newsflow.providers.telegram import FloodWait

    class LimitedClient(PeerClient):
        def iter_dialogs(self, *, limit):
            raise FloodWaitError(None, capture=75)

    client = LimitedClient()
    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
    )
    with pytest.raises(FloodWait) as error:
        provider.history("1", str(CHANNEL), after_id=0, limit=5)
    assert error.value.seconds == 75
    assert client.entities == []
    assert client.disconnected == 1
