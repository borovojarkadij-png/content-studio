"""Adversarial source-edit acceptance, confined to the synthetic verification DB."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
from newsflow.persistence.models import PlannedPublicationModel, RewriteOutputModel
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.publication_planning import PublicationPlanningService
from newsflow.services.rewrite_outputs import RewriteOutputBlocked, RewriteOutputService


def main():
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Source-guard probe requires the isolated verification database")
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    key = "synthetic-persistence:@synthetic_donor:1:revision:1"
    day = datetime.now(UTC).date() + timedelta(days=1)
    with factory() as session:
        output = session.scalars(
            select(RewriteOutputModel).where(RewriteOutputModel.content_key == key)
        ).one()
        output_id, channel_id = output.id, output.output_channel_id
        assert output.approval_state == "PENDING"
        RewriteOutputService(session).approve(output_id, activate_candidate=True)
        planner = PublicationPlanningService(session)
        plan = planner.configure_plan(channel_id, "AUTOMATIC", 1, (540,), "UTC")
        plan_id = plan["id"]
        assert len(planner.plan_day(plan_id, day)) == 1
    with factory() as session, session.begin():
        SqlAlchemyIngestionRepository(session).ingest(
            TelegramMessage(
                "synthetic-persistence",
                "@synthetic_donor",
                1,
                "Edited permitted synthetic news",
                is_edit=True,
            ),
            datetime.now(UTC),
        )
    with factory() as session:
        reviews = RewriteOutputService(session)
        assert reviews.list_outputs(channel_id)[0]["approve_allowed"] is False
        try:
            reviews.approve(output_id, activate_candidate=True)
        except RewriteOutputBlocked as error:
            assert "SOURCE" in str(error)
        else:
            raise AssertionError("Old source revision was approved")
        planner = PublicationPlanningService(session)
        assert planner.plan_day(plan_id, day) == []
        assert session.scalar(select(PlannedPublicationModel.state)) == "BLOCKED_SOURCE"
        assert planner.list_publications(plan_id, day)[0]["source_current"] is False
    engine.dispose()
    print(
        "Source-edit guard passed: old draft cannot be approved; old reservation blocked; no provider/send"
    )


if __name__ == "__main__":
    main()
