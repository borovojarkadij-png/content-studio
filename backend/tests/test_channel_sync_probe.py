import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence import models


def load_probe():
    path = Path(__file__).resolve().parents[2] / "scripts" / "docker_channel_sync_probe.py"
    spec = importlib.util.spec_from_file_location("channel_sync_probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    return probe


def test_probe_reopens_pending_chunk_and_recovers_original_pts_without_reseed(tmp_path):
    probe = load_probe()
    now = datetime(2030, 1, 1, tzinfo=UTC)
    url = f"sqlite:///{tmp_path / 'sync.db'}"
    engine = create_engine(url)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    manifest = probe.seed(factory, tmp_path, now=now)
    probe.verify(factory, manifest, completed=False)
    engine.dispose()

    reopened = create_engine(url)
    try:
        sessions = sessionmaker(reopened)
        probe.verify(sessions, manifest, completed=False)
        with pytest.raises(RuntimeError, match="refusing"):
            probe.seed(sessions, tmp_path, now=now)
        probe.recover(sessions, manifest, now=now + timedelta(seconds=65))
        probe.verify(sessions, manifest, completed=True)
        probe.verify(sessions, manifest, completed=True)
        with sessions() as session:
            cursor = session.get(models.ChannelDifferenceCursorModel, manifest["donor"])
            assert cursor.pts == 12 and cursor.claim_token is None
            assert len(session.scalars(select(models.RewriteJobModel)).all()) == 1
            assert session.get(models.RewriteJobModel, manifest["legacy_job"]).state == "SUPERSEDED"
            assert session.scalar(select(models.RewriteUsageModel)) is None
            assert session.scalar(select(models.PublicationJobModel)) is None
    finally:
        reopened.dispose()


def test_probe_refuses_legacy_manifest_and_early_recovery_without_progress(tmp_path):
    probe = load_probe()
    now = datetime(2030, 1, 1, tzinfo=UTC)
    engine = create_engine(f"sqlite:///{tmp_path / 'sync.db'}")
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    try:
        manifest = probe.seed(sessions, tmp_path, now=now)
        with pytest.raises(RuntimeError, match="version"):
            probe.verify(sessions, {**manifest, "version": 0}, completed=False)
        with pytest.raises(RuntimeError, match="lease"):
            probe.recover(sessions, manifest, now=now)
        probe.verify(sessions, manifest, completed=False)
    finally:
        engine.dispose()


def test_probe_coexists_with_prior_synthetic_pending_job_without_silent_provider_call(tmp_path):
    from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
    from newsflow.domain.technical_filters import MappingTechnicalFilter
    from newsflow.providers.telegram import TelegramMessage
    from newsflow.services.telegram_configuration import TelegramConfigurationService

    probe = load_probe()
    now = datetime(2030, 1, 1, tzinfo=UTC)
    engine = create_engine(f"sqlite:///{tmp_path / 'prior.db'}")
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    try:
        with sessions() as session:
            config = TelegramConfigurationService(session)
            account = config.create_account("Prior fixture", 900901)
            config.create_output(account["id"], -1001777999000, "Prior output")
            result = DurableIngestionWorkflow(
                session,
                technical_filter=MappingTechnicalFilter(
                    mapping_id="synthetic", output_channel_id=1
                ),
            ).ingest(
                TelegramMessage("synthetic", "@donor", 1, "Prior fixture source"),
                observed_at=now,
                sentiment="neutral",
                framing="neutral",
            )
            assert result.status == "REWRITE_QUEUED"
        manifest = probe.seed(sessions, tmp_path, now=now)
        probe.recover(sessions, manifest, now=now + timedelta(seconds=65))
        probe.verify(sessions, manifest, completed=True)
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "url", ["sqlite:///newsflow_verification", "postgresql+psycopg://localhost/production"]
)
def test_probe_main_refuses_nonisolated_or_nonpostgres_target_before_connection(monkeypatch, url):
    probe = load_probe()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("NEWSFLOW_VERIFICATION_PROBE", "1")

    def forbidden(_url):
        raise AssertionError("Unsafe probe opened a database connection")

    monkeypatch.setattr(probe, "create_engine", forbidden)
    with pytest.raises(RuntimeError, match="isolated PostgreSQL"):
        probe.main("seed")


def test_probe_main_refuses_network_enabled_fixture_before_connection(monkeypatch):
    probe = load_probe()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/newsflow_verification")
    monkeypatch.setenv("NEWSFLOW_VERIFICATION_PROBE", "1")
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "1")
    with pytest.raises(RuntimeError, match="network workers disabled"):
        probe.main("seed")


def test_powershell_refuses_combined_channel_sync_and_legacy_suite_before_docker():
    import shutil
    import subprocess

    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell runtime unavailable; parser/runtime evidence pending")
    script = Path(__file__).resolve().parents[2] / "scripts" / "verify-persistence.ps1"
    completed = subprocess.run(
        [executable, "-NoProfile", "-File", str(script), "-ChannelSyncGuard", "-PublicationGuard"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode != 0
    assert "requires a separate fresh fixture" in completed.stderr


def test_probe_main_requires_persistent_synthetic_secret_before_database(monkeypatch, tmp_path):
    from newsflow.security.master_key import MasterKeyUnavailable

    probe = load_probe()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/newsflow_verification")
    monkeypatch.setenv("NEWSFLOW_VERIFICATION_PROBE", "1")
    monkeypatch.setenv("NEWSFLOW_MASTER_KEY_FILE", str(tmp_path / "not-provisioned"))
    for flag in (
        "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
        "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
        "NEWSFLOW_REWRITE_ENABLED",
        "NEWSFLOW_PUBLICATION_ENABLED",
    ):
        monkeypatch.setenv(flag, "0")

    def forbidden(_url):
        raise AssertionError("Missing stable secret reached database setup")

    monkeypatch.setattr(probe, "create_engine", forbidden)
    with pytest.raises(MasterKeyUnavailable):
        probe.main("seed")
    assert not (tmp_path / "not-provisioned").exists()


def test_probe_checks_actual_inbox_truth_before_and_after_recovery(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from newsflow.app import app

    probe = load_probe()
    now = datetime(2030, 1, 1, tzinfo=UTC)
    url = f"sqlite:///{tmp_path / 'api.db'}"
    engine = create_engine(url)
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setenv("DATABASE_URL", url)
    try:
        manifest = probe.seed(sessions, tmp_path, now=now)
        with TestClient(app) as client:
            response = client.get("/api/telegram/incoming-posts")
            assert response.status_code == 200
            probe.verify_inbox(response.json(), manifest, completed=False)
            probe.recover(sessions, manifest, now=now + timedelta(seconds=65))
            response = client.get("/api/telegram/incoming-posts")
            assert response.status_code == 200
            probe.verify_inbox(response.json(), manifest, completed=True)
    finally:
        engine.dispose()


def test_probe_concurrent_source_interleavings_preserve_history_and_refuse_reseed(tmp_path):
    probe = load_probe()
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent.db'}")
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    try:
        probe.concurrent_sources(sessions, now=datetime(2030, 1, 1, tzinfo=UTC))
        with pytest.raises(RuntimeError, match="refusing"):
            probe.concurrent_sources(sessions, now=datetime(2030, 1, 1, tzinfo=UTC))
        with sessions() as session:
            assert session.scalar(select(models.RewriteJobModel)) is None
            assert session.scalar(select(models.RewriteUsageModel)) is None
            assert len(session.scalars(select(models.ContentRevisionModel)).all()) == 3
    finally:
        engine.dispose()
