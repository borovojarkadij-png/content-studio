"""Apply validated channel deletions before any message fan-out; no network IO."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from newsflow.persistence.models import OutboxEventModel, SourceDeletionModel
from newsflow.providers.telegram import TelegramChannelDifference


class SourceDeletionClaimLost(RuntimeError):
    """The lease owner no longer has permission to apply this chunk."""


class SourceDeletionService:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._factory = session_factory

    def record(
        self,
        difference: TelegramChannelDifference,
        *,
        observed_at: datetime,
        transaction_guard: Callable[[Session], bool] | None = None,
    ) -> tuple[int, ...]:
        if not isinstance(difference, TelegramChannelDifference):
            raise TypeError("Validated channel difference required")
        difference.__post_init__()
        account = difference.account_id
        if (
            not account.isascii()
            or not account.isdecimal()
            or not 0 < int(account) <= 2147483647
            or str(int(account)) != account
        ):
            raise ValueError("Canonical account identity required")
        if (
            not isinstance(observed_at, datetime)
            or observed_at.tzinfo is None
            or observed_at.utcoffset() is None
        ):
            raise ValueError("Deletion observation time must be timezone-aware")
        # Absent-row races roll back the WHOLE chunk, then reread authoritative
        # identities. Never commit a partial chunk or invent another outbox event.
        for attempt in range(3):
            try:
                with self._factory.begin() as session:
                    if transaction_guard is not None and not transaction_guard(session):
                        raise SourceDeletionClaimLost("Source deletion lease no longer owned")
                    created = []
                    for message_id in sorted(difference.deleted_message_ids):
                        row = session.scalar(
                            select(SourceDeletionModel)
                            .where(
                                SourceDeletionModel.telegram_account_id == account,
                                SourceDeletionModel.donor_channel_id == difference.donor_identifier,
                                SourceDeletionModel.telegram_message_id == message_id,
                            )
                            .with_for_update()
                            .execution_options(populate_existing=True)
                        )
                        if row is not None:
                            row.latest_pts = max(row.latest_pts, difference.next_pts)
                            continue
                        session.add(
                            SourceDeletionModel(
                                telegram_account_id=account,
                                donor_channel_id=difference.donor_identifier,
                                telegram_message_id=message_id,
                                latest_pts=difference.next_pts,
                                observed_at=observed_at.astimezone(UTC),
                            )
                        )
                        identity = f"{account}:{difference.donor_identifier}:{message_id}"
                        session.add(
                            OutboxEventModel(
                                event_type="source.deleted",
                                aggregate_key=identity,
                                idempotency_key=f"source.deleted:{identity}",
                                created_at=observed_at.astimezone(UTC),
                            )
                        )
                        created.append(message_id)
                    session.flush()
                return tuple(created)
            except IntegrityError:
                if attempt == 2:
                    raise
        raise RuntimeError("Source deletion retry budget exhausted")
