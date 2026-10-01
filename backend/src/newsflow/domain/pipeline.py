"""Telegram ingestion orchestration boundary."""

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

from newsflow.domain.editorial import EditorialGate, EditorialStatus
from newsflow.services.rewrite import RewriteService


@dataclass(frozen=True, slots=True)
class PipelineResult:
    status: str
    rewrite_job_created: bool = False


class IngestionPipeline:
    """Runs cheap deterministic checks before the editorial and AI boundaries."""

    def __init__(self, editorial_gate: EditorialGate, rewrite_service: RewriteService) -> None:
        self._editorial_gate = editorial_gate
        self._rewrite_service = rewrite_service
        self._seen_fingerprints: set[str] = set()

    def process(
        self,
        *,
        text: str,
        content_type: str,
        protected_entities: Sequence[str],
        sentiment: str,
        framing: str,
    ) -> PipelineResult:
        if content_type not in {"text", "photo"}:
            return PipelineResult("REJECTED_TECHNICAL")

        fingerprint = sha256(text.strip().casefold().encode()).hexdigest()
        if fingerprint in self._seen_fingerprints:
            return PipelineResult("REJECTED_DUPLICATE")
        self._seen_fingerprints.add(fingerprint)

        decision = self._editorial_gate.evaluate(
            text=text,
            protected_entities=protected_entities,
            sentiment=sentiment,
            framing=framing,
        )
        if decision.status is EditorialStatus.REJECT:
            return PipelineResult("REJECTED_EDITORIAL")
        if decision.status is EditorialStatus.MANUAL_REVIEW:
            return PipelineResult("MANUAL_REVIEW")

        self._rewrite_service.rewrite(text, decision)
        return PipelineResult("REWRITE_DISPATCHED", rewrite_job_created=True)
