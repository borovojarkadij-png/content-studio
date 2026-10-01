"""Durable editorial decision recording."""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from newsflow.domain.editorial import EditorialGate
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
    ) -> EditorialDecisionModel:
        decision = self._gate.evaluate(
            text=content_key,
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

    def create_rewrite_job(self, decision: EditorialDecisionModel) -> RewriteJobModel | None:
        if decision.status != "PASS" or not decision.rewrite_allowed:
            return None
        job = RewriteJobModel(
            content_key=decision.content_key,
            idempotency_key=f"rewrite.requested:{decision.content_key}",
            state="DISPATCHED",
        )
        self._session.add(job)
        return job
