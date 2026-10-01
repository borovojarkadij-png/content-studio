"""Transactional durable ingress for Telegram content.

This is the production-side ordering seam: cheap technical checks and source
identity deduplication always run before an editorial decision; a RewriteJob
and rewrite-request outbox event exist only for a passing decision.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from newsflow.domain.editorial import EditorialGate, EditorialStatus
from newsflow.domain.ingestion import IngestionResult
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
from newsflow.persistence.models import OutboxEventModel
from newsflow.providers.telegram import TelegramMessage


class DurableIngestionWorkflow:
    def __init__(
        self,
        session: Session,
        *,
        editorial_gate: EditorialGate | None = None,
        allowed_media_types: set[str] | None = None,
    ) -> None:
        self._session = session
        self._editorial_gate = editorial_gate or EditorialGate()
        self._allowed_media_types = allowed_media_types or {"text", "photo"}

    def ingest(
        self,
        event: TelegramMessage,
        *,
        observed_at: datetime,
        protected_entities: Sequence[str] = (),
        sentiment: str = "neutral",
        framing: str = "neutral",
    ) -> IngestionResult:
        source_key = f"{event.account_id}:{event.donor_identifier}:{event.message_id}"
        with self._session.begin():
            if event.media_type not in self._allowed_media_types or not event.text.strip():
                return IngestionResult(False, source_key, "REJECTED_TECHNICAL")

            repository = SqlAlchemyIngestionRepository(self._session)
            revision_number = repository.candidate_revision_number(event)
            if revision_number is None:
                return IngestionResult(False, source_key, "REJECTED_DUPLICATE")

            content_key = f"{source_key}:revision:{revision_number}"
            editorial = DurableEditorialService(self._session, self._editorial_gate)
            decision = editorial.get_or_evaluate(
                content_key,
                protected_entities,
                sentiment,
                framing,
                source_text=event.text,
            )
            if decision.status != EditorialStatus.PASS.value or not decision.rewrite_allowed:
                return IngestionResult(False, source_key, "REJECTED_EDITORIAL")

            persisted = repository.ingest(event, observed_at)
            job = editorial.create_rewrite_job(decision)
            if job is None:
                raise RuntimeError("Passing editorial decision did not create a rewrite job")
            self._session.add(
                OutboxEventModel(
                    event_type="rewrite.requested",
                    aggregate_key=content_key,
                    idempotency_key=f"rewrite.requested:{content_key}",
                )
            )
            return IngestionResult(persisted.created, source_key, "REWRITE_QUEUED")
