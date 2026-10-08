"""Retained SQL member observations are never a complete/publishable album."""

from datetime import UTC, datetime
from os import getenv
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from unattended_postgres import create_postgres_namespace

from alembic import command
from newsflow.app import app
from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.database import reset_database_session_factory
from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutboxEventModel,
    RewriteJobModel,
    RewriteUsageModel,
    SourceDeletionModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.album_observation import AlbumObservationBlocked, AlbumObservationReader
from newsflow.services.channel_sync_enforcement import ChannelSyncEnforcement
from newsflow.services.moderation_inbox import ModerationInboxReader

KEY = "1:-1001234567890:20:revision:1"


def member(
    session, message_id, *, account="1", donor="-1001234567890", album="77", text="", media="photo"
):
    post = IncomingPostModel(
        telegram_account_id=account,
        donor_channel_id=donor,
        telegram_message_id=message_id,
        state="REJECTED_TECHNICAL",
    )
    session.add(post)
    session.flush()
    revision = ContentRevisionModel(
        incoming_post_id=post.id,
        revision_number=1,
        source_text=text,
        media_type=media,
        album_id=album,
        media_protected=False,
    )
    session.add(revision)
    session.flush()
    return post, revision


@pytest.fixture
def album_store(tmp_path, monkeypatch):
    postgres = getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL")
    url = (
        create_postgres_namespace(postgres)
        if postgres is not None
        else f"sqlite:///{tmp_path / 'observed-album.db'}"
    )
    monkeypatch.setenv("DATABASE_URL", url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    with Session(engine) as session:
        member(session, 20, text="Первая подпись")
        member(session, 29, text="Подпись видео", media="video")
        member(session, 34)
        member(session, 21, album="78", text="Другой альбом")
        member(session, 25, account="2", text="Другой аккаунт")
        member(session, 31, donor="-1001234567891", text="Другой донор")
        session.commit()
    yield engine, url
    engine.dispose()


def test_retained_sparse_captions_video_and_captionless_members_never_grant_permission(album_store):
    engine, _ = album_store
    with Session(engine) as session:
        result = AlbumObservationReader(session).read(KEY)
        assert result == {
            "anchor_content_key": KEY,
            "album_id": "77",
            "membership_complete": False,
            "rewrite_allowed": False,
            "publication_allowed": False,
            "source_sync_blocked": False,
            "reason_code": "ALBUM_NORMALIZATION_REQUIRED",
            "members": [
                {
                    "content_key": f"1:-1001234567890:{number}:revision:1",
                    "message_id": number,
                    "revision_number": 1,
                    "text": text,
                    "media_type": media,
                    "media_protected": False,
                    "source_deleted": False,
                }
                for number, text, media in (
                    (20, "Первая подпись", "photo"),
                    (29, "Подпись видео", "video"),
                    (34, "", "photo"),
                )
            ],
        }
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0


def test_latest_member_edits_and_deletions_preserve_history_without_inventing_completeness(
    album_store,
):
    engine, _ = album_store
    with Session(engine) as session:
        post = session.scalar(
            select(IncomingPostModel).where(IncomingPostModel.telegram_message_id == 29)
        )
        session.add(
            ContentRevisionModel(
                incoming_post_id=post.id,
                revision_number=2,
                source_text="Новая подпись",
                media_type="video",
                album_id="77",
                media_protected=True,
            )
        )
        post = session.scalar(
            select(IncomingPostModel).where(IncomingPostModel.telegram_message_id == 34)
        )
        session.add(
            ContentRevisionModel(
                incoming_post_id=post.id,
                revision_number=2,
                source_text="Отдельный пост",
                media_type="photo",
                album_id=None,
                media_protected=False,
            )
        )
        session.add(
            SourceDeletionModel(
                telegram_account_id="1",
                donor_channel_id="-1001234567890",
                telegram_message_id=20,
                latest_pts=12,
                observed_at=datetime.now(UTC),
            )
        )
        session.commit()
    with Session(engine) as session:
        result = AlbumObservationReader(session).read(KEY)
        assert [item["message_id"] for item in result["members"]] == [20, 29]
        assert result["members"][0]["source_deleted"] is True
        assert result["members"][1]["text"] == "Новая подпись"
        assert result["members"][1]["revision_number"] == 2
        assert result["members"][1]["media_protected"] is True
        assert (
            result["membership_complete"]
            is result["rewrite_allowed"]
            is result["publication_allowed"]
            is False
        )
        assert session.scalar(select(func.count()).select_from(ContentRevisionModel)) == 8


@pytest.mark.parametrize("count", [10, 11])
def test_ten_members_still_incomplete_and_eleven_are_not_silently_truncated(album_store, count):
    engine, _ = album_store
    with Session(engine) as session:
        for number in range(40, 40 + count - 3):
            member(session, number)
        session.commit()
        reader = AlbumObservationReader(session)
        if count == 11:
            with pytest.raises(AlbumObservationBlocked, match="ALBUM_MEMBER_LIMIT_EXCEEDED"):
                reader.read(KEY)
        else:
            result = reader.read(KEY)
            assert len(result["members"]) == 10
            assert result["membership_complete"] is result["rewrite_allowed"] is False


def test_stale_anchor_cannot_select_a_previous_album(album_store):
    engine, _ = album_store
    with Session(engine) as session:
        post = session.scalar(
            select(IncomingPostModel).where(IncomingPostModel.telegram_message_id == 20)
        )
        session.add(
            ContentRevisionModel(
                incoming_post_id=post.id,
                revision_number=2,
                source_text="Отдельный пост",
                media_type="photo",
                album_id=None,
                media_protected=False,
            )
        )
        session.commit()
        reader = AlbumObservationReader(session)
        with pytest.raises(AlbumObservationBlocked, match="SOURCE_REVISION_NOT_LATEST"):
            reader.read(KEY)
        with pytest.raises(AlbumObservationBlocked, match="SOURCE_NOT_ALBUM"):
            reader.read(KEY.removesuffix("1") + "2")


@pytest.mark.parametrize("key", [None, True, 1, "", " " * 2, "x" * 256])
def test_invalid_request_never_reaches_sql_or_providers(key):
    class NoSql:
        def __getattr__(self, _):
            raise AssertionError("Invalid request reached SQL")

    with pytest.raises(ValueError):
        AlbumObservationReader(NoSql()).read(key)


def test_real_configured_api_is_no_store_read_only_and_has_no_demo_fallback(
    album_store, monkeypatch
):
    _, url = album_store
    monkeypatch.setenv("DATABASE_URL", url)
    reset_database_session_factory()
    try:
        client = TestClient(app)
        response = client.get("/api/telegram/source-albums", params={"content_key": KEY})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["membership_complete"] is False
        assert len(response.json()["members"]) == 3
        assert (
            client.post("/api/telegram/source-albums", json={"content_key": KEY}).status_code == 405
        )
        assert (
            client.get("/api/telegram/source-albums", params={"content_key": "unknown"}).status_code
            == 404
        )
    finally:
        reset_database_session_factory()


def test_unconfigured_album_api_reports_unavailable_instead_of_demo(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    reset_database_session_factory()
    try:
        response = TestClient(app).get("/api/telegram/source-albums", params={"content_key": KEY})
        assert response.status_code == 503
        assert "members" not in response.json()
    finally:
        reset_database_session_factory()


def test_rejected_editorial_and_sync_gap_remain_nonexecutable_without_writes(album_store):
    engine, _ = album_store
    with Session(engine) as session:
        session.add(
            EditorialDecisionModel(
                content_key=KEY,
                status="REJECT",
                rewrite_allowed=False,
                reason_codes="PROTECTED_ENTITY_NEGATIVE",
                sentiment="negative",
                framing="hostile",
            )
        )
        session.commit()
        reader = AlbumObservationReader(session)
        assert reader.read(KEY)["source_sync_blocked"] is False
        ChannelSyncEnforcement(sessionmaker(engine)).enable(now=datetime.now(UTC))
        result = reader.read(KEY)
        assert result["source_sync_blocked"] is True
        assert result["rewrite_allowed"] is result["publication_allowed"] is False
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 1
        decision = session.scalar(select(EditorialDecisionModel))
        assert (decision.status, decision.rewrite_allowed) == ("REJECT", False)
        assert not session.new and not session.dirty and not session.deleted


def test_ambiguous_opaque_keys_cannot_disclose_a_foreign_album(album_store):
    engine, _ = album_store
    with Session(engine) as session:
        member(session, 1, account="one:two", donor="three", text="Original")
        member(session, 1, account="one", donor="two:three", text="Foreign")
        session.commit()
        with pytest.raises(LookupError):
            AlbumObservationReader(session).read("one:two:three:1:revision:1")


def test_anchor_change_between_reads_is_not_projected_as_current_album(album_store):
    engine, _ = album_store
    injected = False

    def concurrent_edit(connection, cursor, statement, parameters, context, executemany):
        nonlocal injected
        if not injected and "LEFT OUTER JOIN source_deletions" in statement:
            injected = True
            with Session(engine) as writer:
                post = writer.scalar(
                    select(IncomingPostModel).where(IncomingPostModel.telegram_message_id == 20)
                )
                writer.add(
                    ContentRevisionModel(
                        incoming_post_id=post.id,
                        revision_number=2,
                        source_text="Changed",
                        media_type="photo",
                        album_id="77",
                        media_protected=False,
                    )
                )
                writer.commit()

    event.listen(engine, "before_cursor_execute", concurrent_edit)
    try:
        with (
            Session(engine) as session,
            pytest.raises(AlbumObservationBlocked, match="SOURCE_REVISION_NOT_LATEST"),
        ):
            AlbumObservationReader(session).read(KEY)
    finally:
        event.remove(engine, "before_cursor_execute", concurrent_edit)
    assert injected


@pytest.mark.parametrize(
    "change",
    [
        {"album_id": "077"},
        {"album_id": "9223372036854775808"},
        {"album_id": "private-corrupt-value"},
        {"media_type": "text"},
        {"media_type": "executable"},
        {"media_id": "private-corrupt"},
    ],
)
def test_corrupt_persisted_observations_are_not_normalized_or_exposed_as_valid(album_store, change):
    engine, _ = album_store
    with Session(engine) as session:
        revision = session.scalar(
            select(ContentRevisionModel)
            .join(IncomingPostModel)
            .where(IncomingPostModel.telegram_message_id == 20)
        )
        for field, value in change.items():
            setattr(revision, field, value)
        session.commit()
    reset_database_session_factory()
    try:
        response = TestClient(app).get("/api/telegram/source-albums", params={"content_key": KEY})
        assert response.status_code == 409
        assert response.json() == {"detail": "ALBUM_OBSERVATION_INVALID"}
        assert "private-corrupt" not in response.text
    finally:
        reset_database_session_factory()


@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_read_never_flushes_or_overwrites_callers_pending_work(album_store, pending):
    engine, _ = album_store
    with Session(engine) as session:
        revision = session.scalar(
            select(ContentRevisionModel)
            .join(IncomingPostModel)
            .where(IncomingPostModel.telegram_message_id == 20)
        )
        if pending == "new":
            session.add(
                OutboxEventModel(
                    event_type="pending",
                    aggregate_key="private-pending",
                    idempotency_key="private-pending",
                )
            )
        elif pending == "dirty":
            revision.source_text = "Manual uncommitted draft"
        else:
            session.delete(revision)
        with pytest.raises(AlbumObservationBlocked, match="READ_SESSION_HAS_PENDING_CHANGES"):
            AlbumObservationReader(session).read(KEY)
        assert bool(session.new or session.dirty or session.deleted)
        if pending == "dirty":
            assert revision.source_text == "Manual uncommitted draft"
        session.rollback()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0
        result = AlbumObservationReader(session).read(KEY)
        assert result["members"][0]["text"] == "Первая подпись"


def test_missing_migrations_produces_honest_unavailable_without_private_db_error(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty-private.db'}")
    reset_database_session_factory()
    try:
        response = TestClient(app).get("/api/telegram/source-albums", params={"content_key": KEY})
        assert response.status_code == 503
        assert response.json() == {"detail": "Durable database unavailable or requires migrations"}
        assert "empty-private" not in response.text
    finally:
        reset_database_session_factory()


def test_real_grouped_ingress_reopens_as_observations_without_editorial_or_ai_calls(album_store):
    engine, _ = album_store

    class NoEditorialCalls:
        def evaluate(self, *_, **__):
            raise AssertionError("Incomplete album reached editorial/LLM classification")

    for number, caption, media in (
        (100, "Caption", "photo"),
        (109, "Video", "video"),
        (114, "", "photo"),
    ):
        with Session(engine) as session:
            outcome = DurableIngestionWorkflow(session, editorial_gate=NoEditorialCalls()).ingest(
                TelegramMessage(
                    "1",
                    "-1001234567890",
                    number,
                    caption,
                    media_type=media,
                    album_id="88",
                    media_protected=False,
                ),
                observed_at=datetime.now(UTC),
            )
            assert outcome.status == "REJECTED_TECHNICAL"
    with Session(engine) as session:
        result = AlbumObservationReader(session).read("1:-1001234567890:100:revision:1")
        assert [item["message_id"] for item in result["members"]] == [100, 109, 114]
        assert [item["media_type"] for item in result["members"]] == ["photo", "video", "photo"]
        assert (
            result["rewrite_allowed"]
            is result["publication_allowed"]
            is result["membership_complete"]
            is False
        )
        assert session.scalar(select(func.count()).select_from(EditorialDecisionModel)) == 0
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 0
        assert session.scalar(select(func.count()).select_from(RewriteUsageModel)) == 0


def test_inbox_reports_observed_album_without_historical_pass_permission(album_store):
    engine, _ = album_store
    with Session(engine) as session:
        session.add(
            EditorialDecisionModel(
                content_key=KEY,
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
        )
        session.commit()
        item = next(
            item.as_dict()
            for item in ModerationInboxReader(session).list_items()
            if item.source_key == "1:-1001234567890:20"
        )
        assert item.get("album_observed") is True
        assert item["editorial_status"] == "PASS"
        assert item["rewrite_allowed"] is False
        assert session.scalar(select(EditorialDecisionModel)).rewrite_allowed is True
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 0
