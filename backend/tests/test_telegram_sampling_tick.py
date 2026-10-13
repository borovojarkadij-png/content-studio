"""Default-off seam, real migrated sampling and synthetic provider only."""

from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from sqlalchemy import event, func, select
from test_telegram_engagement_history import NOW, history, zero_rewrite_calls
from test_telegram_sampling_runner import Fake, assert_preserved, job_after, mutate
from test_telegram_sampling_runner import store as _store

from newsflow.persistence import models
from newsflow.providers.telegram import FloodWait
from newsflow.security.session_cipher import SessionCipher

store = _store
__all__ = ["zero_rewrite_calls"]
CIPHER = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")


def seam():
    from newsflow.services import telegram_engagement_tick

    return telegram_engagement_tick


def forbidden(*_args, **_kwargs):
    pytest.fail("Disabled or invalid sampling reached IO")


def tick(factory, *, now=NOW, provider=None, **options):
    return seam().run_telegram_engagement_tick(
        factory,
        now=now,
        enabled=True,
        cipher=CIPHER,
        provider=provider or Fake(),
        clock=lambda: now,
        **options,
    )


def test_disabled_is_inert_before_database_provider_credentials_or_validation(monkeypatch):
    module = seam()
    monkeypatch.setattr(module, "load_telegram_credentials", forbidden)
    monkeypatch.setattr(module, "ConfiguredTelegramProvider", forbidden)
    result = module.run_telegram_engagement_tick(forbidden, now=NOW, enabled=False)
    assert result == module.EngagementSamplingTickResult("DISABLED", 0, ())
    assert module.run_telegram_engagement_tick(forbidden, now=None, cursor=8).cursor == 8
    assert (
        module.run_telegram_engagement_tick(
            forbidden,
            now=None,
            provider=type("ForbiddenProvider", (), {"fetch_engagement": forbidden})(),
        ).outcome
        == "DISABLED"
    )
    with pytest.raises(FrozenInstanceError):
        result.cursor = 1


@pytest.mark.parametrize("enabled", [0, 1, "0", "1", None, [], {}])
def test_non_bool_enabled_fails_before_io(enabled, monkeypatch):
    module = seam()
    monkeypatch.setattr(module, "load_telegram_credentials", forbidden)
    monkeypatch.setattr(module, "ConfiguredTelegramProvider", forbidden)
    with pytest.raises(ValueError):
        module.run_telegram_engagement_tick(forbidden, now=NOW, enabled=enabled)


@pytest.mark.parametrize(
    "options",
    [
        {"cipher": None},
        {"now": NOW.replace(tzinfo=None)},
        {"now": None},
        {"cursor": True},
        {"cursor": -1},
        {"cursor": 2**63},
        {"cursor": "1"},
    ],
)
def test_enabled_invalid_preconditions_fail_before_credentials_or_sql(options, monkeypatch):
    module = seam()
    monkeypatch.setattr(module, "load_telegram_credentials", forbidden)
    monkeypatch.setattr(module, "ConfiguredTelegramProvider", forbidden)
    with pytest.raises(ValueError):
        module.run_telegram_engagement_tick(
            forbidden, **({"now": NOW, "enabled": True, "cipher": CIPHER} | options)
        )


def test_noninjected_requires_explicit_credentials_before_io(monkeypatch):
    module = seam()
    monkeypatch.setattr(module, "load_telegram_credentials", forbidden)
    monkeypatch.setattr(module, "ConfiguredTelegramProvider", forbidden)
    with pytest.raises(ValueError, match="credentials"):
        module.run_telegram_engagement_tick(forbidden, now=NOW, enabled=True, cipher=CIPHER)


def test_existing_credential_loader_and_configured_factory_are_used(store, monkeypatch, tmp_path):
    module = seam()
    path = tmp_path / "synthetic-credentials.json"
    path.write_text('{"api_id":123,"api_hash":"' + "a" * 32 + '"}', encoding="utf-8")
    provider = Fake()

    def configured(factory, *, cipher, api_id, api_hash):
        assert factory is store and cipher is CIPHER
        assert (api_id, api_hash) == (123, "a" * 32)
        return provider

    monkeypatch.setattr(module, "ConfiguredTelegramProvider", configured)
    result = module.run_telegram_engagement_tick(
        store, now=NOW, enabled=True, cipher=CIPHER, credentials_path=path, clock=lambda: NOW
    )
    assert (result.outcome, result.cursor, result.queued_ids) == ("SAMPLED", 1, (1,))
    assert provider.calls == [("1", "-1000000000001", 7, NOW)]


def test_injected_provider_needs_no_credentials_and_uses_actual_clock(store, monkeypatch):
    monkeypatch.setattr(seam(), "load_telegram_credentials", forbidden)
    acquired = NOW + timedelta(seconds=10)
    provider = Fake()
    result = seam().run_telegram_engagement_tick(
        store,
        now=NOW,
        enabled=True,
        cipher=CIPHER,
        provider=provider,
        clock=lambda: acquired,
    )
    assert (result.outcome, result.cursor, result.queued_ids) == ("SAMPLED", 1, (1,))
    assert provider.calls == [("1", "-1000000000001", 7, acquired)]
    with store() as session:
        assert history(session).history(1)[0].observed_at == acquired
    assert job_after(store).available_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(seconds=60)


