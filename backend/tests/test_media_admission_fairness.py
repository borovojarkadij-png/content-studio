from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_internet_media import Images
from test_source_photo_acquisition import Photos
from test_source_photo_acquisition import source_store as _source_store
from test_source_rights_configuration import mapped_store

from newsflow.persistence import models
from newsflow.services.durable_media_runner import DurableMediaRunner
from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
from newsflow.services.telegram_configuration import TelegramConfigurationService

source_store = _source_store
NOW = datetime(2030, 1, 1, tzinfo=UTC)


def window(factory, mode):
    with factory() as session:
        original = session.get(models.PublicationCandidateModel, 1)
        original.state = "AWAITING_REWRITE"
        source_key = original.content_key
        draft_text = session.get(models.RewriteOutputModel, 1).rewritten_text
        service = TelegramConfigurationService(session)
        mapping_id = None
        if mode == "REUSE_SOURCE":
            session.commit()
            mapping_id = mapped_store(factory)
            service.set_source_media_rights(mapping_id, "OWNED", "")
        for number in range(100):
            key = f"rejected-window:{number}"
            session.add_all(
                [
                    models.EditorialDecisionModel(
                        content_key=key,
                        status="REJECT",
                        rewrite_allowed=False,
                        sentiment="negative",
                        framing="hostile",
                        protected_entities="Украина",
                    ),
                    models.PublicationCandidateModel(
                        content_key=key,
                        output_channel_id=1,
                        mapping_id=mapping_id,
                        state="READY",
                        priority=1,
                        media_policy=mode,
                    ),
                ]
            )
        session.commit()
        output = service.create_output(1, -1008888888888, "Synthetic late eligible channel")
        if mode == "REUSE_SOURCE":
            mapping = service.create_mapping(1, output["id"], 100, 100)
            mapping_id = mapping["id"]
            service.set_source_media_rights(mapping_id, "OWNED", "")
        job = models.RewriteJobModel(
            content_key=source_key,
            output_channel_id=output["id"],
            idempotency_key="late-eligible-rewrite",
            state="SUCCEEDED",
        )
        session.add(job)
        session.flush()
        session.add(
            models.RewriteOutputModel(
                rewrite_job_id=job.id,
                output_channel_id=output["id"],
                content_key=source_key,
                rewritten_text=draft_text,
                approval_state="APPROVED",
            )
        )
        late = models.PublicationCandidateModel(
            content_key=source_key,
            output_channel_id=output["id"],
            mapping_id=mapping_id,
            state="READY",
            priority=1,
            media_policy=mode,
        )
        session.add(late)
        session.commit()
        return late.id


@pytest.mark.parametrize("mode", ["LICENSED_LIBRARY", "REUSE_SOURCE"])
def test_bounded_admission_advances_past_rejects_and_survives_sql_reopen(
    semantic_store, source_store, tmp_path, mode
):
    factory, root = (semantic_store, tmp_path) if mode == "LICENSED_LIBRARY" else source_store
    late_id = window(factory, mode)
    provider = Images() if mode == "LICENSED_LIBRARY" else Photos()

    def execution(sessions):
        cls = DurableMediaRunner if mode == "LICENSED_LIBRARY" else DurableSourcePhotoRunner
        return cls(sessions, root, provider=provider, clock=lambda: NOW)

    first = execution(factory).enqueue_window(now=NOW, after_id=0, limit=100)
    assert len(first.scanned_ids) == 100 and first.queued_ids == ()
    assert first.blocked_ids == first.scanned_ids
    assert first.cursor < late_id
    reopened = create_engine(str(factory.kw["bind"].url))
    try:
        sessions = sessionmaker(reopened)
        second = execution(sessions).enqueue_window(now=NOW, after_id=first.cursor, limit=100)
        assert second.scanned_ids == (late_id,)
        assert len(second.queued_ids) == 1 and second.blocked_ids == ()
        wrapped = execution(sessions).enqueue_window(now=NOW, after_id=second.cursor, limit=100)
        assert wrapped.cursor == 0 and wrapped.scanned_ids == ()
        again = execution(sessions).enqueue_window(now=NOW, after_id=0, limit=100)
        assert again.queued_ids == ()
        with sessions() as session:
            jobs = session.scalars(select(models.MediaAcquisitionJobModel)).all()
            assert len(jobs) == 1 and jobs[0].candidate_id == late_id and jobs[0].attempts == 0
            assert (
                session.scalar(
                    select(models.RewriteJobModel).where(
                        models.RewriteJobModel.content_key.like("rejected-window:%")
                    )
                )
                is None
            )
            assert session.scalar(select(models.RewriteUsageModel)) is None
    finally:
        reopened.dispose()
    assert provider.calls == []


