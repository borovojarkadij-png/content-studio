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


class MediaJobReader:
    def __init__(self, session, media_root):
        self._session, self._root = session, media_root

    def get_status(self, candidate_id):
        if self._session.get(PublicationCandidateModel, candidate_id) is None:
            raise LookupError("Publication candidate was not found")
        job = self._session.scalar(
            select(MediaAcquisitionJobModel)
            .where(MediaAcquisitionJobModel.candidate_id == candidate_id)
            .execution_options(populate_existing=True)
            .order_by(MediaAcquisitionJobModel.id.desc())
            .limit(1)
        )
        result = {
            "candidate_id": candidate_id,
            "job_id": job.id if job else None,
            "state": job.state if job else "NOT_QUEUED",
            "attempts": job.attempts if job else 0,
            "selected_allowed": False,
            "asset": None,
            "reason_code": job.last_error_code if job else None,
            "illustration": True,
        }
        if job is None or job.state != "SUCCEEDED":
            return result
        try:
            binding = InternetMediaAcquisition._binding(self._session, candidate_id)
            if _digest(binding) != job.binding_sha256:
                raise MediaSelectionBlocked("MEDIA_BINDING_CHANGED")
        except MediaSelectionBlocked:
            result["reason_code"] = "CURRENT_MEDIA_GATE_BLOCKED"
            return result
        asset = self._session.get(MediaAssetModel, job.selected_asset_id)
        if (
            asset is None
            or asset.origin != "LICENSED_LIBRARY"
            or asset.license_code not in {"CC0", "CC-BY"}
        ):
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
        result["selected_allowed"], result["asset"] = True, _project(asset)
        return result
