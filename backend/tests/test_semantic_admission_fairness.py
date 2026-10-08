"""Synthetic release only: historical rejects never spend verifier/rewrite calls."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from test_semantic_approval import DRAFT, SOURCE, SyntheticVerifier

from newsflow.persistence import models
from newsflow.services.durable_semantic_runner import DurableSemanticRunner

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def retained_window(factory):
    """Populate neutral historical drafts first, then reject old sources in SQL."""
    with factory.begin() as session:
        for output in session.scalars(select(models.RewriteOutputModel)):
            output.approval_state = "REJECTED"
        decisions = []
        for number in range(101):
            message_id = 10 + number
            key = f"synthetic:@semantic:{message_id}:revision:1"
            post = models.IncomingPostModel(
                telegram_account_id="synthetic",
                donor_channel_id="@semantic",
                telegram_message_id=message_id,
                state="RECEIVED",
            )
            decision = models.EditorialDecisionModel(
                content_key=key,
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
            job = models.RewriteJobModel(
                content_key=key,
                output_channel_id=1,
                idempotency_key=f"retained-neutral:{number}",
                state="SUCCEEDED",
            )
            session.add_all([post, decision, job])
            session.flush()
            output = models.RewriteOutputModel(
                rewrite_job_id=job.id,
                output_channel_id=1,
                content_key=key,
                rewritten_text=DRAFT,
                approval_state="PENDING",
            )
            session.add_all(
                [
                    models.ContentRevisionModel(
                        incoming_post_id=post.id, revision_number=1, source_text=SOURCE
                    ),
                    output,
                ]
            )
            decisions.append(key)
        session.flush()
        late_id = output.id
        session.add(
            models.PublicationCandidateModel(
                output_channel_id=1,
                content_key=key,
                priority=10,
                state="AWAITING_REWRITE",
            )
        )
    with factory.begin() as session:
        for decision in session.scalars(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key.in_(decisions[:-1])
            )
        ):
            decision.status, decision.rewrite_allowed = "REJECT", False
            decision.sentiment, decision.framing = "negative", "hostile"
            decision.protected_entities = "Украина"
    return late_id


def test_semantic_window_advances_past_historical_rejects_across_sql_reopen(semantic_store):
    late_id = retained_window(semantic_store)
    provider = SyntheticVerifier()
    first = DurableSemanticRunner(
        semantic_store, verifier_for_release=lambda _: provider, clock=lambda: NOW
    ).enqueue_window(now=NOW, limit=100)
    assert len(first.scanned_ids) == 100
    assert first.blocked_ids == first.scanned_ids and first.queued_ids == ()
    assert first.cursor < late_id
    reopened = create_engine(str(semantic_store.kw["bind"].url))
    try:
        factory = sessionmaker(reopened)
        runner = DurableSemanticRunner(
            factory, verifier_for_release=lambda _: provider, clock=lambda: NOW
        )
        second = runner.enqueue_window(now=NOW, after_id=first.cursor, limit=100)
        assert second.scanned_ids == (late_id,) and len(second.queued_ids) == 1
        assert second.blocked_ids == () and second.cursor == late_id
        tail = runner.enqueue_window(now=NOW, after_id=late_id)
        assert tail.cursor == 0 and tail.scanned_ids == ()
        with factory() as session:
            job = session.scalar(select(models.SemanticVerificationJobModel))
            assert job.rewrite_output_id == late_id and job.attempts == 0 and job.state == "QUEUED"
            assert session.scalar(select(func.count()).select_from(models.RewriteJobModel)) == 103
            assert session.scalar(select(models.RewriteUsageModel)) is None
            assert session.scalar(select(models.SemanticVerificationUsageModel)) is None
        assert provider.calls == []
        assert runner.run_next(now=NOW) == "SUCCEEDED"
        assert provider.calls == [(SOURCE, DRAFT)]
        with factory() as session:
            assert session.get(models.RewriteOutputModel, late_id).approval_state == "APPROVED"
            assert (
                session.scalar(select(func.count()).select_from(models.SemanticEvidenceModel)) == 1
            )
            assert session.scalar(select(func.count()).select_from(models.RewriteJobModel)) == 103
    finally:
        reopened.dispose()


@pytest.mark.parametrize(
    "cursor,limit", [(True, 16), (-1, 16), ("0", 16), (0, 0), (0, 101), (0, False)]
)
def test_semantic_window_refuses_invalid_bounds_before_database(cursor, limit):
    def forbidden(*_, **__):
        raise AssertionError("Invalid/disabled admission accessed database/provider")

    runner = DurableSemanticRunner(forbidden, verifier_for_release=forbidden)
    with pytest.raises(ValueError):
        runner.enqueue_window(now=NOW, after_id=cursor, limit=limit)


def test_worker_keeps_scan_progress_and_verifies_only_late_current_output(
    semantic_store, monkeypatch
):
    from newsflow import worker
    from newsflow.security.session_cipher import SessionCipher

    late_id = retained_window(semantic_store)
    state = worker.SemanticAdmissionState()
    provider = SyntheticVerifier()
    monkeypatch.setattr(
        worker, "ConfiguredSemanticVerifierFactory", lambda *_, **__: lambda _release: provider
    )
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    outcomes = [
        worker.run_semantic_tick(
            semantic_store, enabled=True, cipher=cipher, now=NOW, admission=state
        )
        for _ in range(7)
    ]
    assert outcomes == ["IDLE"] * 6 + ["SUCCEEDED"]
    assert state.cursor == late_id
    assert provider.calls == [(SOURCE, DRAFT)]
    with semantic_store() as session:
        assert session.get(models.RewriteOutputModel, late_id).approval_state == "APPROVED"
        assert session.scalar(select(models.RewriteUsageModel)) is None
        assert session.scalar(select(models.PublicationJobModel)) is None


def test_disabled_semantic_tick_never_touches_scan_secrets_or_database():
    from newsflow import worker

    def forbidden(*_, **__):
        raise AssertionError("Disabled semantic tick accessed state")

    state = worker.SemanticAdmissionState(cursor=77)
    assert (
        worker.run_semantic_tick(forbidden, enabled=False, cipher=None, now=NOW, admission=state)
        == "DISABLED"
    )
    assert state.cursor == 77


def test_actual_main_loop_keeps_semantic_cursor_between_iterations(
    semantic_store, monkeypatch, tmp_path
):
    from test_publication_main_loop import KEY, OneIteration, isolated_loop

    from newsflow import worker

    late_id = retained_window(semantic_store)
    isolated_loop((semantic_store, tmp_path), monkeypatch)
    monkeypatch.setattr(worker, "datetime", SimpleNamespace(now=lambda _: NOW))
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "0")
    monkeypatch.setenv("NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED", "1")
    monkeypatch.setattr(worker, "load_runtime_master_key", lambda: KEY)

    class SevenIterations(OneIteration):
        def __init__(self):
            super().__init__()
            self.iterations = 0

        def wait(self, seconds):
            self.iterations += 1
            self.stopped = self.iterations == 7

    monkeypatch.setattr(worker, "Event", SevenIterations)
    provider = SyntheticVerifier()
    monkeypatch.setattr(
        worker, "ConfiguredSemanticVerifierFactory", lambda *_, **__: lambda _release: provider
    )
    worker.main()
    with semantic_store() as session:
        assert session.get(models.RewriteOutputModel, late_id).approval_state == "APPROVED"
        job = session.scalar(select(models.SemanticVerificationJobModel))
        assert job.state == "SUCCEEDED" and job.attempts == 1
        assert session.scalar(select(func.count()).select_from(models.SemanticEvidenceModel)) == 1
        assert session.scalar(select(func.count()).select_from(models.RewriteJobModel)) == 103
        assert session.scalar(select(models.RewriteUsageModel)) is None
        assert session.scalar(select(models.PublicationJobModel)) is None
    assert provider.calls == [(SOURCE, DRAFT)]


@pytest.mark.parametrize("terminal", ["FAILED", "BLOCKED", "REVIEW"])
def test_semantic_wrap_never_reactivates_terminal_history_after_draft_change(
    semantic_store, terminal
):
    late_id = retained_window(semantic_store)
    provider = SyntheticVerifier()
    runner = DurableSemanticRunner(
        semantic_store, verifier_for_release=lambda _: provider, clock=lambda: NOW
    )
    first = runner.enqueue_window(now=NOW, after_id=late_id - 1)
    assert len(first.queued_ids) == 1
    with semantic_store.begin() as session:
        job = session.get(models.SemanticVerificationJobModel, first.queued_ids[0])
        job.state, job.attempts, job.last_error_code = terminal, 2, "RETAINED_HISTORY"
        session.get(models.RewriteOutputModel, late_id).rewritten_text += " Новый заголовок."
    restarted = DurableSemanticRunner(
        semantic_store, verifier_for_release=lambda _: provider, clock=lambda: NOW
    )
    assert restarted.enqueue_window(now=NOW, after_id=late_id - 1).scanned_ids == ()
    assert restarted.enqueue_window(now=NOW, after_id=0, limit=100).queued_ids == ()
    with semantic_store() as session:
        jobs = session.scalars(select(models.SemanticVerificationJobModel)).all()
        assert len(jobs) == 1
        assert (jobs[0].id, jobs[0].state, jobs[0].attempts, jobs[0].last_error_code) == (
            first.queued_ids[0],
            terminal,
            2,
            "RETAINED_HISTORY",
        )
        assert session.scalar(select(models.SemanticVerificationUsageModel)) is None
    assert provider.calls == []


@pytest.mark.parametrize("change", ["reject", "source_edit", "release_revocation"])
def test_semantic_admission_rechecks_current_state_after_enumeration(semantic_store, change):
    late_id = retained_window(semantic_store)
    first_read = True
    provider = SyntheticVerifier()

    @contextmanager
    def changed_factory():
        nonlocal first_read
        with semantic_store() as session:
            yield session
        if first_read:
            first_read = False
            with semantic_store.begin() as session:
                draft = session.get(models.RewriteOutputModel, late_id)
                if change == "reject":
                    decision = session.scalar(
                        select(models.EditorialDecisionModel).where(
                            models.EditorialDecisionModel.content_key == draft.content_key
                        )
                    )
                    decision.status, decision.rewrite_allowed = "REJECT", False
                elif change == "source_edit":
                    source = session.scalar(
                        select(models.ContentRevisionModel)
                        .join(models.IncomingPostModel)
                        .where(models.IncomingPostModel.telegram_message_id == 110)
                    )
                    session.add(
                        models.ContentRevisionModel(
                            incoming_post_id=source.incoming_post_id,
                            revision_number=2,
                            source_text=SOURCE,
                        )
                    )
                else:
                    session.get(models.SemanticVerifierReleaseModel, 1).active = False

    runner = DurableSemanticRunner(
        changed_factory, verifier_for_release=lambda _: provider, clock=lambda: NOW
    )
    result = runner.enqueue_window(now=NOW, after_id=late_id - 1)
    assert result.scanned_ids == result.blocked_ids == (late_id,)
    assert result.queued_ids == () and result.cursor == late_id
    with semantic_store() as session:
        assert session.scalar(select(models.SemanticVerificationJobModel)) is None
        assert session.scalar(select(models.SemanticEvidenceModel)) is None
        assert session.scalar(select(models.SemanticVerificationUsageModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None
        assert session.scalar(select(func.count()).select_from(models.RewriteJobModel)) == 103
    assert provider.calls == []


def test_semantic_provider_error_preserves_scan_attempt_and_pending_draft(
    semantic_store, monkeypatch
):
    from newsflow import worker
    from newsflow.security.session_cipher import SessionCipher

    late_id = retained_window(semantic_store)
    state = worker.SemanticAdmissionState(cursor=late_id - 1)
    provider = SyntheticVerifier(fail=True)
    monkeypatch.setattr(
        worker, "ConfiguredSemanticVerifierFactory", lambda *_, **__: lambda _release: provider
    )
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    assert (
        worker.run_semantic_tick(
            semantic_store, enabled=True, cipher=cipher, now=NOW, admission=state
        )
        == "FAILED"
    )
    assert state.cursor == late_id
    assert (
        worker.run_semantic_tick(
            semantic_store, enabled=True, cipher=cipher, now=NOW, admission=state
        )
        == "IDLE"
    )
    assert state.cursor == 0
    with semantic_store() as session:
        draft = session.get(models.RewriteOutputModel, late_id)
        assert draft.approval_state == "PENDING"
        job = session.scalar(select(models.SemanticVerificationJobModel))
        assert job.state == "FAILED" and job.attempts == 1 and job.evidence_id
        assert session.scalar(select(models.PublicationJobModel)) is None
        assert session.scalar(select(models.SemanticVerificationUsageModel)) is None
    assert provider.calls == [(SOURCE, DRAFT)]