def test_new_tick_instances_restart_duplicate_future_due_and_terminal(store):
    provider = Fake()
    first = tick(store, provider=provider)
    assert (first.outcome, first.cursor, first.queued_ids) == ("SAMPLED", 1, (1,))
    store.kw["bind"].dispose()
    future = tick(store, now=NOW + timedelta(seconds=59), cursor=first.cursor, provider=provider)
    assert (future.outcome, future.cursor, future.queued_ids) == ("IDLE", 1, ())
    for seconds, outcome in [(60, "SAMPLED"), (300, "SAMPLED"), (3600, "SUCCEEDED")]:
        store.kw["bind"].dispose()
        result = tick(store, now=NOW + timedelta(seconds=seconds), cursor=1, provider=provider)
        assert (result.outcome, result.queued_ids) == (outcome, ())
    assert tick(store, now=NOW + timedelta(seconds=3601), provider=provider).outcome == "IDLE"
    with store() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(models.TelegramEngagementSamplingJobModel)
            )
            == 1
        )
        assert [
            int((v.observed_at - NOW).total_seconds()) for v in history(session).history(1)
        ] == [0, 60, 300, 3600]
    assert len(provider.calls) == 4
    assert_preserved(store)


def test_floodwait_survives_new_tick_and_does_not_fetch_early(store):
    provider = Fake(error=FloodWait(120))
    assert tick(store, provider=provider).outcome == "FLOOD_WAIT"
    store.kw["bind"].dispose()
    provider.error = None
    assert tick(store, now=NOW + timedelta(seconds=119), provider=provider).outcome == "IDLE"
    assert len(provider.calls) == 1
    assert tick(store, now=NOW + timedelta(seconds=120), provider=provider).outcome == "SAMPLED"
    assert len(provider.calls) == 2
    assert (job_after(store).step, job_after(store).missed_windows) == (2, 1)


def test_clock_past_fresh_lease_is_stale_with_no_fetch(store):
    times = iter((NOW, NOW + timedelta(seconds=60)))
    provider = Fake()
    result = seam().run_telegram_engagement_tick(
        store,
        now=NOW,
        enabled=True,
        cipher=CIPHER,
        provider=provider,
        clock=lambda: next(times),
    )
    assert result.outcome == "STALE_CLAIM"
    assert provider.calls == []
    assert job_after(store).state == "RUNNING"


def test_tick_admission_bounds_sixteen_and_performs_only_one_rpc_outside_sql(store):
    with store.begin() as session:
        for post_id in range(2, 18):
            session.add(
                models.IncomingPostModel(
                    id=post_id,
                    telegram_account_id="1",
                    donor_channel_id="-1000000000001",
                    telegram_message_id=post_id + 10,
                    state="RECEIVED",
                    created_at=NOW,
                )
            )
        session.flush()
        for post_id in range(2, 18):
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post_id,
                    revision_number=1,
                    source_text="Synthetic other source",
                )
            )

    def no_transaction():
        assert store.kw["bind"].pool.checkedout() == 0

    provider = Fake(callback=no_transaction)
    result = tick(store, provider=provider)
    assert result.cursor == 16
    assert result.queued_ids == tuple(range(1, 17))
    assert result.outcome == "SAMPLED"
    assert provider.calls == [("1", "-1000000000001", 7, NOW)]
    with store() as session:
        assert session.get(models.TelegramEngagementSamplingJobModel, 17) is None
        assert (
            session.scalar(
                select(func.count()).select_from(models.TelegramEngagementSamplingJobModel)
            )
            == 16
        )


def test_sql_interruption_retains_committed_lease_for_fresh_tick_recovery(store):
    engine = store.kw["bind"]
    provider = Fake()

    def fail_finalization(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE telegram_engagement_sampling_jobs"):
            raise RuntimeError("synthetic SQL interruption")

    provider.callback = lambda: event.listen(engine, "before_cursor_execute", fail_finalization)
    try:
        with pytest.raises(RuntimeError, match="synthetic SQL interruption"):
            tick(store, provider=provider)
    finally:
        event.remove(engine, "before_cursor_execute", fail_finalization)
    assert (job_after(store).state, job_after(store).attempts) == ("RUNNING", 1)
    with store() as session:
        assert history(session).history(1) == ()
    engine.dispose()
    provider.callback = None
    assert tick(store, now=NOW + timedelta(seconds=60), provider=provider).outcome == "SAMPLED"
    assert (job_after(store).state, job_after(store).step, job_after(store).attempts) == (
        "QUEUED",
        2,
        0,
    )
    assert len(provider.calls) == 2


@pytest.mark.parametrize("change", ["deletion", "sync", "mapping", "health", "cooldown"])
def test_current_source_or_account_quarantine_prevents_admission(store, change):
    mutate(store, change)
    provider = Fake()
    result = tick(store, provider=provider)
    assert (result.outcome, result.cursor, result.queued_ids) == ("IDLE", 1, ())
    assert provider.calls == []
    with store() as session:
        assert session.scalar(select(models.TelegramEngagementSamplingJobModel)) is None
        assert history(session).history(1) == ()
