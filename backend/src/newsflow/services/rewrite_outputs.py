"""Durable, per-output rewrite drafts with explicit approval."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    EditorialDecisionModel,
    RewriteJobModel,
    RewriteOutputModel,
)


class RewriteOutputBlocked(PermissionError):
    """The rewrite result cannot be stored or approved safely."""


class RewriteOutputConflict(ValueError):
    """An idempotent output write conflicts with an existing durable draft."""


def _project(output: RewriteOutputModel) -> dict[str, object]:
    return {
        "id": output.id,
        "rewrite_job_id": output.rewrite_job_id,
        "output_channel_id": output.output_channel_id,
        "content_key": output.content_key,
        "rewritten_text": output.rewritten_text,
        "approval_state": output.approval_state,
    }


class RewriteOutputService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_succeeded_output(self, rewrite_job_id: int, rewritten_text: str) -> dict[str, object]:
        text = rewritten_text.strip()
        if not text:
            raise ValueError("Rewritten text is required")
        try:
            job = self._session.scalar(
                select(RewriteJobModel)
                .where(RewriteJobModel.id == rewrite_job_id)
                .with_for_update()
            )
            if job is None or job.state != "SUCCEEDED" or job.output_channel_id is None:
                raise RewriteOutputBlocked("Rewrite job is not a succeeded mapped job")
            self._require_editorial_pass(job.content_key)
            existing = self._session.scalar(
                select(RewriteOutputModel)
                .where(RewriteOutputModel.rewrite_job_id == rewrite_job_id)
                .with_for_update()
            )
            if existing is not None:
                if existing.rewritten_text != text:
                    raise RewriteOutputConflict("Rewrite output already exists with different text")
                result = _project(existing)
            else:
                output = RewriteOutputModel(
                    rewrite_job_id=job.id,
                    output_channel_id=job.output_channel_id,
                    content_key=job.content_key,
                    rewritten_text=text,
                    approval_state="PENDING",
                )
                self._session.add(output)
                self._session.flush()
                result = _project(output)
            self._session.commit()
            return result
        except IntegrityError:
            self._session.rollback()
            raise RewriteOutputConflict("Rewrite output already exists") from None
        except Exception:
            self._session.rollback()
            raise

    def approve(self, output_id: int) -> dict[str, object]:
        try:
            output = self._session.scalar(
                select(RewriteOutputModel)
                .where(RewriteOutputModel.id == output_id)
                .with_for_update()
            )
            if output is None:
                raise LookupError("Rewrite output was not found")
            self._require_editorial_pass(output.content_key)
            if output.approval_state == "REJECTED":
                raise RewriteOutputBlocked("Rejected rewrite output cannot be approved")
            output.approval_state = "APPROVED"
            output.approved_at = datetime.now(UTC)
            self._session.flush()
            result = _project(output)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    def _require_editorial_pass(self, content_key: str) -> None:
        decision = self._session.scalar(
            select(EditorialDecisionModel)
            .where(EditorialDecisionModel.content_key == content_key)
            .with_for_update()
        )
        if decision is None or decision.status != "PASS" or not decision.rewrite_allowed:
            raise RewriteOutputBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")
