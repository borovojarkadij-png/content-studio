"""Default-disabled bounded deletion-first orchestration seam, not main activation."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.models import (
    ChannelDifferenceCursorModel,
    ChannelMappingModel,
    DonorChannel,
    TelegramAccount,
)
from newsflow.services.account_health import AccountHealthService
from newsflow.services.channel_baseline import ChannelBaselineService
from newsflow.services.channel_difference_runner import ChannelDifferenceRunner, _clock
from newsflow.services.channel_sync_enforcement import ChannelSyncEnforcement
from newsflow.services.donor_ingestion_runner import DonorIngestionRunner
from newsflow.services.source_sync_replay import SourceSyncReplayService
from newsflow.services.telegram_provider_factory import (
    ConfiguredTelegramProvider,
    load_telegram_credentials,
)


@dataclass(frozen=True, slots=True)
class ChannelSyncTickResult:
    outcome: str
    cursor: int
    outcomes: tuple[tuple[int, str], ...]
    replay_cursor: int = 0
    replay_outcomes: tuple[tuple[int, str], ...] = ()
    health_cursor: int = 0
    health_outcomes: tuple[tuple[int, str], ...] = ()


def _reconnect_cooled_accounts(session_factory, provider, *, now, after_id, limit):
    """Bounded fair read-only session probes, not login or time-based authorization."""
    with session_factory() as session:

        def scan(after):
            return tuple(
                session.scalars(
                    select(TelegramAccount.id)
                    .where(
                        TelegramAccount.id > after,
                        TelegramAccount.health_status == "COOLDOWN",
                        func.length(TelegramAccount.encrypted_session) > 0,
                        TelegramAccount.cooldown_until.is_not(None),
                        TelegramAccount.cooldown_until <= now,
                    )
                    .order_by(TelegramAccount.id)
                    .limit(limit)
                )
            )

        ids = scan(after_id)
        if not ids and after_id:
            ids = scan(0)
    outcomes = []
    for account_id in ids:
        try:
            with session_factory() as session:
                result = AccountHealthService(session, provider).reconnect(account_id, now=now)
                outcome = result.status.value
        except (TimeoutError, ConnectionError):
            outcome = "RETRY_PROVIDER"
        except (SQLAlchemyError, ValueError, TypeError, LookupError):
            outcome = "INTERRUPTED"
        outcomes.append((account_id, outcome))
    return ids[-1] if ids else 0, tuple(outcomes)


def run_channel_sync_tick(
    session_factory,
    *,
    now,
    enabled=False,
    cipher=None,
    provider=None,
    credentials_path=None,
    cursor=0,
    replay_cursor=0,
    health_cursor=0,
    limit=4,
    clock=lambda: datetime.now(UTC),
):
    if type(enabled) is not bool:
        raise ValueError("Channel synchronization requires an explicit boolean opt-in")
    if not enabled:
        return ChannelSyncTickResult("DISABLED", cursor, (), replay_cursor, (), health_cursor)
    if cipher is None:
        raise ValueError("Explicit stable cipher is required for channel synchronization")
    now = _clock(now)
    if (
        type(cursor) is not int
        or cursor < 0
        or type(replay_cursor) is not int
        or replay_cursor < 0
        or type(health_cursor) is not int
        or health_cursor < 0
        or type(limit) is not int
        or not 1 <= limit <= 4
    ):
        raise ValueError("Bounded canonical synchronization cursors/limit required")
    if provider is None:
        if credentials_path is None:
            raise ValueError("Provision Telegram credentials before enabling synchronization")
        api_id, api_hash = load_telegram_credentials(credentials_path)
        provider = ConfiguredTelegramProvider(
            session_factory, cipher=cipher, api_id=api_id, api_hash=api_hash
        )
    ChannelSyncEnforcement(session_factory).enable(now=now)
    health_cursor, health_outcomes = _reconnect_cooled_accounts(
        session_factory, provider, now=now, after_id=health_cursor, limit=limit
    )
    with session_factory() as session:

        def scan(after):
            return tuple(
                session.scalars(
                    select(DonorChannel.id)
                    .join(TelegramAccount)
                    .outerjoin(
                        ChannelDifferenceCursorModel,
                        ChannelDifferenceCursorModel.donor_channel_id == DonorChannel.id,
                    )
                    .where(
                        DonorChannel.id > after,
                        select(ChannelMappingModel.id)
                        .where(ChannelMappingModel.donor_channel_id == DonorChannel.id)
                        .exists(),
                        TelegramAccount.health_status == "CONNECTED",
                        func.length(TelegramAccount.encrypted_session) > 0,
                        or_(
                            TelegramAccount.cooldown_until.is_(None),
                            TelegramAccount.cooldown_until <= now,
                        ),
                        or_(
                            ChannelDifferenceCursorModel.available_at.is_(None),
                            ChannelDifferenceCursorModel.available_at <= now,
                        ),
                        or_(
                            ChannelDifferenceCursorModel.lease_expires_at.is_(None),
                            ChannelDifferenceCursorModel.lease_expires_at <= now,
                        ),
                    )
                    .order_by(DonorChannel.id)
                    .limit(limit)
                )
            )

        donor_ids = scan(cursor)
        if not donor_ids and cursor:
            donor_ids = scan(0)
    baseline = ChannelBaselineService(session_factory, provider=provider, clock=clock)
    difference = ChannelDifferenceRunner(session_factory, provider=provider, clock=clock)
    history = DonorIngestionRunner(session_factory, provider=provider, clock=clock)
    outcomes = []
    for donor_id in donor_ids:
        try:
            outcome = baseline.bootstrap(donor_id)
            if outcome in {"BASELINE_RECORDED", "ALREADY_INITIALIZED"}:
                outcome = difference.run_donor(donor_id, now=_clock(clock()))
                if outcome == "DIFFERENCE_COMPLETE":
                    outcome = history.run_donor(donor_id, now=_clock(clock()))
        except (SQLAlchemyError, ValueError, TypeError, LookupError):
            outcome = "INTERRUPTED"
        outcomes.append((donor_id, outcome))
    replay = SourceSyncReplayService(session_factory, clock=clock).run_batch(after_id=replay_cursor)
    return ChannelSyncTickResult(
        "PROCESSED",
        donor_ids[-1] if donor_ids else 0,
        tuple(outcomes),
        replay.cursor,
        replay.outcomes,
        health_cursor,
        health_outcomes,
    )
