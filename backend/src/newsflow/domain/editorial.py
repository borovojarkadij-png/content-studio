"""Editorial hard-gate domain boundary.

This module deliberately has no dependency on an LLM provider.  A future
classifier may supply structured classifications, but the final eligibility
decision remains deterministic and is enforced again by downstream services.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


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
        return EditorialDecision(
            status=EditorialStatus.PASS,
            rewrite_allowed=True,
            reason_codes=(),
            protected_entities=tuple(protected_entities),
            sentiment=sentiment,
            framing=framing,
        )
