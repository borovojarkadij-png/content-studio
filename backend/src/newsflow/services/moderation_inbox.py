"""Read model for the Telegram moderation inbox."""

from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.technical_filters import stored_source_link_exclusion_reason
from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
)
from newsflow.services.source_revisions import source_identity_deleted, source_identity_sync_blocked


@dataclass(frozen=True, slots=True)
class ModerationInboxItem:
    source_key: str
    state: str
    revision_number: int
    source_text: str
    editorial_status: str | None
    rewrite_allowed: bool | None
    editorial_reason_codes: list[str]
    source_deleted: bool = False
    album_observed: bool = False
    technical_reason_codes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class ModerationInboxReader:
    """Projects latest revision and durable editorial outcome for human moderation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_items(self) -> list[ModerationInboxItem]:
        if self._session.new or self._session.dirty or self._session.deleted:
            raise ValueError("Inbox diagnostics require a clean session")
        posts = self._session.scalars(
            select(IncomingPostModel)
            .order_by(IncomingPostModel.created_at.desc(), IncomingPostModel.id.desc())
            .execution_options(populate_existing=True)
        ).all()
        items: list[ModerationInboxItem] = []
        for post in posts:
            revision = self._session.scalar(
                select(ContentRevisionModel)
                .where(ContentRevisionModel.incoming_post_id == post.id)
                .order_by(ContentRevisionModel.revision_number.desc())
                .execution_options(populate_existing=True)
            )
            if revision is None:
                continue
            source_key = (
                f"{post.telegram_account_id}:{post.donor_channel_id}:{post.telegram_message_id}"
            )
            decision = self._session.scalar(
                select(EditorialDecisionModel)
                .where(
                    EditorialDecisionModel.content_key
                    == f"{source_key}:revision:{revision.revision_number}"
                )
                .execution_options(populate_existing=True)
            )
            reason_codes = (
                decision.reason_codes.split(",") if decision and decision.reason_codes else []
            )
            deleted = source_identity_deleted(
                self._session,
                post.telegram_account_id,
                post.donor_channel_id,
                post.telegram_message_id,
            )
            sync_blocked = source_identity_sync_blocked(
                self._session, post.telegram_account_id, post.donor_channel_id
            )
            # Fixed diagnostics only: never expose captured URLs, repair source
            # metadata or replace a retained editorial verdict with a rejection.
            technical_reasons = []
            if revision.album_id is not None:
                technical_reasons.append("ALBUM_NORMALIZATION_REQUIRED")
            if revision.media_protected is True:
                technical_reasons.append("PROTECTED_CONTENT")
            if revision.media_type == "video":
                technical_reasons.append("VIDEO_MANUAL_REVIEW_REQUIRED")
            if link_reason := stored_source_link_exclusion_reason(revision):
                technical_reasons.append(link_reason)
            items.append(
                ModerationInboxItem(
                    source_key=source_key,
                    state="SOURCE_DELETED"
                    if deleted
                    else "SOURCE_SYNC_REQUIRED"
                    if sync_blocked
                    else post.state,
                    revision_number=revision.revision_number,
                    source_text=revision.source_text,
                    editorial_status=decision.status if decision else None,
                    rewrite_allowed=False
                    if deleted or sync_blocked or technical_reasons
                    else decision.rewrite_allowed
                    if decision
                    else None,
                    editorial_reason_codes=reason_codes,
                    source_deleted=deleted,
                    album_observed=revision.album_id is not None,
                    technical_reason_codes=technical_reasons,
                )
            )
        return items
