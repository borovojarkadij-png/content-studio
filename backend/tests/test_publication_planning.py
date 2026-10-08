from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutputChannel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    PublicationJobModel,
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
    account, donor, message, _, revision = content_key.split(":")
    post = IncomingPostModel(
        telegram_account_id=account,
        donor_channel_id=donor,
        telegram_message_id=int(message),
        state="RECEIVED",
    )
    session.add(post)
    session.flush()
    session.add(
        ContentRevisionModel(
            incoming_post_id=post.id, revision_number=int(revision), source_text="Synthetic source"
        )
    )
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
    approve(database, "content:low:1:revision:1")
    approve(database, "content:high:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 2, (540, 900))
    service.register_candidate(output_id, "content:low:1:revision:1", priority=10)
    service.register_candidate(output_id, "content:high:1:revision:1", priority=90)

    scheduled = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in scheduled] == [
        ("content:high:1:revision:1", "2026-10-05T09:00:00+00:00"),
        ("content:low:1:revision:1", "2026-10-05T15:00:00+00:00"),
    ]
    assert all(item["state"] == "PLANNED" for item in scheduled)
    assert service.plan_day(plan["id"], date(2026, 10, 5)) == scheduled
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 2


def test_published_slots_still_consume_daily_quota_and_are_not_replaced(session):
    database, output_id = session
    approve(database, "content:first:1:revision:1")
    approve(database, "content:second:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540, 900))
    service.register_candidate(output_id, "content:first:1:revision:1", priority=90)
    service.register_candidate(output_id, "content:second:1:revision:1", priority=10)
    service.plan_day(plan["id"], date(2026, 10, 5))
    item = database.scalar(select(PlannedPublicationModel))
    item.state = "PUBLISHED"
    database.get(PublicationCandidateModel, item.candidate_id).state = "PUBLISHED"
    database.commit()
    result = service.plan_day(plan["id"], date(2026, 10, 5))
    assert len(result) == 1 and result[0]["state"] == "PUBLISHED"
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 1


@pytest.mark.parametrize("cancelled", [False, True])
def test_unknown_delivery_retains_quota_after_editorial_revocation_or_cancel(session, cancelled):
    database, output_id = session
    approve(database, "content:unknown:1:revision:1")
    approve(database, "content:replacement:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540, 900))
    service.register_candidate(output_id, "content:unknown:1:revision:1", priority=90)
    service.register_candidate(output_id, "content:replacement:1:revision:1", priority=10)
    service.plan_day(plan["id"], date(2026, 10, 5))
    item = database.scalar(select(PlannedPublicationModel))
    database.add(
        PublicationJobModel(
            planned_id=item.id,
            telegram_account_id=1,
            telegram_channel_id=-1001234567890,
            request_nonce=456,
            binding_sha256="a" * 64,
            state="NEEDS_RECONCILIATION",
            attempts=1,
            available_at=datetime(2026, 10, 5, tzinfo=UTC),
        )
    )
    decision = database.scalar(
        select(EditorialDecisionModel).where(
            EditorialDecisionModel.content_key == "content:unknown:1:revision:1"
        )
    )
    decision.status, decision.rewrite_allowed = "REJECT", False
    if cancelled:
        item.state = "CANCELLED"
    database.commit()
    result = service.plan_day(plan["id"], date(2026, 10, 5))
    assert len(result) == 1 and result[0]["content_key"] == "content:unknown:1:revision:1"
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 1


def test_automatic_plan_respects_candidate_delayed_eligibility_without_wasting_slots(
    session,
) -> None:
    database, output_id = session
    approve(database, "content:delayed:1:revision:1")
    approve(database, "content:immediate:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 2, (540, 600))
    service.register_candidate(output_id, "content:delayed:1:revision:1", priority=90)
    service.register_candidate(output_id, "content:immediate:1:revision:1", priority=10)
    delayed = database.scalar(
        select(PublicationCandidateModel).where(
            PublicationCandidateModel.content_key == "content:delayed:1:revision:1"
        )
    )
    immediate = database.scalar(
        select(PublicationCandidateModel).where(
            PublicationCandidateModel.content_key == "content:immediate:1:revision:1"
        )
    )
    assert delayed is not None and immediate is not None
    delayed.eligible_at = datetime(2026, 10, 5, 9, 45, tzinfo=UTC)
    immediate.eligible_at = datetime(2026, 10, 5, 8, tzinfo=UTC)
    database.commit()

    scheduled = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in scheduled] == [
        ("content:immediate:1:revision:1", "2026-10-05T09:00:00+00:00"),
        ("content:delayed:1:revision:1", "2026-10-05T10:00:00+00:00"),
    ]


def test_automatic_plan_does_not_schedule_editorial_reject_or_create_rewrite_work(session) -> None:
    database, output_id = session
    approve(database, "content:reject:1:revision:1", rewrite_allowed=False)
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540,))

    with pytest.raises(CandidateBlocked, match="EDITORIAL"):
        service.register_candidate(output_id, "content:reject:1:revision:1", priority=100)

    assert service.plan_day(plan["id"], date(2026, 10, 5)) == []
    assert database.scalar(select(func.count()).select_from(PublicationCandidateModel)) == 0
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 0


