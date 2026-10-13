"""Immutable source performance observations and honest, clock-free interval math."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime


def utc_timestamp(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Engagement requires an aware timestamp")
    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError):
        raise ValueError("Engagement timestamp is outside UTC bounds") from None


def validate_engagement_request(account_id, donor_identifier, message_id, observed_at):
    if (
        not isinstance(account_id, str)
        or re.fullmatch(r"[1-9][0-9]{0,18}", account_id) is None
        or not 0 < int(account_id) < 2**63
        or not isinstance(donor_identifier, str)
        or re.fullmatch(r"-[1-9][0-9]{0,18}", donor_identifier) is None
        or not -(2**63) <= int(donor_identifier) <= -1000000000001
        or type(message_id) is not int
        or not 1 <= message_id <= 2**31 - 1
    ):
        raise ValueError("Invalid canonical Telegram engagement identity")
    return utc_timestamp(observed_at)


def validate_engagement_counter(value):
    if value is not None and (type(value) is not int or not 0 <= value < 2**63):
        raise ValueError("Invalid bounded Telegram engagement count")
    return value


@dataclass(frozen=True, slots=True)
class TelegramEngagementObservation:
    account_id: str
    donor_identifier: str
    message_id: int
    published_at: datetime
    observed_at: datetime
    views: int | None = None
    forwards: int | None = None
    reactions: int | None = None

    def __post_init__(self):
        observed = validate_engagement_request(
            self.account_id, self.donor_identifier, self.message_id, self.observed_at
        )
        published = utc_timestamp(self.published_at)
        if published > observed:
            raise ValueError("Publication is after engagement observation")
        for metric in (self.views, self.forwards, self.reactions):
            validate_engagement_counter(metric)
        object.__setattr__(self, "published_at", published)
        object.__setattr__(self, "observed_at", observed)


@dataclass(frozen=True, slots=True)
class EngagementVelocity:
    views_per_minute: float | None
    forwards_per_minute: float | None
    reactions_per_minute: float | None
    reset_metrics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EngagementAcceleration:
    views_per_minute_squared: float | None
    forwards_per_minute_squared: float | None
    reactions_per_minute_squared: float | None


def engagement_velocity(previous, current) -> EngagementVelocity:
    if not isinstance(previous, TelegramEngagementObservation) or not isinstance(
        current, TelegramEngagementObservation
    ):
        raise TypeError("Rates require validated engagement observations")
    if (
        previous.account_id,
        previous.donor_identifier,
        previous.message_id,
        previous.published_at,
    ) != (
        current.account_id,
        current.donor_identifier,
        current.message_id,
        current.published_at,
    ) or current.observed_at <= previous.observed_at:
        raise ValueError("Rates require the same source and strictly increasing observations")
    minutes = (current.observed_at - previous.observed_at).total_seconds() / 60
    rates, resets = [], []
    for name in ("views", "forwards", "reactions"):
        before, after = getattr(previous, name), getattr(current, name)
        if before is None or after is None:
            rates.append(None)
        elif after < before:
            rates.append(None)
            resets.append(name)
        else:
            rates.append((after - before) / minutes)
    return EngagementVelocity(*rates, tuple(resets))


def engagement_acceleration(first, second, third) -> EngagementAcceleration:
    earlier, later = engagement_velocity(first, second), engagement_velocity(second, third)
    # Adjacent midpoint distance equals half the total span, even for unequal intervals.
    midpoint_minutes = (third.observed_at - first.observed_at).total_seconds() / 120
    values = []
    for name in ("views_per_minute", "forwards_per_minute", "reactions_per_minute"):
        before, after = getattr(earlier, name), getattr(later, name)
        values.append(
            None if before is None or after is None else (after - before) / midpoint_minutes
        )
    return EngagementAcceleration(*values)
