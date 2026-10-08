"""Transactional durable ingress for Telegram content.

This is the production-side ordering seam: cheap technical checks and source
identity deduplication always run before an editorial decision; a RewriteJob
and rewrite-request outbox event exist only for a passing decision.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.domain.editorial import EditorialGate, editorial_allows_rewrite
from newsflow.domain.ingestion import IngestionResult
from newsflow.domain.sql_editorial import DurableEditorialService
from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    ChannelMappingModel,
    EditorialDecisionModel,
    MappingContentFingerprintModel,
    OutboxEventModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
)
from newsflow.providers.telegram import TelegramMessage, validate_media_observation
from newsflow.services.mapping_filters import mapping_filter
from newsflow.services.source_revisions import source_identity_deleted


class DurableIngestionWorkflow:
    def __init__(
        self,
        session: Session,
        *,
        editorial_gate: EditorialGate | None = None,
        allowed_media_types: set[str] | None = None,
        technical_filter: MappingTechnicalFilter | None = None,
        configured_mapping_id: int | None = None,
        transaction_guard: Callable[[Session], bool] | None = None,
    ) -> None:
        self._session = session
        self._editorial_gate = editorial_gate or EditorialGate()
        self._configured_mapping_id = configured_mapping_id
        self._transaction_guard = transaction_guard
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
        sentiment: str = "unknown",
        framing: str = "unknown",
    ) -> IngestionResult:
        validate_media_observation(event)
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("Ingestion observation time must be timezone-aware")
        if event.source_updated_at is not None and (
            event.source_updated_at.tzinfo is None or event.source_updated_at.utcoffset() is None
        ):
            raise ValueError("Source update time must be timezone-aware")
        source_key = f"{event.account_id}:{event.donor_identifier}:{event.message_id}"
        with self._session.begin():
            if self._transaction_guard is not None and not self._transaction_guard(self._session):
                return IngestionResult(False, source_key, "STALE_CLAIM")
            if source_identity_deleted(
                self._session, event.account_id, event.donor_identifier, event.message_id
            ):
                return IngestionResult(False, source_key, "REJECTED_TECHNICAL", "SOURCE_DELETED")
            if self._configured_mapping_id is not None:
                mapping = self._session.scalar(
                    select(ChannelMappingModel)
                    .where(ChannelMappingModel.id == self._configured_mapping_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if mapping is None:
                    return IngestionResult(False, source_key, "MAPPING_REMOVED")
                self._technical_filter = mapping_filter(self._session, mapping)
            repository = SqlAlchemyIngestionRepository(self._session)
            if repository.is_stale(event):
                return IngestionResult(False, source_key, "REJECTED_STALE_SOURCE")
            if repository.timestamp_conflicts(event):
                # Telegram timestamps have finite precision. Conflicting payloads
                # at the same time are not an ordering proof or an editorial PASS.
                sentiment = framing = "unknown"
            revision_number = repository.candidate_revision_number(event)
            observed_edit = revision_number is not None and revision_number > 1
            if observed_edit:
                # Observing a changed known source is independent of a mapping's
                # acceptance. Even video/ad/exact-duplicate edits invalidate the
                # former source before returning a cheap rejection.
                repository.ingest(event, observed_at)
                repository.set_state(event, "RECEIVED")
            technical = self._technical_filter.evaluate(event)
            if not technical.accepted:
                if event.album_id is not None:
                    # Preserve captionless/video members too; never manufacture
                    # a complete group from just the first publishable caption.
                    repository.ingest(event, observed_at)
                if observed_edit or event.album_id is not None:
                    repository.set_state(event, "REJECTED_TECHNICAL")
                return IngestionResult(
                    False, source_key, "REJECTED_TECHNICAL", technical.reason_code
                )

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
                    self._blocked_status(existing_decision)
                    if not editorial_allows_rewrite(existing_decision)
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
                if observed_edit:
                    repository.set_state(event, "REJECTED_DUPLICATE")
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
            # An editorial reject is still a real source observation. Persist it
            # before returning, otherwise a previous approved revision remains
            # deceptively current and can be published after a hostile edit.
            persisted = repository.ingest(event, observed_at)
            if not editorial_allows_rewrite(decision):
                status = self._blocked_status(decision)
                repository.set_state(event, status)
                return IngestionResult(persisted.created, source_key, status)

            job = editorial.create_rewrite_job(
                decision, output_channel_id=self._technical_filter.output_channel_id
            )
            if job is None:
                raise RuntimeError("Passing editorial decision did not create a rewrite job")
            self._ensure_publication_candidate(content_key, observed_at)
            self._ensure_rewrite_outbox(job)
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
            select(EditorialDecisionModel)
            .where(EditorialDecisionModel.content_key == content_key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if decision is None:
            return IngestionResult(False, source_key, "REJECTED_DUPLICATE")
        if not editorial_allows_rewrite(decision):
            return IngestionResult(False, source_key, self._blocked_status(decision))
        if self._technical_filter.output_channel_id is None:
            return IngestionResult(False, source_key, "REJECTED_DUPLICATE")
        editorial = DurableEditorialService(self._session, self._editorial_gate)
        job = editorial.create_rewrite_job(
            decision, output_channel_id=self._technical_filter.output_channel_id
        )
        if job is None:
            raise RuntimeError("Passing editorial decision did not create a rewrite job")
        candidate_created = self._ensure_publication_candidate(content_key, observed_at)
        self._ensure_rewrite_outbox(job)
        status = "REWRITE_QUEUED" if candidate_created else "REJECTED_DUPLICATE"
        return IngestionResult(candidate_created, source_key, status)

    @staticmethod
    def _blocked_status(decision: EditorialDecisionModel) -> str:
        return "MANUAL_REVIEW" if decision.status == "MANUAL_REVIEW" else "REJECTED_EDITORIAL"

    def _ensure_rewrite_outbox(self, job: RewriteJobModel) -> None:
        if (
            self._session.scalar(
                select(OutboxEventModel.id).where(
                    OutboxEventModel.idempotency_key == job.idempotency_key
                )
            )
            is None
        ):
            self._session.add(
                OutboxEventModel(
                    event_type="rewrite.requested",
                    aggregate_key=job.content_key,
                    idempotency_key=job.idempotency_key,
                )
            )

    def _ensure_publication_candidate(self, content_key: str, observed_at: datetime) -> bool:
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
        mapping = self._mapping_policy(output_channel_id)
        eligible_at = observed_at.astimezone(UTC) + timedelta(minutes=mapping.delay_minutes)
        try:
            # A concurrent mapping retry can pass the read above; the durable
            # unique constraint is the final idempotency arbiter.
            with self._session.begin_nested():
                self._session.add(
                    PublicationCandidateModel(
                        output_channel_id=output_channel_id,
                        mapping_id=mapping.id,
                        content_key=content_key,
                        priority=mapping.priority,
                        eligible_at=eligible_at,
                        media_policy=mapping.media_policy,
                        state="AWAITING_REWRITE",
                    )
                )
                self._session.flush()
            return True
        except IntegrityError:
            return False

    def _mapping_policy(self, output_channel_id: int):
        """Snapshot configured mapping policy; legacy/test filters remain safe defaults."""
        try:
            mapping_id = int(self._technical_filter.mapping_id)
        except ValueError:
            mapping_id = 0
        mapping = self._session.get(ChannelMappingModel, mapping_id) if mapping_id else None
        if mapping is not None:
            if mapping.output_channel_id != output_channel_id:
                raise ValueError("Mapping output channel does not match technical filter")
            return mapping
        return _DefaultMappingPolicy()


class _DefaultMappingPolicy:
    id = None
    delay_minutes = 0
    priority = 0
    media_policy = "REUSE_SOURCE"
