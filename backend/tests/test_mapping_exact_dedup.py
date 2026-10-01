from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import Base, EditorialDecisionModel, RewriteJobModel
from newsflow.providers.telegram import TelegramMessage


def test_same_content_in_one_mapping_is_deduplicated_before_editorial() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(mapping_id="mapping-1"),
        )

        first = workflow.ingest(
            TelegramMessage("account-a", "@donor-a", 1, "Same headline"),
            observed_at=datetime.now(UTC),
        )
        duplicate = workflow.ingest(
            TelegramMessage("account-a", "@donor-b", 2, " same headline "),
            observed_at=datetime.now(UTC),
        )

        assert first.status == "REWRITE_QUEUED"
        assert duplicate.status == "REJECTED_DUPLICATE"
        assert len(session.scalars(select(EditorialDecisionModel)).all()) == 1
        assert len(session.scalars(select(RewriteJobModel)).all()) == 1


def test_same_content_remains_independently_eligible_in_another_mapping() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        mapping_one = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(mapping_id="mapping-1"),
        )
        mapping_two = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(mapping_id="mapping-2"),
        )

        first = mapping_one.ingest(
            TelegramMessage("account-a", "@donor-a", 1, "Same headline"),
            observed_at=datetime.now(UTC),
        )
        second = mapping_two.ingest(
            TelegramMessage("account-a", "@donor-b", 2, "Same headline"),
            observed_at=datetime.now(UTC),
        )

        assert first.status == second.status == "REWRITE_QUEUED"
        assert len(session.scalars(select(RewriteJobModel)).all()) == 2
