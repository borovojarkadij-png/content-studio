"""Explicit opt-in, bounded Telegram aggregate sampling with durable SQL truth."""

from dataclasses import dataclass
from datetime import UTC, datetime

from newsflow.domain.engagement import utc_timestamp
from newsflow.services.telegram_engagement_sampling import TelegramEngagementSamplingRunner
from newsflow.services.telegram_provider_factory import (
    ConfiguredTelegramProvider,
    load_telegram_credentials,
)


@dataclass(frozen=True, slots=True)
class EngagementSamplingTickResult:
    outcome: str
    cursor: int
    queued_ids: tuple[int, ...]


def run_telegram_engagement_tick(
    session_factory,
    *,
    now,
    enabled=False,
    cipher=None,
    provider=None,
    credentials_path=None,
    cursor=0,
    clock=lambda: datetime.now(UTC),
):
    """Admit at most 16 sources and execute at most one read-only observation.

    Cursor is transient fairness only. Jobs, attempts, leases and observations
    survive new tick instances; IDLE means no bounded claim was acquired.
    """
    if type(enabled) is not bool:
        raise ValueError("NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED requires an exact bool")
    if not enabled:
        return EngagementSamplingTickResult("DISABLED", cursor, ())
    if cipher is None:
        raise ValueError("Explicit stable cipher is required for Telegram engagement sampling")
    now = utc_timestamp(now)
    if type(cursor) is not int or not 0 <= cursor < 2**63:
        raise ValueError("Invalid sampling cursor")
    if provider is None:
        if credentials_path is None:
            raise ValueError("Provision Telegram credentials before enabling engagement sampling")
        api_id, api_hash = load_telegram_credentials(credentials_path)
        provider = ConfiguredTelegramProvider(
            session_factory, cipher=cipher, api_id=api_id, api_hash=api_hash
        )
    runner = TelegramEngagementSamplingRunner(session_factory, provider=provider, clock=clock)
    admission = runner.enqueue_window(now=now, after_id=cursor, limit=16)
    outcome = runner.run_next(now=clock())
    return EngagementSamplingTickResult(outcome, admission.cursor, admission.queued_ids)
