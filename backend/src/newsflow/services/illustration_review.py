"""Atomic immutable review and audit writer. Does not authorize publication."""

import re
from dataclasses import asdict, fields
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from newsflow.domain.illustration_relevance import (
    HumanIllustrationReview,
    IllustrationBinding,
    IllustrationVerdict,
)
from newsflow.persistence.models import IllustrationReviewRecordModel, OutboxEventModel
from newsflow.security.illustration_reviewer import ReviewerPrincipal
from newsflow.services.illustration_binding import IllustrationBindingResolver


class IllustrationReviewConflict(PermissionError):
    pass


def record_binding(record: IllustrationReviewRecordModel) -> IllustrationBinding:
    return IllustrationBinding(
        **{f.name: getattr(record, f.name) for f in fields(IllustrationBinding)}
    )


class IllustrationReviewWriter:
    def __init__(self, session: Session, media_root: Path):
        self._session, self._root = session, media_root

    def _validate(self, principal, operation_key, review_note):
        if type(principal) is not ReviewerPrincipal:
            raise ValueError("Authenticated internal reviewer principal required")
        principal.__post_init__()
        if type(operation_key) is not str or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", operation_key
        ):
            raise ValueError("Bounded operation key required")
        if (
            type(review_note) is not str
            or not review_note.strip()
            or len(review_note) > 2048
            or any(ord(c) < 32 and c not in "\n\t" for c in review_note)
        ):
            raise ValueError("Bounded explicit review note required")
        session = self._session
        if session.new or session.dirty or session.deleted or session.in_transaction():
            raise ValueError(
                "Illustration writer requires a clean session without caller transaction"
            )

    def _serialize(self):
        # Own the transaction from its first SQL statement. SQLite reserves the
        # writer before resolving; PostgreSQL SSI establishes a serial order and
        # may refuse racing writes (caller retries with the same operation key).
        # No candidate-first lock that inverts the draft approval lock order.
        session = self._session
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            session.execute(text("BEGIN IMMEDIATE"))
        elif dialect == "postgresql":
            session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        else:
            raise ValueError("Supported transactional illustration storage required")

    def context(self, candidate_id):
        try:
            return IllustrationBindingResolver(self._session, self._root).resolve(candidate_id)
        except (PermissionError, ValueError):
            raise IllustrationReviewConflict("CURRENT_ILLUSTRATION_CONTEXT_REQUIRED") from None

    def _response(self, row):
        revoked = (
            self._session.scalar(
                select(IllustrationReviewRecordModel.id).where(
                    IllustrationReviewRecordModel.revokes_review_id == row.id
                )
            )
            is not None
        )
        reviewed = row.reviewed_at
        if reviewed.tzinfo is None:  # SQLite stores UTC without tzinfo.
            reviewed = reviewed.replace(tzinfo=UTC)
        return {
            "id": row.id,
            "record_kind": row.record_kind,
            "revokes_review_id": row.revokes_review_id,
            "binding": asdict(record_binding(row)),
            "reviewer_id": row.reviewer_id,
            "provenance": row.provenance,
            "verdict": row.verdict,
            "illustration_acknowledged": row.illustration_acknowledged,
            "review_note": row.review_note,
            "reviewed_at": reviewed.isoformat(),
            "revoked": revoked,
        }

    def _persist(
        self, principal, binding, operation_key, review_note, kind, verdict, acknowledged, parent
    ):
        values = {
            **asdict(binding),
            "operation_key": operation_key,
            "record_kind": kind,
            "revokes_review_id": parent,
            "reviewer_id": principal.reviewer_id,
            "provenance": "AUTHENTICATED_HUMAN_V1",
            "verdict": verdict,
            "illustration_acknowledged": acknowledged,
            "review_note": review_note,
        }
        old = self._session.scalar(
            select(IllustrationReviewRecordModel).where(
                IllustrationReviewRecordModel.operation_key == operation_key
            )
        )
        if old is not None:
            if any(getattr(old, key) != value for key, value in values.items()):
                raise IllustrationReviewConflict("ILLUSTRATION_OPERATION_CONFLICT")
            return self._response(old)
        if kind == "REVIEW":
            if self.context(binding.candidate_id) != binding:
                raise IllustrationReviewConflict("ILLUSTRATION_DISPLAYED_BINDING_CHANGED")
        elif (
            self._session.scalar(
                select(IllustrationReviewRecordModel.id).where(
                    IllustrationReviewRecordModel.revokes_review_id == parent
                )
            )
            is not None
        ):
            raise IllustrationReviewConflict("ILLUSTRATION_ALREADY_REVOKED")
        row = IllustrationReviewRecordModel(**values, reviewed_at=datetime.now(UTC))
        self._session.add(row)
        self._session.flush()
        self._session.add(
            OutboxEventModel(
                event_type="IllustrationReviewRecorded"
                if kind == "REVIEW"
                else "IllustrationReviewRevoked",
                aggregate_key=f"illustration-review:{row.id}",
                idempotency_key="illustration-review-operation:"
                + sha256(operation_key.encode("ascii")).hexdigest(),
            )
        )
        self._session.flush()
        # SQL serialization cannot lock external photo bytes. Recheck after both
        # inserts, immediately before commit; a later filesystem change leaves
        # immutable historical evidence and must be refused by the fresh consumer.
        if kind == "REVIEW" and self.context(binding.candidate_id) != binding:
            raise IllustrationReviewConflict("ILLUSTRATION_BINDING_CHANGED_DURING_WRITE")
        return self._response(row)

    def review(
        self,
        principal,
        *,
        displayed_binding,
        operation_key,
        verdict,
        illustration_acknowledged,
        review_note,
    ):
        self._validate(principal, operation_key, review_note)
        binding = (
            displayed_binding
            if type(displayed_binding) is IllustrationBinding
            else IllustrationBinding(**displayed_binding)
        )
        verdict = IllustrationVerdict(verdict)
        HumanIllustrationReview(
            binding,
            principal.reviewer_id,
            verdict,
            illustration_acknowledged,
            review_note,
            datetime.now(UTC),
        )
        if (
            verdict is IllustrationVerdict.APPROVED_ILLUSTRATION
            and illustration_acknowledged is not True
        ):
            raise ValueError("ILLUSTRATION_ACKNOWLEDGMENT_REQUIRED")
        with self._session.begin():
            self._serialize()
            return self._persist(
                principal,
                binding,
                operation_key,
                review_note,
                "REVIEW",
                verdict.value,
                illustration_acknowledged,
                None,
            )

    def revoke(self, principal, *, review_id, operation_key, review_note):
        self._validate(principal, operation_key, review_note)
        if type(review_id) is not int or not 0 < review_id <= 2**63 - 1:
            raise ValueError("Positive review identity required")
        with self._session.begin():
            self._serialize()
            parent = self._session.get(IllustrationReviewRecordModel, review_id)
            if parent is None or parent.record_kind != "REVIEW":
                raise LookupError("Illustration review not found")
            return self._persist(
                principal,
                record_binding(parent),
                operation_key,
                review_note,
                "REVOCATION",
                None,
                None,
                parent.id,
            )
