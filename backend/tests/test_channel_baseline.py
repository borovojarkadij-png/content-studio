from datetime import UTC, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from test_donor_ingestion_runner import NOW
from test_donor_ingestion_runner import donor_store as _donor_store

from newsflow.persistence import models
from newsflow.providers.telegram import (
    FakeTelegramProvider,
    FloodWait,
    SessionUnavailable,
    TelegramChannelCheckpoint,
)
from newsflow.services.channel_baseline import ChannelBaselineService

donor_store = _donor_store
CHANNEL = "-1001234567890"


class Provider(FakeTelegramProvider):
    def __init__(self, change=None, result=None):
        super().__init__()
        self.calls, self.change = [], change
        self.result = result or TelegramChannelCheckpoint("1", CHANNEL, 1001, 10)

    def channel_checkpoint(self, *args):
        self.calls.append(args)
        if self.change:
            self.change()
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def service(factory, provider):
    return ChannelBaselineService(factory, provider=provider, clock=lambda: NOW)


def healthy(factory):
    with factory.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.health_status = "CONNECTED"
        account.encrypted_session = "synthetic stable encrypted session"


def assert_empty(factory):
    with factory() as session:
        assert session.scalar(select(models.ChannelDifferenceCursorModel)) is None
        assert (
            session.scalar(
                select(models.OutboxEventModel).where(
                    models.OutboxEventModel.event_type == "channel.baseline_recorded"
                )
            )
            is None
        )
        assert session.scalar(select(models.RewriteJobModel)) is None


def test_new_donor_baseline_survives_reopen_and_never_overwrites_pts(donor_store):
    healthy(donor_store)
    provider = Provider()
    assert service(donor_store, provider).bootstrap(1) == "BASELINE_RECORDED"
    reopened = create_engine(str(donor_store.kw["bind"].url))
    try:
        factory = sessionmaker(reopened)
        assert service(factory, provider).bootstrap(1) == "ALREADY_INITIALIZED"
        with factory() as session:
            row = session.get(models.ChannelDifferenceCursorModel, 1)
            assert (
                row.telegram_account_id,
                row.telegram_user_id,
                row.telegram_channel_id,
                row.pts,
            ) == (1, 1001, -1001234567890, 10)
            events = session.scalars(
                select(models.OutboxEventModel).where(
                    models.OutboxEventModel.event_type == "channel.baseline_recorded"
                )
            ).all()
            assert len(events) == 1 and events[0].aggregate_key == "1:1:-1001234567890"
            assert session.scalar(select(models.IncomingPostModel)) is None
            assert session.scalar(select(models.RewriteJobModel)) is None
    finally:
        reopened.dispose()
    assert provider.calls == [("1", CHANNEL)]


@pytest.mark.parametrize("kind", ["source", "poll", "deletion"])
def test_legacy_state_requires_explicit_resync_without_remote_read(donor_store, kind):
    healthy(donor_store)
    with donor_store.begin() as session:
        if kind == "source":
            session.add(
                models.IncomingPostModel(
                    telegram_account_id="1",
                    donor_channel_id=CHANNEL,
                    telegram_message_id=50,
                    state="MANUAL_REVIEW",
                )
            )
        elif kind == "poll":
            session.add(
                models.DonorIngestionCursorModel(
                    donor_channel_id=1, last_message_id=0, available_at=NOW
                )
            )
        else:
            session.add(
                models.SourceDeletionModel(
                    telegram_account_id="1",
                    donor_channel_id=CHANNEL,
                    telegram_message_id=50,
                    latest_pts=9,
                    observed_at=NOW,
                )
            )
    provider = Provider()
    assert service(donor_store, provider).bootstrap(1) == "LEGACY_SYNC_REQUIRED"
    assert provider.calls == []
    assert_empty(donor_store)


