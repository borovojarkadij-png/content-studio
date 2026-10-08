"""Resolve immutable source keys without ambiguous delimiter parsing."""

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    ChannelDifferenceCursorModel,
    ContentRevisionModel,
    DonorChannel,
    IncomingPostModel,
    SourceDeletionModel,
    TelegramAccount,
)
from newsflow.services.channel_sync_enforcement import sync_enforced


def revision_content_key():
    """SQL identity expression; never infer account ownership by splitting keys."""
    return (
        IncomingPostModel.telegram_account_id
        + ":"
        + IncomingPostModel.donor_channel_id
        + ":"
        + cast(IncomingPostModel.telegram_message_id, String)
        + ":revision:"
        + cast(ContentRevisionModel.revision_number, String)
    )


def source_revision(session: Session, content_key: str) -> ContentRevisionModel | None:
    rows = session.scalars(
        select(ContentRevisionModel)
        .join(IncomingPostModel)
        .where(revision_content_key() == content_key)
        .execution_options(populate_existing=True)
        .limit(2)
    ).all()
    return rows[0] if len(rows) == 1 else None


def revision_is_latest(session: Session, revision: ContentRevisionModel) -> bool:
    post = session.get(IncomingPostModel, revision.incoming_post_id, populate_existing=True)
    if post is None or (
        source_identity_deleted(
            session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
        )
        or source_identity_sync_blocked(session, post.telegram_account_id, post.donor_channel_id)
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


def source_identity_sync_blocked(session: Session, account: str, channel: str) -> bool:
    """A known gap/foreign baseline is not a current source, even with cached PASS.

    Without persisted opt-in, legacy sources retain their existing workflow,
    not a synchronization certificate. Opt-in also fences every missing ledger.
    """
    enforced = sync_enforced(session)
    cursors = session.scalars(
        select(ChannelDifferenceCursorModel)
        .outerjoin(DonorChannel, DonorChannel.id == ChannelDifferenceCursorModel.donor_channel_id)
        .where(
            or_(
                (cast(DonorChannel.telegram_account_id, String) == account)
                & (cast(DonorChannel.telegram_channel_id, String) == channel),
                (cast(ChannelDifferenceCursorModel.telegram_account_id, String) == account)
                & (cast(ChannelDifferenceCursorModel.telegram_channel_id, String) == channel),
            )
        )
        .execution_options(populate_existing=True)
        .limit(2)
    ).all()
    if not cursors:
        return enforced
    if len(cursors) != 1:
        return True
    cursor = cursors[0]
    donor = session.get(DonorChannel, cursor.donor_channel_id, populate_existing=True)
    if donor is None:
        return True
    owner = session.get(TelegramAccount, donor.telegram_account_id, populate_existing=True)
    return (
        cursor.last_error_code == "GAP_UNRESOLVED"
        or owner is None
        or (
            enforced
            and (
                cursor.last_error_code is not None
                or cursor.claim_token is not None
                or cursor.lease_expires_at is not None
                or owner.health_status != "CONNECTED"
                or not owner.encrypted_session
            )
        )
        or (cursor.telegram_account_id, cursor.telegram_user_id, cursor.telegram_channel_id)
        != (donor.telegram_account_id, owner.telegram_user_id, donor.telegram_channel_id)
    )


def source_key_unavailable(session: Session, content_key: str) -> bool:
    revision = source_revision(session, content_key)
    if revision is None:
        return sync_enforced(session)
    post = session.get(IncomingPostModel, revision.incoming_post_id, populate_existing=True)
    return post is not None and (
        source_identity_deleted(
            session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
        )
        or source_identity_sync_blocked(session, post.telegram_account_id, post.donor_channel_id)
    )


def revision_sync_waiting(session: Session, revision: ContentRevisionModel) -> bool:
    """Temporary known synchronization, not legacy/foreign/stale/deleted permission.

    Used only to retain a pending job. It never grants processing permission and
    never revives terminal history or changes an editorial decision.
    """
    if not sync_enforced(session):
        return False
    post = session.get(IncomingPostModel, revision.incoming_post_id, populate_existing=True)
    if (
        post is None
        or source_identity_deleted(
            session, post.telegram_account_id, post.donor_channel_id, post.telegram_message_id
        )
        or session.scalar(
            select(func.max(ContentRevisionModel.revision_number)).where(
                ContentRevisionModel.incoming_post_id == post.id
            )
        )
        != revision.revision_number
    ):
        return False
    donors = session.scalars(
        select(DonorChannel)
        .where(
            cast(DonorChannel.telegram_account_id, String) == post.telegram_account_id,
            cast(DonorChannel.telegram_channel_id, String) == post.donor_channel_id,
        )
        .execution_options(populate_existing=True)
        .limit(2)
    ).all()
    if len(donors) != 1:
        return False
    donor = donors[0]
    cursor = session.get(ChannelDifferenceCursorModel, donor.id, populate_existing=True)
    account = session.get(TelegramAccount, donor.telegram_account_id, populate_existing=True)
    if (
        cursor is None
        or account is None
        or not account.encrypted_session
        or account.health_status not in {"CONNECTED", "COOLDOWN"}
        or (cursor.telegram_account_id, cursor.telegram_user_id, cursor.telegram_channel_id)
        != (account.id, account.telegram_user_id, donor.telegram_channel_id)
    ):
        return False
    if cursor.last_error_code not in {
        None,
        "RETRY_PROVIDER",
        "RETRY_PIPELINE",
        "DIFFERENCE_INCOMPLETE",
        "COOLDOWN",
        "MAPPING_CHANGED",
    }:
        return False
    return cursor.last_error_code is not None or (
        cursor.claim_token is not None and cursor.lease_expires_at is not None
    )
