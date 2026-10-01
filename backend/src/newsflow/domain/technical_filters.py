"""Deterministic mapping-level ingress filters with no AI dependency."""

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from newsflow.providers.telegram import TelegramMessage

_URL = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_AD_MARKERS = ("#реклама", "#ad", "рекламная публикация")


@dataclass(frozen=True, slots=True)
class TechnicalFilterDecision:
    accepted: bool
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class MappingTechnicalFilter:
    mapping_id: str
    allowed_media_types: frozenset[str] = field(default_factory=lambda: frozenset({"text", "photo"}))
    blocked_domains: frozenset[str] = field(default_factory=frozenset)
    ad_markers: tuple[str, ...] = _AD_MARKERS

    def evaluate(self, message: TelegramMessage) -> TechnicalFilterDecision:
        if message.media_type not in self.allowed_media_types:
            return TechnicalFilterDecision(False, "UNSUPPORTED_MEDIA")
        text = message.text.strip()
        if not text:
            return TechnicalFilterDecision(False, "EMPTY_CONTENT")
        normalized_text = text.casefold()
        if any(marker.casefold() in normalized_text for marker in self.ad_markers):
            return TechnicalFilterDecision(False, "ADVERTISING")
        if any(self._is_blocked_host(urlparse(url).hostname) for url in _URL.findall(text)):
            return TechnicalFilterDecision(False, "FORBIDDEN_LINK")
        return TechnicalFilterDecision(True)

    def _is_blocked_host(self, host: str | None) -> bool:
        if host is None:
            return False
        normalized_host = host.casefold().removeprefix("www.")
        return any(
            normalized_host == domain.casefold().removeprefix("www.")
            or normalized_host.endswith(f".{domain.casefold().removeprefix('www.')}")
            for domain in self.blocked_domains
        )
