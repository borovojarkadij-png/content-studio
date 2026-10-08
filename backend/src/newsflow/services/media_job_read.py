"""Read-only media-job history and current selection eligibility; no network."""

from hashlib import sha256

from sqlalchemy import select

from newsflow.persistence.models import (
    MappingSourceRightsModel,
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

    def _queue_binding(self, candidate):
        if self._root is None:
            raise MediaUnavailable("Persistent media root is not configured")
        LocalMediaSelectionService(self._session, self._root)._require_current_candidate(
            candidate.id
        )
        if candidate.media_policy == "REUSE_SOURCE":
            rights = (
                self._session.get(
                    MappingSourceRightsModel, candidate.mapping_id, populate_existing=True
                )
                if candidate.mapping_id is not None
                else None
            )
            if rights is None:
                raise MediaSelectionBlocked("CURRENT_MAPPING_SOURCE_RIGHTS_REQUIRED")
            declaration = validate_source_rights(rights.license_code, rights.attribution)
            return source_job_binding_digest(
                self._session,
                SourcePhotoAcquisition(None, self._root, provider=None),
                candidate.id,
                *declaration,
            )
        if candidate.media_policy != "LICENSED_LIBRARY":
            raise MediaSelectionBlocked("MEDIA_ACQUISITION_POLICY_UNSUPPORTED")
        return _digest(InternetMediaAcquisition._binding(self._session, candidate.id))

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
            "acquisition_mode": job.acquisition_mode if job else candidate.media_policy,
            "media_policy": candidate.media_policy,
            "queue_allowed": False,
            "queue_reason_code": None,
            "selected_allowed": False,
            "asset": None,
            "reason_code": job.last_error_code if job else None,
            "illustration": (job.acquisition_mode if job else candidate.media_policy)
            != "REUSE_SOURCE",
        }
        try:
            binding = self._queue_binding(candidate)
            existing = self._session.scalar(
                select(MediaAcquisitionJobModel.id).where(
                    MediaAcquisitionJobModel.candidate_id == candidate_id,
                    MediaAcquisitionJobModel.acquisition_mode == candidate.media_policy,
                    MediaAcquisitionJobModel.binding_sha256 == binding,
                )
            )
            result["queue_allowed"] = existing is None
            if existing is not None:
                result["queue_reason_code"] = "CURRENT_MEDIA_JOB_EXISTS"
        except (MediaSelectionBlocked, MediaUnavailable, ValueError):
            result["queue_reason_code"] = "CURRENT_MEDIA_GATE_BLOCKED"
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

    def preview(self, candidate_id):
        status = self.get_status(candidate_id)
        if not status["selected_allowed"]:
            raise MediaSelectionBlocked("CURRENT_MEDIA_PREVIEW_NOT_ALLOWED")
        asset = status["asset"]
        try:
            root = self._root.resolve(strict=True)
            path = (root / asset["storage_key"]).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise MediaUnavailable("Media preview escapes persistent root")
            with path.open("rb") as stream:
                content = stream.read(16 * 1024 * 1024 + 1)
        except (OSError, RuntimeError):
            raise MediaUnavailable("Media preview is unavailable") from None
        if len(content) > 16 * 1024 * 1024 or sha256(content).hexdigest() != asset["sha256"]:
            raise MediaUnavailable("Media preview identity changed")
        current = self.get_status(candidate_id, job_id=status["job_id"])
        if not current["selected_allowed"] or current["asset"] != asset:
            raise MediaSelectionBlocked("CURRENT_MEDIA_PREVIEW_NOT_ALLOWED")
        return content, asset["mime_type"]
