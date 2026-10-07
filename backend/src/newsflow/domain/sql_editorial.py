"""Durable editorial decision recording."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.editorial import EditorialGate, editorial_allows_rewrite
from newsflow.persistence.models import EditorialDecisionModel, RewriteJobModel


class DurableEditorialService:
    def __init__(self, session: Session, gate: EditorialGate) -> None:
        self._session = session
        self._gate = gate

    def evaluate(
        self,
        content_key: str,
        protected_entities: Sequence[str],
        sentiment: str,
        framing: str,
        *,
        source_text: str | None = None,
    ) -> EditorialDecisionModel:
        decision = self._gate.evaluate(
            text=source_text if source_text is not None else content_key,
            protected_entities=protected_entities,
            sentiment=sentiment,
            framing=framing,
        )
        stored = EditorialDecisionModel(
            content_key=content_key,
            status=decision.status.value,
            rewrite_allowed=decision.rewrite_allowed,
            reason_codes=",".join(decision.reason_codes),
            protected_entities=",".join(decision.protected_entities),
            sentiment=decision.sentiment,
            framing=decision.framing,
        )
        self._session.add(stored)
        return stored

    def get_or_evaluate(
        self,
        content_key: str,
        protected_entities: Sequence[str],
        sentiment: str,
        framing: str,
        *,
        source_text: str,
    ) -> EditorialDecisionModel:
        """Keep the first durable editorial decision authoritative for retries."""
        existing = self._session.scalar(
            select(EditorialDecisionModel).where(EditorialDecisionModel.content_key == content_key)
        )
        if existing is not None:
            return existing
        return self.evaluate(
            content_key,
            protected_entities,
            sentiment,
            framing,
            source_text=source_text,
        )

    def create_rewrite_job(
        self, decision: EditorialDecisionModel, *, output_channel_id: int | None = None
    ) -> RewriteJobModel | None:
        if not editorial_allows_rewrite(decision):
            return None
        suffix = str(output_channel_id) if output_channel_id is not None else "default"
        idempotency_key = f"rewrite.requested:{decision.content_key}:{suffix}"
        existing = self._session.scalar(
            select(RewriteJobModel).where(RewriteJobModel.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        job = RewriteJobModel(
            content_key=decision.content_key,
            output_channel_id=output_channel_id,
            idempotency_key=idempotency_key,
            state="DISPATCHED",
        )
        self._session.add(job)
        return job
