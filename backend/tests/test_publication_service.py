from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from newsflow.domain.editorial import EditorialDecision, EditorialStatus
from newsflow.services import publication


@dataclass
class RecordingPublisher:
    calls: int = 0

    def publish(self, text: str) -> str:
        self.calls += 1
        return "telegram-message-1"


def test_publication_service_blocks_editorial_reject_before_send() -> None:
    publisher = RecordingPublisher()
    service = publication.PublicationService(publisher)
    rejected = EditorialDecision(
        status=EditorialStatus.REJECT,
        rewrite_allowed=False,
        reason_codes=("PROTECTED_ENTITY_NEGATIVE",),
        protected_entities=("Belarus",),
        sentiment="negative",
        framing="hostile",
    )

    with pytest.raises(publication.PublicationBlocked):
        service.publish(
            text="stale rejected text",
            decision=rejected,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scheduled_for=datetime.now(UTC),
            is_cancelled=False,
            idempotency_key="publication-1",
        )

    assert publisher.calls == 0


def test_publication_service_does_not_send_same_idempotency_key_twice() -> None:
    publisher = RecordingPublisher()
    service = publication.PublicationService(publisher)
    passed = EditorialDecision(
        status=EditorialStatus.PASS,
        rewrite_allowed=True,
        reason_codes=(),
        protected_entities=(),
        sentiment="neutral",
        framing="neutral",
    )
    arguments = {
        "text": "permitted text",
        "decision": passed,
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "scheduled_for": datetime.now(UTC),
        "is_cancelled": False,
        "idempotency_key": "publication-1",
    }

    service.publish(**arguments)
    service.publish(**arguments)

    assert publisher.calls == 1
