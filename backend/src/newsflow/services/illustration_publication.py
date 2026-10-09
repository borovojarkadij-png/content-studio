"""Fresh narrow human review evidence; independent publication gates still apply."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from newsflow.domain.illustration_relevance import (
    HumanIllustrationReview,
    IllustrationBinding,
    IllustrationVerdict,
    assess_illustration_review,
)
from newsflow.persistence.models import IllustrationReviewRecordModel
from newsflow.services.durable_semantic_runner import _utc
from newsflow.services.illustration_binding import IllustrationBindingResolver
from newsflow.services.illustration_review import record_binding
from newsflow.services.publication import PublicationBlocked


@dataclass(frozen=True, slots=True)
class CurrentIllustrationReview:
    review_id: int
    binding: IllustrationBinding


def require_current_illustration_review(session, media_root, candidate_id, *, now: datetime):
    """Read newest REVIEW only, re-resolve bytes and refuse any intervening change."""
    resolver = IllustrationBindingResolver(session, media_root)

    def read():
        binding = resolver.resolve(candidate_id)
        row = session.scalar(
            select(IllustrationReviewRecordModel)
            .where(
                IllustrationReviewRecordModel.candidate_id == candidate_id,
                IllustrationReviewRecordModel.record_kind == "REVIEW",
            )
            .order_by(IllustrationReviewRecordModel.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if row is None or row.provenance != "AUTHENTICATED_HUMAN_V1":
            raise PublicationBlocked("HUMAN_ILLUSTRATION_REVIEW_REQUIRED")
        revocation = session.scalar(
            select(IllustrationReviewRecordModel)
            .where(IllustrationReviewRecordModel.revokes_review_id == row.id)
            .execution_options(populate_existing=True)
        )
        review = HumanIllustrationReview(
            record_binding(row),
            row.reviewer_id,
            IllustrationVerdict(row.verdict),
            row.illustration_acknowledged,
            row.review_note,
            _utc(row.reviewed_at),
            _utc(revocation.reviewed_at) if revocation else None,
        )
        result = assess_illustration_review(review, current=binding, now=now)
        if not result.allowed:
            raise PublicationBlocked(result.reason_code)
        return CurrentIllustrationReview(row.id, binding)

    try:
        first = read()
        if read() != first:
            raise PublicationBlocked("ILLUSTRATION_REVIEW_CHANGED_DURING_READ")
        return first
    except (PermissionError, ValueError, TypeError):
        raise PublicationBlocked("HUMAN_ILLUSTRATION_REVIEW_REQUIRED") from None
