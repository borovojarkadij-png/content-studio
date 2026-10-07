"""Durable planning and explicitly opt-in provider drafts; never publication."""

import signal
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from os import getenv
from pathlib import Path
from threading import Event
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from newsflow.persistence.database import configured_session_factory
from newsflow.persistence.models import (
    ChannelMappingModel,
    DonorChannel,
    DonorImportModel,
    DonorImportResolutionJobModel,
    DonorIngestionCursorModel,
    PublicationPlanModel,
    TelegramAccount,
)
from newsflow.security.master_key import load_runtime_master_key
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.donor_import_resolution import DonorImportResolutionRunner
from newsflow.services.donor_ingestion_runner import DonorIngestionRunner
from newsflow.services.durable_media_runner import DurableMediaRunner
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.durable_semantic_runner import DurableSemanticRunner
from newsflow.services.publication_planning import PlanValidationError, PublicationPlanningService
from newsflow.services.rewrite_provider_factory import ConfiguredRewriteProviderFactory
from newsflow.services.semantic_verifier_factory import ConfiguredSemanticVerifierFactory
from newsflow.services.telegram_provider_factory import (
    ConfiguredTelegramProvider,
    load_telegram_credentials,
)

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


def run_media_tick(
    session_factory, *, media_root: Path, enabled: bool, now: datetime, provider=None
) -> str:
    if not enabled:
        return "DISABLED"
    execution = DurableMediaRunner(session_factory, media_root, provider=provider)
    execution.enqueue_pending(now=now)
    return execution.run_next(now=now)


def run_donor_resolution_tick(
    session_factory,
    *,
    enabled: bool,
    cipher: SessionCipher | None,
    now: datetime,
    credentials_path: Path | None = None,
    provider=None,
):
    if not enabled:
        return ()
    if cipher is None:
        raise ValueError("Explicit stable cipher is required for Telegram resolution")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Resolution time must be timezone-aware")
    if provider is None:
        if credentials_path is None:
            raise ValueError("Provision Telegram credentials before enabling resolution")
        api_id, api_hash = load_telegram_credentials(credentials_path)
        provider = ConfiguredTelegramProvider(
            session_factory, cipher=cipher, api_id=api_id, api_hash=api_hash
        )
    with session_factory() as session:
        imports = list(
            session.scalars(
                select(DonorImportModel.id)
                .join(TelegramAccount)
                .outerjoin(DonorImportResolutionJobModel)
                .where(
                    DonorImportModel.status == "PENDING_RESOLUTION",
                    TelegramAccount.health_status != "SESSION_INVALID",
                    func.length(TelegramAccount.encrypted_session) > 0,
                    or_(
                        TelegramAccount.cooldown_until.is_(None),
                        TelegramAccount.cooldown_until <= now,
                    ),
                    or_(
                        DonorImportResolutionJobModel.available_at.is_(None),
                        DonorImportResolutionJobModel.available_at <= now,
                    ),
                    or_(
                        DonorImportResolutionJobModel.lease_expires_at.is_(None),
                        DonorImportResolutionJobModel.lease_expires_at <= now,
                    ),
                )
                .order_by(
                    DonorImportResolutionJobModel.available_at.asc().nulls_first(),
                    DonorImportModel.id,
                )
                .limit(4)
            )
        )
    outcomes = []
    runtime = DonorImportResolutionRunner(session_factory, provider=provider)
    for import_id in imports:
        try:
            outcome = runtime.run_import(import_id, now=now)
        except (SQLAlchemyError, ValueError, LookupError):
            outcome = "INTERRUPTED"
            logger.warning(
                "ingestion.import_interrupted", import_id=import_id, recovery="persisted_lease"
            )
        outcomes.append((import_id, outcome))
    return tuple(outcomes)


