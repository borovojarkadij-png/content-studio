from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_semantic_approval import SyntheticVerifier
from test_semantic_runner import NOW, runner

from newsflow.app import app
from newsflow.persistence import models


def read(factory, output_id=1, now=NOW):
    from newsflow.services.semantic_job_read import SemanticJobReader

    with factory() as session:
        result = SemanticJobReader(session).read(output_id, now=now)
        assert not session.new and not session.dirty
        return result


def test_semantic_status_ready_snapshot_does_not_queue_classify_or_grant_permission(semantic_store):
    result = read(semantic_store)
    assert result == {
        "rewrite_output_id": 1,
        "output_channel_id": 1,
        "approval_state": "PENDING",
        "current_gate": "READY_SNAPSHOT",
        "reason_code": None,
        "network_checked": False,
        "execution_authorized": False,
        "worker_enabled": None,
        "policy_mode": "VERIFIED",
        "configured_release_id": 1,
        "qualified_release": True,
        "latest_job": None,
    }
    with semantic_store() as session:
        assert session.scalar(select(models.SemanticVerificationJobModel)) is None
        assert session.scalar(select(models.SemanticVerificationUsageModel)) is None
        assert session.scalar(select(models.RewriteUsageModel)) is None


def test_semantic_status_retains_job_budget_and_redacts_claims_errors_and_text(semantic_store):
    provider = SyntheticVerifier()
    execution = runner(semantic_store, provider)
    execution.enqueue_pending(now=NOW)
    claim = execution.claim_next(now=NOW)
    with semantic_store.begin() as session:
        session.get(
            models.SemanticVerificationJobModel, claim.job_id
        ).last_error_code = "secret-do-not-project"
    first = read(semantic_store)
    job = first["latest_job"]
    assert job == {
        "id": claim.job_id,
        "state": "RUNNING",
        "attempts": 1,
        "max_attempts": 2,
        "release_id": 1,
        "binding_current": True,
        "available_at": NOW.isoformat(),
        "lease_expires_at": (NOW + timedelta(seconds=60)).isoformat(),
        "lease_expired": False,
    }
    late = read(semantic_store, now=NOW + timedelta(seconds=61))
    assert late["latest_job"]["lease_expired"] is True
    assert late["latest_job"]["state"] == "RUNNING"  # Read is not recovery.
    assert claim.token not in str(first)
    assert "secret-do-not-project" not in str(first)
    assert "rewritten_text" not in str(first) and "source_sha256" not in str(first)
    assert provider.calls == []


@pytest.mark.parametrize(
    "change,gate,reason",
    [
        ("reject", "BLOCKED", "EDITORIAL_HARD_CONSTRAINT_BLOCKED"),
        ("manual", "MANUAL", "SEMANTIC_AUTOMATIC_POLICY_DISABLED"),
        ("revoked", "BLOCKED", "SEMANTIC_VERIFIER_NOT_QUALIFIED"),
        ("fact_changed", "BLOCKED", "FACT_PRESERVATION_BLOCKED"),
        ("reviewed", "NOT_PENDING", "SEMANTIC_DRAFT_NOT_PENDING_OR_MISMATCHED"),
        ("source_edit", "BLOCKED", "SOURCE_REVISION_NOT_CURRENT_OR_MISSING"),
    ],
)
def test_semantic_status_fresh_gate_does_not_hide_retained_queue_history(
    semantic_store, change, gate, reason
):
    execution = runner(semantic_store, SyntheticVerifier())
    execution.enqueue_pending(now=NOW)
    with semantic_store.begin() as session:
        if change == "reject":
            decision = session.scalar(select(models.EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
        elif change == "manual":
            session.get(models.AutomaticApprovalPolicyModel, 1).mode = "MANUAL"
        elif change == "revoked":
            session.get(models.SemanticVerifierReleaseModel, 1).active = False
        elif change == "fact_changed":
            session.get(models.RewriteOutputModel, 1).rewritten_text = "Открыты 7 линий."
        elif change == "reviewed":
            session.get(models.RewriteOutputModel, 1).approval_state = "REJECTED"
        else:
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=1, revision_number=2, source_text="New source"
                )
            )
    report = read(semantic_store)
    assert (report["current_gate"], report["reason_code"]) == (gate, reason)
    assert report["latest_job"]["state"] == "QUEUED"
    assert report["latest_job"]["attempts"] == 0
    assert report["latest_job"]["binding_current"] is (None if change == "reviewed" else False)
    assert report["execution_authorized"] is False and report["network_checked"] is False


