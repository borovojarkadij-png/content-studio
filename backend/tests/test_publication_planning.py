from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutputChannel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    TelegramAccount,
)
from newsflow.services.publication_planning import CandidateBlocked, PublicationPlanningService


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        account = TelegramAccount(
            name="Primary",
            telegram_user_id=1001,
            encrypted_session="",
            health_status="DISCONNECTED",
        )
        session.add(account)
        session.flush()
        output = OutputChannel(
            telegram_account_id=account.id, telegram_channel_id=-1001234567890, title="Destination"
        )
        session.add(output)
        session.commit()
        yield session, output.id
    engine.dispose()


def approve(session: Session, content_key: str, *, rewrite_allowed: bool = True) -> None:
    session.add(
        EditorialDecisionModel(
            content_key=content_key,
            status="PASS" if rewrite_allowed else "REJECT",
            rewrite_allowed=rewrite_allowed,
            sentiment="neutral",
            framing="neutral",
        )
    )
    session.commit()


def test_automatic_plan_selects_highest_priority_candidates_into_daily_slots(session) -> None:
    database, output_id = session
    approve(database, "content:low")
    approve(database, "content:high")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 2, (540, 900))
    service.register_candidate(output_id, "content:low", priority=10)
    service.register_candidate(output_id, "content:high", priority=90)

    scheduled = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in scheduled] == [
        ("content:high", "2026-10-05T09:00:00+00:00"),
        ("content:low", "2026-10-05T15:00:00+00:00"),
    ]
    assert all(item["state"] == "PLANNED" for item in scheduled)
    assert service.plan_day(plan["id"], date(2026, 10, 5)) == scheduled
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 2


def test_automatic_plan_does_not_schedule_editorial_reject_or_create_rewrite_work(session) -> None:
    database, output_id = session
    approve(database, "content:reject", rewrite_allowed=False)
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540,))

    with pytest.raises(CandidateBlocked, match="EDITORIAL"):
        service.register_candidate(output_id, "content:reject", priority=100)

    assert service.plan_day(plan["id"], date(2026, 10, 5)) == []
    assert database.scalar(select(func.count()).select_from(PublicationCandidateModel)) == 0
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 0


def test_manual_plan_never_auto_selects_candidates(session) -> None:
    database, output_id = session
    approve(database, "content:ready")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "MANUAL", 1, (540,))
    service.register_candidate(output_id, "content:ready", priority=100)

    assert service.plan_day(plan["id"], date(2026, 10, 5)) == []
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 0


def test_scheduler_rechecks_editorial_decision_before_it_reserves_a_slot(session) -> None:
    database, output_id = session
    approve(database, "content:stale")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540,))
    service.register_candidate(output_id, "content:stale", priority=100)
    decision = database.scalar(
        select(EditorialDecisionModel).where(EditorialDecisionModel.content_key == "content:stale")
    )
    assert decision is not None
    decision.status = "REJECT"
    decision.rewrite_allowed = False
    database.commit()

    assert service.plan_day(plan["id"], date(2026, 10, 5)) == []
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 0


def test_scheduler_skips_stale_reject_without_wasting_a_daily_slot(session) -> None:
    database, output_id = session
    approve(database, "content:stale")
    approve(database, "content:fresh")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 2, (540, 900))
    service.register_candidate(output_id, "content:stale", priority=100)
    service.register_candidate(output_id, "content:fresh", priority=90)
    stale = database.scalar(
        select(EditorialDecisionModel).where(EditorialDecisionModel.content_key == "content:stale")
    )
    assert stale is not None
    stale.status = "REJECT"
    stale.rewrite_allowed = False
    database.commit()

    scheduled = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in scheduled] == [
        ("content:fresh", "2026-10-05T09:00:00+00:00"),
    ]


def test_scheduler_releases_an_existing_stale_reservation_before_replanning(session) -> None:
    database, output_id = session
    approve(database, "content:stale")
    approve(database, "content:fresh")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540,))
    service.register_candidate(output_id, "content:stale", priority=100)
    assert service.plan_day(plan["id"], date(2026, 10, 5))[0]["content_key"] == "content:stale"
    stale = database.scalar(
        select(EditorialDecisionModel).where(EditorialDecisionModel.content_key == "content:stale")
    )
    assert stale is not None
    stale.status = "REJECT"
    stale.rewrite_allowed = False
    database.commit()
    service.register_candidate(output_id, "content:fresh", priority=90)

    replanned = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in replanned] == [
        ("content:fresh", "2026-10-05T09:00:00+00:00"),
    ]
    assert (
        database.scalar(
            select(PlannedPublicationModel.state).where(
                PlannedPublicationModel.state == "BLOCKED_EDITORIAL"
            )
        )
        == "BLOCKED_EDITORIAL"
    )
