from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import Base, ContentRevisionModel, RewriteJobModel
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.source_revisions import source_is_current

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def ingest(workflow, event):
    return workflow.ingest(event, observed_at=NOW, sentiment="neutral", framing="neutral")


def test_media_only_edit_invalidates_old_source_even_with_identical_text():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        ingest(
            workflow,
            TelegramMessage("a", "-100123", 1, "Caption", media_type="photo", album_id="20"),
        )
        result = ingest(
            workflow,
            TelegramMessage(
                "a", "-100123", 1, "Caption", is_edit=True, media_type="video", album_id="20"
            ),
        )
        assert result.status == "REJECTED_TECHNICAL"
        assert not source_is_current(session, "a:-100123:1:revision:1")
        latest = session.scalars(
            select(ContentRevisionModel).order_by(ContentRevisionModel.revision_number.desc())
        ).first()
        assert latest.media_type == "video"
        assert latest.album_id == "20"
        # Even the earlier photo member was incomplete, not an approved album.
        assert len(session.scalars(select(RewriteJobModel)).all()) == 0


def test_stale_edit_timestamp_cannot_roll_back_latest_revision():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        ingest(workflow, TelegramMessage("a", "-100123", 1, "Original", source_updated_at=NOW))
        ingest(
            workflow,
            TelegramMessage(
                "a",
                "-100123",
                1,
                "Newest",
                is_edit=True,
                source_updated_at=NOW + timedelta(seconds=2),
            ),
        )
        result = ingest(
            workflow,
            TelegramMessage(
                "a",
                "-100123",
                1,
                "Old edit",
                is_edit=True,
                source_updated_at=NOW + timedelta(seconds=1),
            ),
        )
        assert result.status == "REJECTED_STALE_SOURCE"
        assert source_is_current(session, "a:-100123:1:revision:2")
        assert [
            revision.source_text
            for revision in session.scalars(
                select(ContentRevisionModel).order_by(ContentRevisionModel.revision_number)
            )
        ] == ["Original", "Newest"]


def test_conflicting_equal_timestamp_is_retained_but_never_rewritten():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        ingest(workflow, TelegramMessage("a", "-100123", 1, "Original", source_updated_at=NOW))
        result = ingest(
            workflow,
            TelegramMessage("a", "-100123", 1, "Conflicting", is_edit=True, source_updated_at=NOW),
        )
        assert result.status == "MANUAL_REVIEW"
        assert not source_is_current(session, "a:-100123:1:revision:1")
        assert len(session.scalars(select(RewriteJobModel)).all()) == 1


def test_naive_source_timestamp_fails_before_transaction():
    with pytest.raises(ValueError, match="timezone-aware"):
        DurableIngestionWorkflow(None).ingest(
            TelegramMessage(
                "a", "-100123", 1, "Source", source_updated_at=NOW.replace(tzinfo=None)
            ),
            observed_at=NOW,
        )


def test_missing_timestamp_cannot_replace_a_timestamped_source():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        ingest(workflow, TelegramMessage("a", "-100123", 1, "Current", source_updated_at=NOW))
        result = ingest(
            workflow, TelegramMessage("a", "-100123", 1, "Unordered edit", is_edit=True)
        )
        assert result.status == "REJECTED_STALE_SOURCE"
        assert source_is_current(session, "a:-100123:1:revision:1")
        assert len(session.scalars(select(ContentRevisionModel)).all()) == 1


def test_timestamped_conflict_cannot_hide_behind_a_missing_edit_flag():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        ingest(workflow, TelegramMessage("a", "-100123", 1, "Current", source_updated_at=NOW))
        result = ingest(
            workflow,
            TelegramMessage("a", "-100123", 1, "Conflicting current packet", source_updated_at=NOW),
        )
        assert result.status == "MANUAL_REVIEW"
        assert not source_is_current(session, "a:-100123:1:revision:1")
        assert len(session.scalars(select(RewriteJobModel)).all()) == 1
