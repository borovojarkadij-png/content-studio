from types import SimpleNamespace

import pytest
from telethon.errors import FloodWaitError

from newsflow.providers.telegram import FloodWait, SessionUnavailable, TelethonTelegramProvider


class Client:
    def __init__(self, *, authorized=True, failure=None, chat_id=-1001234567890):
        self.authorized = authorized
        self.failure = failure
        self.connected = self.disconnected = 0
        self.history_args = None
        self.raw = SimpleNamespace(id=1, raw_text="News", chat_id=chat_id, media=None)

    async def connect(self):
        self.connected += 1

    async def disconnect(self):
        self.disconnected += 1

    async def is_user_authorized(self):
        if self.failure:
            raise self.failure
        return self.authorized

    async def get_me(self):
        return SimpleNamespace(id=1001)

    def iter_dialogs(self, *, limit):
        from telethon.tl.types import InputPeerChannel

        async def items():
            yield SimpleNamespace(id=-1001234567890, input_entity=InputPeerChannel(1234567890, 999))

        return items()

    def iter_messages(self, entity, **kwargs):
        self.history_args = (entity, kwargs)

        async def items():
            yield self.raw

        return items()


def adapter(client):
    return TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic"},
        client_factory=lambda _: client,
    )


def test_health_checks_actual_authorization_and_always_disconnects():
    client = Client(authorized=False)
    with pytest.raises(SessionUnavailable):
        adapter(client).verify_session("1")
    assert client.connected == client.disconnected == 1


def test_history_is_bounded_ascending_and_preserves_numeric_source_identity():
    client = Client()
    result = adapter(client).history("1", "-1001234567890", after_id=0, limit=5)
    assert [(m.account_id, m.donor_identifier, m.text) for m in result] == [
        ("1", "-1001234567890", "News")
    ]
    from telethon.tl.types import InputPeerChannel

    peer, args = client.history_args
    assert isinstance(peer, InputPeerChannel)
    assert (peer.channel_id, peer.access_hash) == (1234567890, 999)
    assert args == {"min_id": 0, "limit": 5, "reverse": True, "wait_time": 0}
    assert client.connected == client.disconnected == 1


def test_telegram_floodwait_becomes_durable_provider_exception_without_hidden_sleep():
    client = Client(failure=FloodWaitError(None, capture=120))
    with pytest.raises(FloodWait) as error:
        adapter(client).history("1", "-1001234567890", after_id=0, limit=5)
    assert error.value.seconds == 120
    assert client.disconnected == 1


def test_history_refuses_foreign_chat_before_relabeling_it_as_the_requested_donor():
    client = Client(chat_id=-1009876543210)
    with pytest.raises(ValueError, match="identity"):
        adapter(client).history("1", "-1001234567890", after_id=0, limit=5)
    assert client.disconnected == 1


def test_unprovisioned_session_never_constructs_a_client():
    def forbidden(_):
        raise AssertionError("No client construction")

    provider = TelethonTelegramProvider(api_id=123, api_hash="synthetic", client_factory=forbidden)
    with pytest.raises(SessionUnavailable):
        provider.verify_session("1")


def test_unknown_document_is_not_misclassified_as_plain_text():
    raw = SimpleNamespace(id=1, raw_text="Caption", media=object())
    assert (
        TelethonTelegramProvider.normalize_message("1", "-1001234567890", raw).media_type
        == "unsupported"
    )


def test_authorized_session_update_is_saved_even_if_history_later_fails():
    class BrokenHistory(Client):
        def iter_messages(self, *args, **kwargs):
            raise ConnectionError("Synthetic failure")

    client = BrokenHistory()
    client.session = SimpleNamespace(save=lambda: "refreshed")
    saved = []
    provider = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "initial"},
        client_factory=lambda _: client,
        on_session_updated=lambda account, value: saved.append((account, value)),
    )
    with pytest.raises(ConnectionError):
        provider.history("1", "-1001234567890", after_id=0, limit=5)
    assert saved == [("1", "refreshed")]
    assert client.disconnected == 1


def test_empty_session_cannot_start_an_unauthorized_network_connection():
    client = Client()
    provider = TelethonTelegramProvider(
        api_id=123, api_hash="synthetic", sessions={"1": ""}, client_factory=lambda _: client
    )
    with pytest.raises(SessionUnavailable):
        provider.verify_session("1")
    assert client.connected == 0


@pytest.mark.asyncio
async def test_sync_adapter_rejects_async_context_before_connection():
    client = Client()
    with pytest.raises(RuntimeError, match="async event loop"):
        adapter(client).verify_session("1")
    assert client.connected == 0
