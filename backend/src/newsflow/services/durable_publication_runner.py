"""Injected durable publication boundary; no default/live Telegram sender.

The transport MUST call execution_guard after authorization/media preparation,
immediately before its first send RPC. Never hold DB locks across remote calls.
Persist SENDING before that boundary and quarantine ambiguous outcomes.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import randbelow
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from newsflow.persistence.models import (
    OutboxEventModel,
    PlannedPublicationModel,
    PublicationCandidateModel,
    PublicationJobModel,
)
from newsflow.services.durable_semantic_runner import _aware, _utc
from newsflow.services.publication import PublicationBlocked
from newsflow.services.publication_preflight import PublicationPreflight
from newsflow.services.publication_request_snapshot import PublicationRequestSnapshots


class PublicationLeaseLost(PermissionError):
    pass


class PublicationNotSentRetry(Exception):
    """Transport-proven rejection before delivery (e.g. send RPC FloodWait).

    Never wrap a timeout, lost connection or missing/malformed response in this.
    """

    def __init__(self, delay_seconds):
        if type(delay_seconds) is not int or not 1 <= delay_seconds <= 2**31 - 1:
            raise ValueError("Invalid publication retry delay")
        self.delay_seconds = delay_seconds
        super().__init__("PUBLICATION_KNOWN_NOT_SENT_RETRY")


@dataclass(frozen=True, slots=True)
class PublicationClaim:
    job_id: int
    token: str
    attempt: int


@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    account_id: int
    telegram_channel_id: int
    request_nonce: int
    message_id: int


@dataclass(frozen=True, slots=True)
class PublicationAdmission:
    cursor: int
    queued_ids: tuple[int, ...]
    blocked_ids: tuple[int, ...]


class DurablePublicationRunner:
    def __init__(
        self,
        session_factory,
        media_root=None,
        *,
        publisher=None,
        cipher=None,
        clock=lambda: datetime.now(UTC),
    ):
        self._factory, self._publisher, self._clock = session_factory, publisher, clock
        self._preflight = PublicationPreflight(session_factory, media_root)
        self._snapshots = (
            PublicationRequestSnapshots(session_factory, cipher=cipher)
            if cipher is not None
            else None
        )

    def enqueue_due(self, *, now, after_id=0, limit=16):
        _aware(now)
        if (
            type(after_id) is not int
            or after_id < 0
            or type(limit) is not int
            or not 1 <= limit <= 64
        ):
            raise ValueError("Invalid bounded publication admission cursor/limit")
        query = (
            select(PlannedPublicationModel.id)
            .where(
                PlannedPublicationModel.state == "PLANNED",
                PlannedPublicationModel.scheduled_for <= now,
                PlannedPublicationModel.scheduled_for > now - timedelta(hours=6),
                ~select(PublicationJobModel.id)
                .where(PublicationJobModel.planned_id == PlannedPublicationModel.id)
                .exists(),
            )
            .order_by(PlannedPublicationModel.id)
            .limit(limit)
        )
        with self._factory() as session:
            ids = tuple(session.scalars(query.where(PlannedPublicationModel.id > after_id)))
            if not ids and after_id:
                ids = tuple(session.scalars(query))
        queued, blocked = [], []
        for planned_id in ids:
            try:
                self.enqueue(planned_id, now=now)
                queued.append(planned_id)
            except (PublicationBlocked, LookupError, ValueError):
                # Expected stale policy does not hide later channels; never create
                # a forged send intent just to remember a rejected admission.
                blocked.append(planned_id)
        return PublicationAdmission(ids[-1] if ids else 0, tuple(queued), tuple(blocked))

    def enqueue(self, planned_id, *, now):
        envelope = self._preflight.prepare(planned_id, now=now)
        query = select(PublicationJobModel).where(PublicationJobModel.planned_id == planned_id)
        with self._factory() as session:
            job = session.scalar(query)
            if job is None:
                job = PublicationJobModel(
                    planned_id=planned_id,
                    telegram_account_id=envelope.account_id,
                    telegram_channel_id=envelope.telegram_channel_id,
                    request_nonce=randbelow(2**63 - 1) + 1,
                    binding_sha256=envelope.binding_sha256,
                    state="QUEUED",
                    available_at=now,
                )
                session.add(job)
                session.add(
                    OutboxEventModel(
                        event_type="publication.queued",
                        aggregate_key=str(planned_id),
                        idempotency_key=f"publication:{planned_id}:queued",
                    )
                )
                try:
                    if self._snapshots is not None:
                        session.flush()
                        self._snapshots.record(session, job, envelope)
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    job = session.scalar(query)
                    if job is None:
                        raise
            if job.binding_sha256 != envelope.binding_sha256:
                raise PublicationBlocked("PUBLICATION_JOB_BINDING_CHANGED")
            return job.id

    def claim_next(self, *, now):
        _aware(now)
        if self._publisher is None:
            return None
        with self._factory() as session:
            abandoned = session.scalars(
                select(PublicationJobModel)
                .where(
                    PublicationJobModel.state == "SENDING",
                    PublicationJobModel.lease_expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            ).all()
            for job in abandoned:
                self._terminal(job, "NEEDS_RECONCILIATION", "PUBLICATION_SEND_OUTCOME_UNKNOWN")
            job = session.scalar(
                select(PublicationJobModel)
                .where(
                    or_(
                        and_(
                            PublicationJobModel.state == "QUEUED",
                            PublicationJobModel.available_at <= now,
                        ),
                        and_(
                            PublicationJobModel.state == "CLAIMED",
                            PublicationJobModel.lease_expires_at <= now,
                        ),
                    )
                )
                .order_by(PublicationJobModel.id)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                session.commit()
                return None
            if job.attempts >= 2:
                self._terminal(job, "FAILED", "PUBLICATION_ATTEMPTS_EXHAUSTED")
                session.commit()
                return None
            job.state, job.claim_token = "CLAIMED", str(uuid4())
            job.lease_expires_at = now + timedelta(seconds=60)
            job.attempts += 1
            claim = PublicationClaim(job.id, job.claim_token, job.attempts)
            session.commit()
            return claim

    def _owned(self, session, claim, *, state):
        now = self._clock()
        _aware(now)
        job = session.get(
            PublicationJobModel, claim.job_id, populate_existing=True, with_for_update=True
        )
        if (
            job is None
            or job.state != state
            or job.claim_token != claim.token
            or job.attempts != claim.attempt
            or job.lease_expires_at is None
            or _utc(job.lease_expires_at) <= now
        ):
            raise PublicationLeaseLost("PUBLICATION_LEASE_LOST")
        return job

    @staticmethod
    def _terminal(job, state, code):
        job.state, job.last_error_code = state, code
        job.claim_token, job.lease_expires_at = None, None

    def _guard(self, claim, envelope):
        current = self._preflight.prepare(envelope.planned_id, now=self._clock())
        if current.binding_sha256 != envelope.binding_sha256:
            raise PublicationBlocked("PUBLICATION_JOB_BINDING_CHANGED")
        with self._factory() as session:
            job = self._owned(session, claim, state="SENDING")
            if job.binding_sha256 != current.binding_sha256:
                raise PublicationBlocked("PUBLICATION_JOB_BINDING_CHANGED")
            self._validate_snapshot(job.id, current, job.request_nonce)

    def _validate_snapshot(self, job_id, envelope, nonce):
        if self._snapshots is not None:
            original = self._snapshots.read(job_id)
            if original.envelope != envelope or original.request_nonce != nonce:
                raise PublicationBlocked("PUBLICATION_REQUEST_SNAPSHOT_CHANGED")

    def run_next(self, *, now):
        claim = self.claim_next(now=now)
        return "IDLE" if claim is None else self.execute(claim)

    def execute(self, claim):
        sending = False
        guard_failure = None
        guard_passed = False

        def guard():
            nonlocal guard_failure, guard_passed
            try:
                self._guard(claim, envelope)
                guard_passed = True
            except Exception as exc:
                guard_failure = exc
                raise

        try:
            if self._publisher is None:
                return "DISABLED"
            with self._factory() as session:
                job = self._owned(session, claim, state="CLAIMED")
                planned_id, digest, nonce = job.planned_id, job.binding_sha256, job.request_nonce
            envelope = self._preflight.prepare(planned_id, now=self._clock())
            if envelope.binding_sha256 != digest:
                raise PublicationBlocked("PUBLICATION_JOB_BINDING_CHANGED")
            self._validate_snapshot(claim.job_id, envelope, nonce)
            with self._factory() as session:
                job = self._owned(session, claim, state="CLAIMED")
                job.state = "SENDING"
                session.commit()
            sending = True
            receipt = self._publisher.publish(envelope, nonce, execution_guard=guard)
            if not guard_passed or guard_failure is not None:
                return self._finish(
                    claim,
                    "NEEDS_RECONCILIATION",
                    "PUBLICATION_TRANSPORT_GUARD_MISSING",
                    sending=True,
                )
            return self._complete(claim, receipt, envelope, nonce)
        except Exception as exc:  # noqa: BLE001 -- unknown remote outcomes must be durably quarantined
            if isinstance(guard_failure, PublicationLeaseLost) or (
                not sending and isinstance(exc, PublicationLeaseLost)
            ):
                return "LOST_LEASE"
            if (guard_failure is not None or not sending) and isinstance(
                exc, (PublicationBlocked, LookupError, ValueError)
            ):
                return self._finish(
                    claim, "BLOCKED", "PUBLICATION_PREFLIGHT_BLOCKED", sending=sending
                )
            if sending and guard_failure is None and isinstance(exc, PublicationNotSentRetry):
                return self._retry(claim, exc.delay_seconds)
            # Timeout/connection/unknown exception after send intent is not proof of non-delivery.
            return self._finish(
                claim,
                "NEEDS_RECONCILIATION" if sending else "FAILED",
                "PUBLICATION_SEND_OUTCOME_UNKNOWN" if sending else "PUBLICATION_PREPARATION_FAILED",
                sending=sending,
            )

    def _retry(self, claim, delay):
        try:
            with self._factory() as session:
                job = self._owned(session, claim, state="SENDING")
                state = "QUEUED" if job.attempts < 2 else "FAILED"
                self._terminal(job, state, "PUBLICATION_KNOWN_NOT_SENT")
                job.available_at = self._clock() + timedelta(seconds=max(30, delay))
                session.commit()
                return "RETRY" if state == "QUEUED" else state
        except PublicationLeaseLost:
            return "LOST_LEASE"

    def _finish(self, claim, state, code, *, sending):
        try:
            with self._factory() as session:
                job = self._owned(session, claim, state="SENDING" if sending else "CLAIMED")
                self._terminal(job, state, code)
                session.commit()
                return state
        except PublicationLeaseLost:
            return "LOST_LEASE"

    def _complete(self, claim, receipt, envelope, nonce):
        if (
            not isinstance(receipt, PublicationReceipt)
            or any(
                type(value) is not int
                for value in (
                    receipt.account_id,
                    receipt.telegram_channel_id,
                    receipt.request_nonce,
                    receipt.message_id,
                )
            )
            or (receipt.account_id, receipt.telegram_channel_id, receipt.request_nonce)
            != (envelope.account_id, envelope.telegram_channel_id, nonce)
            or not 0 < receipt.message_id <= 2**31 - 1
        ):
            return self._finish(
                claim, "NEEDS_RECONCILIATION", "PUBLICATION_RECEIPT_INVALID", sending=True
            )
        with self._factory() as session:
            job = session.get(
                PublicationJobModel, claim.job_id, populate_existing=True, with_for_update=True
            )
            if (
                job is None
                or job.attempts != claim.attempt
                or (
                    job.telegram_account_id,
                    job.telegram_channel_id,
                    job.request_nonce,
                    job.binding_sha256,
                )
                != (receipt.account_id, receipt.telegram_channel_id, nonce, envelope.binding_sha256)
                or not (
                    (job.state == "SENDING" and job.claim_token == claim.token)
                    or (
                        job.state == "NEEDS_RECONCILIATION"
                        and job.last_error_code == "PUBLICATION_SEND_OUTCOME_UNKNOWN"
                    )
                )
            ):
                raise PublicationLeaseLost("PUBLICATION_ACK_OWNERSHIP_LOST")
            item = session.get(PlannedPublicationModel, job.planned_id, with_for_update=True)
            candidate = session.get(
                PublicationCandidateModel, item.candidate_id, with_for_update=True
            )
            self._terminal(job, "SUCCEEDED", None)
            job.sent_message_id, job.completed_at = receipt.message_id, self._clock()
            item.state, candidate.state = "PUBLISHED", "PUBLISHED"
            session.add(
                OutboxEventModel(
                    event_type="publication.delivered",
                    aggregate_key=str(job.planned_id),
                    idempotency_key=f"publication:{job.planned_id}:delivered",
                )
            )
            session.commit()
        return "SUCCEEDED"