def run_ingestion_tick(
    session_factory,
    *,
    enabled: bool,
    cipher: SessionCipher | None,
    now: datetime,
    credentials_path: Path | None = None,
    provider=None,
) -> tuple[tuple[int, str], ...]:
    if not enabled:
        return ()
    if cipher is None:
        raise ValueError("Explicit stable cipher is required for Telegram ingestion")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Ingestion time must be timezone-aware")
    if provider is None:
        if credentials_path is None:
            raise ValueError("Provision Telegram credentials before enabling ingestion")
        api_id, api_hash = load_telegram_credentials(credentials_path)
        provider = ConfiguredTelegramProvider(
            session_factory, cipher=cipher, api_id=api_id, api_hash=api_hash
        )
    with session_factory() as session:
        donors = list(
            session.scalars(
                select(DonorChannel.id)
                .join(TelegramAccount)
                .outerjoin(DonorIngestionCursorModel)
                .where(
                    select(ChannelMappingModel.id)
                    .where(ChannelMappingModel.donor_channel_id == DonorChannel.id)
                    .exists(),
                    TelegramAccount.health_status != "SESSION_INVALID",
                    func.length(TelegramAccount.encrypted_session) > 0,
                    or_(
                        TelegramAccount.cooldown_until.is_(None),
                        TelegramAccount.cooldown_until <= now,
                    ),
                    or_(
                        DonorIngestionCursorModel.available_at.is_(None),
                        DonorIngestionCursorModel.available_at <= now,
                    ),
                    or_(
                        DonorIngestionCursorModel.lease_expires_at.is_(None),
                        DonorIngestionCursorModel.lease_expires_at <= now,
                    ),
                )
                .order_by(
                    DonorIngestionCursorModel.available_at.asc().nulls_first(), DonorChannel.id
                )
                .limit(4)
            )
        )
    outcomes = []
    poller = DonorIngestionRunner(session_factory, provider=provider)
    for donor_id in donors:
        try:
            outcome = poller.run_donor(donor_id, now=now)
        except (SQLAlchemyError, ValueError, LookupError):
            outcome = "INTERRUPTED"
            logger.warning(
                "ingestion.donor_interrupted", donor_id=donor_id, recovery="persisted_lease"
            )
        outcomes.append((donor_id, outcome))
    return tuple(outcomes)


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
    media_enabled = rewrite_enabled(getenv("NEWSFLOW_INTERNET_MEDIA_ENABLED", "0"))
    ingestion_enabled = rewrite_enabled(getenv("NEWSFLOW_TELEGRAM_INGESTION_ENABLED", "0"))
    provider = getenv("NEWSFLOW_REWRITE_PROVIDER", "OPENAI")
    if provider not in {"OPENAI", "OPENROUTER"}:
        raise ValueError("NEWSFLOW_REWRITE_PROVIDER must be OPENAI or OPENROUTER")
    cipher = (
        SessionCipher(load_runtime_master_key())
        if network_enabled or semantic_enabled or ingestion_enabled
        else None
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
        if ingestion_enabled and not stopped.is_set():
            try:
                import_outcomes = run_donor_resolution_tick(
                    factory,
                    enabled=True,
                    cipher=cipher,
                    now=datetime.now(UTC),
                    credentials_path=Path(
                        getenv(
                            "NEWSFLOW_TELEGRAM_CREDENTIALS_FILE",
                            "/run/secrets/telegram_credentials",
                        )
                    ),
                )
                logger.info("ingestion.import_tick", outcomes=import_outcomes)
                outcomes = run_ingestion_tick(
                    factory,
                    enabled=True,
                    cipher=cipher,
                    now=datetime.now(UTC),
                    credentials_path=Path(
                        getenv(
                            "NEWSFLOW_TELEGRAM_CREDENTIALS_FILE",
                            "/run/secrets/telegram_credentials",
                        )
                    ),
                )
                logger.info("ingestion.tick", outcomes=outcomes)
            except Exception:  # noqa: BLE001 - retain progress/leases, never expose provider secrets
                logger.warning("ingestion.execution_interrupted", recovery="persisted_lease")
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
        if media_enabled and not stopped.is_set():
            try:
                outcome = run_media_tick(
                    factory,
                    enabled=True,
                    media_root=Path(getenv("NEWSFLOW_MEDIA_ROOT", "/var/lib/newsflow/media")),
                    now=datetime.now(UTC),
                )
                logger.info("media.tick", outcome=outcome)
            except Exception:  # noqa: BLE001 - retain committed lease, never log private data
                logger.warning("media.execution_interrupted", recovery="persisted_lease")
        stopped.wait(interval)


if __name__ == "__main__":
    main()
