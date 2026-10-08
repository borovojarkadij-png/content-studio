from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_internet_media import Images, setup

from newsflow.app import app
from newsflow.persistence.models import EditorialDecisionModel, MediaAssetModel


def test_actual_read_api_reports_persisted_job_and_revoked_selection(
    semantic_store, tmp_path, monkeypatch
):
    from newsflow.services.durable_media_runner import DurableMediaRunner

    setup(semantic_store)
    images = Images()
    runner = DurableMediaRunner(semantic_store, tmp_path, provider=images)
    now = datetime.now(UTC)
    runner.enqueue_pending(now=now)
    monkeypatch.setenv("DATABASE_URL", str(semantic_store.kw["bind"].url))
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(tmp_path))
    with TestClient(app) as client:
        response = client.get("/api/telegram/publication-candidates/1/media-acquisition")
        assert response.status_code == 200
        assert response.json()["state"] == "QUEUED"
        assert response.json()["selected_allowed"] is False
        assert images.calls == []
        assert runner.run_next(now=now) == "SUCCEEDED"
        selected = client.get("/api/telegram/publication-candidates/1/media-acquisition").json()
        assert selected["state"] == "SUCCEEDED" and selected["selected_allowed"] is True
        assert selected["asset"]["license_code"] == "CC-BY"
        with semantic_store() as session:
            decision = session.scalar(select(EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
            session.commit()
        blocked = client.get("/api/telegram/publication-candidates/1/media-acquisition").json()
        assert blocked["state"] == "SUCCEEDED"  # History is never rewritten to pretend failure.
        assert blocked["selected_allowed"] is False and blocked["asset"] is None
        assert images.calls == ["search", "download"]


def test_missing_persistent_bytes_are_not_reported_as_usable(semantic_store, tmp_path, monkeypatch):
    from newsflow.services.durable_media_runner import DurableMediaRunner

    setup(semantic_store)
    runner = DurableMediaRunner(semantic_store, tmp_path, provider=Images())
    now = datetime.now(UTC)
    runner.enqueue_pending(now=now)
    assert runner.run_next(now=now) == "SUCCEEDED"
    with semantic_store() as session:
        path = tmp_path / session.scalar(select(MediaAssetModel)).storage_key
    path.unlink()  # Exact test-owned fixture only.
    monkeypatch.setenv("DATABASE_URL", str(semantic_store.kw["bind"].url))
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(tmp_path))
    with TestClient(app) as client:
        response = client.get("/api/telegram/publication-candidates/1/media-acquisition")
        assert response.status_code == 200
        assert response.json()["selected_allowed"] is False
        assert response.json()["reason_code"] == "MEDIA_BYTES_UNAVAILABLE"


def test_library_publication_hold_survives_selection_and_current_policy_changes(
    semantic_store, tmp_path, monkeypatch
):
    from newsflow.persistence.models import PublicationCandidateModel
    from newsflow.services.durable_media_runner import DurableMediaRunner

    setup(semantic_store)
    images = Images()
    runner = DurableMediaRunner(semantic_store, tmp_path, provider=images)
    monkeypatch.setenv("DATABASE_URL", str(semantic_store.kw["bind"].url))
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(tmp_path))
    with TestClient(app) as client:
        before = client.get("/api/telegram/publication-candidates/1/media-acquisition")
        assert before.headers["cache-control"] == "no-store"
        assert (
            before.json()["publication_hold_reason_code"]
            == "ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED"
        )
        assert images.calls == []
        now = datetime.now(UTC)
        runner.enqueue_pending(now=now)
        assert runner.run_next(now=now) == "SUCCEEDED"
        selected = client.get("/api/telegram/publication-candidates/1/media-acquisition").json()
        assert selected["selected_allowed"] is True
        assert (
            selected["publication_hold_reason_code"]
            == "ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED"
        )
        with semantic_store() as session:
            session.get(PublicationCandidateModel, 1).media_policy = "REUSE_SOURCE"
            session.commit()
        current = client.get("/api/telegram/publication-candidates/1/media-acquisition").json()
        assert current["media_policy"] == "REUSE_SOURCE"
        assert current["acquisition_mode"] == "LICENSED_LIBRARY"
        assert current["publication_hold_reason_code"] is None
        assert current["selected_allowed"] is False
        assert images.calls == ["search", "download"]
