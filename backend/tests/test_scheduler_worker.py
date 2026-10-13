from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutputChannel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    PublicationPlanModel,
    TelegramAccount,
)


@pytest.fixture
def scheduler_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scheduler.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        account = TelegramAccount(name="Synthetic", telegram_user_id=1001, encrypted_session="")
        session.add(account)
        session.flush()
        for number, zone, mode, slots in (
            (1, "Europe/Minsk", "AUTOMATIC", "540,900"),
            (2, "UTC", "AUTOMATIC", "1430"),
            (3, "UTC", "MANUAL", "1430"),
        ):
            channel = OutputChannel(
                telegram_account_id=account.id,
                telegram_channel_id=-1001234567890 - number,
                title=f"Synthetic {number}",
            )
            session.add(channel)
            session.flush()
            session.add(
                PublicationPlanModel(
                    output_channel_id=channel.id,
                    mode=mode,
                    daily_limit=1,
                    timezone=zone,
                    slot_minutes=slots,
                )
            )
            key = f"synthetic:@scheduler:{number}:revision:1"
            source = IncomingPostModel(
                telegram_account_id="synthetic",
                donor_channel_id="@scheduler",
                telegram_message_id=number,
                state="RECEIVED",
            )
            session.add(source)
            session.flush()
            session.add(
                ContentRevisionModel(
                    incoming_post_id=source.id, revision_number=1, source_text="Synthetic source"
                )
            )
            session.add(
                EditorialDecisionModel(
                    content_key=key,
                    status="PASS",
                    rewrite_allowed=True,
                    sentiment="neutral",
                    framing="neutral",
                )
            )
            session.add(
                PublicationCandidateModel(
                    output_channel_id=channel.id,
                    content_key=key,
                    priority=10,
                    state="READY",
                    eligible_at=datetime(2030, 1, 1, tzinfo=UTC),
                )
            )
        session.commit()
    yield factory
    engine.dispose()


