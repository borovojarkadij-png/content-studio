"""Deterministic mapping-level ingress filters with no AI dependency."""

import re
from dataclasses import dataclass, field
from hashlib import sha256
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
    output_channel_id: int | None = None
    allowed_media_types: frozenset[str] = field(
        default_factory=lambda: frozenset({"text", "photo"})
    )
    blocked_domains: frozenset[str] = field(default_factory=frozenset)
    ad_markers: tuple[str, ...] = _AD_MARKERS
    intake_percent: int = 100

    def evaluate(self, message: TelegramMessage) -> TechnicalFilterDecision:
        if not 0 <= self.intake_percent <= 100:
            raise ValueError("Intake percent must be between zero and 100")
        seed = f"{self.mapping_id}:{message.account_id}:{message.donor_identifier}:{message.message_id}"
        bucket = int.from_bytes(sha256(seed.encode()).digest()[:8], "big") % 100
        if bucket >= self.intake_percent:
            return TechnicalFilterDecision(False, "INTAKE_SAMPLE")
        if message.media_type not in self.allowed_media_types:
            return TechnicalFilterDecision(False, "UNSUPPORTED_MEDIA")
        if message.media_protected is True:
            return TechnicalFilterDecision(False, "PROTECTED_CONTENT")
        text = message.text.strip()
        if not text:
            return TechnicalFilterDecision(False, "EMPTY_CONTENT")
        normalized_text = text.casefold()
        if any(marker.casefold() in normalized_text for marker in self.ad_markers):
            return TechnicalFilterDecision(False, "ADVERTISING")
        if any(self._is_blocked_host(urlparse(url).hostname) for url in _URL.findall(text)):
            return TechnicalFilterDecision(False, "FORBIDDEN_LINK")
        if message.album_id is not None:
            # A single caption is not proof that every album member passed the
            # media/advertising/link policy. Until a durable complete manifest
            # is validated, neither ingress nor a stale/manual task may rewrite it.
            return TechnicalFilterDecision(False, "ALBUM_NORMALIZATION_REQUIRED")
        return TechnicalFilterDecision(True)

    def _is_blocked_host(self, host: str | None) -> bool:
        if host is None:
            return False
        normalized_host = (
            host.rstrip(".").encode("idna").decode("ascii").casefold().removeprefix("www.")
        )
        return any(
            normalized_host
            == domain.rstrip(".").encode("idna").decode("ascii").casefold().removeprefix("www.")
            or normalized_host.endswith(
                f".{domain.rstrip('.').encode('idna').decode('ascii').casefold().removeprefix('www.')}"
            )
            for domain in self.blocked_domains
        )
