"""Bounded, caller-transaction-owned Telegram ranking evidence; never authority."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.donor_performance import (
    DonorRelativePerformance,
    EngagementWindow,
    donor_relative_performance,
)
from newsflow.domain.engagement import (
    TelegramEngagementObservation,
    utc_timestamp,
    validate_engagement_request,
)
from newsflow.domain.hype import (
    HypeAssessment,
    HypeComponents,
    HypeWeights,
    freshness_score,
    relative_velocity_score,
    score_hype,
)
from newsflow.persistence.models import (
    IncomingPostModel,
    TelegramEngagementSnapshotModel,
    TelegramEngagementSourceModel,
)


@dataclass(frozen=True, slots=True)
class TelegramHypeProjection:
    assessment: HypeAssessment
    performance: DonorRelativePerformance | None
    observed_at: datetime | None
    baseline_truncated: bool
    reason: str


class TelegramHypeService:
    def __init__(self, session: Session):
        self._session = session

    def inspect(
        self,
        incoming_post_id: int,
        *,
        as_of: datetime,
        weights: HypeWeights | None = None,
        minimum_coverage: float = 0.5,
    ) -> TelegramHypeProjection:
        if type(incoming_post_id) is not int or not 1 <= incoming_post_id < 2**63:
            raise ValueError("Hype requires an exact positive signed64 incoming post ID")
        as_of = utc_timestamp(as_of)
        # Validate policy before any missing-source/history early return.
        empty = score_hype(HypeComponents(), weights, minimum_coverage=minimum_coverage)
        weights = empty.weights
        with self._session.no_autoflush:
            # Column reads bypass cached ORM objects and preserve caller-pending edits.
            post = self._session.execute(
                select(
                    IncomingPostModel.telegram_account_id,
                    IncomingPostModel.donor_channel_id,
                    IncomingPostModel.telegram_message_id,
                ).where(IncomingPostModel.id == incoming_post_id)
            ).one_or_none()
            if post is None:
                raise LookupError("Telegram Hype incoming source not found")
            validate_engagement_request(*post, as_of)
            published = self._session.scalar(
                select(TelegramEngagementSourceModel.published_at).where(
                    TelegramEngagementSourceModel.incoming_post_id == incoming_post_id
                )
            )
            if published is None:
                return TelegramHypeProjection(empty, None, None, False, "NO_ENGAGEMENT")
            published = self._utc(published)
            snapshot = TelegramEngagementSnapshotModel
            rows = self._session.execute(
                select(snapshot.observed_at, snapshot.views, snapshot.forwards, snapshot.reactions)
                .where(snapshot.incoming_post_id == incoming_post_id, snapshot.observed_at <= as_of)
                .order_by(snapshot.observed_at.desc())
                .limit(2)
            ).all()
            if not rows:
                return TelegramHypeProjection(empty, None, None, False, "NO_ENGAGEMENT")
            observations = tuple(self._observation(post, published, row) for row in reversed(rows))
            observed_at = observations[-1].observed_at
            components = HypeComponents(freshness=freshness_score(published, as_of))
            performance, truncated = None, False
            stale = as_of - observed_at > timedelta(minutes=5)
            if len(observations) == 2 and not stale:
                target = EngagementWindow(*observations)
                samples, truncated = self._baseline(incoming_post_id, target)
                performance = donor_relative_performance(target, samples)
                components = HypeComponents(
                    freshness=components.freshness,
                    view_velocity=relative_velocity_score(performance.relative_views_velocity),
                    forward_velocity=relative_velocity_score(
                        performance.relative_forwards_velocity
                    ),
                    reaction_velocity=relative_velocity_score(
                        performance.relative_reactions_velocity
                    ),
                )
            assessment = score_hype(components, weights, minimum_coverage=minimum_coverage)
            return TelegramHypeProjection(
                assessment,
                performance,
                observed_at,
                truncated,
                "STALE_ENGAGEMENT" if stale else assessment.reason,
            )

    def _baseline(self, incoming_post_id, target):
        source, snapshot, post = (
            TelegramEngagementSourceModel,
            TelegramEngagementSnapshotModel,
            IncomingPostModel,
        )
        published = target.current.published_at
        earliest = datetime.min.replace(tzinfo=UTC)
        lower = (
            published - timedelta(days=30)
            if published - earliest >= timedelta(days=30)
            else earliest
        )
        rows = self._session.execute(
            select(
                post.id,
                post.telegram_account_id,
                post.donor_channel_id,
                post.telegram_message_id,
                source.published_at,
                snapshot.observed_at,
                snapshot.views,
                snapshot.forwards,
                snapshot.reactions,
            )
            .join(source, source.incoming_post_id == post.id)
            .join(snapshot, snapshot.incoming_post_id == source.incoming_post_id)
            .where(
                post.telegram_account_id == target.current.account_id,
                post.donor_channel_id == target.current.donor_identifier,
                post.id != incoming_post_id,
                source.published_at < published,
                source.published_at >= lower,
                snapshot.observed_at <= target.current.observed_at,
            )
            .order_by(source.published_at.desc(), post.id.desc(), snapshot.observed_at.desc())
            .limit(2001)
        ).all()
        previous, windows = {}, []
        # Reverse the retained prefix, not the entire 2001 rows: the extra row is
        # solely a truncation receipt and cannot provide a baseline interval.
        for row in reversed(rows[:2000]):
            observation = self._observation(row[1:4], self._utc(row[4]), row[5:])
            if row[0] in previous:
                windows.append(EngagementWindow(previous[row[0]], observation))
            previous[row[0]] = observation
        return tuple(windows), len(rows) > 2000

    def _observation(self, identity, published, snapshot):
        return TelegramEngagementObservation(
            *identity, published, self._utc(snapshot[0]), *snapshot[1:]
        )

    def _utc(self, value: datetime) -> datetime:
        if value.tzinfo is None and self._session.get_bind().dialect.name == "sqlite":
            return value.replace(tzinfo=UTC)
        return utc_timestamp(value)
