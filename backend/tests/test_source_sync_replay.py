from datetime import timedelta

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from test_source_photo_acquisition import source_store as _source_store
from test_source_sync_guards import CHANNEL, NOW, mark_gap

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.source_sync_replay import SourceSyncReplayService

source_store = _source_store


def quarantine(factory, message_id=99):
    event = TelegramMessage(
        "1", CHANNEL, message_id, f"Unclassified source {message_id}", source_updated_at=NOW
    )
    with factory() as session:
        result = DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
            event, observed_at=NOW
        )
        assert result.status == "SOURCE_SYNC_REQUIRED"
    return f"1:{CHANNEL}:{message_id}:revision:1"


def marker(factory, key):
    with factory() as session:
        row = session.scalar(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.idempotency_key == f"source.sync_quarantined:{key}"
            )
        )
        assert row is not None, "Retained revision has no durable replay obligation"
        return row.id


def recovered(factory):
    with factory.begin() as session:
        row = session.get(models.ChannelDifferenceCursorModel, 1)
        row.pts, row.last_error_code = 11, None


@pytest.mark.parametrize("change", ["revision", "deletion"])
def test_concurrent_source_change_before_binding_locks_retires_obligation_without_classifier(
    source_store, change
):
    from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
    from newsflow.providers.telegram import TelegramChannelDifference
    from newsflow.services.source_deletions import SourceDeletionService

    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    marker_id = marker(factory, key)
    recovered(factory)
    engine = factory.kw["bind"]
    triggered = []

    def interleave(_connection, _cursor, statement, _parameters, _context, _many):
        if triggered or not statement.lstrip().startswith("SELECT donor_channels."):
            return
        triggered.append(change)
        if change == "revision":
            with factory.begin() as writer:
                SqlAlchemyIngestionRepository(writer).ingest(
                    TelegramMessage(
                        "1",
                        CHANNEL,
                        99,
                        "Newer independent observation",
                        is_edit=True,
                        source_updated_at=NOW + timedelta(seconds=1),
                    ),
                    NOW + timedelta(seconds=1),
                )
        else:
            SourceDeletionService(factory).record(
                TelegramChannelDifference("1", CHANNEL, 11, 12, True, 0, (), (99,)),
                observed_at=NOW + timedelta(seconds=1),
            )

    event.listen(engine, "before_cursor_execute", interleave)
    try:
        assert runtime(factory).replay(marker_id) == "SUPERSEDED"
        assert triggered == [change]
        assert runtime(factory).replay(marker_id) == "ALREADY_COMPLETED"
        with factory() as session:
            assert (
                session.scalar(
                    select(models.EditorialDecisionModel).where(
                        models.EditorialDecisionModel.content_key == key
                    )
                )
                is None
            )
            assert (
                session.scalar(
                    select(models.RewriteJobModel).where(models.RewriteJobModel.content_key == key)
                )
                is None
            )
            assert session.scalar(select(models.RewriteUsageModel)) is None
    finally:
        event.remove(engine, "before_cursor_execute", interleave)


def runtime(factory):
    return SourceSyncReplayService(factory, clock=lambda: NOW)


def test_quarantine_obligation_is_atomic_idempotent_and_unknown_replay_is_not_pass(source_store):
    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    assert quarantine(factory) == key
    marker_id = marker(factory, key)
    assert runtime(factory).replay(marker_id) == "WAIT_SYNC"
    recovered(factory)
    reopened = create_engine(str(factory.kw["bind"].url))
    try:
        durable = sessionmaker(reopened)
        assert runtime(durable).replay(marker_id) == "REPLAYED"
        assert runtime(durable).replay(marker_id) == "ALREADY_COMPLETED"
        with durable() as session:
            decision = session.scalar(
                select(models.EditorialDecisionModel).where(
                    models.EditorialDecisionModel.content_key == key
                )
            )
            assert decision.status == "MANUAL_REVIEW" and decision.rewrite_allowed is False
            assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1
            assert session.scalar(select(models.RewriteUsageModel)) is None
            assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 2
    finally:
        reopened.dispose()


def test_replay_crash_after_first_mapping_resumes_without_new_revisions_or_ai(
    source_store, monkeypatch
):
    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    marker_id = marker(factory, key)
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    with factory() as session:
        config = TelegramConfigurationService(session)
        output = config.create_output(1, -1002222222222, "Synthetic second")
        config.create_mapping(1, output["id"], 100, 50)
    recovered(factory)
    original = DurableIngestionWorkflow.ingest

    def crash(self, event, **kwargs):
        original(self, event, **kwargs)
        raise SystemExit("Synthetic exit after one mapping commit")

    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", crash)
    with pytest.raises(SystemExit):
        runtime(factory).replay(marker_id)
    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", original)
    reopened = create_engine(str(factory.kw["bind"].url))
    try:
        assert runtime(sessionmaker(reopened)).replay(marker_id) == "REPLAYED"
    finally:
        reopened.dispose()
    with factory() as session:
        assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 2
        assert len(session.scalars(select(models.EditorialDecisionModel)).all()) == 2
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1
        assert session.scalar(select(models.RewriteUsageModel)) is None


