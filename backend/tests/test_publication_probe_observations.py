import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence import models
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_publication_runner import (
    DurablePublicationRunner,
    PublicationReceipt,
)
from newsflow.services.publication_request_snapshot import PublicationRequestSnapshots


def test_create_only_probe_preserves_observed_ack_until_independent_recovery(tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts" / "docker_publication_probe.py"
    spec = importlib.util.spec_from_file_location("publication_probe", path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    url = f"sqlite:///{tmp_path / 'probe.db'}"
    engine = create_engine(url)
    models.Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

    class Network:
        def __init__(self):
            self.calls = []

        def publish(self, envelope, nonce, *, execution_guard):
            execution_guard()
            self.calls.append(nonce)
            return PublicationReceipt(envelope.account_id, envelope.telegram_channel_id, nonce, 901)

    publisher = Network()
    execution = DurablePublicationRunner(sessions, tmp_path, publisher=publisher, cipher=cipher)
    probe.seed(sessions, tmp_path, execution)
    manifest = json.loads(
        (tmp_path / "synthetic-publication-intents.json").read_text(encoding="utf-8")
    )
    assert manifest.get("version") == 2, "Probe must identify the observed-ack recovery contract"
    with sessions.begin() as session:
        for job_id in manifest["jobs"][:2]:
            session.get(models.PublicationJobModel, job_id).lease_expires_at = datetime.now(
                UTC
            ) - timedelta(seconds=1)
    probe.recover(sessions, execution, publisher, manifest)
    job_id = manifest["jobs"][0]
    snapshot = PublicationRequestSnapshots(sessions, cipher=cipher).read(job_id)
    with sessions() as session:
        assert session.get(models.PublicationJobModel, job_id).state == "SENDING"
        assert session.get(models.PublicationDeliveryObservationModel, job_id) is not None
        assert (
            session.get(models.PublicationJobModel, manifest["jobs"][1]).state
            == "NEEDS_RECONCILIATION"
        )
    assert len(publisher.calls) == 1
    engine.dispose()
    restored = create_engine(url)
    recovered_sessions = sessionmaker(restored)
    new_publisher = Network()
    restarted = DurablePublicationRunner(
        recovered_sessions, tmp_path, publisher=new_publisher, cipher=cipher
    )
    probe.verify_persisted(recovered_sessions, restarted, new_publisher, manifest, reconcile=True)
    with pytest.raises(RuntimeError, match="Legacy fixture"):
        probe.verify_persisted(
            recovered_sessions, restarted, new_publisher, {**manifest, "version": 1}, reconcile=True
        )
    with pytest.raises(RuntimeError, match="refusing to replace publication history"):
        probe.seed(recovered_sessions, tmp_path, restarted)
    probe.verify_persisted(recovered_sessions, restarted, new_publisher, manifest, reconcile=True)
    assert not new_publisher.calls
    assert PublicationRequestSnapshots(recovered_sessions, cipher=cipher).read(job_id) == snapshot
    with recovered_sessions() as session:
        assert (
            len(
                session.scalars(
                    select(models.OutboxEventModel).where(
                        models.OutboxEventModel.event_type == "publication.delivered"
                    )
                ).all()
            )
            == 1
        )
    restored.dispose()
