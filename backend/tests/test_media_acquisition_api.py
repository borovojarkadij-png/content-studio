from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_internet_media import Images, setup

from newsflow.app import app
from newsflow.persistence.models import (
    EditorialDecisionModel,
    MediaAcquisitionJobModel,
    PublicationCandidateModel,
)
from newsflow.services.durable_media_runner import DurableMediaRunner


def configure(monkeypatch, factory, root):
    monkeypatch.setenv("DATABASE_URL", str(factory.kw["bind"].url))
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(root))


def test_generic_media_api_queues_library_mode_without_search_download_or_success_claim(
    semantic_store, tmp_path, monkeypatch
):
    setup(semantic_store)
    configure(monkeypatch, semantic_store, tmp_path)
    with TestClient(app) as client:
        queued = client.post("/api/telegram/publication-candidates/1/media-acquisition")
        assert queued.status_code == 202
        assert (
            queued.json()["state"] == "QUEUED"
            and queued.json()["acquisition_mode"] == "LICENSED_LIBRARY"
        )
        assert queued.json()["selected_allowed"] is False
        assert queued.json()["queue_allowed"] is False  # duplicate click cannot start another job
        assert (
            client.post("/api/telegram/publication-candidates/1/media-acquisition").json()["job_id"]
            == queued.json()["job_id"]
        )
    with semantic_store() as session:
        assert session.scalar(select(MediaAcquisitionJobModel)).attempts == 0
    assert list(tmp_path.glob("internet/*")) == []


def test_generic_media_api_reject_cannot_queue_a_job(semantic_store, tmp_path, monkeypatch):
    setup(semantic_store)
    configure(monkeypatch, semantic_store, tmp_path)
    with semantic_store.begin() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    with TestClient(app) as client:
        assert (
            client.post("/api/telegram/publication-candidates/1/media-acquisition").status_code
            == 409
        )
    with semantic_store() as session:
        assert session.scalar(select(MediaAcquisitionJobModel)) is None


def test_unknown_media_policy_never_falls_back_to_library_or_invents_permission(
    semantic_store, tmp_path, monkeypatch
):
    setup(semantic_store)
    configure(monkeypatch, semantic_store, tmp_path)
    with semantic_store.begin() as session:
        session.get(PublicationCandidateModel, 1).media_policy = "CORRUPTED"
    with TestClient(app) as client:
        assert (
            client.get("/api/telegram/publication-candidates/1/media-acquisition").json()[
                "queue_allowed"
            ]
            is False
        )
        assert (
            client.post("/api/telegram/publication-candidates/1/media-acquisition").status_code
            == 409
        )
    with semantic_store() as session:
        assert session.scalar(select(MediaAcquisitionJobModel)) is None


def test_media_preview_returns_exact_validated_photo_and_revocation_blocks_bytes(
    semantic_store, tmp_path, monkeypatch
):
    from test_commons_images import png

    setup(semantic_store)
    configure(monkeypatch, semantic_store, tmp_path)
    execution = DurableMediaRunner(semantic_store, tmp_path, provider=Images())
    execution.enqueue_pending(now=datetime.now(UTC))
    assert execution.run_next(now=datetime.now(UTC)) == "SUCCEEDED"
    with TestClient(app) as client:
        photo = client.get("/api/telegram/publication-candidates/1/media-preview")
        assert photo.status_code == 200 and photo.content == png()
        assert photo.headers["content-type"] == "image/png"
        assert photo.headers["cache-control"] == "no-store"
        with semantic_store.begin() as session:
            decision = session.scalar(select(EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
        assert client.get("/api/telegram/publication-candidates/1/media-preview").status_code == 409


def test_media_queue_uses_current_policy_not_other_modes_history(
    semantic_store, tmp_path, monkeypatch
):
    setup(semantic_store)
    configure(monkeypatch, semantic_store, tmp_path)
    with semantic_store.begin() as session:
        session.add(
            MediaAcquisitionJobModel(
                candidate_id=1,
                binding_sha256="b" * 64,
                acquisition_mode="REUSE_SOURCE",
                license_code="OWNED",
                attribution="",
                state="BLOCKED",
                available_at=datetime.now(UTC),
            )
        )
    with TestClient(app) as client:
        status = client.get("/api/telegram/publication-candidates/1/media-acquisition").json()
        assert status["media_policy"] == "LICENSED_LIBRARY" and status["queue_allowed"] is True
        response = client.post("/api/telegram/publication-candidates/1/media-acquisition")
        assert (
            response.status_code == 202
            and response.json()["acquisition_mode"] == "LICENSED_LIBRARY"
        )


def test_preview_missing_root_after_status_validation_is_a_guarded_conflict(
    semantic_store, tmp_path, monkeypatch
):
    from newsflow.services.media_job_read import MediaJobReader

    setup(semantic_store)
    configure(monkeypatch, semantic_store, tmp_path)
    execution = DurableMediaRunner(semantic_store, tmp_path, provider=Images())
    execution.enqueue_pending(now=datetime.now(UTC))
    assert execution.run_next(now=datetime.now(UTC)) == "SUCCEEDED"
    original = MediaJobReader.get_status

    def unavailable(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        self._root = tmp_path / "missing-after-read"
        return result

    monkeypatch.setattr(MediaJobReader, "get_status", unavailable)
    with TestClient(app) as client:
        assert client.get("/api/telegram/publication-candidates/1/media-preview").status_code == 409
