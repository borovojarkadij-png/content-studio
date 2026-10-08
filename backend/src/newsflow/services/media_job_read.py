"""Read-only media-job history and current selection eligibility; no network."""

from sqlalchemy import select

from newsflow.persistence.models import (
    MediaAcquisitionJobModel,
    MediaAssetModel,
    PublicationCandidateModel,
)
from newsflow.services.durable_media_runner import _digest
from newsflow.services.internet_media import InternetMediaAcquisition
from newsflow.services.media_selection import (
    LocalMediaSelectionService,
    MediaSelectionBlocked,
    MediaUnavailable,
    _project,
)
from newsflow.services.source_photo import (
    SourcePhotoAcquisition,
    source_job_binding_digest,
    validate_source_rights,
)


class MediaJobReader:
    def __init__(self, session, media_root):
        self._session, self._root = session, media_root

    def _check_binding(self, job):
        if self._root is None:
            raise MediaUnavailable("Persistent media root is not configured")
        LocalMediaSelectionService(self._session, self._root)._require_current_candidate(
            job.candidate_id
        )
        if job.acquisition_mode == "REUSE_SOURCE":
            acquisition = SourcePhotoAcquisition(None, self._root, provider=None)
            rights = validate_source_rights(job.license_code, job.attribution)
            digest = source_job_binding_digest(
                self._session, acquisition, job.candidate_id, *rights
            )
        else:
            digest = _digest(InternetMediaAcquisition._binding(self._session, job.candidate_id))
        if digest != job.binding_sha256:
            raise MediaSelectionBlocked("MEDIA_BINDING_CHANGED")

    @staticmethod
    def _valid_asset(job, asset, candidate):
        if asset is None:
            return False
        if job.acquisition_mode == "REUSE_SOURCE":
            return (
                asset.origin == "SOURCE"
                and asset.source_content_key == candidate.content_key
                and asset.license_code == job.license_code
                and asset.attribution == job.attribution
            )
        return asset.origin == "LICENSED_LIBRARY" and asset.license_code in {"CC0", "CC-BY"}

    def get_status(self, candidate_id, *, job_id=None):
        candidate = self._session.get(
            PublicationCandidateModel, candidate_id, populate_existing=True
        )
        if candidate is None:
            raise LookupError("Publication candidate was not found")
        job = self._session.scalar(
            select(MediaAcquisitionJobModel)
            .where(
                MediaAcquisitionJobModel.candidate_id == candidate_id,
                True if job_id is None else MediaAcquisitionJobModel.id == job_id,
            )
            .execution_options(populate_existing=True)
            .order_by(MediaAcquisitionJobModel.id.desc())
            .limit(1)
        )
        if job_id is not None and job is None:
            raise LookupError("Media acquisition job was not found for this candidate")
        result = {
            "candidate_id": candidate_id,
            "job_id": job.id if job else None,
            "state": job.state if job else "NOT_QUEUED",
            "attempts": job.attempts if job else 0,
            "selected_allowed": False,
            "asset": None,
            "reason_code": job.last_error_code if job else None,
            "illustration": (job.acquisition_mode if job else candidate.media_policy)
            != "REUSE_SOURCE",
        }
        if job is None or job.state != "SUCCEEDED":
            return result
        try:
            self._check_binding(job)
        except (MediaSelectionBlocked, MediaUnavailable, ValueError):
            result["reason_code"] = "CURRENT_MEDIA_GATE_BLOCKED"
            return result
        asset = self._session.get(MediaAssetModel, job.selected_asset_id, populate_existing=True)
        if not self._valid_asset(job, asset, candidate):
            result["reason_code"] = "MEDIA_ASSET_INVALID"
            return result
        try:
            if self._root is None:
                raise MediaUnavailable("Persistent media root is not configured")
            digest, mime = LocalMediaSelectionService(self._session, self._root)._read_photo(
                asset.storage_key
            )
            if digest != asset.sha256 or mime != asset.mime_type:
                raise MediaUnavailable("Media identity mismatch")
        except MediaUnavailable:
            result["reason_code"] = "MEDIA_BYTES_UNAVAILABLE"
            return result
        try:
            self._check_binding(job)
        except (MediaSelectionBlocked, MediaUnavailable, ValueError):
            result["reason_code"] = "CURRENT_MEDIA_GATE_BLOCKED"
            return result
        result["selected_allowed"], result["asset"] = True, _project(asset)
        return result
