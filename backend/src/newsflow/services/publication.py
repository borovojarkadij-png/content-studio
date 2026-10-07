"""Safe publication boundary."""

from datetime import UTC, datetime
from typing import Protocol

from newsflow.domain.editorial import EditorialDecision, editorial_allows_rewrite


class TelegramPublisher(Protocol):
    def publish(self, text: str) -> str: ...


class PublicationBlocked(PermissionError):
    """Raised when current hard constraints make a send unsafe."""


class PublicationService:
    """Last defensive boundary before Telegram transport is invoked."""

    def __init__(self, publisher: TelegramPublisher) -> None:
        self._publisher = publisher
        self._published_keys: set[str] = set()

    def publish(
        self,
        *,
        text: str,
        decision: EditorialDecision,
        expires_at: datetime,
        scheduled_for: datetime,
        is_cancelled: bool,
        idempotency_key: str,
    ) -> str | None:
        now = datetime.now(UTC)
        if (
            not editorial_allows_rewrite(decision)
            or is_cancelled
            or expires_at <= now
            or scheduled_for > now
        ):
            raise PublicationBlocked("PUBLICATION_HARD_CONSTRAINT_BLOCKED")
        if idempotency_key in self._published_keys:
            return None
        message_id = self._publisher.publish(text)
        self._published_keys.add(idempotency_key)
        return message_id
