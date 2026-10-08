from fastapi.testclient import TestClient
from sqlalchemy import select
from test_source_photo_acquisition import (
    NOW,
    Photos,
)
from test_source_photo_acquisition import (
    source_store as _source_store,
)

from newsflow.app import app
from newsflow.persistence.models import MediaAcquisitionJobModel, PublicationCandidateModel
from newsflow.services.telegram_configuration import TelegramConfigurationService

source_store = _source_store


def mapped_store(factory):
    with factory() as session:
        service = TelegramConfigurationService(session)
        donor = service.create_donor(1, -1001234567890, "Synthetic")
        mapping = service.create_mapping(donor["id"], 1, 100, 100)
        session.get(PublicationCandidateModel, 1).mapping_id = mapping["id"]
        session.commit()
        return mapping["id"]


def test_mapping_source_rights_default_unknown_and_persist_revocation_revision(source_store):
    factory, _ = source_store
    mapping_id = mapped_store(factory)
    with factory() as session:
        service = TelegramConfigurationService(session)
        assert service.source_media_rights(mapping_id) == {
            "mapping_id": mapping_id,
            "license_code": "UNDECLARED",
            "attribution": "",
            "revision": 0,
        }
        first = service.set_source_media_rights(mapping_id, "PERMISSION", "Synthetic permission")
        assert first["revision"] == 1
    with factory() as session:
        service = TelegramConfigurationService(session)
        assert service.source_media_rights(mapping_id) == first
        assert (
            service.set_source_media_rights(mapping_id, "PERMISSION", "Synthetic permission")
            == first
        )
        revoked = service.set_source_media_rights(mapping_id, "UNDECLARED", "")
        assert revoked["revision"] == 2
        renewed = service.set_source_media_rights(mapping_id, "PERMISSION", "Synthetic permission")
        assert renewed["revision"] == 3


def test_mapped_source_automation_requires_declared_rights_and_rechecks_revision(source_store):
    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner

    factory, root = source_store
    mapping_id = mapped_store(factory)
    photos = Photos()
    execution = DurableSourcePhotoRunner(factory, root, provider=photos, clock=lambda: NOW)
    assert execution.enqueue_pending(now=NOW) == 0
    with factory() as session:
        service = TelegramConfigurationService(session)
        service.set_source_media_rights(mapping_id, "PERMISSION", "Synthetic permission")
    assert execution.enqueue_pending(now=NOW) == 1
    assert execution.enqueue_pending(now=NOW) == 0
    with factory() as session:
        service = TelegramConfigurationService(session)
        service.set_source_media_rights(mapping_id, "UNDECLARED", "")
        service.set_source_media_rights(mapping_id, "PERMISSION", "Synthetic permission")
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert photos.calls == []


def test_real_api_queues_without_network_and_cannot_override_missing_rights(
    source_store, monkeypatch
):
    factory, root = source_store
    mapping_id = mapped_store(factory)
    monkeypatch.setenv("DATABASE_URL", str(factory.kw["bind"].url))
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(root))
    with TestClient(app) as client:
        path = f"/api/telegram/mappings/{mapping_id}/source-media-rights"
        assert client.get(path).json()["license_code"] == "UNDECLARED"
        queued_path = "/api/telegram/publication-candidates/1/source-photo-acquisition"
        assert client.post(queued_path).status_code == 409
        assert (
            client.put(path, json={"license_code": "PERMISSION", "attribution": " "}).status_code
            == 422
        )
        response = client.put(
            path, json={"license_code": "PERMISSION", "attribution": "Synthetic permission"}
        )
        assert response.status_code == 200 and response.json()["revision"] == 1
        queued = client.post(queued_path)
        assert queued.status_code == 202 and queued.json()["state"] == "QUEUED"
        assert client.post(queued_path).json()["job_id"] == queued.json()["job_id"]
        status = client.get("/api/telegram/publication-candidates/1/media-acquisition").json()
        assert status["state"] == "QUEUED" and status["selected_allowed"] is False
    with factory() as session:
        assert session.scalar(select(MediaAcquisitionJobModel)).attempts == 0
    assert list(root.iterdir()) == []


def test_disabled_source_worker_never_reads_database_or_network(source_store):
    from newsflow.worker import run_source_photo_tick

    def forbidden():
        raise AssertionError("Disabled source worker touched database")

    assert (
        run_source_photo_tick(
            forbidden, media_root=source_store[1], enabled=False, cipher=None, now=NOW
        )
        == "DISABLED"
    )


def test_enabled_source_worker_runs_configured_jobs_with_fake_provider(source_store, monkeypatch):
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.worker import run_source_photo_tick

    class LiveClock:
        @staticmethod
        def now(tz):
            return NOW

    monkeypatch.setattr("newsflow.services.durable_source_photo_runner.datetime", LiveClock)

    factory, root = source_store
    mapping_id = mapped_store(factory)
    with factory() as session:
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "OWNED", "")
    photos = Photos()
    assert (
        run_source_photo_tick(
            factory,
            media_root=root,
            enabled=True,
            cipher=SessionCipher("QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE="),
            now=NOW,
            provider=photos,
        )
        == "SUCCEEDED"
    )
    assert len(photos.calls) == 1


