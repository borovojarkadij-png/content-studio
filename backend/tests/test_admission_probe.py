import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence import models

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def probe_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "docker_admission_probe.py"
    spec = importlib.util.spec_from_file_location("admission_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_admission_probe_reopens_original_sql_and_queues_only_three_late_rows(tmp_path):
    probe = probe_module()
    url = f"sqlite:///{tmp_path / 'admission.db'}"
    engine = create_engine(url)
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    manifest = probe.seed(factory, tmp_path, now=NOW)
    probe.verify(factory, manifest, admitted=False)
    engine.dispose()
    reopened = create_engine(url)
    try:
        sessions = sessionmaker(reopened)
        probe.verify(sessions, manifest, admitted=False)
        with pytest.raises(RuntimeError, match="refusing"):
            probe.seed(sessions, tmp_path, now=NOW)
        queued = probe.admit(sessions, tmp_path, manifest, now=NOW)
        assert len(queued) == 3
        probe.verify(sessions, manifest, admitted=True, job_ids=queued)
        assert probe.admit(sessions, tmp_path, manifest, now=NOW) == queued
        probe.verify(sessions, manifest, admitted=True, job_ids=queued)
        with sessions() as session:
            assert session.scalar(select(models.SemanticVerificationUsageModel)) is None
            assert session.scalar(select(models.RewriteUsageModel)) is None
            assert session.scalar(select(models.PublicationJobModel)) is None
    finally:
        reopened.dispose()


@pytest.mark.parametrize("invalid", ["version", "foreign_job", "spent_attempt", "boolean_job"])
def test_admission_probe_refuses_corrupt_history_without_reseeding(tmp_path, invalid):
    probe = probe_module()
    engine = create_engine(f"sqlite:///{tmp_path / 'admission.db'}")
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    try:
        manifest = probe.seed(sessions, tmp_path, now=NOW)
        jobs = probe.admit(sessions, tmp_path, manifest, now=NOW)
        if invalid == "version":
            with pytest.raises(RuntimeError):
                probe.verify(sessions, {**manifest, "version": 0}, admitted=True, job_ids=jobs)
        elif invalid == "foreign_job":
            with pytest.raises(AssertionError):
                probe.verify(sessions, manifest, admitted=True, job_ids=(jobs[0] + 999, *jobs[1:]))
        elif invalid == "boolean_job":
            with pytest.raises(RuntimeError):
                probe.verify(sessions, manifest, admitted=True, job_ids=(True, *jobs[1:]))
        else:
            with sessions.begin() as session:
                session.get(models.SemanticVerificationJobModel, jobs[0]).attempts = 1
            with pytest.raises(AssertionError):
                probe.verify(sessions, manifest, admitted=True, job_ids=jobs)
    finally:
        engine.dispose()


@pytest.mark.parametrize("invalid", ["database", "dialect", "optin", "network", "key", "mode"])
def test_admission_cli_refuses_unsafe_target_before_database(monkeypatch, invalid):
    probe = probe_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/newsflow_verification")
    monkeypatch.setenv("NEWSFLOW_VERIFICATION_PROBE", "1")
    for flag in probe.NETWORK_FLAGS:
        monkeypatch.setenv(flag, "0")
    monkeypatch.setattr(probe, "load_runtime_master_key", lambda: probe.KEY)

    def forbidden(*_, **__):
        raise AssertionError("Unsafe admission probe connected to database")

    monkeypatch.setattr(probe, "create_engine", forbidden)
    if invalid == "database":
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/newsflow")
    elif invalid == "dialect":
        monkeypatch.setenv("DATABASE_URL", "sqlite:///newsflow_verification")
    elif invalid == "optin":
        monkeypatch.delenv("NEWSFLOW_VERIFICATION_PROBE")
    elif invalid == "network":
        monkeypatch.setenv("NEWSFLOW_SOURCE_PHOTO_ENABLED", "1")
    elif invalid == "key":
        monkeypatch.setattr(probe, "load_runtime_master_key", lambda: "not-the-public-fixture-key")
    with pytest.raises((ValueError, RuntimeError)):
        probe.main("invalid" if invalid == "mode" else "seed")
