from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_configured_text_publication import ReceiptClient, setup
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store

from newsflow import worker
from newsflow.persistence import models
from newsflow.services.telegram_publication_factory import ConfiguredTelegramPublisher

source_store = _source_store
KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class OneIteration:
    def __init__(self):
        self.stopped = False

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, seconds):
        self.stopped = True


def isolated_loop(store, monkeypatch):
    monkeypatch.setattr(worker, "configured_session_factory", lambda: store[0])
    monkeypatch.setattr(worker, "Event", OneIteration)
    monkeypatch.setattr(worker.signal, "signal", lambda *_: None)
    monkeypatch.setattr(worker, "datetime", SimpleNamespace(now=lambda _: NOW))
    for name in (
        "NEWSFLOW_REWRITE_ENABLED",
        "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
        "NEWSFLOW_INTERNET_MEDIA_ENABLED",
        "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
        "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
        "NEWSFLOW_SOURCE_PHOTO_ENABLED",
    ):
        monkeypatch.setenv(name, "0")
    monkeypatch.setenv("NEWSFLOW_REWRITE_PROVIDER", "OPENAI")
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(store[1]))


def test_main_loop_explicit_publication_flag_processes_due_job_with_fake_network(
    source_store, monkeypatch, tmp_path
):
    client = setup(source_store, ReceiptClient())
    client.factory = source_store[0]
    isolated_loop(source_store, monkeypatch)
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "1")
    credentials = tmp_path / "synthetic-credentials.json"
    credentials.write_text('{"api_id":123,"api_hash":"' + "a" * 32 + '"}', encoding="utf-8")
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setattr(worker, "load_runtime_master_key", lambda: KEY)
    # Replace only external client construction, not tick/preflight/DB/transport.
    monkeypatch.setattr(
        worker,
        "ConfiguredTelegramPublisher",
        lambda *args, **kwargs: ConfiguredTelegramPublisher(
            *args, **kwargs, client_factory=lambda _: client
        ),
    )
    worker.main()
    with source_store[0]() as session:
        job = session.scalar(select(models.PublicationJobModel))
        assert job is not None and job.state == "SUCCEEDED" and job.sent_message_id == 501
    assert len(client.requests) == 1


def test_main_loop_missing_flag_is_inert_without_loading_key(source_store, monkeypatch):
    setup(source_store)
    isolated_loop(source_store, monkeypatch)
    monkeypatch.delenv("NEWSFLOW_PUBLICATION_ENABLED", raising=False)

    def forbidden():
        raise AssertionError("Default-disabled publication cannot load secrets")

    monkeypatch.setattr(worker, "load_runtime_master_key", forbidden)
    worker.main()
    with source_store[0]() as session:
        assert session.scalar(select(models.PublicationJobModel)) is None


def test_invalid_publication_flag_fails_closed(source_store, monkeypatch):
    isolated_loop(source_store, monkeypatch)
    monkeypatch.setenv("NEWSFLOW_PUBLICATION_ENABLED", "true")
    with pytest.raises(ValueError, match="NEWSFLOW_PUBLICATION_ENABLED"):
        worker.main()
