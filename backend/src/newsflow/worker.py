"""Durable planning and explicitly opt-in provider drafts; never publication."""

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
from newsflow.security.master_key import load_runtime_master_key
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.durable_semantic_runner import DurableSemanticRunner
from newsflow.services.publication_planning import PlanValidationError, PublicationPlanningService
from newsflow.services.rewrite_provider_factory import ConfiguredRewriteProviderFactory
from newsflow.services.semantic_verifier_factory import ConfiguredSemanticVerifierFactory

logger = structlog.get_logger()


def rewrite_enabled(value: str) -> bool:
    if value not in {"0", "1"}:
        raise ValueError("NEWSFLOW_REWRITE_ENABLED must be exactly 0 or 1")
    return value == "1"


def run_rewrite_tick(
    session_factory: Callable[[], Session],
    *,
    enabled: bool,
    cipher: SessionCipher | None,
    now: datetime,
    opener=None,
    provider: str = "OPENAI",
) -> str:
    if not enabled:
        return "DISABLED"
    if cipher is None:
        raise ValueError("Explicit stable cipher is required for enabled rewriting")
    configured = ConfiguredRewriteProviderFactory(
        session_factory, cipher=cipher, opener=opener, provider=provider
    )
    runner = DurableRewriteRunner(session_factory, provider_for_channel=configured)
    return runner.run_next(now=now)


@dataclass(frozen=True)
class SchedulerTickResult:
    plans_visited: int
    active_reservations: int
    failed_plan_ids: tuple[int, ...]


def run_semantic_tick(
    session_factory, *, enabled: bool, cipher: SessionCipher | None, now: datetime, opener=None
) -> str:
    if not enabled:
        return "DISABLED"
    if cipher is None:
        raise ValueError("Explicit stable cipher is required for semantic verification")
    execution = DurableSemanticRunner(
        session_factory,
        verifier_for_release=ConfiguredSemanticVerifierFactory(
            session_factory, cipher=cipher, opener=opener
        ),
    )
    execution.enqueue_pending(now=now)
    return execution.run_next(now=now)


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
    network_enabled = rewrite_enabled(getenv("NEWSFLOW_REWRITE_ENABLED", "0"))
    semantic_enabled = rewrite_enabled(getenv("NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED", "0"))
    provider = getenv("NEWSFLOW_REWRITE_PROVIDER", "OPENAI")
    if provider not in {"OPENAI", "OPENROUTER"}:
        raise ValueError("NEWSFLOW_REWRITE_PROVIDER must be OPENAI or OPENROUTER")
    cipher = (
        SessionCipher(load_runtime_master_key()) if network_enabled or semantic_enabled else None
    )
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
        if network_enabled and not stopped.is_set():
            try:
                outcome = run_rewrite_tick(
                    factory, enabled=True, cipher=cipher, now=datetime.now(UTC), provider=provider
                )
                logger.info("rewrite.tick", outcome=outcome)
            except Exception:  # noqa: BLE001 - external failures must not leak secrets or lose leases
                # The committed attempt survives; no secret-bearing error/traceback.
                logger.warning("rewrite.execution_interrupted", recovery="persisted_lease")
        if semantic_enabled and not stopped.is_set():
            try:
                outcome = run_semantic_tick(
                    factory, enabled=True, cipher=cipher, now=datetime.now(UTC)
                )
                logger.info("semantic.tick", outcome=outcome)
            except Exception:  # noqa: BLE001 - preserve committed lease, never log secrets
                logger.warning("semantic.execution_interrupted", recovery="persisted_lease")
        stopped.wait(interval)


if __name__ == "__main__":
    main()