def test_deleted_obligation_completes_as_superseded_without_classification(source_store):
    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    marker_id = marker(factory, key)
    recovered(factory)
    with factory.begin() as session:
        session.add(
            models.SourceDeletionModel(
                telegram_account_id="1",
                donor_channel_id=CHANNEL,
                telegram_message_id=99,
                latest_pts=11,
                observed_at=NOW,
            )
        )
    assert runtime(factory).replay(marker_id) == "SUPERSEDED"
    with factory() as session:
        assert len(session.scalars(select(models.EditorialDecisionModel)).all()) == 1
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1


@pytest.mark.parametrize("change", ["session", "user", "active_difference", "mapping"])
def test_replay_requires_current_bound_idle_baseline_and_mapping(source_store, change):
    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    marker_id = marker(factory, key)
    recovered(factory)
    with factory.begin() as session:
        account = session.get(models.TelegramAccount, 1)
        if change == "session":
            account.encrypted_session = ""
        elif change == "user":
            account.telegram_user_id = 1002
        elif change == "active_difference":
            from datetime import timedelta

            row = session.get(models.ChannelDifferenceCursorModel, 1)
            row.claim_token, row.lease_expires_at = "synthetic-lease", NOW + timedelta(seconds=60)
        else:
            session.delete(session.get(models.ChannelMappingModel, 1))
    assert runtime(factory).replay(marker_id) == "WAIT_SYNC"
    with factory() as session:
        assert len(session.scalars(select(models.EditorialDecisionModel)).all()) == 1


def test_bounded_batch_scans_fairly_and_replays_after_gap_recovers(source_store):
    factory, _ = source_store
    mark_gap(factory)
    keys = [quarantine(factory, number) for number in (99, 100, 101)]
    ids = [marker(factory, key) for key in keys]
    first = runtime(factory).run_batch(limit=2)
    assert first.cursor == ids[1] and first.outcomes == (
        (ids[0], "WAIT_SYNC"),
        (ids[1], "WAIT_SYNC"),
    )
    second = runtime(factory).run_batch(after_id=first.cursor, limit=2)
    assert second.outcomes == ((ids[2], "WAIT_SYNC"),)
    recovered(factory)
    replayed = runtime(factory).run_batch(after_id=second.cursor, limit=2)
    assert replayed.outcomes == ((ids[0], "REPLAYED"), (ids[1], "REPLAYED"))
    assert runtime(factory).run_batch(after_id=replayed.cursor, limit=2).outcomes == (
        (ids[2], "REPLAYED"),
    )
    assert runtime(factory).run_batch().outcomes == ()


def test_obligation_storage_failure_rolls_back_retained_source(source_store):
    factory, _ = source_store
    mark_gap(factory)
    with factory.begin() as session:
        session.execute(
            text(
                "CREATE TRIGGER fail_obligation BEFORE INSERT ON outbox_events "
                "WHEN NEW.event_type='source.sync_quarantined' BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
            )
        )
    with pytest.raises(IntegrityError):
        quarantine(factory)
    with factory() as session:
        assert len(session.scalars(select(models.IncomingPostModel)).all()) == 1
        assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 1


def test_completion_failure_retains_obligation_and_committed_review_for_safe_retry(source_store):
    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    marker_id = marker(factory, key)
    recovered(factory)
    with factory.begin() as session:
        session.execute(
            text(
                "CREATE TRIGGER fail_completion BEFORE INSERT ON outbox_events "
                "WHEN NEW.event_type='source.sync_replay_completed' BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
            )
        )
    assert runtime(factory).replay(marker_id) == "RETRY_STORAGE"
    with factory.begin() as session:
        assert len(session.scalars(select(models.EditorialDecisionModel)).all()) == 2
        session.execute(text("DROP TRIGGER fail_completion"))
    assert runtime(factory).replay(marker_id) == "REPLAYED"
    with factory() as session:
        assert len(session.scalars(select(models.EditorialDecisionModel)).all()) == 2
        assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1


def test_concurrent_policy_change_keeps_obligation_pending_until_new_binding(
    source_store, monkeypatch
):
    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    marker_id = marker(factory, key)
    recovered(factory)
    original = DurableIngestionWorkflow.ingest

    def change(self, event, **kwargs):
        result = original(self, event, **kwargs)
        with factory.begin() as session:
            session.get(models.ChannelMappingModel, 1).priority = 10
        return result

    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", change)
    assert runtime(factory).replay(marker_id) == "WAIT_SYNC"
    monkeypatch.setattr(DurableIngestionWorkflow, "ingest", original)
    assert runtime(factory).replay(marker_id) == "REPLAYED"


def test_existing_editorial_reject_remains_rejected_through_replay(source_store):
    factory, _ = source_store
    mark_gap(factory)
    key = quarantine(factory)
    marker_id = marker(factory, key)
    with factory.begin() as session:
        session.add(
            models.EditorialDecisionModel(
                content_key=key,
                status="REJECT",
                rewrite_allowed=False,
                protected_entities="protected",
                sentiment="negative",
                framing="hostile",
            )
        )
    recovered(factory)
    assert runtime(factory).replay(marker_id) == "REPLAYED"
    with factory() as session:
        row = session.scalar(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key == key
            )
        )
        assert row.status == "REJECT" and row.rewrite_allowed is False
        assert (
            session.scalar(
                select(models.RewriteJobModel).where(models.RewriteJobModel.content_key == key)
            )
            is None
        )
        assert session.scalar(select(models.RewriteUsageModel)) is None
