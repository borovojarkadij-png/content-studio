"""Timer-driven durable slot selection. No rewrite or publication transport yet."""

import signal
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from os import getenv
from threading import Event
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from newsflow.persistence.database import configured_session_factory
from newsflow.persistence.models import PublicationPlanModel
from newsflow.services.publication_planning import PlanValidationError, PublicationPlanningService

logger = structlog.get_logger()


@dataclass(frozen=True)
class SchedulerTickResult:
    plans_visited: int
    active_reservations: int
    failed_plan_ids: tuple[int, ...]


def run_scheduler_tick(
    session_factory: Callable[[], Session], *, now: datetime
) -> SchedulerTickResult:
    if now.tzinfo is None:
        raise ValueError("Scheduler time must be timezone-aware")
    with session_factory() as session:
        plans = session.execute(
            select(PublicationPlanModel.id, PublicationPlanModel.timezone)
            .where(PublicationPlanModel.mode == "AUTOMATIC")
            .order_by(PublicationPlanModel.id)
        ).all()
    failures = []
    active = 0
    for plan_id, timezone in plans:
        try:
            day = now.astimezone(ZoneInfo(timezone)).date()
            with session_factory() as session:
                active += len(
                    PublicationPlanningService(session).plan_day(plan_id, day, not_before=now)
                )
        except (SQLAlchemyError, PlanValidationError, ZoneInfoNotFoundError, LookupError):
            failures.append(plan_id)
            # Exception strings/tracebacks may carry credentials/SQL; do not log them.
            logger.warning("scheduler.plan_failed", plan_id=plan_id, retry="next_tick")
    return SchedulerTickResult(len(plans), active, tuple(failures))


def main() -> None:
    factory = configured_session_factory()
    if factory is None:
        raise RuntimeError("DATABASE_URL is required for the durable scheduler")
    interval = int(getenv("NEWSFLOW_SCHEDULER_POLL_SECONDS", "30"))
    if not 5 <= interval <= 60:
        raise ValueError("Scheduler polling interval must be between 5 and 60 seconds")
    stopped = Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stopped.set())
    while not stopped.is_set():
        try:
            result = run_scheduler_tick(factory, now=datetime.now(UTC))
            logger.info(
                "scheduler.tick",
                plans_visited=result.plans_visited,
                active_reservations=result.active_reservations,
                failed_plan_ids=result.failed_plan_ids,
            )
        except SQLAlchemyError:
            logger.warning("scheduler.database_unavailable", retry="next_tick")
        stopped.wait(interval)


if __name__ == "__main__":
    main()
