"""Deterministic mapping-level ingress filters with no AI dependency."""

import re
from dataclasses import dataclass, field
from hashlib import sha256
from urllib.parse import unquote, urlparse

from newsflow.providers.telegram import TelegramMessage

_URL = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
_AD_MARKERS = ("#реклама", "#ad", "рекламная публикация")
_YOUTUBE_DOMAINS = frozenset({"youtube.com", "youtu.be", "youtube-nocookie.com"})
_LINK_CANDIDATES = re.compile(
    r"(?:https?://|(?<!\S)//)[^\s<>()]+|"
    r"(?<![\w/@.-])(?:[a-z0-9-]+\.)*(?:youtube\.com|youtu\.be|youtube-nocookie\.com)[^\s<>()]*",
    re.IGNORECASE,
)


def visible_link_exclusion_reason(text: str) -> str | None:
    """Canonical visible hosts only; malformed destinations fail closed, no RPC."""
    for value in _LINK_CANDIDATES.findall(text):
        if "\\" in value:
            return "INVALID_LINK"
        value = value.rstrip(".,;:!?…\"'»”")
        try:
            host = urlparse(
                value if value.startswith("//") or "://" in value else "https://" + value
            ).hostname
            if host is None:
                return "INVALID_LINK"
            host = unquote(host).rstrip(".").encode("idna").decode("ascii").casefold().rstrip(".")
        except (ValueError, UnicodeError):
            return "INVALID_LINK"
        if any(host == domain or host.endswith("." + domain) for domain in _YOUTUBE_DOMAINS):
            return "YOUTUBE_LINK"
    return None


def source_link_exclusion_reason(text, destinations):
    if destinations is None:
        return "SOURCE_LINKS_UNKNOWN"
    if (
        not isinstance(destinations, tuple)
        or len(destinations) > 100
        or any(
            not isinstance(value, str)
            or not value
            or len(value) > 2048
            or any(ord(char) < 32 for char in value)
            for value in destinations
        )
    ):
        return "SOURCE_LINKS_INVALID"
    return visible_link_exclusion_reason(text) or next(
        (reason for value in destinations if (reason := visible_link_exclusion_reason(value))),
        None,
    )


def stored_source_link_exclusion_reason(revision):
    values = revision.link_destinations
    if values is not None and not isinstance(values, list):
        return "SOURCE_LINKS_INVALID"
    return source_link_exclusion_reason(
        revision.source_text, tuple(values) if values is not None else None
    )


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
        if not text and message.media_type != "video":
            return TechnicalFilterDecision(False, "EMPTY_CONTENT")
        normalized_text = text.casefold()
        if any(marker.casefold() in normalized_text for marker in self.ad_markers):
            return TechnicalFilterDecision(False, "ADVERTISING")
        link_reason = source_link_exclusion_reason(text, message.link_destinations)
        if link_reason is not None:
            return TechnicalFilterDecision(False, link_reason)
        destinations = " ".join(message.link_destinations)
        if any(
            self._is_blocked_host(urlparse(url).hostname)
            for url in _URL.findall(text + " " + destinations)
        ):
            return TechnicalFilterDecision(False, "FORBIDDEN_LINK")
        if message.album_id is not None:
            # A single caption is not proof that every album member passed the
            # media/advertising/link policy. Until a durable complete manifest
            # is validated, neither ingress nor a stale/manual task may rewrite it.
            return TechnicalFilterDecision(False, "ALBUM_NORMALIZATION_REQUIRED")
        if message.media_type == "video":
            return TechnicalFilterDecision(False, "VIDEO_MANUAL_REVIEW_REQUIRED")
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
