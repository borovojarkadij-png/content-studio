from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.domain.editorial import EditorialGate
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.persistence.models import Base, EditorialDecisionModel, RewriteJobModel


def test_durable_editorial_reject_never_creates_rewrite_job() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = DurableEditorialService(session, EditorialGate())
        decision = service.evaluate("content-1", ["Belarus"], "negative", "hostile")
        session.commit()

        assert decision.status == "REJECT"
        assert session.scalars(select(RewriteJobModel)).all() == []
        stored = session.scalar(select(EditorialDecisionModel))
        assert stored is not None
        assert stored.rewrite_allowed is False


def test_durable_editorial_service_refuses_direct_rewrite_dispatch_for_reject() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        service = DurableEditorialService(session, EditorialGate())
        decision = service.evaluate("content-2", ["Russia"], "negative", "hostile")

        assert service.create_rewrite_job(decision) is None
        assert session.scalars(select(RewriteJobModel)).all() == []
