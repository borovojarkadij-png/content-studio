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
        assert session.scalars(select(OutboxEventModel)).all() == []


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
        assert session.scalars(select(OutboxEventModel)).all() == []


def test_duplicate_delivery_skips_editorial_and_rewrite_dispatch() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(session)
        event = TelegramMessage("account-a", "@donor", 3, "permitted news")

        first = workflow.ingest(event, observed_at=datetime.now(UTC))
        duplicate = workflow.ingest(event, observed_at=datetime.now(UTC))

        assert first.status == "REWRITE_QUEUED"
        assert duplicate.status == "REJECTED_DUPLICATE"
        assert len(session.scalars(select(EditorialDecisionModel)).all()) == 1
        assert len(session.scalars(select(RewriteJobModel)).all()) == 1
        assert [event.event_type for event in session.scalars(select(OutboxEventModel)).all()] == [
            "incoming_post.created",
            "rewrite.requested",
        ]
