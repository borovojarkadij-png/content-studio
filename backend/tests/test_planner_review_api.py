"""Review/planner HTTP contracts use isolated durable state, never live providers."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from newsflow.app import app
from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutboxEventModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.services.rewrite_outputs import RewriteOutputService


@pytest.fixture
def review_store(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'review.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", url)
    with Session(engine) as session:
        account = TelegramAccount(name="Synthetic", telegram_user_id=1001, encrypted_session="")
        session.add(account)
        session.flush()
        channel = OutputChannel(
            telegram_account_id=account.id,
            telegram_channel_id=-1001234567890,
            title="Тестовый канал",
        )
        session.add(channel)
        session.flush()
        decision = EditorialDecisionModel(
            content_key="synthetic:revision:1",
            status="PASS",
            rewrite_allowed=True,
            sentiment="neutral",
            framing="neutral",
        )
        job = RewriteJobModel(
            content_key=decision.content_key,
            output_channel_id=channel.id,
            idempotency_key="synthetic-rewrite-1",
            state="SUCCEEDED",
        )
        candidate = PublicationCandidateModel(
            output_channel_id=channel.id,
            content_key=decision.content_key,
            priority=10,
            state="AWAITING_REWRITE",
        )
        session.add_all([decision, job, candidate])
        session.commit()
        channel_id, job_id = channel.id, job.id
        draft = RewriteOutputService(session).record_succeeded_output(
            job_id, "Синтетический рерайт"
        )
    with TestClient(app) as client:
        yield client, engine, channel_id, job_id, draft["id"]
    engine.dispose()


def test_review_approval_atomically_activates_only_its_candidate_and_is_idempotent(review_store):
    client, engine, channel_id, _, draft_id = review_store
    listing = client.get(f"/api/telegram/rewrite-outputs?output_channel_id={channel_id}")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["approve_allowed"] is True
    approved = client.post(f"/api/telegram/rewrite-outputs/{draft_id}:approve", json={})
    assert approved.status_code == 200
    assert approved.json()["approval_state"] == "APPROVED"
    assert (
        client.post(f"/api/telegram/rewrite-outputs/{draft_id}:approve", json={}).json()
        == approved.json()
    )
    with Session(engine) as session:
        assert session.scalar(select(PublicationCandidateModel.state)) == "READY"
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


@pytest.mark.parametrize("failure", ["editorial_reject", "superseded_job", "mismatched_output"])
def test_stale_or_mismatched_review_cannot_activate_or_schedule(review_store, failure):
    client, engine, channel_id, job_id, draft_id = review_store
    with Session(engine) as session:
        if failure == "editorial_reject":
            decision = session.scalar(select(EditorialDecisionModel))
            decision.status, decision.rewrite_allowed = "REJECT", False
        else:
            job = session.get(RewriteJobModel, job_id)
            if failure == "superseded_job":
                job.state = "SUPERSEDED"
            else:
                job.output_channel_id = None
        session.commit()
    row = client.get("/api/telegram/rewrite-outputs").json()["items"][0]
    assert row["approve_allowed"] is False
    assert (
        client.post(f"/api/telegram/rewrite-outputs/{draft_id}:approve", json={}).status_code == 409
    )
    plan = client.put(
        f"/api/telegram/output-channels/{channel_id}/publication-plan",
        json={
            "mode": "AUTOMATIC",
            "daily_limit": 1,
            "slot_minutes": [540],
            "timezone": "UTC",
        },
    ).json()
    assert client.post(
        f"/api/telegram/publication-plans/{plan['id']}:plan-day", json={"day": "2030-01-02"}
    ).json() == {"items": []}
    with Session(engine) as session:
        assert session.scalar(select(PublicationCandidateModel.state)) == "AWAITING_REWRITE"
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 1
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


def test_review_reject_is_terminal_and_cannot_be_overridden_by_extra_payload(review_store):
    client, engine, _, _, draft_id = review_store
    assert (
        client.post(
            f"/api/telegram/rewrite-outputs/{draft_id}:approve", json={"rewrite_allowed": True}
        ).status_code
        == 422
    )
    rejected = client.post(f"/api/telegram/rewrite-outputs/{draft_id}:reject", json={})
    assert rejected.status_code == 200
    assert rejected.json()["approval_state"] == "REJECTED"
    assert (
        client.post(f"/api/telegram/rewrite-outputs/{draft_id}:approve", json={}).status_code == 409
    )
    with Session(engine) as session:
        assert session.scalar(select(PublicationCandidateModel.state)) == "REJECTED_REVIEW"


def test_plan_reads_survive_new_client_and_do_not_plan_on_get(review_store):
    client, engine, channel_id, _, draft_id = review_store
    client.post(f"/api/telegram/rewrite-outputs/{draft_id}:approve", json={})
    plan = client.put(
        f"/api/telegram/output-channels/{channel_id}/publication-plan",
        json={
            "mode": "AUTOMATIC",
            "daily_limit": 1,
            "slot_minutes": [540],
            "timezone": "Europe/Minsk",
        },
    ).json()
    assert client.get("/api/telegram/publication-plans").json() == {"items": [plan]}
    path = f"/api/telegram/publication-plans/{plan['id']}/publications?day=2030-01-02"
    assert client.get(path).json() == {"items": []}
    planned = client.post(
        f"/api/telegram/publication-plans/{plan['id']}:plan-day", json={"day": "2030-01-02"}
    )
    assert planned.status_code == 200
    assert planned.json()["items"][0]["scheduled_for"] == "2030-01-02T06:00:00+00:00"
    with TestClient(app) as restarted:
        rows = restarted.get(path).json()["items"]
        assert rows[0]["content_key"] == "synthetic:revision:1"
        assert rows[0]["state"] == "PLANNED"
        assert rows[0]["editorial_allowed"] is True
    with Session(engine) as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    # GET projects stale safety state without mutating durable reservations.
    assert client.get(path).json()["items"][0]["editorial_allowed"] is False
    assert client.get(path).json()["items"][0]["state"] == "PLANNED"
    assert client.get(path.replace("2030-01-02", "2030-01-03")).json() == {"items": []}


def test_review_and_planner_missing_state_fails_honestly(review_store, monkeypatch):
    client, _, _, _, _ = review_store
    assert client.post("/api/telegram/rewrite-outputs/999:approve", json={}).status_code == 404
    assert (
        client.get("/api/telegram/publication-plans/999/publications?day=2030-01-02").status_code
        == 404
    )
    monkeypatch.delenv("DATABASE_URL")
    for path in ("rewrite-outputs", "publication-plans"):
        assert client.get(f"/api/telegram/{path}").status_code == 503


def test_media_http_registry_and_selection_use_persistent_root_without_remote_download(
    review_store, tmp_path, monkeypatch
):
    client, engine, _, _, draft_id = review_store
    root = tmp_path / "persistent-media"
    root.mkdir()
    (root / "source.png").write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-api-photo")
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(root))
    payload = {
        "storage_key": "source.png",
        "origin": "SOURCE",
        "license_code": "PERMISSION",
        "attribution": "@authorized_synthetic",
        "source_content_key": "synthetic:revision:1",
        "tags": ["science"],
    }
    registered = client.post("/api/telegram/media-assets", json=payload)
    assert registered.status_code == 201
    assert str(root) not in registered.text
    with TestClient(app) as restarted:
        assert (
            restarted.post("/api/telegram/media-assets", json=payload).json() == registered.json()
        )
    client.post(f"/api/telegram/rewrite-outputs/{draft_id}:approve", json={})
    with Session(engine) as session:
        candidate_id = session.scalar(select(PublicationCandidateModel.id))
    path = f"/api/telegram/publication-candidates/{candidate_id}/media-selection"
    selected = client.get(path)
    assert selected.status_code == 200
    assert selected.json()["items"][0]["storage_key"] == "source.png"
    with Session(engine) as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    assert client.get(path).status_code == 409
    monkeypatch.delenv("NEWSFLOW_MEDIA_ROOT")
    assert client.get(path).status_code == 503
