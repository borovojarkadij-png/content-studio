"""Read-only delivery history, independent of current permission to send."""

from sqlalchemy import select

from newsflow.persistence.models import PlannedPublicationModel, PublicationJobModel
from newsflow.services.durable_semantic_runner import _utc


class PublicationJobReader:
    def __init__(self, session):
        self._session = session

    def get_status(self, planned_id):
        item = self._session.get(PlannedPublicationModel, planned_id, populate_existing=True)
        if item is None:
            raise LookupError("Planned publication was not found")
        job = self._session.scalar(
            select(PublicationJobModel)
            .where(PublicationJobModel.planned_id == item.id)
            .execution_options(populate_existing=True)
        )
        if job is not None and (
            job.state
            not in {
                "QUEUED",
                "CLAIMED",
                "SENDING",
                "SUCCEEDED",
                "BLOCKED",
                "FAILED",
                "NEEDS_RECONCILIATION",
            }
            or not 0 <= job.attempts <= 2
        ):
            raise ValueError("Invalid persisted publication state")
        if job is not None and job.last_error_code not in {
            None,
            "PUBLICATION_ATTEMPTS_EXHAUSTED",
            "PUBLICATION_SEND_OUTCOME_UNKNOWN",
            "PUBLICATION_PREFLIGHT_BLOCKED",
            "PUBLICATION_TRANSPORT_GUARD_MISSING",
            "PUBLICATION_PREPARATION_FAILED",
            "PUBLICATION_KNOWN_NOT_SENT",
            "PUBLICATION_RECEIPT_INVALID",
        }:
            # Never expose arbitrary stored provider exception text through an
            # unauthenticated metadata endpoint, even after data corruption.
            raise ValueError("Invalid persisted publication reason code")
        return {
            "planned_id": item.id,
            "candidate_id": item.candidate_id,
            "output_channel_id": item.output_channel_id,
            "job_id": job.id if job else None,
            "state": job.state if job else "NOT_QUEUED",
            "attempts": job.attempts if job else 0,
            "sent_message_id": job.sent_message_id if job else None,
            "completed_at": _utc(job.completed_at).isoformat()
            if job and job.completed_at
            else None,
            "reason_code": job.last_error_code if job else None,
            # Public send controls remain unavailable; server worker opt-in is
            # separate configuration, not live authorization/delivery proof.
            "live_publication_available": False,
        }
