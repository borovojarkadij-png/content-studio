"""Deterministic mapping-level ingress filters with no AI dependency."""

import re
from dataclasses import dataclass, field
from hashlib import sha256
from urllib.parse import unquote, urlparse

from newsflow.providers.telegram import TelegramMessage

_AD_MARKERS = ("#реклама", "#ad", "рекламная публикация")
_YOUTUBE_DOMAINS = frozenset({"youtube.com", "youtu.be", "youtube-nocookie.com"})
_LINK_CANDIDATES = re.compile(
    r"(?:[a-z][a-z0-9+.-]*://|(?<![\w:])//)[^\s<>()]+|"
    r"(?<![\w/@.-])(?:[a-z0-9-]+\.)*(?:youtube\.com|youtu\.be|youtube-nocookie\.com)[^\s<>()]*",
    re.IGNORECASE,
)


def _strict_host(value: str) -> str:
    """One bounded destination identity; decode once, never repair ambiguity."""
    if (
        not value
        or len(value) > 2048
        or "\\" in value
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
        or re.search(r"%(?![0-9a-fA-F]{2})", value)
    ):
        raise ValueError("Invalid destination")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https", ""} or not parsed.netloc:
        raise ValueError("Unknown destination")
    # Userinfo is not the destination: https://youtube.com@example.org goes
    # to example.org. Only the parsed host participates in domain policy.
    _ = parsed.port  # Invalid/non-numeric/out-of-range ports fail closed.
    host = unquote(parsed.hostname or "", errors="strict")
    if any(char in host for char in "%/\\:@?#") or any(char.isspace() for char in host):
        raise ValueError("Encoded authority separator")
    host = host.rstrip(".").encode("idna").decode("ascii").casefold().rstrip(".")
    if len(host) > 253 or any(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
        for label in host.split(".")
    ):
        raise ValueError("Invalid hostname")
    return host


def _destination_reason(value, blocked_domains=()):
    try:
        host = _strict_host(value)
        blocked = {
            _strict_host("https://" + domain).removeprefix("www.") for domain in blocked_domains
        }
    except (ValueError, UnicodeError):
        return "INVALID_LINK"
    for domains, reason in ((_YOUTUBE_DOMAINS, "YOUTUBE_LINK"), (blocked, "FORBIDDEN_LINK")):
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return reason
    return None


def visible_link_exclusion_reason(text: str, blocked_domains=()) -> str | None:
    """Visible prose and hidden links share exactly the same host identity."""
    values = _LINK_CANDIDATES.findall(text)
    if len(values) > 100:
        return "INVALID_LINK"
    for value in values:
        value = value.rstrip(".,;:!?…\"'»”")
        if not value.startswith("//") and "://" not in value:
            value = "https://" + value
        if reason := _destination_reason(value, blocked_domains):
            return reason
    return None


def source_link_exclusion_reason(text, destinations, blocked_domains=()):
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
    return visible_link_exclusion_reason(text, blocked_domains) or next(
        (
            reason
            for value in destinations
            if (reason := _destination_reason(value, blocked_domains))
        ),
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
        link_reason = source_link_exclusion_reason(
            text, message.link_destinations, self.blocked_domains
        )
        if link_reason is not None:
            return TechnicalFilterDecision(False, link_reason)
        if message.album_id is not None:
            # A single caption is not proof that every album member passed the
            # media/advertising/link policy. Until a durable complete manifest
            # is validated, neither ingress nor a stale/manual task may rewrite it.
            return TechnicalFilterDecision(False, "ALBUM_NORMALIZATION_REQUIRED")
        if message.media_type == "video":
            return TechnicalFilterDecision(False, "VIDEO_MANUAL_REVIEW_REQUIRED")
        return TechnicalFilterDecision(True)
