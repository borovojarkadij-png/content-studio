"""Transactional durable ingress for Telegram content.

This is the production-side ordering seam: cheap technical checks and source
identity deduplication always run before an editorial decision; a RewriteJob
and rewrite-request outbox event exist only for a passing decision.
"""

from collections.abc import Sequence
from datetime import datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.domain.editorial import EditorialGate, EditorialStatus
from newsflow.domain.ingestion import IngestionResult
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    EditorialDecisionModel,
    MappingContentFingerprintModel,
    OutboxEventModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
)
from newsflow.providers.telegram import TelegramMessage


class DurableIngestionWorkflow:
    def __init__(
        self,
        session: Session,
        *,
        editorial_gate: EditorialGate | None = None,
        allowed_media_types: set[str] | None = None,
        technical_filter: MappingTechnicalFilter | None = None,
    ) -> None:
        self._session = session
        self._editorial_gate = editorial_gate or EditorialGate()
        self._technical_filter = technical_filter or MappingTechnicalFilter(
            mapping_id="default",
            allowed_media_types=frozenset(allowed_media_types or {"text", "photo"}),
        )

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
            technical = self._technical_filter.evaluate(event)
            if not technical.accepted:
                return IngestionResult(
                    False, source_key, "REJECTED_TECHNICAL", technical.reason_code
                )

            repository = SqlAlchemyIngestionRepository(self._session)
            revision_number = repository.candidate_revision_number(event)
            if revision_number is None:
                return self._route_existing_source(repository, event, source_key, observed_at)
            content_key = f"{source_key}:revision:{revision_number}"
            existing_decision = self._session.scalar(
                select(EditorialDecisionModel).where(
                    EditorialDecisionModel.content_key == content_key
                )
            )
            if existing_decision is not None:
                status = (
                    "REJECTED_EDITORIAL"
                    if existing_decision.status != EditorialStatus.PASS.value
                    or not existing_decision.rewrite_allowed
                    else "REJECTED_DUPLICATE"
                )
                return IngestionResult(False, source_key, status)

            fingerprint = sha256(event.text.strip().casefold().encode("utf-8")).hexdigest()
            existing_fingerprint = self._session.scalar(
                select(MappingContentFingerprintModel.id).where(
                    MappingContentFingerprintModel.mapping_id == self._technical_filter.mapping_id,
                    MappingContentFingerprintModel.fingerprint == fingerprint,
                )
            )
            if existing_fingerprint is not None:
                return IngestionResult(False, source_key, "REJECTED_DUPLICATE")
            try:
                with self._session.begin_nested():
                    self._session.add(
                        MappingContentFingerprintModel(
                            mapping_id=self._technical_filter.mapping_id,
                            fingerprint=fingerprint,
                        )
                    )
                    self._session.flush()
            except IntegrityError:
                return IngestionResult(False, source_key, "REJECTED_DUPLICATE")

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
            self._ensure_publication_candidate(content_key)
            self._session.add(
                OutboxEventModel(
                    event_type="rewrite.requested",
                    aggregate_key=content_key,
                    idempotency_key=f"rewrite.requested:{content_key}",
                )
            )
            return IngestionResult(persisted.created, source_key, "REWRITE_QUEUED")

    def _route_existing_source(
        self,
        repository: SqlAlchemyIngestionRepository,
        event: TelegramMessage,
        source_key: str,
        observed_at: datetime,
    ) -> IngestionResult:
        """Fan one durable source/rewrite job out to eligible output mappings once."""
        revision_number = repository.current_revision_number(event)
        if revision_number is None:
            return IngestionResult(False, source_key, "REJECTED_DUPLICATE")
        content_key = f"{source_key}:revision:{revision_number}"
        decision = self._session.scalar(
            select(EditorialDecisionModel).where(EditorialDecisionModel.content_key == content_key)
        )
        if decision is None:
            return IngestionResult(False, source_key, "REJECTED_DUPLICATE")
        if decision.status != EditorialStatus.PASS.value or not decision.rewrite_allowed:
            return IngestionResult(False, source_key, "REJECTED_EDITORIAL")
        if self._technical_filter.output_channel_id is None:
            return IngestionResult(False, source_key, "REJECTED_DUPLICATE")
        if (
            self._session.scalar(
                select(RewriteJobModel.id).where(RewriteJobModel.content_key == content_key)
            )
            is None
        ):
            raise RuntimeError("Passing editorial decision did not create a rewrite job")
        candidate_created = self._ensure_publication_candidate(content_key)
        status = "REWRITE_QUEUED" if candidate_created else "REJECTED_DUPLICATE"
        return IngestionResult(candidate_created, source_key, status)

    def _ensure_publication_candidate(self, content_key: str) -> bool:
        output_channel_id = self._technical_filter.output_channel_id
        if output_channel_id is None:
            return False
        if self._session.get(OutputChannel, output_channel_id) is None:
            raise LookupError("Configured output channel was not found")
        existing = self._session.scalar(
            select(PublicationCandidateModel.id).where(
                PublicationCandidateModel.output_channel_id == output_channel_id,
                PublicationCandidateModel.content_key == content_key,
            )
        )
        if existing is not None:
            return False
        self._session.add(
            PublicationCandidateModel(
                output_channel_id=output_channel_id,
                content_key=content_key,
                priority=0,
                state="AWAITING_REWRITE",
            )
        )
        return True
