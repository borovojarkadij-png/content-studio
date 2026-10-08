from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from newsflow.api.telegram import get_moderation_inbox_reader
from newsflow.app import app
from newsflow.persistence.database import reset_database_session_factory
from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
)
from newsflow.services.moderation_inbox import ModerationInboxReader


def test_moderation_inbox_api_returns_latest_revision_and_editorial_decision() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        post = IncomingPostModel(
            telegram_account_id="account-a",
            donor_channel_id="@donor",
            telegram_message_id=17,
            state="REWRITE_QUEUED",
        )
        session.add(post)
        session.flush()
        session.add_all(
            [
                ContentRevisionModel(incoming_post_id=post.id, revision_number=1, source_text="original"),
                ContentRevisionModel(incoming_post_id=post.id, revision_number=2, source_text="corrected"),
                EditorialDecisionModel(
                    content_key="account-a:@donor:17:revision:2",
                    status="PASS",
                    rewrite_allowed=True,
                    reason_codes="",
                    protected_entities="",
                    sentiment="neutral",
                    framing="neutral",
                ),
            ]
        )
        session.commit()

        reader = ModerationInboxReader(session)
        app.dependency_overrides[get_moderation_inbox_reader] = lambda: reader
        try:
            response = TestClient(app).get("/api/telegram/incoming-posts")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "source_key": "account-a:@donor:17",
                "state": "REWRITE_QUEUED",
                "revision_number": 2,
                "source_text": "corrected",
                "editorial_status": "PASS",
                "rewrite_allowed": True,
                "editorial_reason_codes": [],
                "source_deleted": False,
            }
        ]
    }


def test_moderation_inbox_api_reads_database_configured_by_environment(
    monkeypatch, tmp_path
) -> None:
    database_url = f"sqlite:///{tmp_path / 'moderation-inbox.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        post = IncomingPostModel(
            telegram_account_id="account-b",
            donor_channel_id="@durable-donor",
            telegram_message_id=18,
            state="EDITORIAL_REVIEW",
        )
        session.add(post)
        session.flush()
        session.add(ContentRevisionModel(incoming_post_id=post.id, revision_number=1, source_text="draft"))
        session.add(
            EditorialDecisionModel(
                content_key="account-b:@durable-donor:18:revision:1",
                status="REJECT",
                rewrite_allowed=False,
                reason_codes="PROTECTED_ENTITY_NEGATIVE",
                protected_entities="entity-a",
                sentiment="negative",
                framing="hostile",
            )
        )
        session.commit()

    monkeypatch.setenv("DATABASE_URL", database_url)
    reset_database_session_factory()
    try:
        response = TestClient(app).get("/api/telegram/incoming-posts")
    finally:
        reset_database_session_factory()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "source_key": "account-b:@durable-donor:18",
                "state": "EDITORIAL_REVIEW",
                "revision_number": 1,
                "source_text": "draft",
                "editorial_status": "REJECT",
                "rewrite_allowed": False,
                "editorial_reason_codes": ["PROTECTED_ENTITY_NEGATIVE"],
                "source_deleted": False,
            }
        ]
    }
