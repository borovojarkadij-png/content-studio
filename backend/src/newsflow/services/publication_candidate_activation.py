"""Move mapped candidates to scheduler eligibility after durable rewrite completion."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    EditorialDecisionModel,
    PublicationCandidateModel,
    RewriteJobModel,
)


class RewriteCandidateActivationService:
    """No transport, AI call or rewrite dispatch occurs at this transition."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def activate(self, content_key: str) -> int:
        with self._session.begin():
            job = self._session.scalar(
                select(RewriteJobModel)
                .where(RewriteJobModel.content_key == content_key)
                .with_for_update()
            )
            if job is None or job.state != "SUCCEEDED":
                return 0
            decision = self._session.scalar(
                select(EditorialDecisionModel)
                .where(EditorialDecisionModel.content_key == content_key)
                .with_for_update()
            )
            candidates = self._session.scalars(
                select(PublicationCandidateModel)
                .where(
                    PublicationCandidateModel.content_key == content_key,
                    PublicationCandidateModel.state == "AWAITING_REWRITE",
                )
                .with_for_update()
            ).all()
            if decision is None or decision.status != "PASS" or not decision.rewrite_allowed:
                for candidate in candidates:
                    candidate.state = "BLOCKED_EDITORIAL"
                return 0
            for candidate in candidates:
                candidate.state = "READY"
            return len(candidates)
