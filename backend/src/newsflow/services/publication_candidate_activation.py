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
from newsflow.services.automatic_approval import approval_is_current
from newsflow.services.source_revisions import source_is_current


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
            if not source_is_current(self._session, job.content_key):
                return 0  # Retain history; never activate an old or missing source revision.
            approved_output = self._session.scalar(
                select(RewriteOutputModel).where(
                    RewriteOutputModel.rewrite_job_id == job.id,
                    RewriteOutputModel.approval_state == "APPROVED",
                )
            )
            if approved_output is None or not approval_is_current(self._session, approved_output):
                return 0
            for candidate in candidates:
                candidate.state = "READY"
            return len(candidates)
