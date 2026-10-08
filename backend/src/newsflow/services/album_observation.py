"""Read-only retained album member observations; never grants execution rights."""

import re

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from newsflow.persistence.models import ContentRevisionModel, IncomingPostModel, SourceDeletionModel
from newsflow.providers.telegram import TelegramMessage, validate_media_observation
from newsflow.services.source_revisions import (
    revision_content_key,
    source_identity_sync_blocked,
    source_revision,
)


class AlbumObservationBlocked(RuntimeError):
    """Fixed public reason; incomplete observations never authorize an action."""


class AlbumObservationReader:
    def __init__(self, session: Session):
        self._session = session

    def read(self, content_key: str) -> dict[str, object]:
        if (
            not isinstance(content_key, str)
            or not 0 < len(content_key) <= 255
            or content_key != content_key.strip()
        ):
            raise ValueError("Explicit bounded source revision identity required")
        if self._session.new or self._session.dirty or self._session.deleted:
            # Reading must neither autoflush nor overwrite caller-owned drafts.
            raise AlbumObservationBlocked("READ_SESSION_HAS_PENDING_CHANGES")
        anchor = source_revision(self._session, content_key)
        if anchor is None:
            raise LookupError("Source revision not found")
        post = self._session.get(IncomingPostModel, anchor.incoming_post_id, populate_existing=True)
        if post is None:
            raise LookupError("Source revision not found")
        if (
            self._session.scalar(
                select(func.max(ContentRevisionModel.revision_number)).where(
                    ContentRevisionModel.incoming_post_id == anchor.incoming_post_id
                )
            )
            != anchor.revision_number
        ):
            raise AlbumObservationBlocked("SOURCE_REVISION_NOT_LATEST")
        if anchor.album_id is None:
            raise AlbumObservationBlocked("SOURCE_NOT_ALBUM")
        if (
            not isinstance(anchor.album_id, str)
            or re.fullmatch(r"-?(?:0|[1-9][0-9]{0,18})", anchor.album_id) is None
            or str(int(anchor.album_id)) != anchor.album_id
            or not -(2**63) <= int(anchor.album_id) < 2**63
        ):
            raise AlbumObservationBlocked("ALBUM_OBSERVATION_INVALID")

        newer = aliased(ContentRevisionModel)
        latest = (
            select(func.max(newer.revision_number))
            .where(newer.incoming_post_id == IncomingPostModel.id)
            .correlate(IncomingPostModel)
            .scalar_subquery()
        )
        # Resolve ownership from immutable SQL rows, never by splitting a key.
        # The eleventh row is an error, not permission to truncate into an album.
        rows = self._session.execute(
            select(
                IncomingPostModel,
                ContentRevisionModel,
                revision_content_key(),
                SourceDeletionModel.telegram_message_id,
            )
            .join(ContentRevisionModel)
            .outerjoin(
                SourceDeletionModel,
                and_(
                    SourceDeletionModel.telegram_account_id
                    == IncomingPostModel.telegram_account_id,
                    SourceDeletionModel.donor_channel_id == IncomingPostModel.donor_channel_id,
                    SourceDeletionModel.telegram_message_id
                    == IncomingPostModel.telegram_message_id,
                ),
            )
            .where(
                IncomingPostModel.telegram_account_id == post.telegram_account_id,
                IncomingPostModel.donor_channel_id == post.donor_channel_id,
                ContentRevisionModel.album_id == anchor.album_id,
                ContentRevisionModel.revision_number == latest,
            )
            .order_by(IncomingPostModel.telegram_message_id)
            .limit(11)
            .execution_options(populate_existing=True)
        ).all()
        if len(rows) > 10:
            raise AlbumObservationBlocked("ALBUM_MEMBER_LIMIT_EXCEEDED")
        if not any(revision.id == anchor.id for _, revision, _, _ in rows):
            raise AlbumObservationBlocked("SOURCE_REVISION_NOT_LATEST")
        members = []
        for member, revision, key, deleted in rows:
            if (
                type(member.telegram_message_id) is not int
                or not 1 <= member.telegram_message_id <= 2**31 - 1
                or type(revision.revision_number) is not int
                or revision.revision_number < 1
                or not isinstance(revision.source_text, str)
                or revision.media_type not in {"photo", "video", "unsupported", "unknown"}
            ):
                raise AlbumObservationBlocked("ALBUM_OBSERVATION_INVALID")
            try:
                validate_media_observation(
                    TelegramMessage(
                        member.telegram_account_id,
                        member.donor_channel_id,
                        member.telegram_message_id,
                        revision.source_text,
                        media_type=revision.media_type,
                        album_id=revision.album_id,
                        media_id=revision.media_id,
                        media_protected=revision.media_protected,
                    )
                )
            except ValueError:
                raise AlbumObservationBlocked("ALBUM_OBSERVATION_INVALID") from None
            members.append(
                {
                    "content_key": key,
                    "message_id": member.telegram_message_id,
                    "revision_number": revision.revision_number,
                    "text": revision.source_text,
                    "media_type": revision.media_type,
                    "media_protected": revision.media_protected,
                    "source_deleted": deleted is not None,
                }
            )
        return {
            "anchor_content_key": content_key,
            "album_id": anchor.album_id,
            "members": members,
            "membership_complete": False,
            "rewrite_allowed": False,
            "publication_allowed": False,
            "source_sync_blocked": source_identity_sync_blocked(
                self._session, post.telegram_account_id, post.donor_channel_id
            ),
            "reason_code": "ALBUM_NORMALIZATION_REQUIRED",
        }
