"""Telegram vertical-slice domain entities and state machines."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class IncomingPostState(StrEnum):
    RECEIVED = "RECEIVED"
    TECHNICAL_REJECTED = "TECHNICAL_REJECTED"
    DEDUPLICATED = "DEDUPLICATED"
    EDITORIAL_PENDING = "EDITORIAL_PENDING"
    EDITORIAL_REJECTED = "EDITORIAL_REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ELIGIBLE = "ELIGIBLE"
    REWRITE_QUEUED = "REWRITE_QUEUED"


class InvalidStateTransition(ValueError):
    """Raised when a controller or worker requests an unsafe lifecycle jump."""


_INCOMING_TRANSITIONS = {
    IncomingPostState.RECEIVED: {
        IncomingPostState.TECHNICAL_REJECTED,
        IncomingPostState.DEDUPLICATED,
        IncomingPostState.EDITORIAL_PENDING,
    },
    IncomingPostState.EDITORIAL_PENDING: {
        IncomingPostState.EDITORIAL_REJECTED,
        IncomingPostState.MANUAL_REVIEW,
        IncomingPostState.ELIGIBLE,
    },
    IncomingPostState.MANUAL_REVIEW: {IncomingPostState.ELIGIBLE},
    IncomingPostState.ELIGIBLE: {IncomingPostState.REWRITE_QUEUED},
}


def transition_incoming_post(current: IncomingPostState, target: IncomingPostState) -> IncomingPostState:
    if target not in _INCOMING_TRANSITIONS.get(current, set()):
        raise InvalidStateTransition(f"{current} cannot transition to {target}")
    return target


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    telegram_account_id: str
    donor_channel_id: str
    telegram_message_id: int

    @property
    def source_key(self) -> str:
        return f"{self.telegram_account_id}:{self.donor_channel_id}:{self.telegram_message_id}"


@dataclass(frozen=True, slots=True)
class ContentRevision:
    source_identity: SourceIdentity
    revision_number: int
    source_text: str
    observed_at: datetime

    @classmethod
    def new(cls, identity: SourceIdentity, source_text: str, observed_at: datetime) -> "ContentRevision":
        return cls(identity, 1, source_text, observed_at)

    @property
    def source_key(self) -> str:
        return self.source_identity.source_key

    def next_revision(self, source_text: str, observed_at: datetime) -> "ContentRevision":
        return ContentRevision(self.source_identity, self.revision_number + 1, source_text, observed_at)


@dataclass(frozen=True, slots=True)
class ChannelMapping:
    donor_channel_id: str
    output_channel_id: str
    intake_percent: int
    target_mix_percent: int

    def __post_init__(self) -> None:
        if not 0 <= self.intake_percent <= 100 or not 0 <= self.target_mix_percent <= 100:
            raise ValueError("Mapping percentages must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class DonorImportEntry:
    canonical_identifier: str


@dataclass(frozen=True, slots=True)
class DonorImportResult:
    accepted: tuple[DonorImportEntry, ...]
    rejected: tuple[str, ...]


_USERNAME = re.compile(r"^(?:https?://)?(?:t\.me/)?@?([A-Za-z][A-Za-z0-9_]{3,31})$")
_NUMERIC_ID = re.compile(r"^-100\d+$")


def parse_donor_import(raw_text: str) -> DonorImportResult:
    accepted: list[DonorImportEntry] = []
    rejected: list[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        username = _USERNAME.match(candidate)
        if username:
            accepted.append(DonorImportEntry(f"@{username.group(1)}"))
        elif _NUMERIC_ID.match(candidate):
            accepted.append(DonorImportEntry(candidate))
        else:
            rejected.append(candidate)
    return DonorImportResult(tuple(accepted), tuple(rejected))
