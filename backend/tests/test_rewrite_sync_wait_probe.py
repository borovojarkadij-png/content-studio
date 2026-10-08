import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence import models


def load_probe():
    path = Path(__file__).resolve().parents[2] / "scripts" / "docker_rewrite_sync_wait_probe.py"
    spec = importlib.util.spec_from_file_location("rewrite_sync_wait_probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    return probe


def test_wait_probe_retains_original_jobs_across_independent_reopen_and_guarded_recovery(tmp_path):
    probe = load_probe()
    now = datetime(2030, 1, 1, tzinfo=UTC)
    url = f"sqlite:///{tmp_path / 'wait.db'}"
    engine = create_engine(url)
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    manifest = probe.seed(sessions, tmp_path, now=now)
    probe.verify(sessions, manifest, completed=False)
    engine.dispose()
    reopened = create_engine(url)
    try:
        restored = sessionmaker(reopened)
        probe.verify(restored, manifest, completed=False)
        with pytest.raises(RuntimeError, match="refusing"):
            probe.seed(restored, tmp_path, now=now)
        probe.recover(restored, manifest, now=now + timedelta(seconds=35))
        probe.verify(restored, manifest, completed=True)
        probe.verify(restored, manifest, completed=True)
        with restored() as session:
            assert [session.get(models.RewriteJobModel, row).state for row in manifest["jobs"]] == [
                "SUCCEEDED",
                "BLOCKED_EDITORIAL",
                "SUPERSEDED",
                "FAILED",
            ]
            assert session.scalar(select(models.RewriteOutputModel)).approval_state == "PENDING"
    finally:
        reopened.dispose()


def test_wait_probe_refuses_early_retry_and_corrupt_manifest_without_changing_jobs(tmp_path):
    probe = load_probe()
    now = datetime(2030, 1, 1, tzinfo=UTC)
    engine = create_engine(f"sqlite:///{tmp_path / 'wait.db'}")
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    try:
        manifest = probe.seed(sessions, tmp_path, now=now)
        with pytest.raises(RuntimeError, match="version"):
            probe.verify(sessions, {**manifest, "version": 0}, completed=False)
        with pytest.raises(RuntimeError, match="due"):
            probe.recover(sessions, manifest, now=now)
        probe.verify(sessions, manifest, completed=False)
    finally:
        engine.dispose()


def test_wait_probe_verifies_real_api_pending_review_without_fake_publication(
    monkeypatch, tmp_path
):
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
            probe.verify_api(
                client.get("/api/telegram/incoming-posts").json(),
                client.get("/api/telegram/rewrite-outputs").json(),
                manifest,
                completed=False,
            )
            probe.recover(sessions, manifest, now=now + timedelta(seconds=35))
            probe.verify_api(
                client.get("/api/telegram/incoming-posts").json(),
                client.get("/api/telegram/rewrite-outputs").json(),
                manifest,
                completed=True,
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("invalid", ["database", "network", "key", "mode"])
def test_wait_probe_cli_rejects_unsafe_configuration_before_database(monkeypatch, invalid):
    probe = load_probe()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/newsflow_verification")
    monkeypatch.setenv("NEWSFLOW_VERIFICATION_PROBE", "1")
    for flag in (
        "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
        "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
        "NEWSFLOW_REWRITE_ENABLED",
        "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
        "NEWSFLOW_INTERNET_MEDIA_ENABLED",
        "NEWSFLOW_SOURCE_PHOTO_ENABLED",
        "NEWSFLOW_PUBLICATION_ENABLED",
    ):
        monkeypatch.setenv(flag, "0")
    monkeypatch.setattr(
        probe,
        "load_runtime_master_key",
        lambda: probe.KEY if invalid != "key" else "wrong-public-fixture-key",
    )

    def forbidden(_url):
        raise AssertionError("Unsafe fixture reached database connection")

    monkeypatch.setattr(probe, "create_engine", forbidden)
    if invalid == "database":
        monkeypatch.setenv("DATABASE_URL", "sqlite:///newsflow_verification")
    elif invalid == "network":
        monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "1")
    with pytest.raises((RuntimeError, ValueError)):
        probe.main("unsupported" if invalid == "mode" else "seed")
