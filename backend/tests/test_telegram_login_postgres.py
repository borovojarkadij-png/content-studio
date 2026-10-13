"""Explicit PostgreSQL-only login contracts in fresh migrated UUID schemas."""

from datetime import UTC, datetime
from os import getenv

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from telethon.sessions import StringSession
from test_telegram_login import KEY, SESSION, Rpc, empty_metadata, provision, service_for
from test_telethon_rpc import Client
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.migrate import runtime_migration_config
from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutboxEventModel,
    TelegramAccount,
)
from newsflow.providers.telegram_login import TelegramLoginError
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider


@pytest.fixture
def postgres(monkeypatch, record_property):
    raw = getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL")
    if raw is None:
        pytest.skip("PostgreSQL-only: explicit synthetic NEWSFLOW_UNATTENDED_POSTGRES_URL required")
    url = create_postgres_namespace(raw)
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(runtime_migration_config(), "head")
    engine = create_engine(url)
    record_property("synthetic_namespace", engine.url.query["options"].split("=", 1)[1])
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
    try:
        yield factory
        with factory() as session:
            decision = session.scalar(select(EditorialDecisionModel))
            assert decision.status == "REJECT" and decision.rewrite_allowed is False
            assert session.scalar(select(ContentRevisionModel)).source_text == (
                "Immutable synthetic source: rejected."
            )
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
    finally:
        engine.dispose()  # No DROP/reset: retain the separately owned namespace.


@pytest.fixture(autouse=True)
def zero_rewrite_calls(monkeypatch):
    from newsflow.providers.openai_rewrite import OpenAIRewriteProvider
    from newsflow.providers.openrouter import OpenRouterRewriteProvider

    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("Login invoked a rewrite provider")

    monkeypatch.setattr(OpenAIRewriteProvider, "rewrite", forbidden)
    monkeypatch.setattr(OpenRouterRewriteProvider, "rewrite", forbidden)
    yield
    assert calls == []


def test_migrated_insert_outbox_and_encrypted_consumer_sql_reopen(postgres):
    rpc = Rpc()
    service = service_for(postgres, rpc)
    account_id = provision(service, service.preflight("synthetic-login", 29, 1001))
    reopened = create_engine(postgres.kw["bind"].url)
    try:
        sessions = sessionmaker(reopened)
        with sessions() as session:
            row = session.get(TelegramAccount, account_id)
            assert row.health_status == "DISCONNECTED" and row.telegram_user_id == 1001
            assert row.encrypted_session != SESSION
            assert SessionCipher(KEY).decrypt(row.encrypted_session) == SESSION
            audit = session.scalar(select(OutboxEventModel))
            assert audit.event_type == "TelegramSessionProvisioned"
            assert audit.aggregate_key == f"telegram-session:29:{account_id}"
            assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 1
        client = Client()
        client.session = StringSession(SESSION)
        ConfiguredTelegramProvider(
            sessions,
            cipher=SessionCipher(KEY),
            api_id=123,
            api_hash="a" * 32,
            client_factory=lambda _: client,
        ).verify_session(str(account_id))
        assert client.connected == client.disconnected == 1
        assert client.session.save() == SESSION
    finally:
        reopened.dispose()
    before = list(rpc.calls)
    with pytest.raises(TelegramLoginError):
        service.preflight("synthetic-login", 29)
    assert rpc.calls == before


@pytest.mark.parametrize("change", ["name", "user", "session", "health", "cooldown", "delete"])
def test_migrated_metadata_cas_rejects_independent_committed_writer(postgres, change):
    account_id = empty_metadata(postgres)
    rpc = Rpc()
    service = service_for(postgres, rpc)
    request = service.preflight("synthetic-login", 29)
    writer = create_engine(postgres.kw["bind"].url)

    def race():
        with sessionmaker(writer)() as session, session.begin():
            row = session.get(TelegramAccount, account_id)
            if change == "delete":
                session.delete(row)
            else:
                field, value = {
                    "name": ("name", "independent-name"),
                    "user": ("telegram_user_id", 1002),
                    "session": ("encrypted_session", "independent-session"),
                    "health": ("health_status", "CONNECTED"),
                    "cooldown": ("cooldown_until", datetime(2030, 1, 1, tzinfo=UTC)),
                }[change]
                setattr(row, field, value)

    rpc.before_identity = race
    try:
        with pytest.raises(TelegramLoginError):
            provision(service, request)
    finally:
        writer.dispose()
    with postgres() as session:
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0
        row = session.get(TelegramAccount, account_id)
        if change == "delete":
            assert row is None
        else:
            assert row.encrypted_session == ("independent-session" if change == "session" else "")
    assert rpc.calls.count("send_code") == rpc.calls.count("code") == 1


@pytest.mark.parametrize("same_name", [False, True])
def test_migrated_uniqueness_race_never_replaces_independent_account(postgres, same_name):
    rpc = Rpc()
    service = service_for(postgres, rpc)
    request = service.preflight("synthetic-login", 29)
    writer = create_engine(postgres.kw["bind"].url)
    rpc.before_identity = lambda: empty_metadata(
        sessionmaker(writer), name="synthetic-login" if same_name else "other"
    )
    try:
        with pytest.raises(TelegramLoginError):
            provision(service, request)
    finally:
        writer.dispose()
    with postgres() as session:
        assert session.scalar(select(func.count()).select_from(TelegramAccount)) == 1
        assert session.scalar(select(TelegramAccount)).encrypted_session == ""
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


@pytest.mark.parametrize("existing", [False, True])
def test_migrated_audit_failure_rolls_back_insert_or_cas(postgres, existing):
    if existing:
        empty_metadata(postgres)
    rpc = Rpc()
    service = service_for(postgres, rpc)
    request = service.preflight("synthetic-login", 29)
    failed = []

    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT") and "outbox_events" in statement:
            failed.append(True)
            raise RuntimeError("private-synthetic-audit-failure")

    engine = postgres.kw["bind"]
    event.listen(engine, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(TelegramLoginError):
            provision(service, request)
    finally:
        event.remove(engine, "before_cursor_execute", fail_audit)
    assert failed == [True]
    with postgres() as session:
        assert session.scalar(select(func.count()).select_from(TelegramAccount)) == int(existing)
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0
        if existing:
            assert session.scalar(select(TelegramAccount)).encrypted_session == ""
