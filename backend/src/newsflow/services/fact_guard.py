"""Conservative deterministic anchors, NOT semantic fact verification.

Preserving anchors allows only a review draft. It never authorizes unattended
approval: reversing a claim can preserve every number/name/link in a source.
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

_NUMBERS = re.compile(r"[+-]?\d+(?:[.,:/-]\d+)*%?")
_LINKS = re.compile(r"https?://[^\s<>\"«»]+", re.IGNORECASE)
_MENTIONS = re.compile(r"(?<!\w)@[A-Za-z0-9_]+")
_QUOTES = re.compile(r'«([^»\n]*)»|“([^”\n]*)”|"([^"\n]*)"')
_TEXT_LIMIT = 32000


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("−", "-")


def _contains_literal(text: str, literal: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(literal) + r"(?!\w)", text, re.IGNORECASE) is not None


@dataclass(frozen=True, slots=True)
class FactCheckReport:
    anchors_preserved: bool
    reason_codes: tuple[str, ...]
    requires_manual_review: bool = True


class FactPreservationBlocked(PermissionError):
    def __init__(self, report: FactCheckReport) -> None:
        # Do not echo provider output, prompts or credentials in an exception.
        super().__init__("FACT_PRESERVATION_BLOCKED")
        self.reason_codes = report.reason_codes


class FactGuard:
    def validate_source(self, source_text: str) -> None:
        if not isinstance(source_text, str) or not source_text.strip():
            raise ValueError("Source text is required")
        if len(source_text) > _TEXT_LIMIT:
            raise ValueError("Source text exceeds the rewrite limit")

    def check(
        self, source_text: str, rewritten_text: str, *, required_literals: Sequence[str] = ()
    ) -> FactCheckReport:
        self.validate_source(source_text)
        if not isinstance(rewritten_text, str) or not rewritten_text.strip():
            return FactCheckReport(False, ("EMPTY_REWRITE",))
        if len(rewritten_text) > _TEXT_LIMIT:
            return FactCheckReport(False, ("TEXT_LIMIT_EXCEEDED",))
        source, rewritten = _normalize(source_text), _normalize(rewritten_text)
        reasons = []
        if Counter(_NUMBERS.findall(source)) != Counter(_NUMBERS.findall(rewritten)):
            reasons.append("NUMERIC_FACTS_CHANGED")
        source_links = Counter(link.rstrip(".,;:!?)") for link in _LINKS.findall(source))
        output_links = Counter(link.rstrip(".,;:!?)") for link in _LINKS.findall(rewritten))
        if source_links != output_links:
            reasons.append("LINKS_CHANGED")
        if Counter(_MENTIONS.findall(source)) != Counter(_MENTIONS.findall(rewritten)):
            reasons.append("MENTIONS_CHANGED")
        source_quotes = Counter(
            next(part for part in match if part) for match in _QUOTES.findall(source) if any(match)
        )
        output_quotes = Counter(
            next(part for part in match if part)
            for match in _QUOTES.findall(rewritten)
            if any(match)
        )
        if source_quotes != output_quotes:
            reasons.append("QUOTES_CHANGED")
        for literal in required_literals:
            if not isinstance(literal, str) or not literal.strip() or len(literal) > 255:
                raise ValueError("Required fact literal is invalid")
            normalized = _normalize(literal.strip())
            if not _contains_literal(source, normalized):
                raise ValueError("Required fact literal is not present in the source")
            if (
                not _contains_literal(rewritten, normalized)
                and "REQUIRED_LITERAL_MISSING" not in reasons
            ):
                reasons.append("REQUIRED_LITERAL_MISSING")
        return FactCheckReport(not reasons, tuple(reasons))

    def require_preserved(
        self, source_text: str, rewritten_text: str, *, required_literals: Sequence[str] = ()
    ) -> FactCheckReport:
        report = self.check(source_text, rewritten_text, required_literals=required_literals)
        if not report.anchors_preserved:
            raise FactPreservationBlocked(report)
        return report
