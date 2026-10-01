from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutboxEventModel,
    RewriteJobModel,
)
from newsflow.providers.telegram import TelegramMessage


def test_mapping_forbidden_domain_is_rejected_before_editorial_and_rewrite() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1",
                blocked_domains=frozenset({"example.org"}),
            ),
        )

        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 1, "Read https://example.org/deal"),
            observed_at=datetime.now(UTC),
        )

        assert result.status == "REJECTED_TECHNICAL"
        assert result.reason_code == "FORBIDDEN_LINK"
        assert session.scalars(select(EditorialDecisionModel)).all() == []
        assert session.scalars(select(RewriteJobModel)).all() == []
        assert session.scalars(select(OutboxEventModel)).all() == []


def test_mapping_ad_marker_is_rejected_before_editorial_and_rewrite() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        workflow = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(mapping_id="mapping-1"),
        )

        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 2, "#реклама выгодное предложение"),
            observed_at=datetime.now(UTC),
        )

        assert result.status == "REJECTED_TECHNICAL"
        assert result.reason_code == "ADVERTISING"
        assert session.scalars(select(EditorialDecisionModel)).all() == []
        assert session.scalars(select(RewriteJobModel)).all() == []
        assert session.scalars(select(OutboxEventModel)).all() == []
