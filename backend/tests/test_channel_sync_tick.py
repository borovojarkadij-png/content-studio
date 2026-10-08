from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_channel_baseline import healthy
from test_configured_text_publication import CIPHER
from test_donor_ingestion_runner import NOW
from test_donor_ingestion_runner import donor_store as _donor_store

from newsflow import worker
from newsflow.persistence import models
from newsflow.providers.telegram import (
    FakeTelegramProvider,
    TelegramChannelCheckpoint,
    TelegramChannelDifference,
    TelegramMessage,
)
from newsflow.providers.telegram_difference import ChannelDifferenceGapUnresolved

donor_store = _donor_store
CHANNEL = "-1001234567890"


class Provider(FakeTelegramProvider):
    def __init__(self, difference=None):
        super().__init__()
        self.calls = []
        self.difference = difference or TelegramChannelDifference(
            "1", CHANNEL, 10, 11, True, 0, (), ()
        )
        self.seed_channel_checkpoint(TelegramChannelCheckpoint("1", CHANNEL, 1001, 10))
        self.seed_message("1", CHANNEL, 20, "Unclassified news")

    def channel_checkpoint(self, *args):
        self.calls.append("checkpoint")
        return super().channel_checkpoint(*args)

    def channel_difference(self, *args, **kwargs):
        self.calls.append("difference")
        if isinstance(self.difference, Exception):
            raise self.difference
        return self.difference

    def history(self, *args, **kwargs):
        self.calls.append("history")
        return super().history(*args, **kwargs)


def tick(factory, **kwargs):
    return worker.run_channel_sync_tick(factory, now=NOW, clock=lambda: NOW, **kwargs)


def test_disabled_sync_tick_touches_no_database_credentials_or_provider():
    def forbidden():
        raise AssertionError("Disabled sync touched storage")

    result = tick(forbidden, enabled=False, cipher=None, cursor=5)
    assert result.outcome == "DISABLED" and result.cursor == 5 and result.outcomes == ()


def test_sync_tick_orders_new_bootstrap_deletion_first_difference_then_history(donor_store):
    healthy(donor_store)
    provider = Provider()
    result = tick(donor_store, enabled=True, cipher=CIPHER, provider=provider)
    assert result.outcomes == ((1, "POLL_COMPLETE"),)
    assert provider.calls == ["checkpoint", "difference", "history"]
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 11
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 20
        assert session.scalar(select(models.EditorialDecisionModel)).status == "MANUAL_REVIEW"
        assert session.scalar(select(models.RewriteJobModel)) is None


def test_sync_tick_verifies_expired_cooldown_before_resuming_read_pipeline(donor_store):
    healthy(donor_store)
    with donor_store.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.health_status = "COOLDOWN"
        account.cooldown_until = NOW - timedelta(seconds=1)

    class Reconnecting(Provider):
        def verify_session(self, account_id):
            self.calls.append("health")
            return super().verify_session(account_id)

    provider = Reconnecting()
    result = tick(donor_store, enabled=True, cipher=CIPHER, provider=provider)
    assert result.outcomes == ((1, "POLL_COMPLETE"),)
    assert provider.calls[0] == "health"
    assert result.health_outcomes == ((1, "CONNECTED"),)
    with donor_store() as session:
        assert session.get(models.TelegramAccount, 1).health_status == "CONNECTED"
        assert session.get(models.TelegramAccount, 1).cooldown_until is None
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 20


@pytest.mark.parametrize("state", ["future", "invalid", "empty", "missing_cooldown"])
def test_sync_tick_never_reconnects_unexpired_invalid_or_unprovisioned_accounts(donor_store, state):
    healthy(donor_store)
    with donor_store.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.health_status = "COOLDOWN"
        account.cooldown_until = NOW + timedelta(seconds=60)
        if state == "invalid":
            account.health_status = "SESSION_INVALID"
            account.cooldown_until = NOW - timedelta(seconds=1)
        elif state == "empty":
            account.encrypted_session = ""
            account.cooldown_until = NOW - timedelta(seconds=1)
        elif state == "missing_cooldown":
            account.cooldown_until = None
    provider = Provider()
    assert tick(donor_store, enabled=True, cipher=CIPHER, provider=provider).outcomes == ()
    assert provider.calls == []
    assert provider.session_probe_count("1") == 0


def test_sync_health_retry_is_fair_bounded_and_never_authorizes_failed_probe(donor_store):
    healthy(donor_store)
    with donor_store.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.health_status, account.cooldown_until = "COOLDOWN", NOW
        for number in range(2, 7):
            session.add(
                models.TelegramAccount(
                    id=number,
                    name=f"Synthetic cooldown {number}",
                    telegram_user_id=1000 + number,
                    encrypted_session="synthetic-only",
                    health_status="COOLDOWN",
                    cooldown_until=NOW,
                )
            )

    class Unavailable(Provider):
        def verify_session(self, account_id):
            self.calls.append(account_id)
            raise TimeoutError("Private synthetic provider details")

    provider = Unavailable()
    cursor = 0
    for expected in ((1, 2), (3, 4), (5, 6), (1, 2)):
        result = tick(
            donor_store,
            enabled=True,
            cipher=CIPHER,
            provider=provider,
            health_cursor=cursor,
            limit=2,
        )
        assert result.outcomes == ()
        assert result.health_outcomes == tuple((item, "RETRY_PROVIDER") for item in expected)
        cursor = result.health_cursor
    assert provider.calls == ["1", "2", "3", "4", "5", "6", "1", "2"]
    with donor_store() as session:
        assert set(session.scalars(select(models.TelegramAccount.health_status))) == {"COOLDOWN"}