def test_timer_tick_plans_without_button_using_each_channel_day_and_no_past_slots(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    summary = run_scheduler_tick(scheduler_store, now=datetime(2030, 1, 2, 23, 45, tzinfo=UTC))
    assert summary.failed_plan_ids == ()
    with scheduler_store() as session:
        rows = session.scalars(
            select(PlannedPublicationModel).order_by(PlannedPublicationModel.output_channel_id)
        ).all()
        assert [(row.output_channel_id, row.scheduled_for.isoformat()) for row in rows] == [
            (1, "2030-01-03T06:00:00"),
            (2, "2030-01-02T23:50:00"),
        ]
        assert (
            session.scalar(
                select(PublicationCandidateModel.state).where(
                    PublicationCandidateModel.output_channel_id == 3
                )
            )
            == "READY"
        )


def test_scheduler_restart_is_idempotent_and_stale_reject_releases_reservation(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    now = datetime(2030, 1, 2, 23, 45, tzinfo=UTC)
    run_scheduler_tick(scheduler_store, now=now)
    run_scheduler_tick(scheduler_store, now=now)
    with scheduler_store() as session:
        assert session.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 2
        decision = session.scalar(
            select(EditorialDecisionModel).where(
                EditorialDecisionModel.content_key == "synthetic:@scheduler:1:revision:1"
            )
        )
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    run_scheduler_tick(scheduler_store, now=now)
    with scheduler_store() as session:
        assert (
            session.scalar(
                select(PlannedPublicationModel.state).where(
                    PlannedPublicationModel.output_channel_id == 1
                )
            )
            == "BLOCKED_EDITORIAL"
        )


def test_bad_channel_configuration_does_not_prevent_other_channel_planning(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    with scheduler_store() as session:
        session.get(PublicationPlanModel, 1).timezone = "Invalid/Timezone"
        session.commit()
    result = run_scheduler_tick(scheduler_store, now=datetime(2030, 1, 2, 23, 45, tzinfo=UTC))
    assert result.failed_plan_ids == (1,)
    with scheduler_store() as session:
        assert session.scalar(select(PlannedPublicationModel.output_channel_id)) == 2


def test_tick_rejects_naive_time_before_any_planning(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    with pytest.raises(ValueError, match="timezone-aware"):
        # Deliberately invalid input: the scheduler must reject naive timestamps.
        run_scheduler_tick(scheduler_store, now=datetime(2030, 1, 2, tzinfo=None))


@pytest.mark.parametrize("value", ["true", "false", " 1", "1 ", "", "01", 1, True, None])
def test_engagement_flag_rejects_every_nonexact_optin(value):
    from newsflow.worker import telegram_engagement_enabled

    with pytest.raises(ValueError, match="NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED"):
        telegram_engagement_enabled(value)


@pytest.mark.parametrize("value,want", [("0", False), ("1", True)])
def test_engagement_flag_accepts_exact_zero_or_one(value, want):
    from newsflow.worker import telegram_engagement_enabled

    assert telegram_engagement_enabled(value) is want


def engagement_loop(monkeypatch, *, flags=None, ticks=1, factory=None):
    """Keep scheduling real when SQL supplied; replace other external boundaries."""
    from types import SimpleNamespace

    from test_telegram_engagement_history import NOW

    from newsflow import worker

    calls, logs = [], []
    options = flags or {}

    class Stop:
        stopped = False
        completed = 0

        def is_set(self):
            return self.stopped

        def set(self):
            self.stopped = True

        def wait(self, _interval):
            self.completed += 1
            self.stopped = self.completed >= ticks

    stop = Stop()
    monkeypatch.setattr(worker, "getenv", lambda name, default=None: options.get(name, default))
    monkeypatch.setattr(worker, "Event", lambda: stop)
    monkeypatch.setattr(worker.signal, "signal", lambda *_: None)
    monkeypatch.setattr(worker, "datetime", SimpleNamespace(now=lambda _: NOW))
    monkeypatch.setattr(worker, "configured_session_factory", lambda: factory or object())

    def key():
        calls.append("key")
        return "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    monkeypatch.setattr(worker, "load_runtime_master_key", key)
    if factory is None:
        monkeypatch.setattr(
            worker,
            "run_scheduler_tick",
            lambda *_, **__: SimpleNamespace(
                plans_visited=0, active_reservations=0, failed_plan_ids=()
            ),
        )

    def log(event, **fields):
        logs.append((event, fields))

    monkeypatch.setattr(worker, "logger", SimpleNamespace(info=log, warning=log))
    for name in (
        "run_rewrite_tick",
        "run_semantic_tick",
        "run_media_tick",
        "run_source_photo_tick",
        "run_ingestion_tick",
        "run_publication_tick",
        "run_channel_sync_tick",
        "run_donor_resolution_tick",
    ):
        monkeypatch.setattr(worker, name, lambda *_, **__: pytest.fail("Unrequested worker IO"))
    return worker, stop, calls, logs


@pytest.mark.parametrize("flag", [None, "0"])
def test_main_engagement_missing_or_zero_flag_never_loads_cipher_or_calls_tick(monkeypatch, flag):
    flags = {} if flag is None else {"NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED": flag}
    worker, _, calls, logs = engagement_loop(monkeypatch, flags=flags)
    monkeypatch.setattr(
        worker,
        "run_telegram_engagement_tick",
        lambda *_, **__: pytest.fail("Disabled tick IO"),
        raising=False,
    )
    worker.main()
    assert calls == []
    assert not any(event.startswith("telegram_engagement.") for event, _ in logs)


def test_main_invalid_engagement_flag_fails_before_cipher_or_tick(monkeypatch):
    worker, _, calls, _ = engagement_loop(
        monkeypatch, flags={"NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED": "true"}
    )
    with pytest.raises(ValueError, match="NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED"):
        worker.main()
    assert calls == []


def test_main_engagement_requires_existing_stable_key(monkeypatch):
    worker, _, _, _ = engagement_loop(
        monkeypatch, flags={"NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED": "1"}
    )

    def unavailable():
        raise RuntimeError("synthetic stable key unavailable")

    monkeypatch.setattr(worker, "load_runtime_master_key", unavailable)
    with pytest.raises(RuntimeError, match="stable key unavailable"):
        worker.main()


@pytest.mark.parametrize("credentials", [None, "synthetic-explicit-credentials.json"])
def test_main_enabled_tick_retains_cursor_only_after_success_and_continues_work(
    monkeypatch, credentials
):
    from pathlib import Path

    from newsflow.services.telegram_engagement_tick import EngagementSamplingTickResult

    flags = {
        "NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED": "1",
        "NEWSFLOW_TELEGRAM_INGESTION_ENABLED": "1",
        "NEWSFLOW_EDITORIAL_CLASSIFICATION_ENABLED": "1",
        "NEWSFLOW_REWRITE_ENABLED": "1",
    }
    if credentials:
        flags["NEWSFLOW_TELEGRAM_CREDENTIALS_FILE"] = credentials
    worker, _, calls, logs = engagement_loop(monkeypatch, flags=flags, ticks=3)
    cursors, ciphers = [], []
    monkeypatch.setattr(worker, "run_donor_resolution_tick", lambda *_, **__: ())
    monkeypatch.setattr(
        worker, "run_ingestion_tick", lambda *_, **__: calls.append("ingestion") or ()
    )

    def sample(_factory, *, enabled, cipher, now, credentials_path, cursor):
        assert enabled is True and now.tzinfo is not None
        assert credentials_path == Path(credentials or "/run/secrets/telegram_credentials")
        cursors.append(cursor)
        ciphers.append(cipher)
        calls.append("sampling")
        if len(cursors) == 2:
            raise RuntimeError("PRIVATE_SESSION_DIGEST_SENTINEL")
        return EngagementSamplingTickResult("IDLE", 17, ())

    monkeypatch.setattr(worker, "run_telegram_engagement_tick", sample)
    monkeypatch.setattr(
        worker,
        "run_editorial_classification_tick",
        lambda *_, **__: calls.append("editorial") or "IDLE",
    )
    monkeypatch.setattr(
        worker, "run_rewrite_tick", lambda *_, **__: calls.append("rewrite") or "IDLE"
    )
    worker.main()
    assert calls == ["key"] + ["ingestion", "sampling", "editorial", "rewrite"] * 3
    assert cursors == [0, 17, 17]
    assert all(cipher is ciphers[0] for cipher in ciphers)
    assert [entry for entry in logs if entry[0] == "telegram_engagement.execution_interrupted"] == [
        ("telegram_engagement.execution_interrupted", {"recovery": "persisted_lease"})
    ]
    assert "PRIVATE_SESSION_DIGEST_SENTINEL" not in repr(logs)


def test_main_stopped_before_engagement_skips_tick(monkeypatch):
    from types import SimpleNamespace

    worker, stop, calls, _ = engagement_loop(
        monkeypatch, flags={"NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED": "1"}
    )

    def schedule(*_, **__):
        stop.set()
        return SimpleNamespace(plans_visited=0, active_reservations=0, failed_plan_ids=())

    monkeypatch.setattr(worker, "run_scheduler_tick", schedule)
    monkeypatch.setattr(
        worker,
        "run_telegram_engagement_tick",
        lambda *_, **__: pytest.fail("Stopped IO"),
        raising=False,
    )
    worker.main()
    assert calls == ["key"]


def test_main_optin_runs_actual_sql_tick_without_other_optins(monkeypatch, tmp_path):
    from test_telegram_engagement_history import NOW
    from test_telegram_sampling_runner import Fake, assert_preserved, seed_sampling

    from newsflow.services import telegram_engagement_tick

    engine = create_engine(f"sqlite:///{tmp_path / 'main-engagement.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    seed_sampling(factory)
    provider = Fake()
    worker, _, calls, logs = engagement_loop(
        monkeypatch, flags={"NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED": "1"}, factory=factory
    )
    actual_tick = telegram_engagement_tick.run_telegram_engagement_tick

    def injected_tick(*args, **options):
        return actual_tick(*args, **(options | {"provider": provider, "clock": lambda: NOW}))

    monkeypatch.setattr(worker, "run_telegram_engagement_tick", injected_tick)
    try:
        worker.main()
        assert calls == ["key"]
        assert provider.calls == [("1", "-1000000000001", 7, NOW)]
        assert ("telegram_engagement.tick", {"outcome": "SAMPLED", "queued_count": 1}) in logs
        assert_preserved(factory)
    finally:
        engine.dispose()


@pytest.mark.parametrize("sync_failure", [False, True])
def test_main_engagement_follows_sync_success_but_respects_sync_error_continue(
    monkeypatch, sync_failure
):
    from types import SimpleNamespace

    from newsflow.services.telegram_engagement_tick import EngagementSamplingTickResult

    worker, _, calls, logs = engagement_loop(
        monkeypatch,
        flags={
            "NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED": "1",
            "NEWSFLOW_TELEGRAM_INGESTION_ENABLED": "1",
            "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED": "1",
            "NEWSFLOW_EDITORIAL_CLASSIFICATION_ENABLED": "1",
        },
    )
    monkeypatch.setattr(worker, "load_telegram_credentials", lambda _: (123, "a" * 32))
    monkeypatch.setattr(
        worker,
        "ChannelSyncEnforcement",
        lambda _: SimpleNamespace(enable=lambda **_: calls.append("enforcement")),
    )
    monkeypatch.setattr(
        worker, "run_donor_resolution_tick", lambda *_, **__: calls.append("resolution") or ()
    )

    def sync(*_, **__):
        calls.append("sync")
        if sync_failure:
            raise RuntimeError("PRIVATE_SYNC_SENTINEL")
        return SimpleNamespace(
            cursor=1,
            replay_cursor=2,
            health_cursor=3,
            outcomes=(),
            replay_outcomes=(),
            health_outcomes=(),
        )

    monkeypatch.setattr(worker, "run_channel_sync_tick", sync)
    monkeypatch.setattr(
        worker,
        "run_telegram_engagement_tick",
        lambda *_, **__: calls.append("sampling") or EngagementSamplingTickResult("IDLE", 1, ()),
    )
    monkeypatch.setattr(
        worker,
        "run_editorial_classification_tick",
        lambda *_, **__: calls.append("editorial") or "IDLE",
    )
    worker.main()
    assert calls == ["key", "enforcement", "resolution", "sync"] + (
        [] if sync_failure else ["sampling", "editorial"]
    )
    assert "PRIVATE_SYNC_SENTINEL" not in repr(logs)
    if sync_failure:
        assert ("channel_sync.execution_interrupted", {"recovery": "persisted_state"}) in logs
