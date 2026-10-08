"""Resolve immutable source keys without ambiguous delimiter parsing."""

from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import ContentRevisionModel, IncomingPostModel, SourceDeletionModel


def source_revision(session: Session, content_key: str) -> ContentRevisionModel | None:
    key = (
        IncomingPostModel.telegram_account_id
        + ":"
        + IncomingPostModel.donor_channel_id
        + ":"
        + cast(IncomingPostModel.telegram_message_id, String)
        + ":revision:"
        + cast(ContentRevisionModel.revision_number, String)
    )
    rows = session.scalars(
        select(ContentRevisionModel)
        .join(IncomingPostModel)
        .where(key == content_key)
        .execution_options(populate_existing=True)
        .limit(2)
    ).all()
    return rows[0] if len(rows) == 1 else None


def revision_is_latest(session: Session, revision: ContentRevisionModel) -> bool:
    post = session.get(IncomingPostModel, revision.incoming_post_id, populate_existing=True)
    if post is None or source_identity_deleted(
        session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
    ):
        return False
    return (
        session.scalar(
            select(func.max(ContentRevisionModel.revision_number)).where(
                ContentRevisionModel.incoming_post_id == revision.incoming_post_id
            )
        )
        == revision.revision_number
    )


def source_is_current(session: Session, content_key: str) -> bool:
    revision = source_revision(session, content_key)
    return revision is not None and revision_is_latest(session, revision)


def source_identity_deleted(session: Session, account: str, channel: str, message_id: int) -> bool:
    return (
        session.get(SourceDeletionModel, (account, channel, message_id), populate_existing=True)
        is not None
    )


def source_key_deleted(session: Session, content_key: str) -> bool:
    revision = source_revision(session, content_key)
    if revision is None:
        return False
    post = session.get(IncomingPostModel, revision.incoming_post_id, populate_existing=True)
    return post is not None and source_identity_deleted(
        session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
    )
