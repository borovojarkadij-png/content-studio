from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from test_donor_ingestion_runner import NOW
from test_donor_ingestion_runner import donor_store as _donor_store

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.telegram import (
    FakeTelegramProvider,
    FloodWait,
    SessionUnavailable,
    TelegramChannelDifference,
    TelegramMessage,
)
from newsflow.providers.telegram_difference import ChannelDifferenceGapUnresolved
from newsflow.services.channel_difference_runner import ChannelDifferenceRunner
from newsflow.services.telegram_configuration import TelegramConfigurationService

donor_store = _donor_store
CHANNEL = "-1001234567890"


def runner(factory, provider, now=NOW):
    return ChannelDifferenceRunner(factory, provider=provider, clock=lambda: now)


def checkpoint(factory):
    with factory.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        account.encrypted_session, account.health_status = (
            "synthetic stable encrypted session",
            "CONNECTED",
        )
        session.add(
            models.ChannelDifferenceCursorModel(
                donor_channel_id=1,
                telegram_account_id=1,
                telegram_user_id=1001,
                telegram_channel_id=int(CHANNEL),
                pts=10,
                available_at=NOW,
            )
        )


def chunk(*, final=True, delay=0, messages=None, deleted=(), start=10, next_pts=11):
    return TelegramChannelDifference(
        "1", CHANNEL, start, next_pts, final, delay, tuple(messages or ()), deleted
    )


def message(message_id=20):
    return TelegramMessage(
        "1", CHANNEL, message_id, "Unclassified synthetic news", source_updated_at=NOW
    )


class Provider(FakeTelegramProvider):
    def __init__(self, result, change=None):
        super().__init__()
        self.result, self.calls, self.change = result, [], change

    def channel_difference(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.change:
            self.change()
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_missing_checkpoint_never_invents_baseline_or_calls_provider(donor_store):
    provider = Provider(chunk())
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "BOOTSTRAP_REQUIRED"
    assert provider.calls == []


@pytest.mark.parametrize(
    "result,outcome",
    [
        (TimeoutError("synthetic"), "RETRY_PROVIDER"),
        (chunk(final=False), "DIFFERENCE_CONTINUE"),
        (chunk(), "DIFFERENCE_COMPLETE"),
    ],
)
def test_gap_quarantine_survives_claim_failure_and_nonfinal_recovery(donor_store, result, outcome):
    checkpoint(donor_store)
    with donor_store.begin() as session:
        session.get(models.ChannelDifferenceCursorModel, 1).last_error_code = "GAP_UNRESOLVED"

    def observe():
        with donor_store() as session:
            assert (
                session.get(models.ChannelDifferenceCursorModel, 1).last_error_code
                == "GAP_UNRESOLVED"
            )

    execution = runner(donor_store, Provider(result, observe))
    assert execution.run_donor(1, now=NOW) == outcome
    with donor_store() as session:
        code = session.get(models.ChannelDifferenceCursorModel, 1).last_error_code
        assert code == (None if outcome == "DIFFERENCE_COMPLETE" else "GAP_UNRESOLVED")


def test_difference_persists_messages_and_advances_pts_only_after_fanout(donor_store):
    checkpoint(donor_store)
    provider = Provider(chunk(messages=(message(),)))
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "DIFFERENCE_COMPLETE"
    with donor_store() as session:
        cursor = session.get(models.ChannelDifferenceCursorModel, 1)
        assert cursor.pts == 11 and cursor.claim_token is None
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert decision.status == "MANUAL_REVIEW" and decision.rewrite_allowed is False
        assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 1
        assert session.scalar(select(models.RewriteJobModel)) is None
    assert provider.calls == [(("1", CHANNEL), {"pts": 10, "limit": 50})]


def test_deletions_commit_before_same_chunk_message_or_classifier(donor_store, monkeypatch):
    checkpoint(donor_store)
    provider = Provider(chunk(messages=(message(),), deleted=(20,)))
    original = DurableIngestionWorkflow.ingest

    def observe(self, event, **kwargs):
        with donor_store() as session:
            assert session.get(models.SourceDeletionModel, ("1", CHANNEL, 20)) is not None
        return original(self, event, sentiment="neutral", framing="neutral", **kwargs)

    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", observe)
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "DIFFERENCE_COMPLETE"
    with donor_store() as session:
        assert session.scalar(select(models.IncomingPostModel)) is None
        assert session.scalar(select(models.EditorialDecisionModel)) is None
        assert session.scalar(select(models.RewriteJobModel)) is None
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 11


def test_crash_after_first_mapping_never_advances_and_replays_idempotently(
    donor_store, monkeypatch
):
    checkpoint(donor_store)
    provider = Provider(chunk(messages=(message(),), deleted=(99,)))
    original = DurableIngestionWorkflow.ingest
    calls = 0

    def crash(self, event, **kwargs):
        nonlocal calls
        result = original(self, event, sentiment="neutral", framing="neutral", **kwargs)
        calls += 1
        if calls == 1:
            raise SystemExit("Synthetic process exit after first mapping commit")
        return result

    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", crash)
    with pytest.raises(SystemExit):
        runner(donor_store, provider).run_donor(1, now=NOW)
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 10
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1
        assert session.get(models.SourceDeletionModel, ("1", CHANNEL, 99)) is not None
    late = NOW + timedelta(seconds=61)
    reopened = create_engine(str(donor_store.kw["bind"].url))
    try:
        assert (
            runner(sessionmaker(reopened), provider, late).run_donor(1, now=late)
            == "DIFFERENCE_COMPLETE"
        )
    finally:
        reopened.dispose()
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 11
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 2
        assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 1
        events = session.scalars(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.event_type == "source.deleted"
            )
        ).all()
        assert len(events) == 1


