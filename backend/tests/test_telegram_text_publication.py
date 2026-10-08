"""Real TL requests/receipts with a synthetic network boundary, no actual sends."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from importlib import import_module
from importlib.util import find_spec
from types import SimpleNamespace

import pytest
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.types import (
    Channel,
    ChatAdminRights,
    ChatPhotoEmpty,
    Message,
    PeerChannel,
    UpdateMessageID,
    UpdateNewChannelMessage,
    Updates,
)

from newsflow.providers.telegram import (
    SessionUnavailable,
    TelegramChannelPeer,
    TelethonTelegramProvider,
)
from newsflow.services.durable_publication_runner import PublicationNotSentRetry, PublicationReceipt
from newsflow.services.publication import PublicationBlocked
from newsflow.services.publication_preflight import PublicationEnvelope

NOW = datetime(2026, 10, 8, tzinfo=UTC)
CHANNEL = -1001234567890
NONCE = 987654321


def envelope():
    return PublicationEnvelope(
        1,
        1,
        1,
        1001,
        1,
        CHANNEL,
        "synthetic:1:1",
        1,
        "Тестовый пост 42",
        NOW,
        NOW + timedelta(hours=6),
        None,
        None,
        "a" * 64,
    )


def reply(*, nonce=NONCE, channel=1234567890, text="Тестовый пост 42", message_id=501):
    return Updates(
        [
            UpdateMessageID(message_id, nonce),
            UpdateNewChannelMessage(
                Message(message_id, PeerChannel(channel), NOW, text, out=True, post=True), 10, 1
            ),
        ],
        [],
        [],
        NOW,
        1,
    )


class Client:
    def __init__(self):
        self.session = SimpleNamespace(save=lambda: "synthetic")
        self.authorized = True
        self.user_id = 1001
        self.channel = Channel(
            1234567890,
            "Synthetic output",
            ChatPhotoEmpty(),
            NOW,
            broadcast=True,
            admin_rights=ChatAdminRights(post_messages=True),
            access_hash=999,
        )
        self.response = reply()
        self.requests = []
        self.events = []
        self.failure = None
        self.during_permissions = None

    async def connect(self):
        self.events.append("connect")

    async def disconnect(self):
        self.events.append("disconnect")

    async def is_user_authorized(self):
        return self.authorized

    async def get_me(self):
        return SimpleNamespace(id=self.user_id)

    async def get_entity(self, peer):
        assert (peer.channel_id, peer.access_hash) == (1234567890, 999)
        self.events.append("permissions")
        if self.during_permissions:
            self.during_permissions()
        return self.channel

    async def __call__(self, request):
        self.events.append("send-rpc")
        self.requests.append(request)
        if self.failure:
            raise self.failure
        return self.response


def publisher(client, *, expected_user_id=1001):
    module = "newsflow.providers.telegram_publication"
    assert find_spec(module) is not None, "Guarded Telegram text transport is not implemented"
    implementation = import_module(module)
    adapter = TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic-session"},
        client_factory=lambda _: client,
        expected_user_id=expected_user_id,
        peers=(TelegramChannelPeer("1", CHANNEL, 999),),
    )
    return implementation.TelethonTextPublisher(lambda _: adapter)


def test_plain_text_uses_committed_nonce_exact_channel_and_post_auth_guard():
    client = Client()
    result = publisher(client).publish(
        envelope(), NONCE, execution_guard=lambda: client.events.append("guard")
    )
    assert result == PublicationReceipt(1, CHANNEL, NONCE, 501)
    assert client.events == ["connect", "permissions", "guard", "send-rpc", "disconnect"]
    (request,) = client.requests
    assert isinstance(request, SendMessageRequest)
    assert (request.peer.channel_id, request.message, request.random_id) == (
        1234567890,
        "Тестовый пост 42",
        987654321,
    )
    assert request.no_webpage is True
    assert not request.entities and not request.reply_to and not request.schedule_date
    assert not request.allow_paid_stars and not request.allow_paid_floodskip


def test_final_editorial_guard_failure_sends_zero_requests():
    client = Client()

    def reject():
        raise PublicationBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")

    with pytest.raises(PublicationBlocked):
        publisher(client).publish(envelope(), NONCE, execution_guard=reject)
    assert not client.requests
    assert client.events[-1] == "disconnect"


@pytest.mark.parametrize("change", ["no-admin", "foreign", "group", "left", "minimal"])
def test_unverified_destination_permissions_never_send(change):
    client = Client()
    if change == "no-admin":
        client.channel.admin_rights = ChatAdminRights(edit_messages=True)
    elif change == "foreign":
        client.channel.id = 9876543210
    elif change == "group":
        client.channel.megagroup = True
    elif change == "left":
        client.channel.left = True
    else:
        client.channel.min = True
    with pytest.raises(PublicationBlocked):
        publisher(client).publish(envelope(), NONCE, execution_guard=lambda: None)
    assert not client.requests


@pytest.mark.parametrize("authorized,user", [(False, 1001), (True, 9999)])
def test_unauthorized_or_foreign_session_never_sends(authorized, user):
    client = Client()
    client.authorized, client.user_id = authorized, user
    with pytest.raises(SessionUnavailable):
        publisher(client).publish(envelope(), NONCE, execution_guard=lambda: None)
    assert not client.requests


@pytest.mark.parametrize(
    "nonce,channel,text",
    [
        (987654322, 1234567890, "Тестовый пост 42"),
        (NONCE, 9876543210, "Тестовый пост 42"),
        (NONCE, 1234567890, "Другой пост"),
    ],
)
def test_foreign_or_altered_acknowledgement_is_not_success(nonce, channel, text):
    client = Client()
    client.response = reply(nonce=nonce, channel=channel, text=text)
    with pytest.raises(ValueError):
        publisher(client).publish(envelope(), NONCE, execution_guard=lambda: None)
    assert len(client.requests) == 1


def test_only_explicit_send_rpc_floodwait_is_known_not_sent():
    client = Client()
    client.failure = FloodWaitError(None, capture=120)
    with pytest.raises(PublicationNotSentRetry) as error:
        publisher(client).publish(envelope(), NONCE, execution_guard=lambda: None)
    assert error.value.delay_seconds == 120
    assert len(client.requests) == 1


def test_timeout_after_rpc_never_becomes_retry_or_fresh_nonce():
    client = Client()
    client.failure = TimeoutError("synthetic acknowledgement lost")
    with pytest.raises(TimeoutError):
        publisher(client).publish(envelope(), NONCE, execution_guard=lambda: None)
    assert [request.random_id for request in client.requests] == [NONCE]


@pytest.mark.parametrize(
    "changes",
    [
        {"media_asset_id": 1, "media_sha256": "b" * 64},
        {"text": " "},
        {"text": "😀" * 2049},
        {"account_id": True},
    ],
)
def test_unsupported_or_invalid_request_is_rejected_before_connect(changes):
    client = Client()
    with pytest.raises((PublicationBlocked, ValueError)):
        publisher(client).publish(
            replace(envelope(), **changes), NONCE, execution_guard=lambda: None
        )
    assert not client.events and not client.requests


def test_adapter_without_bound_provisioned_user_cannot_connect():
    client = Client()
    with pytest.raises(SessionUnavailable):
        publisher(client, expected_user_id=None).publish(
            envelope(), NONCE, execution_guard=lambda: None
        )
    assert not client.events


@pytest.mark.parametrize(
    "change", ["missing-map", "duplicate-map", "duplicate-message", "incoming", "not-post"]
)
def test_ambiguous_or_non_output_updates_never_confirm_delivery(change):
    client = Client()
    if change == "missing-map":
        client.response.updates = client.response.updates[1:]
    elif change == "duplicate-map":
        client.response.updates.append(UpdateMessageID(502, NONCE))
    elif change == "duplicate-message":
        client.response.updates.append(client.response.updates[1])
    elif change == "incoming":
        client.response.updates[1].message.out = False
    else:
        client.response.updates[1].message.post = False
    with pytest.raises(ValueError):
        publisher(client).publish(envelope(), NONCE, execution_guard=lambda: None)
    assert len(client.requests) == 1
