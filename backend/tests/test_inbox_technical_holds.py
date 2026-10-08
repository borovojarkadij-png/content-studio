"""Read-only diagnostics must explain holds without rewriting editorial history."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, null, select
from sqlalchemy.orm import Session
from test_mapping_fanout_dedup import mapping_store as _mapping_store

from newsflow.app import app
from newsflow.persistence import models
from newsflow.services.moderation_inbox import ModerationInboxReader

mapping_store = _mapping_store


@pytest.mark.parametrize("status", ["PASS", "REJECT", None])
@pytest.mark.parametrize(
    "media,caption,links,album,protected,want",
    [
        ("text", "Safe source", [], None, False, []),
        ("video", "Video source", [], None, False, ["VIDEO_MANUAL_REVIEW_REQUIRED"]),
        ("text", "See https://youtu.be/abc", [], None, False, ["YOUTUBE_LINK"]),
        (
            "photo",
            "Hidden source",
            ["https://youtube.com/watch?v=abc"],
            None,
            False,
            ["YOUTUBE_LINK"],
        ),
        ("text", "Legacy source", None, None, False, ["SOURCE_LINKS_UNKNOWN"]),
        (
            "text",
            "Corrupt source",
            {"private": "must-not-leak"},
            None,
            False,
            ["SOURCE_LINKS_INVALID"],
        ),
        ("text", "Malformed https://[invalid", [], None, False, ["INVALID_LINK"]),
        (
            "photo",
            "Sparse album",
            [],
            "99",
            True,
            ["ALBUM_NORMALIZATION_REQUIRED", "PROTECTED_CONTENT"],
        ),
        (
            "video",
            "Combined source",
            ["https://youtu.be/abc"],
            None,
            False,
            ["VIDEO_MANUAL_REVIEW_REQUIRED", "YOUTUBE_LINK"],
        ),
    ],
)
def test_current_http_holds_preserve_editorial_and_have_no_processing_side_effect(
    mapping_store, status, media, caption, links, album, protected, want
):
    engine = create_engine(mapping_store[0])
    key = "1:-1001234567890:21:revision:1"
    with Session(engine) as session:
        post = models.IncomingPostModel(
            telegram_account_id="1",
            donor_channel_id="-1001234567890",
            telegram_message_id=21,
            state="MANUAL_REVIEW",
        )
        session.add(post)
        session.flush()
        session.add(
            models.ContentRevisionModel(
                incoming_post_id=post.id,
                revision_number=1,
                source_text=caption,
                media_type=media,
                link_destinations=null() if links is None else links,
                album_id=album,
                media_protected=protected,
            )
        )
        if status is not None:
            session.add(
                models.EditorialDecisionModel(
                    content_key=key,
                    status=status,
                    rewrite_allowed=status == "PASS",
                    sentiment="neutral",
                    framing="neutral",
                    reason_codes="ORIGINAL_REASON",
                )
            )
        session.commit()
    with TestClient(app) as client:
        for _ in range(2):
            response = client.get("/api/telegram/incoming-posts")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            item = response.json()["items"][0]
            assert item["technical_reason_codes"] == want
            assert item["editorial_status"] == status
            assert item["editorial_reason_codes"] == (["ORIGINAL_REASON"] if status else [])
            assert item["source_text"] == caption
            assert item["rewrite_allowed"] == (
                False if want or status == "REJECT" else True if status else None
            )
            assert "must-not-leak" not in response.text
            assert "link_destinations" not in item
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(models.RewriteJobModel)) == 0
        assert session.scalar(select(func.count()).select_from(models.PublicationJobModel)) == 0
        assert session.scalar(select(func.count()).select_from(models.OutboxEventModel)) == 0
        decision = session.scalar(select(models.EditorialDecisionModel))
        assert decision is None if status is None else decision.status == status
        assert session.scalar(select(models.IncomingPostModel)).state == "MANUAL_REVIEW"
    engine.dispose()


def test_same_reader_refreshes_external_link_hold_without_touching_historical_jobs(mapping_store):
    engine = create_engine(mapping_store[0])
    with Session(engine) as session:
        post = models.IncomingPostModel(
            telegram_account_id="1",
            donor_channel_id="-1001234567890",
            telegram_message_id=21,
            state="REWRITE_QUEUED",
        )
        session.add(post)
        session.flush()
        revision = models.ContentRevisionModel(
            incoming_post_id=post.id,
            revision_number=1,
            source_text="Retained source",
            media_type="text",
            link_destinations=[],
        )
        decision = models.EditorialDecisionModel(
            content_key="1:-1001234567890:21:revision:1",
            status="PASS",
            rewrite_allowed=True,
            sentiment="neutral",
            framing="neutral",
        )
        job = models.RewriteJobModel(
            content_key=decision.content_key,
            idempotency_key="historical-hold-job",
            state="SUPERSEDED",
        )
        session.add_all([revision, decision, job])
        session.commit()
        reader = ModerationInboxReader(session)
        assert reader.list_items()[0].rewrite_allowed is True
        with Session(engine) as writer:
            writer.get(models.ContentRevisionModel, revision.id).link_destinations = [
                "https://youtu.be/new"
            ]
            writer.commit()
        item = reader.list_items()[0].as_dict()
        assert item["technical_reason_codes"] == ["YOUTUBE_LINK"]
        assert item["rewrite_allowed"] is False and item["editorial_status"] == "PASS"
        assert job.state == "SUPERSEDED" and decision.rewrite_allowed is True
        assert not session.new and not session.dirty and not session.deleted
    engine.dispose()


@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_diagnostic_read_refuses_pending_caller_work_without_flush_or_overwrite(
    mapping_store, pending
):
    engine = create_engine(mapping_store[0])
    with Session(engine) as session:
        post = models.IncomingPostModel(
            telegram_account_id="1",
            donor_channel_id="-1001234567890",
            telegram_message_id=21,
            state="RECEIVED",
        )
        session.add(post)
        session.commit()
        if pending == "new":
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post.id,
                    revision_number=1,
                    source_text="Caller pending source",
                )
            )
        elif pending == "dirty":
            post.state = "MANUAL_REVIEW"
        else:
            session.delete(post)
        with pytest.raises(ValueError, match="clean session"):
            ModerationInboxReader(session).list_items()
        assert getattr(session, pending)
        with Session(engine) as reader:
            assert reader.scalar(select(models.IncomingPostModel)).state == "RECEIVED"
            assert reader.scalar(select(func.count()).select_from(models.ContentRevisionModel)) == 0
    engine.dispose()