def test_semantic_status_real_http_is_read_only_no_store_and_error_redacted(
    semantic_store, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", str(semantic_store.kw["bind"].url))
    with TestClient(app) as client:
        response = client.get("/api/telegram/rewrite-outputs/1/semantic-status")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json()["execution_authorized"] is False
        assert client.get("/api/telegram/rewrite-outputs/999/semantic-status").status_code == 404
        assert (
            client.post("/api/telegram/rewrite-outputs/1/semantic-status", json={}).status_code
            == 405
        )
        assert client.get("/api/telegram/rewrite-outputs/0/semantic-status").status_code == 422
    monkeypatch.delenv("DATABASE_URL")
    with TestClient(app) as client:
        assert client.get("/api/telegram/rewrite-outputs/1/semantic-status").status_code == 503


@pytest.mark.parametrize("output_id", [True, 0, -1, "1"])
def test_semantic_status_invalid_identity_refused_before_database(output_id):
    from newsflow.services.semantic_job_read import SemanticJobReader

    with pytest.raises(ValueError):
        SemanticJobReader(None).read(output_id, now=NOW)


def test_semantic_status_refreshes_cached_draft_decision_policy_release_and_job(semantic_store):
    from newsflow.services.semantic_job_read import SemanticJobReader

    execution = runner(semantic_store, SyntheticVerifier())
    execution.enqueue_pending(now=NOW)
    with semantic_store() as cached:
        reader = SemanticJobReader(cached)
        assert reader.read(1, now=NOW)["current_gate"] == "READY_SNAPSHOT"
        with semantic_store.begin() as writer:
            decision = writer.scalar(select(models.EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
            writer.get(models.AutomaticApprovalPolicyModel, 1).mode = "MANUAL"
            writer.get(models.SemanticVerifierReleaseModel, 1).active = False
            job = writer.scalar(select(models.SemanticVerificationJobModel))
            job.state, job.attempts = "FAILED", 2
        result = reader.read(1, now=NOW)
        assert result["reason_code"] == "EDITORIAL_HARD_CONSTRAINT_BLOCKED"
        assert result["policy_mode"] == "MANUAL" and not result["qualified_release"]
        assert (result["latest_job"]["state"], result["latest_job"]["attempts"]) == ("FAILED", 2)
        assert not cached.new and not cached.dirty
        with semantic_store.begin() as writer:
            writer.get(models.RewriteOutputModel, 1).approval_state = "REJECTED"
        assert reader.read(1, now=NOW)["approval_state"] == "REJECTED"


def test_semantic_status_preserves_terminal_job_and_changed_draft_without_reactivation(
    semantic_store,
):
    execution = runner(semantic_store, SyntheticVerifier())
    execution.enqueue_pending(now=NOW)
    with semantic_store.begin() as session:
        job = session.scalar(select(models.SemanticVerificationJobModel))
        job.state, job.attempts = "REVIEW", 2
        session.get(models.RewriteOutputModel, 1).rewritten_text = "Завод открыл 3 линии."
    report = read(semantic_store)
    assert report["current_gate"] == "READY_SNAPSHOT"
    assert report["latest_job"]["binding_current"] is False
    assert report["latest_job"]["state"] == "REVIEW"
    assert report["latest_job"]["attempts"] == 2
    with semantic_store() as session:
        assert session.scalar(select(models.SemanticEvidenceModel)) is None
        assert session.scalar(select(models.SemanticVerificationUsageModel)) is None
        assert session.get(models.RewriteOutputModel, 1).approval_state == "PENDING"


@pytest.mark.parametrize("now", [None, "2030-01-01", NOW.replace(tzinfo=None)])
def test_semantic_status_invalid_clock_refused_before_database(now):
    from newsflow.services.semantic_job_read import SemanticJobReader

    with pytest.raises(ValueError, match="Aware"):
        SemanticJobReader(None).read(1, now=now)
