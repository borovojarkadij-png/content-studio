"""Synthetic RPCs around actual login, SQLite, cipher and read-only consumer."""

import asyncio
import base64
import socket
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession
from telethon.tl.types import User
from telethon.tl.types.auth import SentCode, SentCodeTypeSms

from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutboxEventModel,
    TelegramAccount,
)
from newsflow.providers.telegram_login import (
    TelegramLoginError,
    TelethonLoginAdapter,
)
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.telegram_login import SessionProvisioningService
from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
PHONE = "+15550001001"
# A literal SDK StringSession with a synthetic 256-byte key of 0x01; never live.
SESSION = (
    "1ApWapzMBuwEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE"
    "BAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE"
    "BAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE"
    "BAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE"
    "BAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
)


class Rpc:
    """External boundary only; any unexpected Telegram method fails closed."""

    def __init__(self, *, two_factor=False, failure=None, stage=None):
        self.calls = []
        self.constructions = 0
        self.two_factor = two_factor
        self.failure = failure
        self.stage = stage
        self.me = User(id=1001, phone="15550001001", bot=False)
        self.authorized = True
        self.session = StringSession(SESSION)
        self.before_identity = None

    async def action(self, name):
        self.calls.append(name)
        if name == self.stage:
            if self.failure == "hang":
                await asyncio.Event().wait()
            raise self.failure

    async def connect(self):
        await self.action("connect")

    async def disconnect(self):
        await self.action("disconnect")

    async def send_code_request(self, phone):
        assert phone == PHONE
        await self.action("send_code")
        return SentCode(SentCodeTypeSms(5), "synthetic-code-hash")

    async def sign_in(self, **kwargs):
        if "password" in kwargs:
            assert kwargs == {"password": "synthetic-only-password"}
            await self.action("password")
        else:
            assert kwargs == {
                "phone": PHONE,
                "code": "12345",
                "phone_code_hash": "synthetic-code-hash",
            }
            await self.action("code")
            if self.two_factor:
                raise SessionPasswordNeededError(None)

    async def is_user_authorized(self):
        await self.action("authorized")
        return self.authorized

    async def get_me(self):
        await self.action("identity")
        if self.before_identity:
            self.before_identity()
        return self.me


def adapter(rpc, configs=None):
    def create(session, api_id, api_hash, **options):
        rpc.constructions += 1
        assert isinstance(session, StringSession) and session.auth_key is None
        assert (api_id, api_hash) == (123, "a" * 32)
        if configs is not None:
            configs.append(options)
        return rpc

    return TelethonLoginAdapter(123, "a" * 32, client_factory=create)


def provision(service, request, **overrides):
    options = {
        "phone": PHONE,
        "read_code": lambda: "12345",
        "read_password": lambda: "synthetic-only-password",
    }
    options.update(overrides)
    return asyncio.run(service.provision(request, **options))


def login(rpc, **overrides):
    options = {"read_code": lambda: "12345", "read_password": lambda: "synthetic-only-password"}
    options.update(overrides)
    return asyncio.run(adapter(rpc).authorize(PHONE, **options))


def service_for(store, rpc, key=lambda: KEY):
    return SessionProvisioningService(store, master_key_loader=key, login_adapter=adapter(rpc))


def empty_metadata(store, **values):
    args = {"name": "synthetic-login", "telegram_user_id": 1001, "encrypted_session": ""}
    args.update(values)
    with store() as session, session.begin():
        row = TelegramAccount(**args)
        session.add(row)
        session.flush()
        return row.id


