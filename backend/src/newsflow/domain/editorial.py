"""Editorial hard-gate domain boundary.

This module deliberately has no dependency on an LLM provider.  A future
classifier may supply structured classifications, but the final eligibility
decision remains deterministic and is enforced again by downstream services.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class EditorialStatus(StrEnum):
    PASS = "PASS"
    REJECT = "REJECT"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True, slots=True)
class EditorialDecision:
    status: EditorialStatus
    rewrite_allowed: bool
    reason_codes: tuple[str, ...]
    protected_entities: tuple[str, ...]
    sentiment: str
    framing: str


class EditorialGate:
    """Applies the hard policy rule before any rewrite can be dispatched."""

    def evaluate(
        self,
        *,
        text: str,
        protected_entities: Sequence[str],
        sentiment: str,
        framing: str,
    ) -> EditorialDecision:
        del text  # Classifier input is intentionally not used by this policy adapter yet.
        is_hostile = sentiment.lower() == "negative" or framing.lower() == "hostile"
        has_protected_entity = bool(protected_entities)
        if is_hostile and has_protected_entity:
            return EditorialDecision(
                status=EditorialStatus.REJECT,
                rewrite_allowed=False,
                reason_codes=("PROTECTED_ENTITY_NEGATIVE",),
                protected_entities=tuple(protected_entities),
                sentiment=sentiment,
                framing=framing,
            )
        if sentiment.lower() not in {"negative", "neutral", "positive"} or framing.lower() not in {
            "hostile",
            "neutral",
            "positive",
        }:
            return EditorialDecision(
                status=EditorialStatus.MANUAL_REVIEW,
                rewrite_allowed=False,
                reason_codes=("CLASSIFICATION_REQUIRED",),
                protected_entities=tuple(protected_entities),
                sentiment=sentiment,
                framing=framing,
            )
        return EditorialDecision(
            status=EditorialStatus.PASS,
            rewrite_allowed=True,
            reason_codes=(),
            protected_entities=tuple(protected_entities),
            sentiment=sentiment,
            framing=framing,
        )


class EditorialRecord(Protocol):
    status: str
    rewrite_allowed: bool
    protected_entities: Sequence[str] | str
    sentiment: str
    framing: str


def editorial_allows_rewrite(decision: EditorialDecision | EditorialRecord | None) -> bool:
    """Recheck flags AND protected-entity constraints for domain/durable records."""
    if (
        decision is None
        or decision.status != EditorialStatus.PASS
        or decision.rewrite_allowed is not True
    ):
        return False
    entities = decision.protected_entities
    if isinstance(entities, str):
        entities = entities.split(",")
    current = EditorialGate().evaluate(
        text="",
        protected_entities=tuple(entity.strip() for entity in entities if entity.strip()),
        sentiment=decision.sentiment,
        framing=decision.framing,
    )
    return current.status is EditorialStatus.PASS and current.rewrite_allowed
