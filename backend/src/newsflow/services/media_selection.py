"""Read-only, free local photo selection. No network, AI, download or publication."""

import json
import re
import warnings
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    ChannelMappingModel,
    EditorialDecisionModel,
    MappingSourceRightsModel,
    MediaAssetModel,
    PublicationCandidateModel,
    RewriteOutputModel,
)
from newsflow.services.automatic_approval import approval_is_current
from newsflow.services.source_revisions import source_is_current


class MediaUnavailable(ValueError):
    """Persistent media is missing, unsafe or no longer matches its identity."""


class MediaSelectionBlocked(PermissionError):
    """Current candidate/editorial constraints prevent media selection."""


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[^\W_]+", text.casefold()) if len(token) >= 3}


def _project(asset: MediaAssetModel) -> dict[str, object]:
    return {
        "id": asset.id,
        "storage_key": asset.storage_key,
        "sha256": asset.sha256,
        "mime_type": asset.mime_type,
        "origin": asset.origin,
        "source_content_key": asset.source_content_key,
        "license_code": asset.license_code,
        "attribution": asset.attribution,
        "tags": json.loads(asset.tags),
    }


class LocalMediaSelectionService:
    def __init__(self, session: Session, media_root: Path) -> None:
        self._session = session
        self._root = media_root.resolve()
        if not self._root.is_dir():
            raise MediaUnavailable("Persistent media root is unavailable")

    def _read_photo(self, storage_key: str) -> tuple[str, str]:
        key = PurePosixPath(storage_key)
        if (
            not storage_key
            or len(storage_key) > 512
            or "\\" in storage_key
            or ":" in storage_key
            or key.is_absolute()
            or ".." in key.parts
            or str(key) != storage_key
            or key.suffix.lower() not in {".png", ".jpg", ".jpeg"}
        ):
            raise MediaUnavailable("Invalid local media storage key")
        try:
            path = (self._root / storage_key).resolve(strict=True)
            if not path.is_relative_to(self._root) or not path.is_file():
                raise MediaUnavailable("Media storage key escapes persistent root")
            # Bound allocation even if a file grows after the stat check.
            with path.open("rb") as stream:
                content = stream.read(16 * 1024 * 1024 + 1)
        except (OSError, RuntimeError):
            raise MediaUnavailable("Persistent media asset is unavailable") from None
        if len(content) > 16 * 1024 * 1024:
            raise MediaUnavailable("Local photo exceeds size limit")
        if content.startswith(b"\x89PNG\r\n\x1a\n") and key.suffix.lower() == ".png":
            mime = "image/png"
        elif content.startswith(b"\xff\xd8\xff") and key.suffix.lower() in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        else:
            raise MediaUnavailable("Media signature does not match a supported photo")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if (
                        image.format not in {"PNG", "JPEG"}
                        or image.get_format_mimetype() != mime
                        or image.width * image.height > 25_000_000
                        or getattr(image, "n_frames", 1) != 1
                    ):
                        raise MediaUnavailable("Local photo decode constraints failed")
                    image.verify()
                with Image.open(BytesIO(content)) as image:
                    image.load()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ):
            raise MediaUnavailable("Local photo decode constraints failed") from None
        return sha256(content).hexdigest(), mime

    def register_asset(
        self,
        storage_key: str,
        *,
        origin: str,
        license_code: str,
        attribution: str,
        tags: tuple[str, ...],
        source_content_key: str | None = None,
        commit: bool = True,
    ) -> dict[str, object]:
        attribution = attribution.strip()
        if (
            origin not in {"SOURCE", "LICENSED_LIBRARY"}
            or license_code not in {"OWNED", "PERMISSION", "CC0", "CC-BY"}
            or (license_code in {"PERMISSION", "CC-BY"} and not attribution)
            or (
                origin == "SOURCE"
                and (license_code not in {"OWNED", "PERMISSION"} or not source_content_key)
            )
            or (origin == "LICENSED_LIBRARY" and source_content_key is not None)
            or len(attribution) > 2048
            or (source_content_key is not None and len(source_content_key) > 255)
        ):
            raise ValueError("Media rights/provenance must be explicitly declared")
        normalized_tags = sorted({tag.strip().casefold() for tag in tags if tag.strip()})
        tags_json = json.dumps(normalized_tags, ensure_ascii=False)
        if len(tags_json) > 2048:
            raise ValueError("Media tags exceed size limit")
        digest, mime = self._read_photo(storage_key)
        values = {
            "storage_key": storage_key,
            "sha256": digest,
            "mime_type": mime,
            "origin": origin,
            "license_code": license_code,
            "attribution": attribution,
            "tags": tags_json,
            "source_content_key": source_content_key,
        }
        try:
            existing = self._session.scalar(
                select(MediaAssetModel).where(MediaAssetModel.storage_key == storage_key)
            )
            if existing is not None:
                if any(getattr(existing, field) != value for field, value in values.items()):
                    raise ValueError(
                        "Media asset is already registered with different identity/rights"
                    )
                result = _project(existing)
            else:
                asset = MediaAssetModel(**values)
                self._session.add(asset)
                self._session.flush()
                result = _project(asset)
            if commit:
                self._session.commit()
            return result
        except IntegrityError:
            self._session.rollback()
            raise ValueError("Media asset is already registered") from None
        except Exception:
            self._session.rollback()
            raise

    def select_for_candidate(
        self, candidate_id: int, *, query: str, limit: int = 10
    ) -> dict[str, object]:
        if type(limit) is not int or not 1 <= limit <= 10 or len(query) > 10000:
            raise ValueError("Invalid media selection limit/query")
        candidate = self._require_current_candidate(candidate_id)
        rights_binding = self._source_rights_binding(candidate)
        binding = (
            candidate.content_key,
            candidate.output_channel_id,
            candidate.media_policy,
            rights_binding,
        )
        if candidate.media_policy == "REUSE_SOURCE":
            assets = self._session.scalars(
                select(MediaAssetModel)
                .where(
                    MediaAssetModel.origin == "SOURCE",
                    MediaAssetModel.source_content_key == candidate.content_key,
                )
                .order_by(MediaAssetModel.id)
                .execution_options(populate_existing=True)
            ).all()
            if rights_binding is not None:
                assets = [
                    asset
                    for asset in assets
                    if (asset.license_code, asset.attribution) == rights_binding[1:3]
                ]
        elif candidate.media_policy == "LICENSED_LIBRARY":
            matches = _tokens(query)
            ranked = []
            for asset in self._session.scalars(
                select(MediaAssetModel)
                .where(MediaAssetModel.origin == "LICENSED_LIBRARY")
                .execution_options(populate_existing=True)
            ):
                score = len(matches & _tokens(" ".join(json.loads(asset.tags))))
                if score:
                    ranked.append((score, asset))
            assets = [
                asset for _, asset in sorted(ranked, key=lambda match: (-match[0], match[1].id))
            ]
        else:
            raise MediaSelectionBlocked("Unknown candidate media policy")
        selected = []
        for asset in assets[:limit]:
            digest, mime = self._read_photo(asset.storage_key)
            if digest != asset.sha256 or mime != asset.mime_type:
                raise MediaUnavailable("Persisted media integrity check failed")
            selected.append(_project(asset))
        current = self._require_current_candidate(candidate_id)
        if (
            current.content_key,
            current.output_channel_id,
            current.media_policy,
            self._source_rights_binding(current),
        ) != binding:
            raise MediaSelectionBlocked("MEDIA_BINDING_CHANGED")
        return {
            "status": "SELECTED" if selected else "NO_MATCH",
            "policy": current.media_policy,
            "items": selected,
        }

    def _require_current_candidate(self, candidate_id):
        candidate = self._session.get(
            PublicationCandidateModel, candidate_id, populate_existing=True
        )
        if candidate is None:
            raise LookupError("Publication candidate was not found")
        decision = self._session.scalar(
            select(EditorialDecisionModel)
            .where(EditorialDecisionModel.content_key == candidate.content_key)
            .execution_options(populate_existing=True)
        )
        if not editorial_allows_rewrite(decision):
            raise MediaSelectionBlocked("EDITORIAL_HARD_CONSTRAINT_BLOCKED")
        if candidate.state not in {"READY", "SCHEDULED"}:
            raise MediaSelectionBlocked("Candidate is not approved for media preparation")
        if not source_is_current(self._session, candidate.content_key):
            raise MediaSelectionBlocked("SOURCE_REVISION_NOT_CURRENT_OR_MISSING")
        output = self._session.scalar(
            select(RewriteOutputModel)
            .where(
                RewriteOutputModel.content_key == candidate.content_key,
                RewriteOutputModel.output_channel_id == candidate.output_channel_id,
            )
            .execution_options(populate_existing=True)
        )
        if output is None or not approval_is_current(self._session, output):
            raise MediaSelectionBlocked("CURRENT_APPROVAL_REQUIRED")
        if candidate.mapping_id is not None and candidate.media_policy == "REUSE_SOURCE":
            mapping = self._session.get(
                ChannelMappingModel, candidate.mapping_id, populate_existing=True
            )
            rights = self._session.get(
                MappingSourceRightsModel, candidate.mapping_id, populate_existing=True
            )
            if (
                mapping is None
                or mapping.media_policy != "REUSE_SOURCE"
                or rights is None
                or rights.license_code not in {"OWNED", "PERMISSION"}
            ):
                raise MediaSelectionBlocked("CURRENT_MAPPING_SOURCE_RIGHTS_REQUIRED")
        return candidate

    def _source_rights_binding(self, candidate):
        if candidate.mapping_id is None or candidate.media_policy != "REUSE_SOURCE":
            return None
        rights = self._session.get(
            MappingSourceRightsModel, candidate.mapping_id, populate_existing=True
        )
        if rights is None or rights.license_code not in {"OWNED", "PERMISSION"}:
            raise MediaSelectionBlocked("CURRENT_MAPPING_SOURCE_RIGHTS_REQUIRED")
        return (candidate.mapping_id, rights.license_code, rights.attribution, rights.revision)
