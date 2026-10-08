from datetime import timedelta

import pytest
from sqlalchemy import select
from test_source_photo_acquisition import (
    NOW,
    Photos,
)
from test_source_photo_acquisition import (
    source_store as _source_store,
)

from newsflow.persistence.models import (
    EditorialDecisionModel,
    MediaAcquisitionJobModel,
    MediaAssetModel,
)
from newsflow.services.media_selection import MediaSelectionBlocked

source_store = _source_store


def runner(factory, root, photos, clock=lambda: NOW):
    from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner

    return DurableSourcePhotoRunner(factory, root, provider=photos, clock=clock)


def enqueue(execution):
    return execution.enqueue(
        1, license_code="PERMISSION", attribution="Synthetic permission", now=NOW
    )


def test_source_photo_job_persists_rights_and_completes_atomically(source_store):
    factory, root = source_store
    photos = Photos()
    execution = runner(factory, root, photos)
    job_id = enqueue(execution)
    assert enqueue(execution) == job_id
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    assert execution.run_next(now=NOW) == "IDLE"
    with factory() as session:
        job = session.get(MediaAcquisitionJobModel, job_id)
        assert (job.acquisition_mode, job.license_code, job.attribution) == (
            "REUSE_SOURCE",
            "PERMISSION",
            "Synthetic permission",
        )
        assert job.state == "SUCCEEDED" and job.attempts == 1
        asset = session.get(MediaAssetModel, job.selected_asset_id)
        assert asset.origin == "SOURCE" and asset.attribution == "Synthetic permission"
        assert (root / asset.storage_key).read_bytes() == photos._photos[
            ("1", "-1001234567890", 20)
        ]
    assert len(photos.calls) == 1


def test_source_old_owner_cannot_download_after_restart_recovery(source_store):
    factory, root = source_store
    photos = Photos()
    first = runner(factory, root, photos)
    enqueue(first)
    old = first.claim_next(now=NOW)
    recovered = runner(factory, root, photos, clock=lambda: NOW + timedelta(seconds=61))
    new = recovered.claim_next(now=NOW + timedelta(seconds=61))
    assert new.attempt == 2 and new.token != old.token
    assert first.execute(old) == "LOST_LEASE"
    assert photos.calls == []
    assert recovered.execute(new) == "SUCCEEDED"
    assert len(photos.calls) == 1


def test_source_lease_lost_during_rpc_cannot_register_asset(source_store):
    factory, root = source_store
    clock = [NOW]
    execution = None

    def expire():
        clock[0] = NOW + timedelta(seconds=61)
        execution.claim_next(now=clock[0])

    execution = runner(factory, root, Photos(change=expire), clock=lambda: clock[0])
    enqueue(execution)
    assert execution.run_next(now=NOW) == "LOST_LEASE"
    with factory() as session:
        assert session.scalar(select(MediaAssetModel)) is None
        job = session.scalar(select(MediaAcquisitionJobModel))
        assert job.state == "RUNNING" and job.selected_asset_id is None and job.attempts == 2
    assert not list(root.rglob("*.png"))


def test_source_editorial_reject_blocks_existing_job_without_rpc(source_store):
    factory, root = source_store
    photos = Photos()
    execution = runner(factory, root, photos)
    enqueue(execution)
    with factory.begin() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert photos.calls == []
    with pytest.raises(MediaSelectionBlocked):
        enqueue(execution)


@pytest.mark.parametrize("license_code,credit", [(None, ""), ("CC0", ""), ("PERMISSION", " ")])
def test_source_job_cannot_infer_rights(source_store, license_code, credit):
    factory, root = source_store
    photos = Photos()
    execution = runner(factory, root, photos)
    with pytest.raises(ValueError):
        execution.enqueue(1, license_code=license_code, attribution=credit, now=NOW)
    with factory() as session:
        assert session.scalar(select(MediaAcquisitionJobModel)) is None
    assert photos.calls == []


def test_internet_runner_never_claims_source_jobs(source_store):
    from newsflow.services.durable_media_runner import DurableMediaRunner

    factory, root = source_store
    enqueue(runner(factory, root, Photos()))
    internet = DurableMediaRunner(factory, root)
    assert internet.claim_next(now=NOW) is None
    with factory() as session:
        assert session.scalar(select(MediaAcquisitionJobModel)).attempts == 0


def test_source_job_attempt_budget_survives_abandoned_claims(source_store):
    factory, root = source_store
    photos = Photos()
    execution = runner(factory, root, photos)
    enqueue(execution)
    execution.claim_next(now=NOW)
    execution.claim_next(now=NOW + timedelta(seconds=61))
    assert execution.claim_next(now=NOW + timedelta(seconds=122)) is None
    with factory() as session:
        job = session.scalar(select(MediaAcquisitionJobModel))
        assert job.state == "FAILED" and job.attempts == 2
    assert photos.calls == []


