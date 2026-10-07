"""Durable, per-output rewrite drafts with explicit approval."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    EditorialDecisionModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
)
from newsflow.services.source_revisions import source_is_current


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

    def list_outputs(self, output_channel_id: int | None = None) -> list[dict[str, object]]:
        query = (
            select(RewriteOutputModel, RewriteJobModel, EditorialDecisionModel)
            .outerjoin(RewriteJobModel, RewriteJobModel.id == RewriteOutputModel.rewrite_job_id)
            .outerjoin(
                EditorialDecisionModel,
                EditorialDecisionModel.content_key == RewriteOutputModel.content_key,
            )
            .order_by(RewriteOutputModel.id)
        )
        if output_channel_id is not None:
            query = query.where(RewriteOutputModel.output_channel_id == output_channel_id)
        items = []
        for output, job, decision in self._session.execute(query):
            items.append(
                {
                    **_project(output),
                    "editorial_status": decision.status if decision else None,
                    "approve_allowed": (
                        output.approval_state != "REJECTED"
                        and editorial_allows_rewrite(decision)
                        and job is not None
                        and job.state == "SUCCEEDED"
                        and job.output_channel_id == output.output_channel_id
                        and job.content_key == output.content_key
                        and source_is_current(self._session, output.content_key)
                    ),
                }
            )
        return items

    def record_succeeded_output(
        self, rewrite_job_id: int, rewritten_text: str
    ) -> dict[str, object]:
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
            self._require_current_source(job.content_key)
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

    def approve(self, output_id: int, *, activate_candidate: bool = False) -> dict[str, object]:
        return self._review(output_id, approve=True, activate_candidate=activate_candidate)

    def reject(self, output_id: int) -> dict[str, object]:
        return self._review(output_id, approve=False, activate_candidate=False)

    def _review(
        self, output_id: int, *, approve: bool, activate_candidate: bool
    ) -> dict[str, object]:
        try:
            # All rewrite paths lock job -> editorial -> draft -> candidate.
            job_id = self._session.scalar(
                select(RewriteOutputModel.rewrite_job_id).where(RewriteOutputModel.id == output_id)
            )
            if job_id is None:
                raise LookupError("Rewrite output was not found")
            job = self._session.scalar(
                select(RewriteJobModel).where(RewriteJobModel.id == job_id).with_for_update()
            )
            if approve:
                if job is None or job.state != "SUCCEEDED":
                    raise RewriteOutputBlocked("Rewrite job is no longer succeeded")
                self._require_editorial_pass(job.content_key)
                self._require_current_source(job.content_key)
            output = self._session.scalar(
                select(RewriteOutputModel)
                .where(RewriteOutputModel.id == output_id)
                .with_for_update()
            )
            if output is None:
                raise LookupError("Rewrite output was not found")
            if approve:
                if (
                    job.output_channel_id != output.output_channel_id
                    or job.content_key != output.content_key
                ):
                    raise RewriteOutputBlocked("Rewrite output no longer matches its job")
                if output.approval_state == "REJECTED":
                    raise RewriteOutputBlocked("Rejected rewrite output cannot be approved")
                output.approval_state = "APPROVED"
                if output.approved_at is None:
                    output.approved_at = datetime.now(UTC)
            else:
                if output.approval_state == "APPROVED":
                    raise RewriteOutputBlocked(
                        "Approved output cannot be rejected through pending review"
                    )
                output.approval_state = "REJECTED"
            if activate_candidate or not approve:
                candidates = self._session.scalars(
                    select(PublicationCandidateModel)
                    .where(
                        PublicationCandidateModel.content_key == output.content_key,
                        PublicationCandidateModel.output_channel_id == output.output_channel_id,
                        PublicationCandidateModel.state == "AWAITING_REWRITE",
                    )
                    .with_for_update()
                ).all()
                for candidate in candidates:
                    candidate.state = "READY" if approve else "REJECTED_REVIEW"
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
        if not editorial_allows_rewrite(decision):
            raise RewriteOutputBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")

    def _require_current_source(self, content_key: str) -> None:
        if not source_is_current(self._session, content_key):
            raise RewriteOutputBlocked("SOURCE_REVISION_NOT_CURRENT_OR_MISSING")
