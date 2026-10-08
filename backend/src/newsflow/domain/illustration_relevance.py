"""Narrow human illustration review, independent of fact/model qualification.

These are internal validated values, NOT an authentication/authorization API.
A future durable writer must authenticate the reviewer and resolve all hashes
from fresh canonical records and decoded bytes, never trust client hashes.
An allowed result attests only this exact human illustration review; it cannot
override editorial, source, draft, technical, rights or publication constraints.
No existing publication hold is removed by introducing this domain contract.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


def _identity(value: object) -> bool:
    return type(value) is int and 0 < value <= 2**63 - 1


def _aware(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True, slots=True)
class IllustrationBinding:
    candidate_id: int
    output_channel_id: int
    mapping_id: int
    content_key: str
    source_revision_id: int
    source_sha256: str
    rewrite_output_id: int
    draft_sha256: str
    media_asset_id: int
    media_sha256: str
    # Canonical origin/storage/MIME/license/attribution identity, not keywords
    # or a model confidence score. Future SQL resolver owns its construction.
    asset_metadata_sha256: str

    def __post_init__(self) -> None:
        identities = (
            self.candidate_id,
            self.output_channel_id,
            self.mapping_id,
            self.source_revision_id,
            self.rewrite_output_id,
            self.media_asset_id,
        )
        digests = (
            self.source_sha256,
            self.draft_sha256,
            self.media_sha256,
            self.asset_metadata_sha256,
        )
        if (
            not all(_identity(value) for value in identities)
            or type(self.content_key) is not str
            or not 1 <= len(self.content_key) <= 255
            or self.content_key != self.content_key.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in self.content_key)
            or not all(
                type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) for value in digests
            )
        ):
            raise ValueError("Exact canonical illustration binding is required")


class IllustrationVerdict(StrEnum):
    APPROVED_ILLUSTRATION = "APPROVED_ILLUSTRATION"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True, slots=True)
class HumanIllustrationReview:
    binding: IllustrationBinding
    reviewer_id: int
    verdict: IllustrationVerdict
    illustration_acknowledged: bool
    review_note: str
    reviewed_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.binding) is not IllustrationBinding:
            raise ValueError("Exact illustration binding is required")
        self.binding.__post_init__()
        if (
            not _identity(self.reviewer_id)
            or type(self.verdict) is not IllustrationVerdict
            or type(self.illustration_acknowledged) is not bool
            or type(self.review_note) is not str
            or not self.review_note.strip()
            or len(self.review_note) > 2048
            or "\x00" in self.review_note
            or not _aware(self.reviewed_at)
            or (self.revoked_at is not None and not _aware(self.revoked_at))
        ):
            raise ValueError("Explicit bounded human illustration review is required")


@dataclass(frozen=True, slots=True)
class IllustrationReviewResult:
    allowed: bool
    reason_code: str


def assess_illustration_review(
    review: object, *, current: object, now: datetime
) -> IllustrationReviewResult:
    """Revalidate internal evidence against freshly resolved context, fail closed.

    No coercion from JSON/SQL booleans or model evidence. This function does not
    resolve a candidate or perform I/O; a caller must still establish freshness,
    permissions and all independent hard gates before using the narrow result.
    """
    if type(current) is not IllustrationBinding:
        return IllustrationReviewResult(False, "CURRENT_ILLUSTRATION_BINDING_REQUIRED")
    try:
        current.__post_init__()
    except ValueError:
        return IllustrationReviewResult(False, "CURRENT_ILLUSTRATION_BINDING_REQUIRED")
    if type(review) is not HumanIllustrationReview:
        return IllustrationReviewResult(False, "HUMAN_ILLUSTRATION_REVIEW_REQUIRED")
    try:
        review.__post_init__()
    except ValueError:
        return IllustrationReviewResult(False, "HUMAN_ILLUSTRATION_REVIEW_REQUIRED")
    if not _aware(now):
        return IllustrationReviewResult(False, "ILLUSTRATION_REVIEW_TIME_INVALID")
    try:
        # Local wall-clock comparison ignores fold for shared tzinfo objects.
        # Only canonical instants may establish whether a review is future.
        future = review.reviewed_at.astimezone(UTC) > now.astimezone(UTC)
    except (ValueError, OverflowError):
        return IllustrationReviewResult(False, "ILLUSTRATION_REVIEW_TIME_INVALID")
    if future:
        return IllustrationReviewResult(False, "ILLUSTRATION_REVIEW_TIME_INVALID")
    if review.revoked_at is not None:
        return IllustrationReviewResult(False, "ILLUSTRATION_REVIEW_REVOKED")
    if review.binding != current:
        return IllustrationReviewResult(False, "ILLUSTRATION_REVIEW_BINDING_CHANGED")
    if review.verdict is not IllustrationVerdict.APPROVED_ILLUSTRATION:
        return IllustrationReviewResult(False, "ILLUSTRATION_REVIEW_NOT_APPROVED")
    if review.illustration_acknowledged is not True:
        return IllustrationReviewResult(False, "ILLUSTRATION_ACKNOWLEDGMENT_REQUIRED")
    return IllustrationReviewResult(True, "CURRENT_HUMAN_ILLUSTRATION_REVIEW")