def assert_empty(store):
    with store() as session:
        assert session.scalar(select(func.count()).select_from(TelegramAccount)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'login.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as session, session.begin():
        post = IncomingPostModel(
            telegram_account_id="synthetic",
            donor_channel_id="@synthetic",
            telegram_message_id=1,
            state="RECEIVED",
        )
        session.add(post)
        session.flush()
        session.add_all(
            [
                ContentRevisionModel(
                    incoming_post_id=post.id,
                    revision_number=1,
                    source_text="Immutable synthetic source: rejected.",
                ),
                EditorialDecisionModel(
                    content_key="synthetic:revision:1",
                    status="REJECT",
                    rewrite_allowed=False,
                    sentiment="negative",
                    framing="hostile",
                ),
            ]
        )
    yield factory
    with factory() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        assert decision.status == "REJECT" and decision.rewrite_allowed is False
        assert session.scalar(select(ContentRevisionModel)).source_text == (
            "Immutable synthetic source: rejected."
        )
        # Login may touch only accounts/outbox; every job/usage/media/publication/rights table stays empty.
        allowed = {
            "telegram_accounts",
            "outbox_events",
            "incoming_posts",
            "incoming_post_revisions",
            "editorial_decisions",
        }
        for table in Base.metadata.sorted_tables:
            if table.name not in allowed:
                assert session.scalar(select(func.count()).select_from(table)) == 0, table.name
    engine.dispose()


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter import OpenRouterRewriteProvider

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("Unexpected external network/rewrite call")

    original_connect = socket.socket.connect

    def connect(sock, address):
        # Windows ProactorEventLoop creates its own loopback socketpair.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return forbidden(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(OpenRouterRewriteProvider, "rewrite", forbidden)
    yield
    assert calls == []


def test_provision_encrypts_commits_audit_and_independent_provider_reopens(store):
    # Removing the durable insert or using plaintext must break this test.
    from test_telethon_rpc import Client

    rpc = Rpc()
    service = service_for(store, rpc)
    request = service.preflight("synthetic-login", 29, expected_user_id=1001)
    account_id = asyncio.run(
        service.provision(
            request,
            phone=PHONE,
            read_code=lambda: "12345",
            read_password=lambda: "synthetic-only-password",
        )
    )
    with store() as session:
        account = session.get(TelegramAccount, account_id)
        assert account.telegram_user_id == 1001
        assert account.health_status == "DISCONNECTED"
        assert account.encrypted_session != SESSION
        assert SessionCipher(KEY).decrypt(account.encrypted_session) == SESSION
        event = session.scalar(select(OutboxEventModel))
        assert event.event_type == "TelegramSessionProvisioned"
        assert event.aggregate_key == f"telegram-session:29:{account_id}"
        assert event.idempotency_key.startswith("telegram-session-provision:")
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 1
    client = Client()
    client.session = StringSession(SESSION)
    reopened = create_engine(store.kw["bind"].url)
    try:
        ConfiguredTelegramProvider(
            sessionmaker(reopened),
            cipher=SessionCipher(KEY),
            api_id=123,
            api_hash="a" * 32,
            client_factory=lambda _: client,
        ).verify_session(str(account_id))
    finally:
        reopened.dispose()
    assert client.connected == client.disconnected == 1


@pytest.mark.parametrize("two_factor", [False, True])
def test_login_sends_one_code_and_at_most_one_password(two_factor):
    rpc = Rpc(two_factor=two_factor)
    reads = []

    def password():
        reads.append("password")
        return "synthetic-only-password"

    result = login(rpc, read_password=password)
    assert reads == (["password"] if two_factor else [])
    assert (result.telegram_user_id, result.phone, result.string_session) == (1001, PHONE, SESSION)
    assert rpc.calls == [
        "connect",
        "send_code",
        "code",
        *(["password"] if two_factor else []),
        "authorized",
        "identity",
        "disconnect",
    ]
    assert PHONE not in repr(result) and SESSION not in repr(result) and "1001" not in repr(result)


def test_constructed_client_disables_retries_updates_and_logging():
    rpc, configs = Rpc(), []
    result = asyncio.run(
        adapter(rpc, configs).authorize(
            PHONE, read_code=lambda: "12345", read_password=lambda: "synthetic-only-password"
        )
    )
    assert result.telegram_user_id == 1001
    options = configs[0]
    assert {
        "request_retries": 0,
        "connection_retries": 0,
        "auto_reconnect": False,
        "flood_sleep_threshold": 0,
        "receive_updates": False,
    }.items() <= options.items()
    logger = options["base_logger"]
    assert logger.propagate is False and logger.disabled is True


def test_sdk_child_loggers_cannot_emit_private_rpc_data(caplog):
    rpc = Rpc()

    def create(session, api_id, api_hash, **options):
        options["base_logger"].getChild("network").error("synthetic-private-rpc-log")
        return rpc

    result = asyncio.run(
        TelethonLoginAdapter(123, "a" * 32, create).authorize(
            PHONE, read_code=lambda: "12345", read_password=lambda: "synthetic-only-password"
        )
    )
    assert result.telegram_user_id == 1001
    assert "synthetic-private-rpc-log" not in caplog.text


@pytest.mark.parametrize(
    "api_id,api_hash", [(True, "a" * 32), (0, "a" * 32), (2**31, "a" * 32), (123, "secret-invalid")]
)
def test_credentials_refused_without_constructing_client(api_id, api_hash):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid credentials reached client construction")

    with pytest.raises(TelegramLoginError):
        asyncio.run(
            TelethonLoginAdapter(api_id, api_hash, forbidden).authorize(
                PHONE, read_code=lambda: "12345", read_password=lambda: "password"
            )
        )


@pytest.mark.parametrize(
    "phone",
    [None, "15550001001", "+05550001001", "+1234", "+" + "1" * 16, "+１２３４５", PHONE + "\n"],
)
def test_bad_phone_prevents_all_rpcs(store, phone):
    rpc = Rpc()
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29), phone=phone)
    assert rpc.calls == []
    assert rpc.constructions == 0
    assert_empty(store)