def test_stale_claim_cannot_call_provider_or_apply_chunk(donor_store):
    checkpoint(donor_store)
    provider = Provider(chunk(messages=(message(),), deleted=(20,)))
    old = runner(donor_store, provider).claim(1, now=NOW)
    late = NOW + timedelta(seconds=61)
    replacement = runner(donor_store, provider, late)
    new = replacement.claim(1, now=late)
    assert new.token != old.token
    assert replacement.execute(old) == "STALE_CLAIM" and provider.calls == []
    assert replacement.execute(new) == "DIFFERENCE_COMPLETE"


@pytest.mark.parametrize("mutation", ["session", "user", "donor", "cooldown"])
def test_identity_or_health_change_during_rpc_fences_every_write(donor_store, mutation):
    checkpoint(donor_store)

    def change():
        with donor_store.begin() as session:
            account = session.get(models.TelegramAccount, 1)
            if mutation == "session":
                account.encrypted_session = "manually replaced session"
            elif mutation == "user":
                account.telegram_user_id = 1002
            elif mutation == "donor":
                session.get(models.DonorChannel, 1).telegram_channel_id = -1001234567899
            else:
                account.health_status, account.cooldown_until = (
                    "COOLDOWN",
                    NOW + timedelta(minutes=10),
                )

    provider = Provider(chunk(messages=(message(),), deleted=(20,)), change)
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "STALE_CLAIM"
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 10
        assert session.scalar(select(models.SourceDeletionModel)) is None
        assert session.scalar(select(models.IncomingPostModel)) is None


def test_too_long_gap_never_resets_pts_or_treats_snapshot_as_recovery(donor_store):
    checkpoint(donor_store)
    provider = Provider(ChannelDifferenceGapUnresolved("Synthetic unrecovered gap"))
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "GAP_UNRESOLVED"
    with donor_store() as session:
        cursor = session.get(models.ChannelDifferenceCursorModel, 1)
        assert cursor.pts == 10 and cursor.last_error_code == "GAP_UNRESOLVED"
        assert cursor.claim_token is None


def test_nonfinal_chunk_is_persisted_but_never_called_full_recovery(donor_store):
    checkpoint(donor_store)
    provider = Provider(chunk(final=False, messages=(message(),)))
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "DIFFERENCE_CONTINUE"
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 11


def test_no_database_lock_is_held_across_difference_rpc(donor_store):
    checkpoint(donor_store)

    def independent_writer():
        with donor_store.begin() as session:
            session.get(models.OutputChannel, 1).title = "Independent writer completed"

    provider = Provider(chunk(), independent_writer)
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "DIFFERENCE_COMPLETE"
    with donor_store() as session:
        assert session.get(models.OutputChannel, 1).title == "Independent writer completed"


@pytest.mark.parametrize("change", ["mapping", "policy"])
@pytest.mark.parametrize("gap", [False, True])
def test_changed_fanout_or_filters_never_advances_partial_chunk(
    donor_store, monkeypatch, change, gap
):
    checkpoint(donor_store)
    if gap:
        with donor_store.begin() as session:
            session.get(models.ChannelDifferenceCursorModel, 1).last_error_code = "GAP_UNRESOLVED"
    provider = Provider(chunk(messages=(message(),)))
    original = DurableIngestionWorkflow.ingest
    calls = 0

    def mutate(self, event, **kwargs):
        nonlocal calls
        result = original(self, event, **kwargs)
        calls += 1
        if calls == 1:
            with donor_store() as session:
                config = TelegramConfigurationService(session)
                if change == "mapping":
                    channel = config.create_output(1, -1001234567899, "Synthetic new route")
                    config.create_mapping(1, channel["id"], 100, 100)
                else:
                    session.add(
                        models.MappingFilterPolicyModel(
                            mapping_id=1,
                            allowed_media_types=["photo"],
                            blocked_domains=[],
                            ad_markers=[],
                        )
                    )
                    session.commit()
        return result

    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", mutate)
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "MAPPING_CHANGED"
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 10
        if gap:
            assert (
                session.get(models.ChannelDifferenceCursorModel, 1).last_error_code
                == "GAP_UNRESOLVED"
            )