def test_source_floodwait_persists_retry_without_overwriting_longer_account_cooldown(source_store):
    from newsflow.persistence.models import TelegramAccount
    from newsflow.providers.telegram import FloodWait

    factory, root = source_store

    def rate_limit():
        with factory.begin() as session:
            session.get(TelegramAccount, 1).cooldown_until = NOW + timedelta(seconds=180)
        raise FloodWait(90)

    photos = Photos(change=rate_limit)
    execution = runner(factory, root, photos)
    job_id = enqueue(execution)
    assert execution.run_next(now=NOW) == "RETRY"
    assert execution.claim_next(now=NOW + timedelta(seconds=89)) is None
    with factory() as session:
        job = session.get(MediaAcquisitionJobModel, job_id)
        assert job.state == "QUEUED" and job.attempts == 1
        assert job.available_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(seconds=180)
        assert session.get(TelegramAccount, 1).cooldown_until.replace(
            tzinfo=NOW.tzinfo
        ) == NOW + timedelta(seconds=180)
    assert len(photos.calls) == 1


def test_source_transport_retry_budget_is_persisted_and_bounded(source_store):
    factory, root = source_store
    clock = [NOW]

    def failure():
        raise TimeoutError("Synthetic network timeout")

    photos = Photos(change=failure)
    execution = runner(factory, root, photos, clock=lambda: clock[0])
    enqueue(execution)
    assert execution.run_next(now=NOW) == "RETRY"
    clock[0] = NOW + timedelta(seconds=31)
    assert execution.run_next(now=clock[0]) == "FAILED"
    assert execution.run_next(now=clock[0] + timedelta(seconds=31)) == "IDLE"
    assert len(photos.calls) == 2


def test_source_registry_rolls_back_when_completion_loses_lease(source_store):
    factory, root = source_store
    clock = [NOW]
    execution = runner(factory, root, Photos(), clock=lambda: clock[0])
    enqueue(execution)
    register = __import__(
        "newsflow.services.media_selection", fromlist=["LocalMediaSelectionService"]
    ).LocalMediaSelectionService.register_asset

    def expire_after_registration(self, *args, **kwargs):
        result = register(self, *args, **kwargs)
        clock[0] = NOW + timedelta(seconds=61)
        return result

    from unittest.mock import patch

    with patch(
        "newsflow.services.media_selection.LocalMediaSelectionService.register_asset",
        expire_after_registration,
    ):
        assert execution.run_next(now=NOW) == "LOST_LEASE"
    with factory() as session:
        assert session.scalar(select(MediaAssetModel)) is None
        assert session.scalar(select(MediaAcquisitionJobModel)).selected_asset_id is None


def test_source_floodwait_can_recover_after_persisted_cooldown_expires(source_store):
    from newsflow.providers.telegram import FloodWait

    factory, root = source_store
    clock = [NOW]

    def rate_limit():
        raise FloodWait(90)

    photos = Photos(change=rate_limit)
    execution = runner(factory, root, photos, clock=lambda: clock[0])
    enqueue(execution)
    assert execution.run_next(now=NOW) == "RETRY"
    photos.change = None
    clock[0] = NOW + timedelta(seconds=91)
    assert (
        runner(factory, root, photos, clock=lambda: clock[0]).run_next(now=clock[0]) == "SUCCEEDED"
    )
    assert len(photos.calls) == 2


def test_source_job_rights_tampering_blocks_before_rpc(source_store):
    factory, root = source_store
    photos = Photos()
    execution = runner(factory, root, photos)
    job_id = enqueue(execution)
    with factory.begin() as session:
        session.get(MediaAcquisitionJobModel, job_id).attribution = "Different declaration"
    assert execution.run_next(now=NOW) == "BLOCKED"
    assert photos.calls == []


def test_source_job_status_checks_actual_source_rights_and_current_editorial(source_store):
    from newsflow.services.media_job_read import MediaJobReader

    factory, root = source_store
    execution = runner(factory, root, Photos())
    enqueue(execution)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    with factory() as session:
        result = MediaJobReader(session, root).get_status(1)
        assert result["selected_allowed"] is True
        assert result["illustration"] is False
        assert result["asset"]["origin"] == "SOURCE"
        assert result["asset"]["license_code"] == "PERMISSION"
    with factory.begin() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    with factory() as session:
        result = MediaJobReader(session, root).get_status(1)
        assert result["state"] == "SUCCEEDED"  # history is immutable to this read
        assert result["selected_allowed"] is False and result["asset"] is None


def test_source_status_rechecks_editorial_after_reading_photo_bytes(source_store, monkeypatch):
    from newsflow.services.media_job_read import MediaJobReader
    from newsflow.services.media_selection import LocalMediaSelectionService

    factory, root = source_store
    execution = runner(factory, root, Photos())
    enqueue(execution)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    read = LocalMediaSelectionService._read_photo

    def revoke(self, key):
        value = read(self, key)
        with factory.begin() as session:
            decision = session.scalar(select(EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
        return value

    monkeypatch.setattr(LocalMediaSelectionService, "_read_photo", revoke)
    with factory() as session:
        result = MediaJobReader(session, root).get_status(1)
        assert result["selected_allowed"] is False and result["asset"] is None


@pytest.mark.parametrize(
    "fields",
    [
        {"license_code": None},
        {"license_code": "CC0"},
        {"attribution": None},
        {"attribution": " "},
        {"acquisition_mode": "LICENSED_LIBRARY"},
    ],
)
def test_source_job_database_constraint_rejects_invalid_rights(source_store, fields):
    from sqlalchemy.exc import IntegrityError

    factory, root = source_store
    job_id = enqueue(runner(factory, root, Photos()))
    with pytest.raises(IntegrityError), factory.begin() as session:
        job = session.get(MediaAcquisitionJobModel, job_id)
        for name, value in fields.items():
            setattr(job, name, value)
