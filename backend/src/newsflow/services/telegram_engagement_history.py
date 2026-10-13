"""Caller-transaction-owned, immutable Telegram observation persistence."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.engagement import (
    TelegramEngagementObservation,
    utc_timestamp,
    validate_engagement_request,
)
from newsflow.persistence.models import (
    DonorChannel,
    IncomingPostModel,
    TelegramAccount,
    TelegramEngagementSnapshotModel,
    TelegramEngagementSourceModel,
)


class TelegramEngagementHistory:
    def __init__(self, session: Session):
        self._session = session

    def record(self, observation: TelegramEngagementObservation) -> bool:
        if not isinstance(observation, TelegramEngagementObservation):
            raise TypeError("Validated Telegram engagement observation required")
        # Reconstruct at the trust boundary, including forged frozen instances.
        value = TelegramEngagementObservation(
            observation.account_id,
            observation.donor_identifier,
            observation.message_id,
            observation.published_at,
            observation.observed_at,
            observation.views,
            observation.forwards,
            observation.reactions,
        )
        post = self._session.scalar(
            select(IncomingPostModel)
            .where(
                IncomingPostModel.telegram_account_id == value.account_id,
                IncomingPostModel.donor_channel_id == value.donor_identifier,
                IncomingPostModel.telegram_message_id == value.message_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if post is None:
            raise LookupError("Telegram engagement source not found")
        self._require_configured(post)
        source = self._session.get(TelegramEngagementSourceModel, post.id)
        if source is not None and self._utc(source.published_at) != value.published_at:
            raise ValueError("Telegram engagement publication time is immutable")
        existing = self._session.get(TelegramEngagementSnapshotModel, (post.id, value.observed_at))
        if existing is not None:
            if (existing.views, existing.forwards, existing.reactions) != (
                value.views,
                value.forwards,
                value.reactions,
            ):
                raise ValueError("Conflicting Telegram engagement replay")
            return False
        if source is None:
            source = TelegramEngagementSourceModel(
                incoming_post_id=post.id, published_at=value.published_at
            )
            self._session.add(source)
            self._session.flush()
        self._session.add(
            TelegramEngagementSnapshotModel(
                incoming_post_id=post.id,
                observed_at=value.observed_at,
                views=value.views,
                forwards=value.forwards,
                reactions=value.reactions,
            )
        )
        self._session.flush()
        return True

    def history(
        self, incoming_post_id: int, *, limit: int = 60
    ) -> tuple[TelegramEngagementObservation, ...]:
        if (
            type(incoming_post_id) is not int
            or not 1 <= incoming_post_id < 2**63
            or type(limit) is not int
            or not 1 <= limit <= 1000
        ):
            raise ValueError("Invalid bounded Telegram engagement history request")
        post = self._session.scalar(
            select(IncomingPostModel)
            .where(IncomingPostModel.id == incoming_post_id)
            .execution_options(populate_existing=True)
        )
        if post is None:
            raise LookupError("Telegram engagement source not found")
        self._validate_identity(post)
        source = self._session.get(TelegramEngagementSourceModel, incoming_post_id)
        if source is None:
            return ()
        rows = self._session.scalars(
            select(TelegramEngagementSnapshotModel)
            .where(TelegramEngagementSnapshotModel.incoming_post_id == incoming_post_id)
            .order_by(TelegramEngagementSnapshotModel.observed_at.desc())
            .limit(limit)
        ).all()
        return tuple(
            TelegramEngagementObservation(
                post.telegram_account_id,
                post.donor_channel_id,
                post.telegram_message_id,
                self._utc(source.published_at),
                self._utc(row.observed_at),
                row.views,
                row.forwards,
                row.reactions,
            )
            for row in reversed(rows)
        )

    def _require_configured(self, post: IncomingPostModel) -> None:
        self._validate_identity(post)
        account_id = int(post.telegram_account_id)
        donor = self._session.scalar(
            select(DonorChannel.id)
            .join(TelegramAccount, DonorChannel.telegram_account_id == TelegramAccount.id)
            .where(
                TelegramAccount.id == account_id,
                DonorChannel.telegram_channel_id == int(post.donor_channel_id),
            )
        )
        if donor is None:
            raise LookupError("Configured Telegram engagement source not found")

    @staticmethod
    def _validate_identity(post: IncomingPostModel) -> None:
        # Identity validation needs no wall clock or current provider configuration.
        validate_engagement_request(
            post.telegram_account_id,
            post.donor_channel_id,
            post.telegram_message_id,
            datetime(2000, 1, 1, tzinfo=UTC),
        )

    def _utc(self, value: datetime) -> datetime:
        # SQLite's DateTime codec drops tzinfo; only this storage boundary restores UTC.
        if value.tzinfo is None and self._session.get_bind().dialect.name == "sqlite":
            return value.replace(tzinfo=UTC)
        return utc_timestamp(value)
