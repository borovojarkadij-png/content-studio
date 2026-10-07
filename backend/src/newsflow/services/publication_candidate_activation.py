"""Move mapped candidates to scheduler eligibility after durable rewrite completion."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    EditorialDecisionModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
)


class RewriteCandidateActivationService:
    """No transport, AI call or rewrite dispatch occurs at this transition."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def activate(self, rewrite_job_id: int) -> int:
        with self._session.begin():
            job = self._session.scalar(
                select(RewriteJobModel)
                .where(RewriteJobModel.id == rewrite_job_id)
                .with_for_update()
            )
            if job is None or job.state != "SUCCEEDED":
                return 0
            decision = self._session.scalar(
                select(EditorialDecisionModel)
                .where(EditorialDecisionModel.content_key == job.content_key)
                .with_for_update()
            )
            if job.output_channel_id is None:
                return 0
            candidates = self._session.scalars(
                select(PublicationCandidateModel)
                .where(
                    PublicationCandidateModel.content_key == job.content_key,
                    PublicationCandidateModel.output_channel_id == job.output_channel_id,
                    PublicationCandidateModel.state == "AWAITING_REWRITE",
                )
                .with_for_update()
            ).all()
            if not editorial_allows_rewrite(decision):
                for candidate in candidates:
                    candidate.state = "BLOCKED_EDITORIAL"
                return 0
            approved_output = self._session.scalar(
                select(RewriteOutputModel.id).where(
                    RewriteOutputModel.rewrite_job_id == job.id,
                    RewriteOutputModel.approval_state == "APPROVED",
                )
            )
            if approved_output is None:
                return 0
            for candidate in candidates:
                candidate.state = "READY"
            return len(candidates)