@pytest.mark.parametrize("change", ["session", "user", "donor", "health", "mapping"])
def test_context_changed_during_rpc_cannot_record_baseline(donor_store, change):
    healthy(donor_store)

    def mutate():
        # Independent connection can write while network runs: no held SQL locks.
        with donor_store.begin() as session:
            account = session.get(models.TelegramAccount, 1)
            if change == "session":
                account.encrypted_session = "replacement"
            elif change == "user":
                account.telegram_user_id = 1002
            elif change == "donor":
                session.get(models.DonorChannel, 1).telegram_channel_id = -1002222222222
            elif change == "health":
                account.health_status = "SESSION_INVALID"
            else:
                session.get(models.ChannelMappingModel, 1).output_channel_id = 99

    provider = Provider(mutate)
    assert service(donor_store, provider).bootstrap(1) == "STALE_CONTEXT"
    assert provider.calls == [("1", CHANNEL)]
    assert_empty(donor_store)


def test_history_started_during_rpc_is_not_silently_baselined(donor_store):
    healthy(donor_store)

    def start_poll():
        with donor_store.begin() as session:
            session.add(
                models.DonorIngestionCursorModel(
                    donor_channel_id=1, last_message_id=20, available_at=NOW
                )
            )

    assert service(donor_store, Provider(start_poll)).bootstrap(1) == "LEGACY_SYNC_REQUIRED"
    assert_empty(donor_store)


@pytest.mark.parametrize(
    "result",
    [
        TelegramChannelCheckpoint("2", CHANNEL, 1001, 10),
        TelegramChannelCheckpoint("1", "-1002222222222", 1001, 10),
        TelegramChannelCheckpoint("1", CHANNEL, 1002, 10),
        "unvalidated",
    ],
)
def test_foreign_or_untyped_checkpoint_cannot_initialize(donor_store, result):
    healthy(donor_store)
    assert service(donor_store, Provider(result=result)).bootstrap(1) == "FAILED_PROVIDER_CONTRACT"
    assert_empty(donor_store)


def test_outbox_storage_failure_rolls_back_entire_baseline(donor_store):
    healthy(donor_store)
    with donor_store.begin() as session:
        session.execute(
            text(
                "CREATE TRIGGER fail_baseline BEFORE INSERT ON outbox_events "
                "WHEN NEW.event_type = 'channel.baseline_recorded' BEGIN "
                "SELECT RAISE(ABORT, 'synthetic storage failure'); END"
            )
        )
    assert service(donor_store, Provider()).bootstrap(1) == "RETRY_STORAGE"
    assert_empty(donor_store)


@pytest.mark.parametrize(
    "failure,status",
    [(FloodWait(120), "COOLDOWN"), (SessionUnavailable("synthetic"), "SESSION_INVALID")],
)
def test_provider_health_failure_is_durable_and_prevents_immediate_retry(
    donor_store, failure, status
):
    healthy(donor_store)
    provider = Provider(result=failure)
    assert service(donor_store, provider).bootstrap(1) == status
    with donor_store() as session:
        account = session.get(models.TelegramAccount, 1)
        assert account.health_status == status
        if status == "COOLDOWN":
            assert account.cooldown_until.replace(tzinfo=UTC) == NOW + timedelta(seconds=120)
    assert service(donor_store, provider).bootstrap(1) == "ACCOUNT_UNAVAILABLE"
    assert len(provider.calls) == 1
    assert_empty(donor_store)


def test_old_session_failure_never_invalidates_replacement(donor_store):
    healthy(donor_store)

    def replace():
        with donor_store.begin() as session:
            session.get(models.TelegramAccount, 1).encrypted_session = "replacement"

    assert (
        service(donor_store, Provider(replace, SessionUnavailable("old"))).bootstrap(1)
        == "STALE_CONTEXT"
    )
    with donor_store() as session:
        assert session.get(models.TelegramAccount, 1).health_status == "CONNECTED"
    assert_empty(donor_store)


def test_existing_baseline_is_not_reset_even_when_provider_would_return_new_pts(donor_store):
    healthy(donor_store)
    assert service(donor_store, Provider()).bootstrap(1) == "BASELINE_RECORDED"
    with donor_store.begin() as session:
        row = session.get(models.ChannelDifferenceCursorModel, 1)
        row.pts, row.last_error_code = 11, "GAP_UNRESOLVED"
    provider = Provider(result=TelegramChannelCheckpoint("1", CHANNEL, 1001, 999))
    assert service(donor_store, provider).bootstrap(1) == "ALREADY_INITIALIZED"
    assert provider.calls == []
    with donor_store() as session:
        row = session.get(models.ChannelDifferenceCursorModel, 1)
        assert row.pts == 11 and row.last_error_code == "GAP_UNRESOLVED"