def test_legacy_history_never_falls_back_to_poll_without_trusted_sync(donor_store):
    healthy(donor_store)
    with donor_store.begin() as session:
        session.add(
            models.DonorIngestionCursorModel(
                donor_channel_id=1, last_message_id=20, available_at=NOW
            )
        )
    provider = Provider()
    result = tick(donor_store, enabled=True, cipher=CIPHER, provider=provider)
    assert result.outcomes == ((1, "LEGACY_SYNC_REQUIRED"),)
    assert provider.calls == []


@pytest.mark.parametrize(
    "difference,expected",
    [
        (ChannelDifferenceGapUnresolved("synthetic"), "GAP_UNRESOLVED"),
        (TelegramChannelDifference("1", CHANNEL, 10, 11, False, 0, (), ()), "DIFFERENCE_CONTINUE"),
        (TimeoutError("synthetic"), "RETRY_PROVIDER"),
    ],
)
def test_failed_or_nonfinal_sync_never_polls_history(donor_store, difference, expected):
    healthy(donor_store)
    provider = Provider(difference)
    result = tick(donor_store, enabled=True, cipher=CIPHER, provider=provider)
    assert result.outcomes == ((1, expected),)
    assert provider.calls == ["checkpoint", "difference"]
    with donor_store() as session:
        assert session.scalar(select(models.IncomingPostModel)) is None
        assert session.scalar(select(models.RewriteJobModel)) is None


def test_deleted_history_is_not_revived_or_classified(donor_store):
    healthy(donor_store)
    provider = Provider(TelegramChannelDifference("1", CHANNEL, 10, 11, True, 0, (), (20,)))
    result = tick(donor_store, enabled=True, cipher=CIPHER, provider=provider)
    assert result.outcomes == ((1, "POLL_COMPLETE"),)
    with donor_store() as session:
        assert session.get(models.SourceDeletionModel, ("1", CHANNEL, 20)) is not None
        assert session.scalar(select(models.IncomingPostModel)) is None
        assert session.scalar(select(models.EditorialDecisionModel)) is None
        assert session.scalar(select(models.RewriteJobModel)) is None


def test_missing_cipher_or_credentials_fails_before_database():
    def forbidden():
        raise AssertionError("Invalid runtime touched storage")

    with pytest.raises(ValueError):
        tick(forbidden, enabled=True, cipher=None)
    with pytest.raises(ValueError):
        tick(forbidden, enabled=True, cipher=CIPHER)


@pytest.mark.parametrize(
    "options",
    [
        {"enabled": 1},
        {"cursor": True},
        {"limit": 0},
        {"limit": 5},
        {"replay_cursor": -1},
        {"health_cursor": True},
        {"health_cursor": -1},
    ],
)
def test_invalid_sync_options_fail_before_storage(options):
    def forbidden():
        raise AssertionError("Invalid sync options touched database")

    with pytest.raises(ValueError):
        tick(forbidden, **({"enabled": True, "cipher": CIPHER, "provider": Provider()} | options))


def test_fair_scan_moves_past_legacy_donor_and_bounds_each_tick(donor_store):
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    healthy(donor_store)
    fake = FakeTelegramProvider()
    with donor_store() as session:
        config = TelegramConfigurationService(session)
        for number in range(2, 8):
            channel = -1001234567890 - number
            donor = config.create_donor(1, channel, f"Synthetic {number}")
            config.create_mapping(donor["id"], 1, 100, 50)
            fake.seed_channel_checkpoint(TelegramChannelCheckpoint("1", str(channel), 1001, 10))
            fake.seed_channel_difference(
                TelegramChannelDifference("1", str(channel), 10, 11, True, 0, (), ())
            )
        session.add(
            models.DonorIngestionCursorModel(
                donor_channel_id=1, last_message_id=20, available_at=NOW
            )
        )
        session.commit()
    cursor = 0
    visited = []
    for expected in ((1, 2), (3, 4), (5, 6), (7,)):
        result = tick(
            donor_store, enabled=True, cipher=CIPHER, provider=fake, cursor=cursor, limit=2
        )
        assert tuple(row[0] for row in result.outcomes) == expected
        visited.extend(row[0] for row in result.outcomes)
        cursor = result.cursor
    assert visited == list(range(1, 8))
    wrapped = tick(donor_store, enabled=True, cipher=CIPHER, provider=fake, cursor=cursor, limit=2)
    assert wrapped.outcomes[0] == (1, "LEGACY_SYNC_REQUIRED")


