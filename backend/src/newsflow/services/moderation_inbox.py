"""Read model for the Telegram moderation inbox."""

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

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

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class ModerationInboxReader:
    """Projects latest revision and durable editorial outcome for human moderation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_items(self) -> list[ModerationInboxItem]:
        posts = self._session.scalars(
            select(IncomingPostModel).order_by(
                IncomingPostModel.created_at.desc(), IncomingPostModel.id.desc()
            )
        ).all()
        items: list[ModerationInboxItem] = []
        for post in posts:
            revision = self._session.scalar(
                select(ContentRevisionModel)
                .where(ContentRevisionModel.incoming_post_id == post.id)
                .order_by(ContentRevisionModel.revision_number.desc())
            )
            if revision is None:
                continue
            source_key = (
                f"{post.telegram_account_id}:{post.donor_channel_id}:{post.telegram_message_id}"
            )
            decision = self._session.scalar(
                select(EditorialDecisionModel).where(
                    EditorialDecisionModel.content_key
                    == f"{source_key}:revision:{revision.revision_number}"
                )
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
                    if deleted or sync_blocked or revision.album_id is not None
                    else decision.rewrite_allowed
                    if decision
                    else None,
                    editorial_reason_codes=reason_codes,
                    source_deleted=deleted,
                    album_observed=revision.album_id is not None,
                )
            )
        return items
