from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutputChannel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    PublicationPlanModel,
    TelegramAccount,
)


@pytest.fixture
def scheduler_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'scheduler.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        account = TelegramAccount(name="Synthetic", telegram_user_id=1001, encrypted_session="")
        session.add(account)
        session.flush()
        for number, zone, mode, slots in (
            (1, "Europe/Minsk", "AUTOMATIC", "540,900"),
            (2, "UTC", "AUTOMATIC", "1430"),
            (3, "UTC", "MANUAL", "1430"),
        ):
            channel = OutputChannel(
                telegram_account_id=account.id,
                telegram_channel_id=-1001234567890 - number,
                title=f"Synthetic {number}",
            )
            session.add(channel)
            session.flush()
            session.add(
                PublicationPlanModel(
                    output_channel_id=channel.id,
                    mode=mode,
                    daily_limit=1,
                    timezone=zone,
                    slot_minutes=slots,
                )
            )
            key = f"synthetic:{number}"
            session.add(
                EditorialDecisionModel(
                    content_key=key,
                    status="PASS",
                    rewrite_allowed=True,
                    sentiment="neutral",
                    framing="neutral",
                )
            )
            session.add(
                PublicationCandidateModel(
                    output_channel_id=channel.id,
                    content_key=key,
                    priority=10,
                    state="READY",
                    eligible_at=datetime(2030, 1, 1, tzinfo=UTC),
                )
            )
        session.commit()
    yield factory
    engine.dispose()


def test_timer_tick_plans_without_button_using_each_channel_day_and_no_past_slots(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    summary = run_scheduler_tick(scheduler_store, now=datetime(2030, 1, 2, 23, 45, tzinfo=UTC))
    assert summary.failed_plan_ids == ()
    with scheduler_store() as session:
        rows = session.scalars(
            select(PlannedPublicationModel).order_by(PlannedPublicationModel.output_channel_id)
        ).all()
        assert [(row.output_channel_id, row.scheduled_for.isoformat()) for row in rows] == [
            (1, "2030-01-03T06:00:00"),
            (2, "2030-01-02T23:50:00"),
        ]
        assert (
            session.scalar(
                select(PublicationCandidateModel.state).where(
                    PublicationCandidateModel.output_channel_id == 3
                )
            )
            == "READY"
        )


def test_scheduler_restart_is_idempotent_and_stale_reject_releases_reservation(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    now = datetime(2030, 1, 2, 23, 45, tzinfo=UTC)
    run_scheduler_tick(scheduler_store, now=now)
    run_scheduler_tick(scheduler_store, now=now)
    with scheduler_store() as session:
        assert session.scalar(select(func.count()).select_from(PlannedPublicationModel)) == 2
        decision = session.scalar(
            select(EditorialDecisionModel).where(
                EditorialDecisionModel.content_key == "synthetic:1"
            )
        )
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    run_scheduler_tick(scheduler_store, now=now)
    with scheduler_store() as session:
        assert (
            session.scalar(
                select(PlannedPublicationModel.state).where(
                    PlannedPublicationModel.output_channel_id == 1
                )
            )
            == "BLOCKED_EDITORIAL"
        )


def test_bad_channel_configuration_does_not_prevent_other_channel_planning(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    with scheduler_store() as session:
        session.get(PublicationPlanModel, 1).timezone = "Invalid/Timezone"
        session.commit()
    result = run_scheduler_tick(scheduler_store, now=datetime(2030, 1, 2, 23, 45, tzinfo=UTC))
    assert result.failed_plan_ids == (1,)
    with scheduler_store() as session:
        assert session.scalar(select(PlannedPublicationModel.output_channel_id)) == 2


def test_tick_rejects_naive_time_before_any_planning(scheduler_store):
    from newsflow.worker import run_scheduler_tick

    with pytest.raises(ValueError, match="timezone-aware"):
        run_scheduler_tick(scheduler_store, now=datetime(2030, 1, 2, tzinfo=None))  # noqa: DTZ001 -- deliberately invalid input
