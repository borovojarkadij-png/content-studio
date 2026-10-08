from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_durable_rewrite_runner import NOW, SafeSyntheticProvider
from test_durable_rewrite_runner import rewrite_store as _rewrite_store
from test_source_photo_acquisition import source_store as _source_store

from newsflow.app import app
from newsflow.persistence import models
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

rewrite_store = _rewrite_store
source_store = _source_store


def read(factory):
    from newsflow.services.studio_overview import StudioOverviewReader

    with factory() as session:
        result = StudioOverviewReader(session).read(now=NOW)
        assert not session.new and not session.dirty
        return result


def test_overview_uses_durable_history_and_unknown_usage_is_not_a_zero_invoice(rewrite_store):
    with rewrite_store.begin() as session:
        jobs = session.scalars(
            select(models.RewriteJobModel).order_by(models.RewriteJobModel.id)
        ).all()
        jobs[0].attempts, jobs[1].attempts = 2, 1
        jobs[1].state = "BLOCKED_EDITORIAL"
        session.add_all(
            [
                models.RewriteUsageModel(
                    rewrite_job_id=jobs[0].id,
                    attempt=1,
                    provider="OPENAI",
                    model="private-model-metadata",
                    style="NEUTRAL",
                    input_tokens=100,
                    cached_tokens=40,
                    output_tokens=20,
                    estimated_cost_usd=Decimal("0.0001234567"),
                ),
                models.RewriteUsageModel(
                    rewrite_job_id=jobs[0].id,
                    attempt=2,
                    provider="OPENAI",
                    model="private-model-metadata",
                    style="TABLOID",
                    input_tokens=60,
                    cached_tokens=0,
                    output_tokens=10,
                    estimated_cost_usd=None,
                ),
            ]
        )
    result = read(rewrite_store)
    assert result["scope"] == "ALL_RETAINED_HISTORY"
    assert result["network_checked"] is False and result["billing_complete"] is False
    assert result["configuration"] == {
        "accounts": 1,
        "donors": 1,
        "output_channels": 2,
        "mappings": 2,
    }
    assert result["history"] == {
        "source_posts": 1,
        "source_revisions": 1,
        "rewrite_jobs": 2,
        "active_rewrite_jobs": 1,
        "acknowledged_publications": 0,
        "uncertain_publications": 0,
    }
    assert result["usage"][0] == {
        "operation": "REWRITE",
        "records": 2,
        "input_tokens": 160,
        "cached_tokens": 40,
        "output_tokens": 30,
        "known_estimated_cost_usd": "0.0001234567",
        "unknown_cost_records": 1,
        "durable_attempts": 3,
        "unobserved_attempts": 1,
    }
    assert "private-model-metadata" not in str(result)
    assert "source_text" not in str(result) and "encrypted_session" not in str(result)


def test_unobserved_crash_budget_is_not_fabricated_as_measured_provider_calls(rewrite_store):
    runner = DurableRewriteRunner(
        rewrite_store, provider_for_channel=lambda _: SafeSyntheticProvider()
    )
    assert runner.claim_next(now=NOW) is not None
    abandoned = read(rewrite_store)
    assert abandoned["usage"][0]["durable_attempts"] == 1
    assert abandoned["usage"][0]["unobserved_attempts"] == 1
    assert abandoned["usage"][0]["records"] == 0
    # Expired abandoned work still counts as pending, not success or zero cost proof.
    assert runner.run_next(now=NOW + timedelta(seconds=61)) == "SUCCEEDED"
    result = read(rewrite_store)
    assert result["history"]["rewrite_jobs"] == 2
    assert result["history"]["active_rewrite_jobs"] == 1
    assert result["usage"][0]["records"] == 0
    assert result["billing_complete"] is False


def test_semantic_usage_and_missing_observations_are_reported_separately(semantic_store):
    from test_semantic_approval import SyntheticVerifier

    from newsflow.providers.openai_rewrite import RewriteUsage
    from newsflow.services.durable_semantic_runner import DurableSemanticRunner

    provider = SyntheticVerifier()
    provider.last_usage = RewriteUsage("synthetic-model", 12, 3, 4, None)
    runner = DurableSemanticRunner(
        semantic_store, verifier_for_release=lambda _: provider, clock=lambda: NOW
    )
    assert runner.enqueue_pending(now=NOW) == 2
    assert runner.run_next(now=NOW) == "SUCCEEDED"
    assert runner.claim_next(now=NOW) is not None
    result = read(semantic_store)
    assert result["usage"][1] == {
        "operation": "SEMANTIC_VERIFICATION",
        "records": 1,
        "input_tokens": 12,
        "cached_tokens": 3,
        "output_tokens": 4,
        "known_estimated_cost_usd": "0.0000000000",
        "unknown_cost_records": 1,
        "durable_attempts": 2,
        "unobserved_attempts": 1,
    }


def test_overview_http_is_read_only_no_store_and_storage_errors_are_redacted(
    rewrite_store, tmp_path, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", str(rewrite_store.kw["bind"].url))
    with TestClient(app) as client:
        response = client.get("/api/studio/overview")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json()["configuration"]["donors"] == 1
        assert client.post("/api/studio/overview", json={}).status_code == 405
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'missing-tables.db'}")
    with TestClient(app) as client:
        response = client.get("/api/studio/overview")
        assert response.status_code == 503
        assert "SELECT" not in response.text and "missing-tables.db" not in response.text


def test_acknowledged_and_uncertain_history_are_never_confused(source_store):
    from test_publication_preflight import seed_plan
    from test_publication_runner import NOW as publication_now
    from test_publication_runner import Publisher, runner

    seed_plan(source_store)
    publisher = Publisher(failure=TimeoutError("synthetic uncertain remote outcome"))
    execution = runner(source_store, publisher)
    execution.enqueue(1, now=publication_now)
    assert execution.run_next(now=publication_now) == "NEEDS_RECONCILIATION"
    uncertain = read(source_store[0])
    assert uncertain["history"]["uncertain_publications"] == 1
    assert uncertain["history"]["acknowledged_publications"] == 0
    # Record only a synthetic acknowledgement to exercise the read model, no retry/send.
    with source_store[0].begin() as session:
        job = session.scalar(select(models.PublicationJobModel))
        job.state = "SUCCEEDED"
        job.sent_message_id = 101
        job.completed_at = publication_now
    acknowledged = read(source_store[0])
    assert acknowledged["history"]["uncertain_publications"] == 0
    assert acknowledged["history"]["acknowledged_publications"] == 1
    assert acknowledged["network_checked"] is False