def test_concurrent_bootstrap_winner_is_preserved_without_duplicate_outbox(donor_store):
    healthy(donor_store)

    def other_bootstrap():
        assert (
            service(
                donor_store, Provider(result=TelegramChannelCheckpoint("1", CHANNEL, 1001, 11))
            ).bootstrap(1)
            == "BASELINE_RECORDED"
        )

    assert service(donor_store, Provider(other_bootstrap)).bootstrap(1) == "ALREADY_INITIALIZED"
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 11
        events = session.scalars(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.event_type == "channel.baseline_recorded"
            )
        ).all()
        assert len(events) == 1


def test_real_encrypted_factory_checkpoint_bootstraps_without_history_or_rewrite(donor_store):
    from types import SimpleNamespace

    from test_telegram_channel_checkpoint import full
    from test_telegram_channel_difference import DifferenceClient

    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    healthy(donor_store)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with donor_store.begin() as session:
        session.get(models.TelegramAccount, 1).encrypted_session = cipher.encrypt("initial")
    client = DifferenceClient(full())
    client.session = SimpleNamespace(save=lambda: "initial")
    provider = ConfiguredTelegramProvider(
        donor_store, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    assert service(donor_store, provider).bootstrap(1) == "BASELINE_RECORDED"
    assert client.history_args is None and len(client.requests) == 1
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 10
        assert session.scalar(select(models.RewriteJobModel)) is None


def test_own_session_refresh_requires_fresh_baseline_context(donor_store):
    from types import SimpleNamespace

    from test_telegram_channel_checkpoint import full
    from test_telegram_channel_difference import DifferenceClient

    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    healthy(donor_store)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with donor_store.begin() as session:
        session.get(models.TelegramAccount, 1).encrypted_session = cipher.encrypt("initial")
    client = DifferenceClient(full())
    client.session = SimpleNamespace(save=lambda: "refreshed")
    provider = ConfiguredTelegramProvider(
        donor_store, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    assert service(donor_store, provider).bootstrap(1) == "STALE_CONTEXT"
    assert_empty(donor_store)
    assert service(donor_store, provider).bootstrap(1) == "BASELINE_RECORDED"
    assert len(client.requests) == 2


@pytest.mark.parametrize("health", ["DISCONNECTED", "SESSION_INVALID", "COOLDOWN"])
def test_unhealthy_account_is_inert_before_provider(donor_store, health):
    healthy(donor_store)
    with donor_store.begin() as session:
        session.get(models.TelegramAccount, 1).health_status = health
    provider = Provider()
    assert service(donor_store, provider).bootstrap(1) == "ACCOUNT_UNAVAILABLE"
    assert provider.calls == []
    assert_empty(donor_store)


def test_source_appearing_mid_request_blocks_baseline(donor_store):
    healthy(donor_store)

    def ingest():
        with donor_store.begin() as session:
            session.add(
                models.IncomingPostModel(
                    telegram_account_id="1",
                    donor_channel_id=CHANNEL,
                    telegram_message_id=10,
                    state="MANUAL_REVIEW",
                )
            )

    assert service(donor_store, Provider(ingest)).bootstrap(1) == "LEGACY_SYNC_REQUIRED"
    assert_empty(donor_store)


def test_malformed_floodwait_never_persists_fake_cooldown(donor_store):
    healthy(donor_store)
    assert (
        service(donor_store, Provider(result=FloodWait(True))).bootstrap(1)
        == "FAILED_PROVIDER_CONTRACT"
    )
    with donor_store() as session:
        account = session.get(models.TelegramAccount, 1)
        assert account.health_status == "CONNECTED" and account.cooldown_until is None
    assert_empty(donor_store)