@pytest.mark.parametrize(
    "field,value",
    [
        ("read_code", ""),
        ("read_code", "123"),
        ("read_code", "123456789"),
        ("read_code", "１２３４５"),
        ("read_code", None),
        ("read_password", ""),
        ("read_password", "x" * 1025),
        ("read_password", None),
    ],
)
def test_invalid_masked_input_never_repeats_or_saves(store, field, value):
    rpc = Rpc(two_factor=True)
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29), **{field: lambda: value})
    assert rpc.calls[-1] == "disconnect"
    assert rpc.calls.count("send_code") == 1
    assert rpc.calls.count("code") == (0 if field == "read_code" else 1)
    assert rpc.calls.count("password") == 0
    assert_empty(store)


@pytest.mark.parametrize(
    "stage,error",
    [
        ("code", PhoneCodeInvalidError(None)),
        ("code", PhoneCodeExpiredError(None)),
        ("send_code", FloodWaitError(None, capture=90)),
        ("identity", RuntimeError("synthetic-private-error")),
    ],
)
def test_rpc_failure_private_no_retry_or_database_write(store, stage, error):
    rpc = Rpc(stage=stage, failure=error)
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError) as raised:
        provision(service, service.preflight("synthetic-login", 29))
    assert str(raised.value) == "Telegram authorization failed"
    assert raised.value.__suppress_context__
    assert rpc.calls[-1] == "disconnect" and rpc.calls.count(stage) == 1
    assert_empty(store)


@pytest.mark.parametrize(
    "stage", ["connect", "send_code", "code", "password", "authorized", "identity", "disconnect"]
)
def test_each_rpc_has_deadline_and_cleanup_is_bounded(store, monkeypatch, stage):
    import newsflow.providers.telegram_login as module

    original = asyncio.wait_for
    deadlines = []

    async def quick(awaitable, timeout):
        deadlines.append(timeout)
        return await original(awaitable, timeout=0.005)

    monkeypatch.setattr(module.asyncio, "wait_for", quick)
    rpc = Rpc(two_factor=True, stage=stage, failure="hang")
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert deadlines[-1] == 3 and all(value == 15 for value in deadlines[:-1])
    assert rpc.calls[-1] == "disconnect" and rpc.calls.count(stage) == 1
    assert_empty(store)


@pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt(), asyncio.CancelledError()])
def test_operator_abort_disconnects_and_never_saves(store, error):
    rpc = Rpc()
    service = service_for(store, rpc)

    def abort():
        raise error

    with pytest.raises(type(error)):
        provision(service, service.preflight("synthetic-login", 29), read_code=abort)
    assert rpc.calls == ["connect", "send_code", "disconnect"]
    assert_empty(store)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": True},
        {"id": 0},
        {"id": 2**63},
        {"bot": True},
        {"phone": "15550001002"},
        {"phone": "+15550001001"},
        {"phone": None},
    ],
)
def test_invalid_rpc_identity_fails_closed(store, changes):
    rpc = Rpc()
    for field, value in changes.items():
        setattr(rpc.me, field, value)
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert rpc.calls[-1] == "disconnect"
    assert_empty(store)


@pytest.mark.parametrize("session", ["", "not-a-session", "x" * 4097, None])
def test_malformed_saved_session_never_persists(store, session):
    rpc = Rpc()
    rpc.session = SimpleNamespace(save=lambda: session)
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert_empty(store)


def test_unauthorized_rpc_cannot_claim_success(store):
    rpc = Rpc()
    rpc.authorized = False
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert "identity" not in rpc.calls
    assert_empty(store)


