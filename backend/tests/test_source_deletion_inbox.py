from fastapi.testclient import TestClient
from sqlalchemy import select
from test_source_deletion_guards import record
from test_source_photo_acquisition import CHANNEL, KEY
from test_source_photo_acquisition import source_store as _source_store

from newsflow.app import app
from newsflow.persistence import models
from newsflow.services.moderation_inbox import ModerationInboxReader

source_store = _source_store


def test_inbox_retains_deleted_original_and_historical_pass_but_no_rewrite_permission(source_store):
    with source_store[0]() as session:
        reader = ModerationInboxReader(session)
        assert reader.list_items()[0].rewrite_allowed is True
        record(source_store[0])
        item = reader.list_items()[0].as_dict()
        assert item["source_deleted"] is True
        assert item["state"] == "SOURCE_DELETED"
        assert item["editorial_status"] == "PASS" and item["rewrite_allowed"] is False
        assert item["source_text"] == "Photo caption" and item["editorial_reason_codes"] == []
        assert session.get(models.IncomingPostModel, 1).state == "RECEIVED"
        decision = session.scalar(
            select(models.EditorialDecisionModel).where(
                models.EditorialDecisionModel.content_key == KEY
            )
        )
        assert decision.status == "PASS" and decision.rewrite_allowed is True


def test_deleted_inbox_http_retains_source_identity_and_never_mutates_history(
    source_store, monkeypatch
):
    record(source_store[0])
    monkeypatch.setenv("DATABASE_URL", str(source_store[0].kw["bind"].url))
    with TestClient(app) as client:
        response = client.get("/api/telegram/incoming-posts")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["source_key"] == f"1:{CHANNEL}:20"
        assert item["source_deleted"] is True and item["rewrite_allowed"] is False
    with source_store[0]() as session:
        assert session.get(models.RewriteJobModel, 1).state == "SUCCEEDED"
        assert session.scalar(select(models.PublicationJobModel)) is None