@pytest.mark.parametrize("value", [True, -1, "0", None])
def test_invalid_scan_cursor_is_refused_before_any_database_activity(tmp_path, value):
    def forbidden():
        raise AssertionError("Invalid window touched database")

    operation = DurableMediaRunner(forbidden, tmp_path)
    with pytest.raises(ValueError):
        operation.enqueue_window(now=NOW, after_id=value, limit=16)


@pytest.mark.parametrize("mode", ["LICENSED_LIBRARY", "REUSE_SOURCE"])
def test_worker_retains_fair_progress_without_changing_the_outcome_contract(
    semantic_store, source_store, tmp_path, mode
):
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.worker import MediaAdmissionState, run_media_tick, run_source_photo_tick

    factory, root = (semantic_store, tmp_path) if mode == "LICENSED_LIBRARY" else source_store
    late_id = window(factory, mode)
    provider = Images() if mode == "LICENSED_LIBRARY" else Photos()
    state = MediaAdmissionState()
    outcomes = []
    for _ in range(7):
        options = {
            "enabled": True,
            "media_root": root,
            "now": NOW,
            "provider": provider,
            "admission": state,
        }
        if mode == "REUSE_SOURCE":
            options["cipher"] = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        operation = run_media_tick if mode == "LICENSED_LIBRARY" else run_source_photo_tick
        outcomes.append(operation(factory, **options))
    assert outcomes == ["IDLE"] * 6 + ["SUCCEEDED"]
    assert state.cursor == late_id
    with factory() as session:
        job = session.scalar(select(models.MediaAcquisitionJobModel))
        assert job.candidate_id == late_id and job.state == "SUCCEEDED"
        assert job.attempts == 1
        assert session.scalar(select(models.RewriteUsageModel)) is None
    assert len(provider.calls) == (2 if mode == "LICENSED_LIBRARY" else 1)


@pytest.mark.parametrize("mode", ["LICENSED_LIBRARY", "REUSE_SOURCE"])
@pytest.mark.parametrize("terminal", ["FAILED", "BLOCKED", "NO_MATCH"])
def test_wrap_and_restart_never_reactivate_terminal_media_history(
    semantic_store, source_store, tmp_path, mode, terminal
):
    factory, root = (semantic_store, tmp_path) if mode == "LICENSED_LIBRARY" else source_store
    late_id = window(factory, mode)
    provider = Images() if mode == "LICENSED_LIBRARY" else Photos()
    cls = DurableMediaRunner if mode == "LICENSED_LIBRARY" else DurableSourcePhotoRunner
    first = cls(factory, root, provider=provider, clock=lambda: NOW).enqueue_window(
        now=NOW, after_id=late_id - 1
    )
    assert len(first.queued_ids) == 1
    with factory.begin() as session:
        job = session.get(models.MediaAcquisitionJobModel, first.queued_ids[0])
        job.state, job.attempts = terminal, 2
        job.last_error_code = "RETAINED_TERMINAL_HISTORY"
        # A changed approval binding still must not implicitly create a new job.
        draft = session.scalar(
            select(models.RewriteOutputModel).where(
                models.RewriteOutputModel.output_channel_id
                == session.get(models.PublicationCandidateModel, late_id).output_channel_id
            )
        )
        draft.rewritten_text += " Updated manual draft."
    restarted = cls(factory, root, provider=provider, clock=lambda: NOW)
    result = restarted.enqueue_window(now=NOW, after_id=late_id - 1)
    assert result.scanned_ids == () and result.queued_ids == () and result.cursor == 0
    with factory() as session:
        jobs = session.scalars(select(models.MediaAcquisitionJobModel)).all()
        assert len(jobs) == 1
        assert (jobs[0].id, jobs[0].state, jobs[0].attempts, jobs[0].last_error_code) == (
            first.queued_ids[0],
            terminal,
            2,
            "RETAINED_TERMINAL_HISTORY",
        )
    assert provider.calls == []


