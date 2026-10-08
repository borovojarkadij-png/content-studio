"""Explicit-rights source-photo jobs. No implied permission, approval or send."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from newsflow.persistence.models import (
    MappingSourceRightsModel,
    MediaAcquisitionJobModel,
    PublicationCandidateModel,
    TelegramAccount,
)
from newsflow.providers.telegram import FloodWait, SessionUnavailable
from newsflow.services.durable_media_runner import DurableMediaRunner, MediaLeaseLost
from newsflow.services.durable_semantic_runner import _aware, _utc
from newsflow.services.media_selection import MediaSelectionBlocked, MediaUnavailable
from newsflow.services.source_photo import (
    SourcePhotoAcquisition,
    source_job_binding_digest,
    validate_source_rights,
)


class DurableSourcePhotoRunner(DurableMediaRunner):
    acquisition_mode = "REUSE_SOURCE"

    def __init__(self, session_factory, media_root, *, provider, clock=lambda: datetime.now(UTC)):
        self._factory, self._clock = session_factory, clock
        self._acquisition = SourcePhotoAcquisition(
            session_factory, media_root, provider=provider, clock=clock
        )

    def enqueue(self, candidate_id, *, license_code, attribution, now):
        _aware(now)
        if type(candidate_id) is not int or candidate_id <= 0:
            raise ValueError("Candidate identity must be positive")
        license_code, attribution = validate_source_rights(license_code, attribution)
        with self._factory() as session:
            digest = source_job_binding_digest(
                session, self._acquisition, candidate_id, license_code, attribution
            )
            job = session.scalar(
                select(MediaAcquisitionJobModel).where(
                    MediaAcquisitionJobModel.candidate_id == candidate_id,
                    MediaAcquisitionJobModel.binding_sha256 == digest,
                )
            )
            if job is not None:
                return job.id
            job = MediaAcquisitionJobModel(
                candidate_id=candidate_id,
                binding_sha256=digest,
                acquisition_mode=self.acquisition_mode,
                license_code=license_code,
                attribution=attribution,
                state="QUEUED",
                available_at=now,
            )
            session.add(job)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                job = session.scalar(
                    select(MediaAcquisitionJobModel).where(
                        MediaAcquisitionJobModel.candidate_id == candidate_id,
                        MediaAcquisitionJobModel.binding_sha256 == digest,
                    )
                )
                if job is None:
                    raise
            return job.id

    def enqueue_configured(self, candidate_id, *, now):
        with self._factory() as session:
            candidate = session.get(PublicationCandidateModel, candidate_id)
            if candidate is None:
                raise LookupError("Publication candidate was not found")
            rights = (
                session.get(MappingSourceRightsModel, candidate.mapping_id)
                if candidate.mapping_id
                else None
            )
            if rights is None or rights.license_code == "UNDECLARED":
                raise MediaSelectionBlocked("DECLARED_MAPPING_SOURCE_RIGHTS_REQUIRED")
            license_code, attribution = rights.license_code, rights.attribution
        return self.enqueue(
            candidate_id, license_code=license_code, attribution=attribution, now=now
        )

    def _pending_query(self):
        return (
            super()
            ._pending_query()
            .join(
                MappingSourceRightsModel,
                MappingSourceRightsModel.mapping_id == PublicationCandidateModel.mapping_id,
            )
            .where(MappingSourceRightsModel.license_code.in_(("OWNED", "PERMISSION")))
        )

    def _enqueue_automatic(self, candidate_id, *, now):
        return self.enqueue_configured(candidate_id, now=now)

    def _guard(self, session, claim):
        job = self._owned(session, claim)
        rights = validate_source_rights(job.license_code, job.attribution)
        if (
            source_job_binding_digest(session, self._acquisition, job.candidate_id, *rights)
            != job.binding_sha256
        ):
            raise MediaSelectionBlocked("SOURCE_PHOTO_JOB_BINDING_CHANGED")

    def execute(self, claim):
        try:
            with self._factory() as session:
                self._guard(session, claim)
                job = self._owned(session, claim)
                candidate_id, license_code, attribution = (
                    job.candidate_id,
                    job.license_code,
                    job.attribution,
                )
                binding = self._acquisition._binding(session, candidate_id)
                account_id = int(binding[4].account_id)
                account = session.get(TelegramAccount, account_id, populate_existing=True)
                account_binding = (
                    account_id,
                    sha256(account.encrypted_session.encode()).hexdigest(),
                )

            def complete(session, asset_id):
                self._guard(session, claim)
                job = self._owned(session, claim)
                job.state, job.selected_asset_id = "SUCCEEDED", asset_id
                job.claim_token, job.lease_expires_at = None, None

            self._acquisition.acquire(
                candidate_id,
                license_code=license_code,
                attribution=attribution,
                execution_guard=lambda session: self._guard(session, claim),
                completion=complete,
            )
            return "SUCCEEDED"
        except MediaLeaseLost:
            return "LOST_LEASE"
        except (MediaSelectionBlocked, PermissionError):
            return self._finish(claim, "BLOCKED", "SOURCE_PHOTO_GUARD_BLOCKED")
        except FloodWait as exc:
            return self._source_retry(claim, account_binding, delay=exc.seconds, flood=True)
        except (TimeoutError, ConnectionError):
            return self._source_retry(claim, account_binding, delay=30)
        except SessionUnavailable:
            return self._finish(claim, "BLOCKED", "SOURCE_PHOTO_SESSION_UNAVAILABLE")
        except (LookupError, MediaUnavailable, OSError, ValueError):
            return self._finish(claim, "FAILED", "SOURCE_PHOTO_ACQUISITION_FAILED")

    def _source_retry(self, claim, account_binding, *, delay, flood=False):
        if type(delay) is not int or not 1 <= delay <= 2**31 - 1:
            return self._finish(claim, "FAILED", "SOURCE_PHOTO_INVALID_RETRY")
        now = self._clock()
        _aware(now)
        try:
            with self._factory() as session:
                job = self._owned(session, claim)
                available = now + timedelta(seconds=max(30, delay))
                if flood:
                    account = session.get(
                        TelegramAccount,
                        account_binding[0],
                        populate_existing=True,
                        with_for_update=True,
                    )
                    if (
                        account is not None
                        and sha256(account.encrypted_session.encode()).hexdigest()
                        == account_binding[1]
                        and account.health_status != "SESSION_INVALID"
                    ):
                        available = max(
                            available,
                            _utc(account.cooldown_until) if account.cooldown_until else now,
                        )
                        account.cooldown_until = available
                        account.health_status = "COOLDOWN"
                        account.health_checked_at = max(
                            _utc(account.health_checked_at) if account.health_checked_at else now,
                            now,
                        )
                job.state = "QUEUED" if job.attempts < 2 else "FAILED"
                job.available_at, job.last_error_code = (
                    available,
                    "SOURCE_PHOTO_FLOOD_WAIT" if flood else "SOURCE_PHOTO_TRANSPORT_RETRY",
                )
                job.claim_token, job.lease_expires_at = None, None
                state = "RETRY" if job.state == "QUEUED" else "FAILED"
                session.commit()
                return state
        except MediaLeaseLost:
            return "LOST_LEASE"