def test_real_encrypted_factory_runs_full_readonly_sync_pipeline(donor_store):
    from types import SimpleNamespace

    from telethon.tl.functions.channels import GetFullChannelRequest
    from telethon.tl.functions.updates import GetChannelDifferenceRequest
    from telethon.tl.types.updates import ChannelDifferenceEmpty
    from test_telegram_channel_checkpoint import full
    from test_telethon_rpc import Client as BaseClient

    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    healthy(donor_store)
    with donor_store.begin() as session:
        session.get(models.TelegramAccount, 1).encrypted_session = CIPHER.encrypt("initial")

    class Client(BaseClient):
        def __init__(self):
            super().__init__()
            self.session = SimpleNamespace(save=lambda: "initial")
            self.raw.date = NOW
            self.requests = []

        async def __call__(self, request):
            self.requests.append(request)
            if isinstance(request, GetFullChannelRequest):
                return full()
            assert isinstance(request, GetChannelDifferenceRequest)
            return ChannelDifferenceEmpty(pts=11, final=True, timeout=30)

    client = Client()
    provider = ConfiguredTelegramProvider(
        donor_store, cipher=CIPHER, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    result = tick(donor_store, enabled=True, cipher=CIPHER, provider=provider)
    assert result.outcomes == ((1, "POLL_COMPLETE"),)
    assert len(client.requests) == 2 and client.connected == client.disconnected
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 11
        assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 1
        assert CIPHER.decrypt(session.get(models.TelegramAccount, 1).encrypted_session) == "initial"
        assert session.scalar(select(models.RewriteJobModel)) is None


def test_reopened_tick_keeps_original_baseline_and_poll_identity(donor_store):
    healthy(donor_store)
    first = Provider()
    assert tick(donor_store, enabled=True, cipher=CIPHER, provider=first).outcomes == (
        (1, "POLL_COMPLETE"),
    )
    reopened = create_engine(str(donor_store.kw["bind"].url))
    try:
        provider = Provider(TelegramChannelDifference("1", CHANNEL, 11, 12, True, 0, (), ()))
        result = tick(sessionmaker(reopened), enabled=True, cipher=CIPHER, provider=provider)
        assert result.outcomes == ((1, "POLL_COMPLETE"),)
        assert provider.calls == ["difference", "history"]
        with sessionmaker(reopened)() as session:
            assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 12
            assert session.get(models.DonorIngestionCursorModel, 1).last_message_id == 20
            assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 1
            assert session.scalar(select(models.RewriteJobModel)) is None
    finally:
        reopened.dispose()


def test_gap_retry_delay_prevents_early_rpc_and_keeps_old_pts(donor_store):
    healthy(donor_store)
    provider = Provider(ChannelDifferenceGapUnresolved("synthetic"))
    assert tick(donor_store, enabled=True, cipher=CIPHER, provider=provider).outcomes == (
        (1, "GAP_UNRESOLVED"),
    )
    assert tick(donor_store, enabled=True, cipher=CIPHER, provider=provider).outcomes == ()
    assert provider.calls == ["checkpoint", "difference"]
    late = NOW + timedelta(seconds=301)
    provider.difference = TelegramChannelDifference("1", CHANNEL, 10, 11, True, 0, (), ())
    result = worker.run_channel_sync_tick(
        donor_store, now=late, clock=lambda: late, enabled=True, cipher=CIPHER, provider=provider
    )
    assert result.outcomes == ((1, "POLL_COMPLETE"),)
    assert provider.calls == ["checkpoint", "difference", "difference", "history"]


def test_nonfinal_enforced_chunk_retains_obligation_until_final_recovery(donor_store):
    healthy(donor_store)
    provider = Provider(
        TelegramChannelDifference(
            "1",
            CHANNEL,
            10,
            11,
            False,
            0,
            (TelegramMessage("1", CHANNEL, 30, "Retained continuation", source_updated_at=NOW),),
            (),
        )
    )
    assert tick(donor_store, enabled=True, cipher=CIPHER, provider=provider).outcomes == (
        (1, "DIFFERENCE_CONTINUE"),
    )
    with donor_store() as session:
        assert (
            session.get(models.ChannelDifferenceCursorModel, 1).last_error_code
            == "DIFFERENCE_INCOMPLETE"
        )
        assert session.scalar(select(models.EditorialDecisionModel)) is None
        assert session.scalar(select(models.RewriteJobModel)) is None
    provider.difference = TelegramChannelDifference("1", CHANNEL, 11, 12, True, 0, (), ())
    result = tick(donor_store, enabled=True, cipher=CIPHER, provider=provider)
    assert result.outcomes == ((1, "POLL_COMPLETE"),)
    assert any(outcome == "REPLAYED" for _, outcome in result.replay_outcomes)
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).last_error_code is None
        decisions = session.scalars(select(models.EditorialDecisionModel)).all()
        assert len(decisions) == 2 and all(row.status == "MANUAL_REVIEW" for row in decisions)
        assert session.scalar(select(models.RewriteJobModel)) is None