def test_source_worker_uses_live_lease_clock_not_frozen_tick_time(source_store, monkeypatch):
    from datetime import timedelta

    from newsflow.security.session_cipher import SessionCipher
    from newsflow.worker import run_source_photo_tick

    factory, root = source_store
    mapping_id = mapped_store(factory)
    with factory() as session:
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "OWNED", "")
    clock = [NOW]

    class LiveClock:
        @staticmethod
        def now(tz):
            return clock[0]

    monkeypatch.setattr("newsflow.services.durable_source_photo_runner.datetime", LiveClock)

    def expire():
        clock[0] = NOW + timedelta(seconds=61)

    photos = Photos(change=expire)
    assert (
        run_source_photo_tick(
            factory,
            media_root=root,
            enabled=True,
            cipher=SessionCipher("QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE="),
            now=NOW,
            provider=photos,
        )
        == "LOST_LEASE"
    )
    with factory() as session:
        assert session.scalar(select(MediaAcquisitionJobModel)).selected_asset_id is None


def test_source_queue_api_returns_the_exact_job_not_newer_other_mode_history(
    source_store, monkeypatch
):
    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner

    factory, root = source_store
    mapping_id = mapped_store(factory)
    with factory() as session:
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "OWNED", "")
    source_id = DurableSourcePhotoRunner(factory, root, provider=None).enqueue_configured(
        1, now=NOW
    )
    with factory.begin() as session:
        session.add(
            MediaAcquisitionJobModel(
                candidate_id=1, binding_sha256="a" * 64, state="NO_MATCH", available_at=NOW
            )
        )
    monkeypatch.setenv("DATABASE_URL", str(factory.kw["bind"].url))
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(root))
    with TestClient(app) as client:
        result = client.post("/api/telegram/publication-candidates/1/source-photo-acquisition")
        assert result.status_code == 202
        assert result.json()["job_id"] == source_id and result.json()["state"] == "QUEUED"


def test_revoked_mapping_rights_block_existing_registered_source_photo_selection(source_store):
    import pytest

    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
    from newsflow.services.media_selection import LocalMediaSelectionService, MediaSelectionBlocked

    factory, root = source_store
    mapping_id = mapped_store(factory)
    with factory() as session:
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "OWNED", "")
    execution = DurableSourcePhotoRunner(factory, root, provider=Photos(), clock=lambda: NOW)
    execution.enqueue_configured(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    with factory() as session:
        assert (
            LocalMediaSelectionService(session, root).select_for_candidate(1, query="photo")[
                "status"
            ]
            == "SELECTED"
        )
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "UNDECLARED", "")
    with factory() as session, pytest.raises(MediaSelectionBlocked):
        LocalMediaSelectionService(session, root).select_for_candidate(1, query="photo")


def test_changed_mapping_attribution_cannot_select_old_rights_asset(source_store):
    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
    from newsflow.services.media_selection import LocalMediaSelectionService

    factory, root = source_store
    mapping_id = mapped_store(factory)
    with factory() as session:
        TelegramConfigurationService(session).set_source_media_rights(
            mapping_id, "PERMISSION", "Old permission"
        )
    execution = DurableSourcePhotoRunner(factory, root, provider=Photos(), clock=lambda: NOW)
    execution.enqueue_configured(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    with factory() as session:
        TelegramConfigurationService(session).set_source_media_rights(
            mapping_id, "PERMISSION", "New permission"
        )
        result = LocalMediaSelectionService(session, root).select_for_candidate(1, query="photo")
        assert result["status"] == "NO_MATCH" and result["items"] == []


def test_mapping_rights_renewal_during_decode_blocks_current_selection(source_store, monkeypatch):
    import pytest

    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
    from newsflow.services.media_selection import LocalMediaSelectionService, MediaSelectionBlocked

    factory, root = source_store
    mapping_id = mapped_store(factory)
    with factory() as session:
        TelegramConfigurationService(session).set_source_media_rights(mapping_id, "OWNED", "")
    execution = DurableSourcePhotoRunner(factory, root, provider=Photos(), clock=lambda: NOW)
    execution.enqueue_configured(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    read = LocalMediaSelectionService._read_photo

    def renew(self, key):
        value = read(self, key)
        with factory() as session:
            service = TelegramConfigurationService(session)
            service.set_source_media_rights(mapping_id, "UNDECLARED", "")
            service.set_source_media_rights(mapping_id, "OWNED", "")
        return value

    monkeypatch.setattr(LocalMediaSelectionService, "_read_photo", renew)
    with factory() as session, pytest.raises(MediaSelectionBlocked):
        LocalMediaSelectionService(session, root).select_for_candidate(1, query="photo")