@pytest.mark.parametrize(
    "result, expected",
    [
        (None, "FAILED_PROVIDER_CONTRACT"),
        (TimeoutError("synthetic"), "RETRY_PROVIDER"),
        (SessionUnavailable("synthetic"), "SESSION_INVALID"),
        (FloodWait(45), "COOLDOWN"),
    ],
)
def test_provider_failures_persist_safe_code_without_advancing(donor_store, result, expected):
    checkpoint(donor_store)
    provider = Provider(result)
    assert runner(donor_store, provider).run_donor(1, now=NOW) == expected
    with donor_store() as session:
        cursor = session.get(models.ChannelDifferenceCursorModel, 1)
        assert cursor.pts == 10 and cursor.last_error_code == expected
        assert cursor.claim_token is None and cursor.available_at.replace(tzinfo=NOW.tzinfo) > NOW
        assert session.scalar(select(models.IncomingPostModel)) is None
        if expected in {"COOLDOWN", "SESSION_INVALID"}:
            assert session.get(models.TelegramAccount, 1).health_status == expected
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "IDLE"
    assert len(provider.calls) == 1


def test_final_retry_after_delay_and_nonfinal_continuation_use_persisted_pts(donor_store):
    checkpoint(donor_store)
    provider = Provider(chunk(final=False))
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "DIFFERENCE_CONTINUE"
    provider.result = chunk(start=11, next_pts=12, delay=45)
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "DIFFERENCE_COMPLETE"
    assert runner(donor_store, provider).run_donor(1, now=NOW + timedelta(seconds=1)) == "IDLE"
    assert [kwargs["pts"] for _args, kwargs in provider.calls] == [10, 11]
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 12


@pytest.mark.parametrize("field", ["account", "channel", "start", "bound"])
def test_foreign_or_oversized_provider_chunk_never_applies(donor_store, field):
    checkpoint(donor_store)
    if field == "account":
        result = TelegramChannelDifference("2", CHANNEL, 10, 11, True, 0, (), (20,))
    elif field == "channel":
        result = TelegramChannelDifference("1", "-1001234567899", 10, 11, True, 0, (), (20,))
    elif field == "start":
        result = chunk(start=9, deleted=(20,))
    else:
        result = chunk(deleted=tuple(range(1, 52)))
    assert runner(donor_store, Provider(result)).run_donor(1, now=NOW) == "FAILED_PROVIDER_CONTRACT"
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 10
        assert session.scalar(select(models.SourceDeletionModel)) is None


def test_rpc_exceeding_lease_cannot_apply_deletion_or_progress(donor_store):
    checkpoint(donor_store)
    clock = [NOW]
    provider = Provider(
        chunk(deleted=(20,)), change=lambda: clock.__setitem__(0, NOW + timedelta(seconds=61))
    )
    execution = ChannelDifferenceRunner(donor_store, provider=provider, clock=lambda: clock[0])
    assert execution.run_donor(1, now=NOW) == "STALE_CLAIM"
    with donor_store() as session:
        assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 10
        assert session.scalar(select(models.SourceDeletionModel)) is None


def test_real_outbox_failure_leaves_no_partial_deletion_or_cursor_advance(donor_store):
    checkpoint(donor_store)
    with donor_store.begin() as session:
        session.execute(
            text(
                "CREATE TRIGGER synthetic_delta_storage_fault BEFORE INSERT ON outbox_events WHEN NEW.event_type='source.deleted' BEGIN SELECT RAISE(ABORT, 'synthetic fault'); END"
            )
        )
    provider = Provider(chunk(messages=(message(),), deleted=(99,)))
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "RETRY_PIPELINE"
    with donor_store() as session:
        assert session.scalar(select(models.SourceDeletionModel)) is None
        assert session.scalar(select(models.IncomingPostModel)) is None
        cursor = session.get(models.ChannelDifferenceCursorModel, 1)
        assert cursor.pts == 10 and cursor.claim_token is None


@pytest.mark.parametrize("condition", ["session", "baseline", "invalid", "cooldown"])
def test_unusable_account_or_foreign_baseline_never_calls_rpc(donor_store, condition):
    checkpoint(donor_store)
    with donor_store.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        if condition == "session":
            account.encrypted_session = ""
        elif condition == "baseline":
            session.get(models.ChannelDifferenceCursorModel, 1).telegram_user_id = 1002
        elif condition == "invalid":
            account.health_status = "SESSION_INVALID"
        else:
            account.cooldown_until = NOW + timedelta(minutes=10)
    provider = Provider(chunk())
    assert runner(donor_store, provider).run_donor(1, now=NOW) == "IDLE"
    assert provider.calls == []
