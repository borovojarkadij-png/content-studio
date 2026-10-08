"""Explicit-rights, exact-source photo acquisition; no AI, login or publication.

RPCs run outside DB transactions. Durable worker/API orchestration is separate;
this seam never interprets donor accessibility as permission to reuse media.
"""

import json
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import select

from newsflow.persistence.models import (
    ChannelMappingModel,
    DonorChannel,
    IncomingPostModel,
    MappingSourceRightsModel,
    PublicationCandidateModel,
    RewriteOutputModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage, TelegramPhotoDownload
from newsflow.services.media_selection import (
    LocalMediaSelectionService,
    MediaSelectionBlocked,
    MediaUnavailable,
)
from newsflow.services.source_revisions import source_revision


def _utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def validate_source_rights(license_code, attribution):
    if (
        not isinstance(license_code, str)
        or license_code not in {"OWNED", "PERMISSION"}
        or not isinstance(attribution, str)
        or len(attribution.strip()) > 2048
        or (license_code == "PERMISSION" and not attribution.strip())
    ):
        raise ValueError("Source reuse requires explicit valid rights/attribution")
    return license_code, attribution.strip()


def source_job_digest(binding, license_code, attribution, policy_revision=None):
    key, channel_id, revision_id, user_id, message, draft_sha = binding
    observation = (
        message.account_id,
        message.donor_identifier,
        message.message_id,
        message.text,
        message.media_type,
        message.media_id,
        message.media_protected,
        message.album_id,
        message.source_updated_at.isoformat(),
    )
    value = (
        key,
        channel_id,
        revision_id,
        user_id,
        observation,
        draft_sha,
        license_code,
        attribution,
        policy_revision,
    )
    return sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


def source_job_binding_digest(session, acquisition, candidate_id, license_code, attribution):
    binding = acquisition._binding(session, candidate_id)
    candidate = session.get(PublicationCandidateModel, candidate_id, populate_existing=True)
    revision = None
    if candidate.mapping_id is not None:
        mapping = session.scalar(
            select(ChannelMappingModel)
            .where(ChannelMappingModel.id == candidate.mapping_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        rights = session.get(MappingSourceRightsModel, candidate.mapping_id, populate_existing=True)
        donor = (
            session.get(DonorChannel, mapping.donor_channel_id, populate_existing=True)
            if mapping
            else None
        )
        if (
            mapping is None
            or donor is None
            or mapping.media_policy != "REUSE_SOURCE"
            or mapping.output_channel_id != candidate.output_channel_id
            or str(donor.telegram_account_id) != binding[4].account_id
            or str(donor.telegram_channel_id) != binding[4].donor_identifier
            or rights is None
            or (rights.license_code, rights.attribution) != (license_code, attribution)
            or rights.license_code not in {"OWNED", "PERMISSION"}
        ):
            raise MediaSelectionBlocked("CURRENT_MAPPING_SOURCE_RIGHTS_REQUIRED")
        revision = (mapping.id, rights.revision)
    return source_job_digest(binding, license_code, attribution, revision)


class SourcePhotoAcquisition:
    def __init__(
        self, session_factory, media_root: Path, *, provider, clock=lambda: datetime.now(UTC)
    ):
        self._factory, self._provider, self._clock = session_factory, provider, clock
        try:
            self._root = media_root.resolve(strict=True)
        except (OSError, RuntimeError):
            raise MediaUnavailable("Persistent media root is unavailable") from None
        if not self._root.is_dir():
            raise MediaUnavailable("Persistent media root is unavailable")

    def _binding(self, session, candidate_id):
        candidate = LocalMediaSelectionService(session, self._root)._require_current_candidate(
            candidate_id
        )
        source = source_revision(session, candidate.content_key)
        if (
            candidate.media_policy != "REUSE_SOURCE"
            or source is None
            or source.media_type != "photo"
            or source.album_id is not None
            or source.media_id is None
            or source.media_protected is not False
            or source.source_updated_at is None
        ):
            raise MediaSelectionBlocked("KNOWN_SINGLE_SOURCE_PHOTO_REQUIRED")
        post = session.get(IncomingPostModel, source.incoming_post_id, populate_existing=True)
        try:
            account_id, channel_id = int(post.telegram_account_id), int(post.donor_channel_id)
            if (
                account_id <= 0
                or str(account_id) != post.telegram_account_id
                or str(channel_id) != post.donor_channel_id
                or not -(2**63) <= channel_id < -1000000000000
            ):
                raise ValueError("Invalid source identity")
        except (ValueError, TypeError, AttributeError):
            raise MediaSelectionBlocked("CANONICAL_SOURCE_IDENTITY_REQUIRED") from None
        account = session.get(TelegramAccount, account_id, populate_existing=True)
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Source acquisition time must be timezone-aware")
        if (
            account is None
            or not account.encrypted_session
            or account.health_status not in {"CONNECTED", "COOLDOWN"}
            or (account.cooldown_until is not None and _utc(account.cooldown_until) > now)
        ):
            raise MediaSelectionBlocked("HEALTHY_PROVISIONED_SOURCE_ACCOUNT_REQUIRED")
        output = session.scalar(
            select(RewriteOutputModel)
            .where(
                RewriteOutputModel.content_key == candidate.content_key,
                RewriteOutputModel.output_channel_id == candidate.output_channel_id,
            )
            .execution_options(populate_existing=True)
        )
        expected = TelegramMessage(
            post.telegram_account_id,
            post.donor_channel_id,
            post.telegram_message_id,
            source.source_text,
            media_type="photo",
            media_id=source.media_id,
            media_protected=False,
            source_updated_at=_utc(source.source_updated_at),
            link_destinations=tuple(source.link_destinations)
            if isinstance(source.link_destinations, list)
            else None,
        )
        return (
            candidate.content_key,
            candidate.output_channel_id,
            source.id,
            account.telegram_user_id,
            expected,
            sha256(output.rewritten_text.encode()).hexdigest(),
        )

    @staticmethod
    def _same_observation(expected, received):
        return all(
            getattr(expected, name) == getattr(received, name)
            for name in (
                "account_id",
                "donor_identifier",
                "message_id",
                "text",
                "media_type",
                "media_id",
                "media_protected",
                "album_id",
                "source_updated_at",
                "link_destinations",
            )
        )

    def acquire(
        self,
        candidate_id: int,
        *,
        license_code: str,
        attribution: str,
        tags: tuple[str, ...] = (),
        execution_guard=None,
        completion=None,
    ) -> dict[str, object]:
        license_code, attribution = validate_source_rights(license_code, attribution)
        if (
            not isinstance(tags, (tuple, list))
            or len(tags) > 20
            or any(not isinstance(tag, str) or not 0 < len(tag.strip()) <= 100 for tag in tags)
        ):
            raise ValueError("Source reuse requires explicit valid rights/attribution")
        attribution = attribution.strip()
        tags = tuple(sorted({tag.strip().casefold() for tag in tags}))
        with self._factory() as session:
            if execution_guard:
                execution_guard(session)
            binding = self._binding(session, candidate_id)
        expected = binding[4]
        result = self._provider.download_photo(
            expected.account_id, expected.donor_identifier, expected.message_id
        )
        if not isinstance(result, TelegramPhotoDownload) or not self._same_observation(
            expected, result.message
        ):
            raise MediaSelectionBlocked("REMOTE_SOURCE_PHOTO_BINDING_CHANGED")
        content = result.content
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            extension = ".png"
        elif content.startswith(b"\xff\xd8\xff"):
            extension = ".jpg"
        else:
            raise MediaUnavailable("Unsupported source photo signature")
        with self._factory() as session:
            if execution_guard:
                execution_guard(session)
            if self._binding(session, candidate_id) != binding:
                raise MediaSelectionBlocked("SOURCE_PHOTO_BINDING_CHANGED")
            directory = self._root / "source"
            directory.mkdir(exist_ok=True)
            if directory.is_symlink() or directory.resolve(strict=True) != directory:
                raise MediaUnavailable("Source media directory must not be a link")
            rights = json.dumps((binding[0], license_code, attribution, tags), ensure_ascii=False)
            name = (
                sha256(rights.encode()).hexdigest() + "-" + sha256(content).hexdigest() + extension
            )
            destination = directory / name
            with NamedTemporaryFile(
                dir=directory, prefix="acquire-", suffix=extension, delete=False
            ) as staged:
                temporary = Path(staged.name)
                staged.write(content)
                staged.flush()
                os.fsync(staged.fileno())
            try:
                media = LocalMediaSelectionService(session, self._root)
                digest, mime = media._read_photo("source/" + temporary.name)
                if execution_guard:
                    execution_guard(session)
                if self._binding(session, candidate_id) != binding:
                    raise MediaSelectionBlocked("SOURCE_PHOTO_BINDING_CHANGED")
                try:
                    os.link(
                        temporary, destination
                    )  # Atomic create-only, never overwrite an original.
                except FileExistsError:
                    if destination.is_symlink() or destination.resolve() != destination:
                        raise MediaUnavailable("Source media target must not be a link") from None
                    actual_digest, actual_mime = media._read_photo("source/" + name)
                    if (actual_digest, actual_mime) != (digest, mime):
                        raise MediaUnavailable("Source media identity conflict") from None
                asset = media.register_asset(
                    "source/" + name,
                    origin="SOURCE",
                    license_code=license_code,
                    attribution=attribution,
                    tags=tags,
                    source_content_key=binding[0],
                    commit=False,
                )
                if self._binding(session, candidate_id) != binding:
                    raise MediaSelectionBlocked("SOURCE_PHOTO_BINDING_CHANGED")
                if completion:
                    completion(session, asset["id"])
                session.commit()
            finally:
                temporary.unlink()  # Only this invocation's generated staging file.
        return {"status": "ACQUIRED", "items": [asset], "illustration": False}
