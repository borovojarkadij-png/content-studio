"""Explicit durable fail-closed sync opt-in, never erased by a runtime flag.

The immutable outbox fact is shared by API and workers. Disabling orchestration
is not permission to waive synchronization of legacy sources. No reset API.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from newsflow.persistence.models import OutboxEventModel

KEY = "channel.sync_enforcement_enabled:v1"


def sync_enforced(session):
    # Corrupt metadata on this unique retained key must not silently disable safety.
    return (
        session.scalar(select(OutboxEventModel.id).where(OutboxEventModel.idempotency_key == KEY))
        is not None
    )


class ChannelSyncEnforcement:
    def __init__(self, session_factory):
        self._sessions = session_factory

    def enable(self, *, now):
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Synchronization enforcement time must be timezone-aware")
        for attempt in range(3):
            try:
                with self._sessions.begin() as session:
                    if sync_enforced(session):
                        return
                    session.add(
                        OutboxEventModel(
                            event_type="channel.sync_enforcement_enabled",
                            aggregate_key="global",
                            idempotency_key=KEY,
                            created_at=now.astimezone(UTC),
                        )
                    )
                    session.flush()
                return
            except IntegrityError:
                if attempt == 2:
                    raise
