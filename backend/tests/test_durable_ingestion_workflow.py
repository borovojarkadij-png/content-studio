from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutboxEventModel,
    RewriteJobModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.moderation_inbox import ModerationInboxReader


def test_technical_rejection_creates_no_editorial_decision_rewrite_job_or_outbox_event() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)

        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 1, "video payload", media_type="video"),
            observed_at=datetime.now(UTC),
        )

        assert result.status == "REJECTED_TECHNICAL"
        assert session.scalars(select(EditorialDecisionModel)).all() == []
        assert session.scalars(select(RewriteJobModel)).all() == []
        assert session.scalars(select(OutboxEventModel)).all() == []


def test_editorial_reject_never_creates_rewrite_job_or_rewrite_outbox_event() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)

        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 2, "hostile claim"),
            observed_at=datetime.now(UTC),
            protected_entities=["Belarus"],
            sentiment="negative",
            framing="hostile",
        )

        assert result.status == "REJECTED_EDITORIAL"
        decision = session.scalar(select(EditorialDecisionModel))
        assert decision is not None
        assert decision.rewrite_allowed is False
        assert session.scalars(select(RewriteJobModel)).all() == []
        assert (
            session.scalars(
                select(OutboxEventModel).where(OutboxEventModel.event_type == "rewrite.requested")
            ).all()
            == []
        )


def test_editorial_reject_retry_remains_idempotently_blocked() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        event = TelegramMessage("account-a", "@donor", 22, "hostile claim")

        first = workflow.ingest(
            event,
            observed_at=datetime.now(UTC),
            protected_entities=["Belarus"],
            sentiment="negative",
            framing="hostile",
        )
        retry = workflow.ingest(
            event,
            observed_at=datetime.now(UTC),
            protected_entities=["Belarus"],
            sentiment="negative",
            framing="hostile",
        )

        assert first.status == retry.status == "REJECTED_EDITORIAL"
        assert len(session.scalars(select(EditorialDecisionModel)).all()) == 1
        assert session.scalars(select(RewriteJobModel)).all() == []
        assert (
            session.scalars(
                select(OutboxEventModel).where(OutboxEventModel.event_type == "rewrite.requested")
            ).all()
            == []
        )


def test_duplicate_delivery_skips_editorial_and_rewrite_dispatch() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        event = TelegramMessage("account-a", "@donor", 3, "permitted news")

        first = workflow.ingest(
            event, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral"
        )
        duplicate = workflow.ingest(event, observed_at=datetime.now(UTC))

        assert first.status == "REWRITE_QUEUED"
        assert duplicate.status == "REJECTED_DUPLICATE"
        assert len(session.scalars(select(EditorialDecisionModel)).all()) == 1
        assert len(session.scalars(select(RewriteJobModel)).all()) == 1
        assert [event.event_type for event in session.scalars(select(OutboxEventModel)).all()] == [
            "incoming_post.created",
            "rewrite.requested",
        ]


def test_missing_classification_is_persisted_for_review_without_rewrite():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        result = DurableIngestionWorkflow(session).ingest(
            TelegramMessage("account-a", "@donor", 41, "Needs actual classification"),
            observed_at=datetime.now(UTC),
        )
        assert result.status == "MANUAL_REVIEW"
        assert session.scalars(select(RewriteJobModel)).all() == []
        item = ModerationInboxReader(session).list_items()[0]
        assert item.editorial_status == "MANUAL_REVIEW"
        assert item.rewrite_allowed is False


def test_rejected_edit_replaces_current_source_and_remains_in_inbox():
    from newsflow.services.source_revisions import source_is_current

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        workflow.ingest(
            TelegramMessage("account-a", "@donor", 42, "Original"),
            observed_at=datetime.now(UTC),
            sentiment="neutral",
            framing="neutral",
        )
        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 42, "Negative changed claim", is_edit=True),
            observed_at=datetime.now(UTC),
            protected_entities=("Belarus",),
            sentiment="negative",
            framing="hostile",
        )
        assert result.status == "REJECTED_EDITORIAL"
        assert not source_is_current(session, "account-a:@donor:42:revision:1")
        item = ModerationInboxReader(session).list_items()[0]
        assert item.revision_number == 2
        assert item.editorial_status == "REJECT"
        assert len(session.scalars(select(RewriteJobModel)).all()) == 1


def test_technical_rejected_edit_invalidates_previously_eligible_source():
    from newsflow.services.source_revisions import source_is_current

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        workflow.ingest(
            TelegramMessage("account-a", "@donor", 43, "Original"),
            observed_at=datetime.now(UTC),
            sentiment="neutral",
            framing="neutral",
        )
        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 43, "#ad changed", is_edit=True),
            observed_at=datetime.now(UTC),
        )
        assert result.status == "REJECTED_TECHNICAL"
        assert not source_is_current(session, "account-a:@donor:43:revision:1")
        assert len(session.scalars(select(EditorialDecisionModel)).all()) == 1
        assert len(session.scalars(select(RewriteJobModel)).all()) == 1


def test_exact_duplicate_edit_still_invalidates_old_revision():
    from newsflow.services.source_revisions import source_is_current

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        for number, text in ((44, "Original"), (45, "Other headline")):
            workflow.ingest(
                TelegramMessage("account-a", "@donor", number, text),
                observed_at=datetime.now(UTC),
                sentiment="neutral",
                framing="neutral",
            )
        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 44, "Other headline", is_edit=True),
            observed_at=datetime.now(UTC),
        )
        assert result.status == "REJECTED_DUPLICATE"
        assert not source_is_current(session, "account-a:@donor:44:revision:1")
        assert len(session.scalars(select(EditorialDecisionModel)).all()) == 2
        assert len(session.scalars(select(RewriteJobModel)).all()) == 2