def test_manual_plan_never_auto_selects_candidates(session) -> None:
    database, output_id = session
    approve(database, "content:ready:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "MANUAL", 1, (540,))
    service.register_candidate(output_id, "content:ready:1:revision:1", priority=100)

    assert service.plan_day(plan["id"], date(2026, 10, 5)) == []
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 0


def test_scheduler_rechecks_editorial_decision_before_it_reserves_a_slot(session) -> None:
    database, output_id = session
    approve(database, "content:stale:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540,))
    service.register_candidate(output_id, "content:stale:1:revision:1", priority=100)
    decision = database.scalar(
        select(EditorialDecisionModel).where(
            EditorialDecisionModel.content_key == "content:stale:1:revision:1"
        )
    )
    assert decision is not None
    decision.status = "REJECT"
    decision.rewrite_allowed = False
    database.commit()

    assert service.plan_day(plan["id"], date(2026, 10, 5)) == []
    assert database.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 0


def test_scheduler_skips_stale_reject_without_wasting_a_daily_slot(session) -> None:
    database, output_id = session
    approve(database, "content:stale:1:revision:1")
    approve(database, "content:fresh:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 2, (540, 900))
    service.register_candidate(output_id, "content:stale:1:revision:1", priority=100)
    service.register_candidate(output_id, "content:fresh:1:revision:1", priority=90)
    stale = database.scalar(
        select(EditorialDecisionModel).where(
            EditorialDecisionModel.content_key == "content:stale:1:revision:1"
        )
    )
    assert stale is not None
    stale.status = "REJECT"
    stale.rewrite_allowed = False
    database.commit()

    scheduled = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in scheduled] == [
        ("content:fresh:1:revision:1", "2026-10-05T09:00:00+00:00"),
    ]


def test_scheduler_releases_an_existing_stale_reservation_before_replanning(session) -> None:
    database, output_id = session
    approve(database, "content:stale:1:revision:1")
    approve(database, "content:fresh:1:revision:1")
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540,))
    service.register_candidate(output_id, "content:stale:1:revision:1", priority=100)
    assert (
        service.plan_day(plan["id"], date(2026, 10, 5))[0]["content_key"]
        == "content:stale:1:revision:1"
    )
    stale = database.scalar(
        select(EditorialDecisionModel).where(
            EditorialDecisionModel.content_key == "content:stale:1:revision:1"
        )
    )
    assert stale is not None
    stale.status = "REJECT"
    stale.rewrite_allowed = False
    database.commit()
    service.register_candidate(output_id, "content:fresh:1:revision:1", priority=90)

    replanned = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in replanned] == [
        ("content:fresh:1:revision:1", "2026-10-05T09:00:00+00:00"),
    ]
    assert (
        database.scalar(
            select(PlannedPublicationModel.state).where(
                PlannedPublicationModel.state == "BLOCKED_EDITORIAL"
            )
        )
        == "BLOCKED_EDITORIAL"
    )


def test_scheduler_keeps_multiple_blocked_reservation_history_for_the_same_slot(session) -> None:
    database, output_id = session
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 1, (540,))
    for content_key in (
        "content:first:1:revision:1",
        "content:second:1:revision:1",
        "content:third:1:revision:1",
    ):
        approve(database, content_key)
        service.register_candidate(output_id, content_key, priority=10)
        scheduled = service.plan_day(plan["id"], date(2026, 10, 5))
        assert scheduled[0]["content_key"] == content_key
        if content_key != "content:third:1:revision:1":
            decision = database.scalar(
                select(EditorialDecisionModel).where(
                    EditorialDecisionModel.content_key == content_key
                )
            )
            assert decision is not None
            decision.status = "REJECT"
            decision.rewrite_allowed = False
            database.commit()

    assert (
        database.scalar(
            select(func.count())
            .select_from(PlannedPublicationModel)
            .where(PlannedPublicationModel.state == "BLOCKED_EDITORIAL")
        )
        == 2
    )


def test_scheduler_refills_a_slot_released_from_a_partially_planned_day(session) -> None:
    database, output_id = session
    for content_key in (
        "content:first:1:revision:1",
        "content:second:1:revision:1",
        "content:fresh:1:revision:1",
    ):
        approve(database, content_key)
    service = PublicationPlanningService(database)
    plan = service.configure_plan(output_id, "AUTOMATIC", 2, (540, 900))
    service.register_candidate(output_id, "content:first:1:revision:1", priority=100)
    service.register_candidate(output_id, "content:second:1:revision:1", priority=90)
    service.plan_day(plan["id"], date(2026, 10, 5))
    decision = database.scalar(
        select(EditorialDecisionModel).where(
            EditorialDecisionModel.content_key == "content:first:1:revision:1"
        )
    )
    assert decision is not None
    decision.status = "REJECT"
    decision.rewrite_allowed = False
    database.commit()
    service.register_candidate(output_id, "content:fresh:1:revision:1", priority=80)

    replanned = service.plan_day(plan["id"], date(2026, 10, 5))

    assert [(item["content_key"], item["scheduled_for"]) for item in replanned] == [
        ("content:fresh:1:revision:1", "2026-10-05T09:00:00+00:00"),
        ("content:second:1:revision:1", "2026-10-05T15:00:00+00:00"),
    ]
