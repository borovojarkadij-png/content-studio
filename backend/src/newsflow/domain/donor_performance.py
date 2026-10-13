"""Pure comparable donor interval evidence; no SDK or persistence dependency."""

import math
from dataclasses import dataclass, fields
from statistics import median

from newsflow.domain.engagement import TelegramEngagementObservation, engagement_velocity


def _validated_observation(observation):
    if not isinstance(observation, TelegramEngagementObservation):
        raise TypeError("Windows require engagement observations")
    return TelegramEngagementObservation(
        **{
            field.name: getattr(observation, field.name)
            for field in fields(TelegramEngagementObservation)
        }
    )


@dataclass(frozen=True, slots=True)
class EngagementWindow:
    previous: TelegramEngagementObservation
    current: TelegramEngagementObservation

    def __post_init__(self):
        previous = _validated_observation(self.previous)
        current = _validated_observation(self.current)
        engagement_velocity(previous, current)
        object.__setattr__(self, "previous", previous)
        object.__setattr__(self, "current", current)


@dataclass(frozen=True, slots=True)
class DonorRelativePerformance:
    expected_views_per_minute: float | None
    relative_views_velocity: float | None
    views_samples: int
    expected_forwards_per_minute: float | None
    relative_forwards_velocity: float | None
    forwards_samples: int
    expected_reactions_per_minute: float | None
    relative_reactions_velocity: float | None
    reactions_samples: int


def _validated_window(window):
    if not isinstance(window, EngagementWindow):
        raise TypeError("Donor performance requires engagement windows")
    return EngagementWindow(window.previous, window.current)


def _identity(observation):
    return observation.account_id, observation.donor_identifier, observation.message_id


def _dimensions(window):
    return (
        window.current.observed_at - window.current.published_at,
        window.current.observed_at - window.previous.observed_at,
    )


def donor_relative_performance(target, samples, *, minimum_samples=5) -> DonorRelativePerformance:
    """Compare adjacent rates with one deterministic, comparable interval per prior message."""
    if type(minimum_samples) is not int or not 1 <= minimum_samples <= 200:
        raise ValueError("minimum_samples requires an exact int in 1..200")
    if type(samples) is not tuple:
        raise TypeError("Donor samples require an explicit tuple")
    if len(samples) > 2000:
        raise ValueError("Donor samples are bounded to 2000 windows")
    target = _validated_window(target)
    samples = tuple(_validated_window(sample) for sample in samples)

    publications, observations = {}, {}
    for window in (target, *samples):
        for observation in (window.previous, window.current):
            identity = _identity(observation)
            publication = publications.setdefault(identity, observation.published_at)
            if publication != observation.published_at:
                raise ValueError("A canonical source has conflicting publication times")
            key = identity, observation.observed_at
            known = observations.setdefault(key, observation)
            if known != observation:
                raise ValueError("A canonical observation has conflicting values")

    target_age, target_duration = _dimensions(target)
    selected = {}
    for sample in samples:
        end = sample.current
        if (
            _identity(end)[:2] != _identity(target.current)[:2]
            or end.message_id == target.current.message_id
            or end.published_at >= target.current.published_at
            or end.observed_at > target.current.observed_at
        ):
            continue
        age, duration = _dimensions(sample)
        age_distance = abs(age - target_age)
        duration_distance = abs(duration - target_duration)
        # Timedelta arithmetic preserves inclusive boundaries down to a microsecond.
        if 4 * age_distance > target_age or 4 * duration_distance > target_duration:
            continue
        order = (
            age_distance,
            duration_distance,
            target.current.observed_at - end.observed_at,
            target.current.observed_at - sample.previous.observed_at,
        )
        existing = selected.get(end.message_id)
        if existing is None or order < existing[0]:
            selected[end.message_id] = order, sample

    velocities = [
        engagement_velocity(sample.previous, sample.current) for _, sample in selected.values()
    ]
    target_velocity = engagement_velocity(target.previous, target.current)
    result = []
    for metric in ("views_per_minute", "forwards_per_minute", "reactions_per_minute"):
        rates = [
            getattr(velocity, metric)
            for velocity in velocities
            if getattr(velocity, metric) is not None
        ]
        expected = median(rates) if len(rates) >= minimum_samples else None
        actual = getattr(target_velocity, metric)
        ratio = None
        if actual is not None and expected is not None and expected > 0:
            ratio = actual / expected
            if not math.isfinite(ratio):
                raise ValueError("Donor relative velocity overflow")
        result.extend((expected, ratio, len(rates)))
    return DonorRelativePerformance(*result)
