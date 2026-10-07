"""Strict semantic evidence contract; parsing a verdict is not model evaluation."""

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from newsflow.services.fact_guard import FactGuard

PROMPT_VERSION = "semantic-facts-v1"
BENCHMARK_VERSION = "semantic-facts-v1"


def text_digest(value: str) -> str:
    # Exact UTF-8, not normalized: editing whitespace invalidates previous evidence.
    return sha256(value.encode("utf-8")).hexdigest()


def parse_semantic_evidence(raw: str) -> object:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 262144:
        raise ValueError("SEMANTIC_EVIDENCE_LIMIT")

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("SEMANTIC_DUPLICATE_KEY")
            value[key] = item
        return value

    return json.loads(raw, object_pairs_hook=unique_pairs)


class ClaimEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_quote: str = Field(max_length=32000)
    draft_quote: str = Field(max_length=32000)
    relation: Literal["SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "OMITTED", "UNCERTAIN"]


class SemanticAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    verdict: Literal["PRESERVED", "CHANGED", "UNCERTAIN"]
    source_complete: bool
    draft_complete: bool
    claims: list[ClaimEvidence] = Field(min_length=1, max_length=64)


@dataclass(frozen=True, slots=True)
class SemanticReport:
    verdict: str
    reason_codes: tuple[str, ...]
    evidence_json: str = "{}"

    @property
    def eligible(self) -> bool:
        return self.verdict == "PRESERVED" and not self.reason_codes


def _covered(text: str, quotes: list[str]) -> bool:
    covered = bytearray(len(text))
    for quote in quotes:
        if not quote:
            continue
        start = text.find(quote)
        while start >= 0:
            covered[start : start + len(quote)] = b"\x01" * len(quote)
            start = text.find(quote, start + len(quote))
    return all(covered[index] for index, char in enumerate(text) if char.isalnum())


def assess_semantic_facts(source: str, draft: str, value: object) -> SemanticReport:
    anchors = FactGuard().check(source, draft)
    if not anchors.anchors_preserved:
        return SemanticReport("CHANGED", anchors.reason_codes)
    try:
        assessment = SemanticAssessment.model_validate(value)
        canonical = json.dumps(assessment.model_dump(), ensure_ascii=False, sort_keys=True)
        if len(canonical.encode("utf-8")) > 262144:
            return SemanticReport("ERROR", ("SEMANTIC_EVIDENCE_LIMIT",))
    except (ValidationError, TypeError, ValueError):
        return SemanticReport("ERROR", ("SEMANTIC_SCHEMA_INVALID",))
    source_quotes, draft_quotes = [], []
    relations = set()
    for claim in assessment.claims:
        source_quote, draft_quote = claim.source_quote, claim.draft_quote
        if (source_quote and source_quote not in source) or (
            draft_quote and draft_quote not in draft
        ):
            return SemanticReport("ERROR", ("SEMANTIC_QUOTE_NOT_FOUND",))
        if (
            not source_quote
            and not draft_quote
            or claim.relation in {"SUPPORTED", "CONTRADICTED"}
            and (not source_quote or not draft_quote)
            or claim.relation == "OMITTED"
            and (not source_quote or draft_quote)
            or claim.relation == "UNSUPPORTED"
            and not draft_quote
        ):
            return SemanticReport("ERROR", ("SEMANTIC_CLAIM_INVALID",))
        source_quotes.append(source_quote)
        draft_quotes.append(draft_quote)
        relations.add(claim.relation)
    if relations & {"CONTRADICTED", "UNSUPPORTED", "OMITTED"}:
        return SemanticReport("CHANGED", ("SEMANTIC_FACTS_CHANGED",), canonical)
    if (
        assessment.verdict != "PRESERVED"
        or "UNCERTAIN" in relations
        or not assessment.source_complete
        or not assessment.draft_complete
        or not _covered(source, source_quotes)
        or not _covered(draft, draft_quotes)
    ):
        return SemanticReport("UNCERTAIN", ("SEMANTIC_NOT_FULLY_SUPPORTED",), canonical)
    return SemanticReport("PRESERVED", (), canonical)
