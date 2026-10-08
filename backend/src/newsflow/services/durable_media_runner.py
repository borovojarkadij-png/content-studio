"""Fenced durable illustration jobs; no rewrite, scheduling or publication."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from newsflow.persistence.models import MediaAcquisitionJobModel, PublicationCandidateModel
from newsflow.providers.commons_images import ImageProviderRetryable, ImageProviderUnavailable
from newsflow.services.durable_semantic_runner import _aware, _utc
from newsflow.services.internet_media import InternetMediaAcquisition
from newsflow.services.media_selection import MediaSelectionBlocked, MediaUnavailable
from newsflow.services.semantic_facts import text_digest


def _digest(binding):
    return text_digest(json.dumps(binding, ensure_ascii=False))


class MediaLeaseLost(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class MediaClaim:
    job_id: int
    token: str
    attempt: int


@dataclass(frozen=True, slots=True)
class MediaAdmissionWindow:
    cursor: int
    scanned_ids: tuple[int, ...]
    queued_ids: tuple[int, ...]
    blocked_ids: tuple[int, ...]


class DurableMediaRunner:
    acquisition_mode = "LICENSED_LIBRARY"

    def __init__(
        self, session_factory, media_root, *, provider=None, clock=lambda: datetime.now(UTC)
    ):
        self._factory, self._clock = session_factory, clock
        self._acquisition = InternetMediaAcquisition(session_factory, media_root, provider=provider)

    def enqueue_candidate(self, candidate_id, *, now):
        _aware(now)
        if (
            type(candidate_id) is not int
            or candidate_id <= 0
            or self.acquisition_mode != "LICENSED_LIBRARY"
        ):
            raise ValueError("Library media candidate identity/mode is invalid")
        with self._factory() as session:
            digest = _digest(self._acquisition._binding(session, candidate_id))
            query = select(MediaAcquisitionJobModel).where(
                MediaAcquisitionJobModel.candidate_id == candidate_id,
                MediaAcquisitionJobModel.binding_sha256 == digest,
                MediaAcquisitionJobModel.acquisition_mode == self.acquisition_mode,
            )
            job = session.scalar(query)
            if job is not None:
                return job.id
            job = MediaAcquisitionJobModel(
                candidate_id=candidate_id,
                binding_sha256=digest,
                state="QUEUED",
                available_at=now,
                acquisition_mode=self.acquisition_mode,
            )
            session.add(job)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                job = session.scalar(query)
                if job is None:
                    raise
            return job.id

    def _pending_query(self):
        return select(PublicationCandidateModel.id).where(
            PublicationCandidateModel.state.in_(("READY", "SCHEDULED")),
            PublicationCandidateModel.media_policy == self.acquisition_mode,
            ~select(MediaAcquisitionJobModel.id)
            .where(
                MediaAcquisitionJobModel.candidate_id == PublicationCandidateModel.id,
                MediaAcquisitionJobModel.acquisition_mode == self.acquisition_mode,
            )
            .exists(),
        )

    def _enqueue_automatic(self, candidate_id, *, now):
        return self.enqueue_candidate(candidate_id, now=now)

    def enqueue_pending(self, *, now, limit=100):
        return len(self.enqueue_window(now=now, after_id=0, limit=limit).queued_ids)

    def enqueue_window(self, *, now, after_id=0, limit=16):
        """Bounded fair admission; progress never overrides a current media gate.

        Caller retains only scan progress. Reset/wrap/restart enumerate retained
        candidates again; task identity, terminal history and retries remain SQL-owned.
        """
        _aware(now)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Media enqueue limit must be between 1 and 100")
        if type(after_id) is not int or after_id < 0:
            raise ValueError("Media scan cursor must be a nonnegative canonical integer")
        with self._factory() as session:
            ids = session.scalars(
                self._pending_query()
                .where(PublicationCandidateModel.id > after_id)
                .order_by(PublicationCandidateModel.id)
                .limit(limit)
            ).all()
        queued, blocked = [], []
        for candidate_id in ids:
            try:
                queued.append(self._enqueue_automatic(candidate_id, now=now))
            except (MediaSelectionBlocked, ValueError, LookupError, IntegrityError):
                blocked.append(candidate_id)
        return MediaAdmissionWindow(
            ids[-1] if ids else 0, tuple(ids), tuple(queued), tuple(blocked)
        )

    def claim_next(self, *, now):
        _aware(now)
        with self._factory() as session:
            job = session.scalar(
                select(MediaAcquisitionJobModel)
                .where(
                    MediaAcquisitionJobModel.acquisition_mode == self.acquisition_mode,
                    or_(
                        and_(
                            MediaAcquisitionJobModel.state == "QUEUED",
                            MediaAcquisitionJobModel.available_at <= now,
                        ),
                        and_(
                            MediaAcquisitionJobModel.state == "RUNNING",
                            MediaAcquisitionJobModel.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(MediaAcquisitionJobModel.id)
                .with_for_update(skip_locked=True)
            )
            if job is None:
                return None
            if job.attempts >= 2:
                job.state, job.claim_token, job.lease_expires_at = "FAILED", None, None
                job.last_error_code = "MEDIA_ATTEMPTS_EXHAUSTED"
                session.commit()
                return None
            job.state, job.claim_token = "RUNNING", str(uuid4())
            job.lease_expires_at = now + timedelta(seconds=60)
            job.attempts += 1
            claim = MediaClaim(job.id, job.claim_token, job.attempts)
            session.commit()
            return claim

    def _owned(self, session, claim):
        now = self._clock()
        _aware(now)
        job = session.scalar(
            select(MediaAcquisitionJobModel)
            .where(MediaAcquisitionJobModel.id == claim.job_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if (
            job is None
            or job.acquisition_mode != self.acquisition_mode
            or job.state != "RUNNING"
            or job.claim_token != claim.token
            or job.attempts != claim.attempt
            or job.lease_expires_at is None
            or _utc(job.lease_expires_at) <= now
        ):
            raise MediaLeaseLost("MEDIA_LEASE_LOST")
        return job

    def _guard(self, session, claim):
        job = self._owned(session, claim)
        if _digest(self._acquisition._binding(session, job.candidate_id)) != job.binding_sha256:
            raise MediaSelectionBlocked("MEDIA_JOB_BINDING_CHANGED")

    def run_next(self, *, now):
        claim = self.claim_next(now=now)
        return "IDLE" if claim is None else self.execute(claim)

    def execute(self, claim):
        try:
            with self._factory() as session:
                candidate_id = self._owned(session, claim).candidate_id

            def complete(session, asset_id):
                job = self._owned(session, claim)
                job.state = "SUCCEEDED" if asset_id is not None else "NO_MATCH"
                job.selected_asset_id = asset_id
                job.claim_token, job.lease_expires_at = None, None

            result = self._acquisition.acquire(
                candidate_id,
                execution_guard=lambda session: self._guard(session, claim),
                completion=complete,
            )
            return "SUCCEEDED" if result["status"] == "ACQUIRED" else "NO_MATCH"
        except MediaLeaseLost:
            return "LOST_LEASE"
        except MediaSelectionBlocked:
            return self._finish(claim, "BLOCKED", "MEDIA_GUARD_BLOCKED")
        except ImageProviderRetryable:
            return self._retry(claim)
        except (ImageProviderUnavailable, MediaUnavailable, OSError, ValueError):
            return self._finish(claim, "FAILED", "MEDIA_ACQUISITION_FAILED")

    def _finish(self, claim, state, error):
        try:
            with self._factory() as session:
                job = self._owned(session, claim)
                job.state, job.last_error_code = state, error
                job.claim_token, job.lease_expires_at = None, None
                session.commit()
            return state
        except MediaLeaseLost:
            return "LOST_LEASE"

    def _retry(self, claim):
        try:
            with self._factory() as session:
                job = self._owned(session, claim)
                job.state = "QUEUED" if job.attempts < 2 else "FAILED"
                job.available_at = self._clock() + timedelta(seconds=30)
                job.last_error_code = "MEDIA_PROVIDER_UNAVAILABLE"
                job.claim_token, job.lease_expires_at = None, None
                state = "RETRY" if job.state == "QUEUED" else "FAILED"
                session.commit()
                return state
        except MediaLeaseLost:
            return "LOST_LEASE"
