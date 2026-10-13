"""Pure evidence-weighted ranking inputs; scores grant no editorial authority."""

import math
from dataclasses import dataclass, fields

from newsflow.domain.engagement import utc_timestamp


def _finite_number(value, *, minimum, maximum=None):
    if type(value) not in (int, float):
        raise ValueError("Expected an exact finite int or float")
    try:
        valid = math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or value < minimum or (maximum is not None and value > maximum):
        raise ValueError("Numeric input is outside finite bounds")
    return value


@dataclass(frozen=True, slots=True)
class HypeComponents:
    freshness: float | None = None
    view_velocity: float | None = None
    forward_velocity: float | None = None
    reaction_velocity: float | None = None
    cross_source_trend: float | None = None
    source_authority: float | None = None
    breaking_signals: float | None = None
    ai_importance: float | None = None
    channel_relevance: float | None = None
    topic_priority: float | None = None
    historical_performance: float | None = None

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if value is not None:
                _finite_number(value, minimum=0, maximum=100)


@dataclass(frozen=True, slots=True)
class HypeWeights:
    freshness: int = 10
    view_velocity: int = 20
    forward_velocity: int = 10
    reaction_velocity: int = 10
    cross_source_trend: int = 10
    source_authority: int = 5
    breaking_signals: int = 5
    ai_importance: int = 5
    channel_relevance: int = 10
    topic_priority: int = 10
    historical_performance: int = 5

    def __post_init__(self):
        values = [getattr(self, field.name) for field in fields(self)]
        if any(type(value) is not int or not 0 <= value <= 1000 for value in values):
            raise ValueError("Hype weights require exact ints in 0..1000")
        if sum(values) == 0:
            raise ValueError("Hype weights require a positive total")


@dataclass(frozen=True, slots=True)
class HypeAssessment:
    score: float | None
    coverage: float
    components: HypeComponents
    weights: HypeWeights
    reason: str


def score_hype(components, weights=None, *, minimum_coverage=0.5) -> HypeAssessment:
    """Average known enabled evidence, preserving explicit coverage and cold starts."""
    _finite_number(minimum_coverage, minimum=0, maximum=1)
    if not isinstance(components, HypeComponents):
        raise TypeError("Scoring requires HypeComponents")
    if weights is None:
        weights = HypeWeights()
    if not isinstance(weights, HypeWeights):
        raise TypeError("Scoring requires HypeWeights")
    # Reconstruct at the boundary: frozen dataclasses can still be forged with object.__setattr__.
    components = HypeComponents(
        **{field.name: getattr(components, field.name) for field in fields(HypeComponents)}
    )
    weights = HypeWeights(
        **{field.name: getattr(weights, field.name) for field in fields(HypeWeights)}
    )
    total_weight = 0
    known_weight = 0
    weighted_values = []
    for field in fields(HypeComponents):
        weight = getattr(weights, field.name)
        value = getattr(components, field.name)
        total_weight += weight
        if weight > 0 and value is not None:
            known_weight += weight
            weighted_values.append(value * weight)
    coverage = known_weight / total_weight
    if known_weight == 0 or coverage < minimum_coverage:
        return HypeAssessment(None, coverage, components, weights, "INSUFFICIENT_EVIDENCE")
    return HypeAssessment(
        math.fsum(weighted_values) / known_weight, coverage, components, weights, "READY"
    )


def freshness_score(published_at, as_of, *, half_life_minutes=30):
    """Clock-free exponential decay, measured from publication to an explicit instant."""
    _finite_number(half_life_minutes, minimum=1, maximum=10080)
    published_at, as_of = utc_timestamp(published_at), utc_timestamp(as_of)
    if published_at > as_of:
        raise ValueError("Freshness requires publication at or before as_of")
    age_minutes = (as_of - published_at).total_seconds() / 60
    return 100 * 2 ** (-age_minutes / half_life_minutes)


def relative_velocity_score(ratio):
    if ratio is None:
        return None
    _finite_number(ratio, minimum=0)
    # Saturate before multiplication, including finite ratios whose product would overflow.
    return 100.0 if ratio >= 2 else 50 * ratio
