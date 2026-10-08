import pytest
from sqlalchemy import select
from test_channel_baseline import healthy
from test_channel_sync_tick import Provider
from test_donor_ingestion_runner import donor_store as _donor_store
from test_publication_main_loop import KEY, isolated_loop

from newsflow import worker
from newsflow.persistence import models
from newsflow.services.channel_sync_enforcement import sync_enforced

donor_store = _donor_store


def test_invalid_sync_flag_fails_before_key_or_network(donor_store, monkeypatch, tmp_path):
    isolated_loop((donor_store, tmp_path), monkeypatch)
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED", "true")
    with pytest.raises(ValueError, match="NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED"):
        worker.main()


def test_sync_optin_requires_ingestion_optin(donor_store, monkeypatch, tmp_path):
    isolated_loop((donor_store, tmp_path), monkeypatch)
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED", "1")
    with pytest.raises(ValueError, match="INGESTION"):
        worker.main()


def test_main_loop_sync_enforces_then_reads_before_scheduler_without_legacy_poll(
    donor_store, monkeypatch, tmp_path
):
    from newsflow.services import channel_sync_tick

    healthy(donor_store)
    isolated_loop((donor_store, tmp_path), monkeypatch)
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_INGESTION_ENABLED", "1")
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED", "1")
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "0")
    credentials = tmp_path / "synthetic-credentials.json"
    credentials.write_text('{"api_id":123,"api_hash":"' + "a" * 32 + '"}', encoding="utf-8")
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setattr(worker, "load_runtime_master_key", lambda: KEY)
    provider = Provider()
    monkeypatch.setattr(worker, "ConfiguredTelegramProvider", lambda *_, **__: provider)
    monkeypatch.setattr(channel_sync_tick, "ConfiguredTelegramProvider", lambda *_, **__: provider)
    scheduler = worker.run_scheduler_tick

    def observed_scheduler(*args, **kwargs):
        assert provider.calls == ["checkpoint", "difference", "history"]
        with donor_store() as session:
            assert sync_enforced(session)
            assert session.get(models.ChannelDifferenceCursorModel, 1).pts == 11
        return scheduler(*args, **kwargs)

    monkeypatch.setattr(worker, "run_scheduler_tick", observed_scheduler)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Sync mode fell back to legacy history tick")

    monkeypatch.setattr(worker, "run_ingestion_tick", forbidden)
    worker.main()
    with donor_store() as session:
        assert session.scalar(select(models.EditorialDecisionModel)).status == "MANUAL_REVIEW"
        assert session.scalar(select(models.RewriteJobModel)) is None
        assert session.scalar(select(models.PublicationJobModel)) is None


def test_missing_sync_flag_is_inert_without_enforcement_or_key(donor_store, monkeypatch, tmp_path):
    isolated_loop((donor_store, tmp_path), monkeypatch)
    monkeypatch.delenv("NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED", raising=False)
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "0")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Default-disabled sync reached network or secrets")

    monkeypatch.setattr(worker, "load_runtime_master_key", forbidden)
    monkeypatch.setattr(worker, "run_channel_sync_tick", forbidden)
    worker.main()
    with donor_store() as session:
        assert not sync_enforced(session)


def test_sync_execution_failure_skips_downstream_and_never_logs_exception_secret(
    donor_store, monkeypatch, tmp_path, capsys
):
    isolated_loop((donor_store, tmp_path), monkeypatch)
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_INGESTION_ENABLED", "1")
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED", "1")
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "0")
    credentials = tmp_path / "synthetic-credentials.json"
    credentials.write_text('{"api_id":123,"api_hash":"' + "a" * 32 + '"}', encoding="utf-8")
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setattr(worker, "load_runtime_master_key", lambda: KEY)
    monkeypatch.setattr(worker, "run_donor_resolution_tick", lambda *_, **__: ())

    def fail(*_args, **_kwargs):
        raise ConnectionError("synthetic-secret-do-not-log")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Failed sync reached downstream actions")

    monkeypatch.setattr(worker, "run_channel_sync_tick", fail)
    monkeypatch.setattr(worker, "run_scheduler_tick", forbidden)
    monkeypatch.setattr(worker, "run_rewrite_tick", forbidden)
    monkeypatch.setattr(worker, "run_publication_tick", forbidden)
    worker.main()
    assert "synthetic-secret-do-not-log" not in capsys.readouterr().out
    with donor_store() as session:
        assert sync_enforced(session)
