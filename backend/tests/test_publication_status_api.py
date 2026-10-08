from fastapi.testclient import TestClient
from sqlalchemy import select
from test_publication_preflight import seed_plan
from test_publication_runner import Publisher, runner
from test_source_photo_acquisition import NOW
from test_source_photo_acquisition import source_store as _source_store

from newsflow.app import app
from newsflow.persistence import models

source_store = _source_store


def test_delivery_status_is_read_only_not_queued_and_has_no_secret_fields(
    source_store, monkeypatch
):
    seed_plan(source_store)
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    with TestClient(app) as client:
        response = client.get("/api/telegram/planned-publications/1/delivery-status")
        assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "planned_id": 1,
            "candidate_id": 1,
            "output_channel_id": 1,
            "job_id": None,
            "state": "NOT_QUEUED",
            "attempts": 0,
            "sent_message_id": None,
            "completed_at": None,
            "reason_code": None,
            "live_publication_available": False,
        }
        assert (
            client.post("/api/telegram/planned-publications/1/delivery-status").status_code == 405
        )
        assert (
            client.get("/api/telegram/planned-publications/999/delivery-status").status_code == 404
        )
    with source_store[0]() as session:
        assert session.scalar(select(models.PublicationJobModel)) is None


def test_read_api_does_not_retry_unknown_outcome_or_hide_it_after_editorial_reject(
    source_store, monkeypatch
):
    seed_plan(source_store)
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    sender = Publisher(failure=TimeoutError("synthetic lost response"))
    execution = runner(source_store, sender)
    job_id = execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "NEEDS_RECONCILIATION"
    with source_store[0].begin() as session:
        decision = session.scalar(select(models.EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get("/api/telegram/planned-publications/1/delivery-status")
            assert response.status_code == 200
            status = response.json()
            assert status["state"] == "NEEDS_RECONCILIATION" and status["job_id"] == job_id
            assert status["sent_message_id"] is None and status["completed_at"] is None
            assert status["reason_code"] == "PUBLICATION_SEND_OUTCOME_UNKNOWN"
            assert (
                not {"request_nonce", "claim_token", "binding_sha256", "encrypted_session"}
                & status.keys()
            )
    assert len(sender.calls) == 1


def test_read_api_only_shows_confirmed_message_after_persisted_receipt(source_store, monkeypatch):
    seed_plan(source_store)
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    execution = runner(source_store, Publisher())
    execution.enqueue(1, now=NOW)
    assert execution.run_next(now=NOW) == "SUCCEEDED"
    with TestClient(app) as client:
        status = client.get("/api/telegram/planned-publications/1/delivery-status").json()
        assert status["state"] == "SUCCEEDED" and status["sent_message_id"] == 101
        assert status["completed_at"] == "2026-10-08T00:00:00+00:00"


def test_untrusted_persisted_error_detail_is_not_returned_as_a_reason_code(
    source_store, monkeypatch
):
    seed_plan(source_store)
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    job_id = runner(source_store, None).enqueue(1, now=NOW)
    with source_store[0].begin() as session:
        session.get(
            models.PublicationJobModel, job_id
        ).last_error_code = "synthetic private error detail"
    with TestClient(app) as client:
        response = client.get("/api/telegram/planned-publications/1/delivery-status")
        assert response.status_code == 503
        assert "synthetic private error detail" not in response.text


def test_trusted_receipt_conflict_is_visible_without_exposing_evidence_or_allowing_send(
    source_store, monkeypatch
):
    seed_plan(source_store)
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    job_id = runner(source_store, None).enqueue(1, now=NOW)
    with source_store[0].begin() as session:
        job = session.get(models.PublicationJobModel, job_id)
        job.state, job.attempts, job.last_error_code = (
            "NEEDS_RECONCILIATION",
            1,
            "PUBLICATION_OBSERVATION_CONFLICT",
        )
    with TestClient(app) as client:
        response = client.get("/api/telegram/planned-publications/1/delivery-status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["reason_code"] == "PUBLICATION_OBSERVATION_CONFLICT"
        assert payload["sent_message_id"] is None and payload["live_publication_available"] is False
        assert not {"encrypted_receipt", "encrypted_envelope", "request_nonce"} & payload.keys()
        assert (
            client.post("/api/telegram/planned-publications/1/delivery-status").status_code == 405
        )