@pytest.mark.parametrize(
    "name,actor,expected",
    [
        ("", 29, None),
        ("x" * 101, 29, None),
        ("a\n", 29, None),
        ("a\u200b", 29, None),
        ("ok", True, None),
        ("ok", 0, None),
        ("ok", 2**63, None),
        ("ok", 29, True),
        ("ok", 29, -1),
        ("ok", 29, 2**63),
    ],
)
def test_invalid_preflight_never_constructs_client_or_writes(store, name, actor, expected):
    rpc = Rpc()
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        service.preflight(name, actor, expected)
    assert rpc.calls == []
    assert_empty(store)


@pytest.mark.parametrize(
    "changes",
    [
        {"encrypted_session": "saved-private-session"},
        {"health_status": "CONNECTED"},
        {"cooldown_until": datetime(2020, 1, 1, tzinfo=UTC)},
    ],
)
def test_existing_incompatible_metadata_refused_before_client(store, changes):
    empty_metadata(store, **changes)
    rpc = Rpc()
    with pytest.raises(TelegramLoginError):
        service_for(store, rpc).preflight("synthetic-login", 29)
    assert rpc.calls == []
    assert rpc.constructions == 0
    with store() as session:
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


def test_compatible_metadata_filled_and_refused_on_repeat(store):
    account_id = empty_metadata(store)
    rpc = Rpc()
    service = service_for(store, rpc)
    request = service.preflight(" synthetic-login ", 29)
    assert "synthetic-login" not in repr(request) and KEY not in repr(request)
    assert provision(service, request) == account_id
    calls = list(rpc.calls)
    with pytest.raises(TelegramLoginError):
        service.preflight("synthetic-login", 29)
    assert rpc.calls == calls
    with store() as session:
        assert session.scalar(select(func.count()).select_from(TelegramAccount)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 1


def test_expected_identity_metadata_mismatch_preflight_and_rpc_mismatch_no_write(store):
    empty_metadata(store)
    rpc = Rpc()
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        service.preflight("synthetic-login", 29, 1002)
    assert rpc.calls == []
    rpc.me.id = 1002
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    with store() as session:
        assert session.get(TelegramAccount, 1).encrypted_session == ""
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


def test_changed_master_key_after_authorization_does_not_save(store):
    keys = iter([KEY, "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="])
    rpc = Rpc()
    service = service_for(store, rpc, key=lambda: next(keys))
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert "identity" in rpc.calls
    assert_empty(store)


@pytest.mark.parametrize(
    "change", ["name", "health_status", "encrypted_session", "user_id", "cooldown_until", "delete"]
)
def test_independent_writer_changes_reject_exact_snapshot_cas(store, change):
    empty_metadata(store)
    rpc = Rpc()
    service = service_for(store, rpc)
    request = service.preflight("synthetic-login", 29)

    def race():
        with store() as session, session.begin():
            row = session.get(TelegramAccount, 1)
            if change == "delete":
                session.delete(row)
            else:
                values = {
                    "name": "renamed",
                    "health_status": "CONNECTED",
                    "encrypted_session": "independent-session",
                    "user_id": 1002,
                    "cooldown_until": datetime(2020, 1, 1),
                }
                setattr(row, "telegram_user_id" if change == "user_id" else change, values[change])

    rpc.before_identity = race
    with pytest.raises(TelegramLoginError):
        provision(service, request)
    with store() as session:
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0
        row = session.get(TelegramAccount, 1)
        if row:
            assert row.encrypted_session == (
                "independent-session" if change == "encrypted_session" else ""
            )


@pytest.mark.parametrize("same_name", [False, True])
def test_different_name_user_and_concurrent_creation_never_overwritten(store, same_name):
    rpc = Rpc()
    service = service_for(store, rpc)
    request = service.preflight("synthetic-login", 29)
    rpc.before_identity = lambda: empty_metadata(
        store, name="synthetic-login" if same_name else "other"
    )
    with pytest.raises(TelegramLoginError):
        provision(service, request)
    with store() as session:
        assert session.scalar(select(func.count()).select_from(TelegramAccount)) == 1
        assert session.scalar(select(TelegramAccount)).encrypted_session == ""
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("stage", ["encryption", "account_sql", "audit", "commit"])
def test_durable_failures_rollback_account_and_audit(store, monkeypatch, existing, stage):
    if existing:
        empty_metadata(store)
    rpc = Rpc()
    service = service_for(store, rpc)
    request = service.preflight("synthetic-login", 29)
    attempts = []

    def fail(*args, **kwargs):
        attempts.append(stage)
        raise RuntimeError("private synthetic failure")

    if stage == "encryption":
        monkeypatch.setattr(SessionCipher, "encrypt", fail)
    elif stage == "commit":
        event.listen(store.kw["bind"], "commit", fail)
    else:

        def sql_failure(conn, cursor, statement, parameters, context, executemany):
            target = "outbox_events" if stage == "audit" else "telegram_accounts"
            if statement.startswith(("INSERT", "UPDATE")) and target in statement:
                fail()

        event.listen(store.kw["bind"], "before_cursor_execute", sql_failure)
    try:
        with pytest.raises(TelegramLoginError) as raised:
            provision(service, request)
        assert attempts == [stage]
        assert raised.value.__suppress_context__ and "private synthetic" not in str(raised.value)
        assert rpc.calls[-1] == "disconnect" and rpc.calls.count("code") == 1
    finally:
        if stage == "commit":
            event.remove(store.kw["bind"], "commit", fail)
        elif stage in {"account_sql", "audit"}:
            event.remove(store.kw["bind"], "before_cursor_execute", sql_failure)
    with store() as session:
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0
        assert session.scalar(select(func.count()).select_from(TelegramAccount)) == int(existing)
        if existing:
            assert session.get(TelegramAccount, 1).encrypted_session == ""


@pytest.mark.parametrize("key", ["malformed-key", None, "non-ascii-秘密"])
def test_bad_master_key_fails_preflight_with_zero_rpc(store, key):
    rpc = Rpc()
    with pytest.raises(TelegramLoginError) as raised:
        service_for(store, rpc, key=lambda: key).preflight("synthetic-login", 29)
    assert raised.value.__suppress_context__
    assert rpc.calls == []
    assert_empty(store)


def test_request_is_frozen_service_bound_and_single_use(store):
    rpc = Rpc()
    service = service_for(store, rpc)
    request = service.preflight("synthetic-login", 29)
    with pytest.raises(FrozenInstanceError):
        request.actor_id = 30
    for invalid in [None, replace(request, actor_id=30)]:
        with pytest.raises(TelegramLoginError):
            provision(service, invalid)
    with pytest.raises(TelegramLoginError):
        provision(service_for(store, rpc), request)
    assert rpc.calls == []
    provision(service, request)
    calls = list(rpc.calls)
    with pytest.raises(TelegramLoginError):
        provision(service, request)
    assert rpc.calls == calls


@pytest.mark.parametrize("abort_at", ["read_code", "read_password"])
@pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt(), asyncio.CancelledError()])
def test_abort_remains_primary_when_disconnect_also_fails(store, abort_at, error):
    rpc = Rpc(two_factor=True, stage="disconnect", failure=RuntimeError("private-cleanup"))
    service = service_for(store, rpc)

    def abort():
        raise error

    with pytest.raises(type(error)):
        provision(service, service.preflight("synthetic-login", 29), **{abort_at: abort})
    assert rpc.calls[-1] == "disconnect" and rpc.calls.count("send_code") == 1
    assert_empty(store)


