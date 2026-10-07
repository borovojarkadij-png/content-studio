from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from test_internet_media import Images, setup

from newsflow.persistence.models import EditorialDecisionModel, MediaAssetModel

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def execution(factory, root, images, clock=lambda: NOW):
    from newsflow.services.durable_media_runner import DurableMediaRunner

    return DurableMediaRunner(factory, root, provider=images, clock=clock)


def test_media_job_is_durable_idempotent_and_selected_asset_is_atomic(semantic_store, tmp_path):
    from newsflow.persistence.models import MediaAcquisitionJobModel

    setup(semantic_store)
    images = Images()
    runner = execution(semantic_store, tmp_path, images)
    assert runner.enqueue_pending(now=NOW) == 1
    assert runner.enqueue_pending(now=NOW) == 0
    assert runner.run_next(now=NOW) == "SUCCEEDED"
    assert runner.run_next(now=NOW) == "IDLE"
    with semantic_store() as session:
        job = session.scalar(select(MediaAcquisitionJobModel))
        assert job.state == "SUCCEEDED" and job.attempts == 1
        assert job.claim_token is None
        assert session.get(MediaAssetModel, job.selected_asset_id) is not None
    assert images.calls == ["search", "download"]


def test_expired_media_owner_cannot_download_or_select(semantic_store, tmp_path):
    setup(semantic_store)
    images = Images()
    runner = execution(semantic_store, tmp_path, images)
    runner.enqueue_pending(now=NOW)
    old = runner.claim_next(now=NOW)
    recovered = execution(
        semantic_store, tmp_path, images, clock=lambda: NOW + timedelta(seconds=61)
    )
    new = recovered.claim_next(now=NOW + timedelta(seconds=61))
    assert old.job_id == new.job_id and old.token != new.token and new.attempt == 2
    assert runner.execute(old) == "LOST_LEASE"
    assert recovered.execute(new) == "SUCCEEDED"
    assert images.calls == ["search", "download"]


def test_reject_after_enqueue_makes_zero_network_requests(semantic_store, tmp_path):
    setup(semantic_store)
    images = Images()
    runner = execution(semantic_store, tmp_path, images)
    runner.enqueue_pending(now=NOW)
    with semantic_store() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    assert runner.run_next(now=NOW) == "BLOCKED"
    assert images.calls == []


def test_lost_media_lease_during_download_cannot_persist_result(semantic_store, tmp_path):
    from newsflow.persistence.models import MediaAcquisitionJobModel

    setup(semantic_store)
    clock = [NOW]
    runner = None

    def expire():
        clock[0] = NOW + timedelta(seconds=61)
        runner.claim_next(now=clock[0])

    images = Images(change=expire)
    runner = execution(semantic_store, tmp_path, images, clock=lambda: clock[0])
    runner.enqueue_pending(now=NOW)
    assert runner.run_next(now=NOW) == "LOST_LEASE"
    with semantic_store() as session:
        assert session.scalar(select(MediaAssetModel)) is None
        assert session.scalar(select(MediaAcquisitionJobModel)).selected_asset_id is None


def test_media_attempt_budget_is_persisted_before_network(semantic_store, tmp_path):
    from newsflow.persistence.models import MediaAcquisitionJobModel

    setup(semantic_store)
    images = Images()
    runner = execution(semantic_store, tmp_path, images)
    runner.enqueue_pending(now=NOW)
    runner.claim_next(now=NOW)
    runner.claim_next(now=NOW + timedelta(seconds=61))
    runner.claim_next(now=NOW + timedelta(seconds=122))
    with semantic_store() as session:
        job = session.scalar(select(MediaAcquisitionJobModel))
        assert job.state == "FAILED" and job.attempts == 2
    assert images.calls == []


def test_disabled_media_worker_never_reads_database_or_network(tmp_path):
    from newsflow.worker import run_media_tick

    def forbidden():
        raise AssertionError("Disabled worker touched database")

    assert run_media_tick(forbidden, media_root=tmp_path, enabled=False, now=NOW) == "DISABLED"


def test_no_match_is_a_durable_terminal_result_not_endless_network_retry(semantic_store, tmp_path):
    from newsflow.persistence.models import MediaAcquisitionJobModel

    setup(semantic_store)
    images = Images()
    images.search = lambda text, limit=5: []
    runner = execution(semantic_store, tmp_path, images)
    runner.enqueue_pending(now=NOW)
    assert runner.run_next(now=NOW) == "NO_MATCH"
    assert runner.enqueue_pending(now=NOW) == 0
    assert runner.run_next(now=NOW) == "IDLE"
    with semantic_store() as session:
        job = session.scalar(select(MediaAcquisitionJobModel))
        assert job.state == "NO_MATCH" and job.selected_asset_id is None


def test_media_asset_registration_rolls_back_when_completion_loses_lease(semantic_store, tmp_path):
    from newsflow.persistence.models import MediaAcquisitionJobModel

    setup(semantic_store)
    clock = [NOW]
    runner = execution(semantic_store, tmp_path, Images(), clock=lambda: clock[0])
    persist = runner._acquisition._persist

    def expire_after_disk_write(*args):
        result = persist(*args)
        clock[0] = NOW + timedelta(seconds=61)
        return result

    runner._acquisition._persist = expire_after_disk_write
    runner.enqueue_pending(now=NOW)
    assert runner.run_next(now=NOW) == "LOST_LEASE"
    with semantic_store() as session:
        assert session.scalar(select(MediaAssetModel)) is None
        assert session.scalar(select(MediaAcquisitionJobModel)).state == "RUNNING"


def test_media_migration_refuses_durable_history_loss(semantic_store, tmp_path, monkeypatch):
    import pytest

    from alembic import command
    from newsflow.migrate import runtime_migration_config

    setup(semantic_store)
    runner = execution(semantic_store, tmp_path, Images())
    runner.enqueue_pending(now=NOW)
    monkeypatch.setenv("DATABASE_URL", str(semantic_store.kw["bind"].url))
    config = runtime_migration_config()
    # The isolated fixture uses metadata.create_all. Stamp only this test store;
    # separate migration tests/gates exercise real upgrade/drift on empty stores.
    command.stamp(config, "head")
    with pytest.raises(RuntimeError, match="Refusing"):
        command.downgrade(config, "d82f6a190bc4")


def test_transient_image_failure_has_durable_bounded_retry(semantic_store, tmp_path):
    from newsflow.persistence.models import MediaAcquisitionJobModel
    from newsflow.providers.commons_images import ImageProviderRetryable

    setup(semantic_store)
    images = Images()

    def unavailable(text, *, limit=5):
        raise ImageProviderRetryable("synthetic private response must not persist")

    images.search = unavailable
    runner = execution(semantic_store, tmp_path, images)
    runner.enqueue_pending(now=NOW)
    assert runner.run_next(now=NOW) == "RETRY"
    assert runner.run_next(now=NOW) == "IDLE"
    retry = execution(semantic_store, tmp_path, images, clock=lambda: NOW + timedelta(seconds=31))
    assert retry.run_next(now=NOW + timedelta(seconds=31)) == "FAILED"
    with semantic_store() as session:
        job = session.scalar(select(MediaAcquisitionJobModel))
        assert job.attempts == 2 and job.state == "FAILED"
        assert job.last_error_code == "MEDIA_PROVIDER_UNAVAILABLE"