@pytest.mark.parametrize("value", [False, 0, 101, "16", 1.5, None])
def test_invalid_scan_limit_is_refused_before_database_activity(tmp_path, value):
    def forbidden():
        raise AssertionError("Invalid limit touched database")

    with pytest.raises(ValueError):
        DurableMediaRunner(forbidden, tmp_path).enqueue_window(now=NOW, limit=value)


@pytest.mark.parametrize("mode", ["LICENSED_LIBRARY", "REUSE_SOURCE"])
def test_admission_reloads_reject_or_revoked_rights_after_scan(
    semantic_store, source_store, tmp_path, mode
):
    factory, root = (semantic_store, tmp_path) if mode == "LICENSED_LIBRARY" else source_store
    late_id = window(factory, mode)
    provider = Images() if mode == "LICENSED_LIBRARY" else Photos()
    first_read = True

    @contextmanager
    def changed_factory():
        nonlocal first_read
        with factory() as session:
            yield session
        if first_read:
            first_read = False
            with factory() as session:
                candidate = session.get(models.PublicationCandidateModel, late_id)
                if mode == "REUSE_SOURCE":
                    TelegramConfigurationService(session).set_source_media_rights(
                        candidate.mapping_id, "UNDECLARED", ""
                    )
                else:
                    decision = session.scalar(
                        select(models.EditorialDecisionModel).where(
                            models.EditorialDecisionModel.content_key == candidate.content_key
                        )
                    )
                    decision.status, decision.rewrite_allowed = "REJECT", False
                    session.commit()

    cls = DurableMediaRunner if mode == "LICENSED_LIBRARY" else DurableSourcePhotoRunner
    result = cls(changed_factory, root, provider=provider).enqueue_window(
        now=NOW, after_id=late_id - 1
    )
    assert result.scanned_ids == result.blocked_ids == (late_id,)
    assert result.cursor == late_id and result.queued_ids == ()
    with factory() as session:
        assert session.scalar(select(models.MediaAcquisitionJobModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None
    assert provider.calls == []


@pytest.mark.parametrize("mode", ["LICENSED_LIBRARY", "REUSE_SOURCE"])
def test_provider_crash_does_not_reset_fair_scan_or_erase_committed_attempt(
    semantic_store, source_store, tmp_path, mode
):
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.worker import MediaAdmissionState, run_media_tick, run_source_photo_tick

    factory, root = (semantic_store, tmp_path) if mode == "LICENSED_LIBRARY" else source_store
    late_id = window(factory, mode)

    class CrashingProvider:
        def search(self, *_, **__):
            raise RuntimeError("Synthetic provider crash")

        def download_photo(self, *_, **__):
            raise RuntimeError("Synthetic provider crash")

    state = MediaAdmissionState(cursor=late_id - 1)
    options = {
        "enabled": True,
        "media_root": root,
        "now": NOW,
        "provider": CrashingProvider(),
        "admission": state,
    }
    if mode == "REUSE_SOURCE":
        options["cipher"] = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    operation = run_media_tick if mode == "LICENSED_LIBRARY" else run_source_photo_tick
    with pytest.raises(RuntimeError, match="Synthetic provider crash"):
        operation(factory, **options)
    assert state.cursor == late_id
    with factory() as session:
        job = session.scalar(select(models.MediaAcquisitionJobModel))
        assert job.state == "RUNNING" and job.attempts == 1 and job.claim_token
        assert job.selected_asset_id is None
    assert operation(factory, **options) == "IDLE"
    assert state.cursor == 0


@pytest.mark.parametrize("mode", ["LICENSED_LIBRARY", "REUSE_SOURCE"])
def test_disabled_worker_leaves_admission_progress_and_database_untouched(tmp_path, mode):
    from newsflow.worker import MediaAdmissionState, run_media_tick, run_source_photo_tick

    def forbidden():
        raise AssertionError("Disabled worker touched database")

    state = MediaAdmissionState(cursor=99)
    options = {"enabled": False, "media_root": tmp_path, "now": NOW, "admission": state}
    if mode == "REUSE_SOURCE":
        options["cipher"] = None
    operation = run_media_tick if mode == "LICENSED_LIBRARY" else run_source_photo_tick
    assert operation(forbidden, **options) == "DISABLED"
    assert state.cursor == 99


@pytest.mark.parametrize("mode", ["LICENSED_LIBRARY", "REUSE_SOURCE"])
def test_actual_main_loop_does_not_restart_scan_at_rejected_first_page(
    semantic_store, source_store, tmp_path, monkeypatch, mode
):
    from test_publication_main_loop import KEY, OneIteration, isolated_loop

    from newsflow import worker

    factory, root = (semantic_store, tmp_path) if mode == "LICENSED_LIBRARY" else source_store
    late_id = window(factory, mode)
    isolated_loop((factory, root), monkeypatch)
    monkeypatch.setattr(worker, "datetime", SimpleNamespace(now=lambda _: NOW))
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "0")
    monkeypatch.setenv(
        "NEWSFLOW_INTERNET_MEDIA_ENABLED"
        if mode == "LICENSED_LIBRARY"
        else "NEWSFLOW_SOURCE_PHOTO_ENABLED",
        "1",
    )
    monkeypatch.setattr(worker, "load_runtime_master_key", lambda: KEY)

    class SevenIterations(OneIteration):
        def __init__(self):
            super().__init__()
            self.iterations = 0

        def wait(self, seconds):
            self.iterations += 1
            self.stopped = self.iterations == 7

    monkeypatch.setattr(worker, "Event", SevenIterations)
    provider = Images() if mode == "LICENSED_LIBRARY" else Photos()
    operation_name = "run_media_tick" if mode == "LICENSED_LIBRARY" else "run_source_photo_tick"
    actual_tick = getattr(worker, operation_name)
    outcomes = []

    def injected_provider(*args, **kwargs):
        outcomes.append(actual_tick(*args, **kwargs, provider=provider))
        return outcomes[-1]

    monkeypatch.setattr(worker, operation_name, injected_provider)
    if mode == "REUSE_SOURCE":
        # Concurrent library scan wraps every other tick. Sharing one cursor
        # would repeatedly reset the source scan before its late eligible row.
        with factory.begin() as session:
            original = session.get(models.PublicationCandidateModel, 1)
            original.state, original.media_policy = "READY", "LICENSED_LIBRARY"
        monkeypatch.setenv("NEWSFLOW_INTERNET_MEDIA_ENABLED", "1")
        actual_library_tick = worker.run_media_tick
        library_provider = Images()

        def injected_library(*args, **kwargs):
            return actual_library_tick(*args, **kwargs, provider=library_provider)

        monkeypatch.setattr(worker, "run_media_tick", injected_library)
    worker.main()
    assert outcomes == ["IDLE"] * 6 + ["SUCCEEDED"]
    with factory() as session:
        job = session.scalar(
            select(models.MediaAcquisitionJobModel).where(
                models.MediaAcquisitionJobModel.candidate_id == late_id
            )
        )
        assert job.candidate_id == late_id and job.state == "SUCCEEDED"
        assert job.attempts == 1
        assert session.scalar(select(models.RewriteUsageModel)) is None
        assert session.scalar(select(models.PublicationJobModel)) is None
    assert len(provider.calls) == (2 if mode == "LICENSED_LIBRARY" else 1)
    if mode == "REUSE_SOURCE":
        assert library_provider.calls == ["search", "download"]