def test_disconnect_failure_after_success_cannot_report_durable_success(store):
    rpc = Rpc(stage="disconnect", failure=RuntimeError("private-cleanup"))
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert_empty(store)


@pytest.mark.parametrize("bad_hash", [None, "", "x" * 4097, 123])
def test_missing_code_hash_prevents_code_reader_and_signin(store, bad_hash):
    class MalformedCodeRpc(Rpc):
        async def send_code_request(self, phone):
            await self.action("send_code")
            return SimpleNamespace(phone_code_hash=bad_hash)

    rpc = MalformedCodeRpc()
    service = service_for(store, rpc)

    def forbidden():
        pytest.fail("Unbound code was requested")

    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29), read_code=forbidden)
    assert rpc.calls == ["connect", "send_code", "disconnect"]
    assert_empty(store)


def test_service_requires_expected_identity_for_new_account(store):
    rpc = Rpc()
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29, expected_user_id=1002))
    assert "identity" in rpc.calls
    assert_empty(store)


def test_serialized_session_without_auth_key_is_not_authorized(store):
    rpc = Rpc()
    rpc.session = StringSession()
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert_empty(store)


def test_nonempty_sdk_string_with_zero_key_is_not_authorization(store):
    value = "1" + base64.urlsafe_b64encode(b"\x02\x95\x9a\xa7\x33\x01\xbb" + b"\x00" * 256).decode(
        "ascii"
    )
    assert value and StringSession(value).auth_key is None
    rpc = Rpc()
    rpc.session = SimpleNamespace(save=lambda: value)
    service = service_for(store, rpc)
    with pytest.raises(TelegramLoginError):
        provision(service, service.preflight("synthetic-login", 29))
    assert_empty(store)
