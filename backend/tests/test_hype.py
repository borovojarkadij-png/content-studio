from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta, timezone

import pytest

from newsflow.domain.hype import (
    HypeComponents,
    HypeWeights,
    freshness_score,
    relative_velocity_score,
    score_hype,
)

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)


def weights(**changes):
    values = dict.fromkeys((field.name for field in fields(HypeWeights)), 0)
    values.update(changes)
    return HypeWeights(**values)


def test_weighted_known_zero_is_evidence_and_missing_is_unknown():
    result = score_hype(
        HypeComponents(freshness=100, view_velocity=0),
        weights(freshness=1, view_velocity=3),
    )
    assert (result.score, result.coverage, result.reason) == (25, 1, "READY")
    empty = score_hype(HypeComponents())
    assert (empty.score, empty.coverage, empty.reason) == (None, 0, "INSUFFICIENT_EVIDENCE")


def test_default_weights_and_all_eleven_components_participate():
    # Default freshness10 + view20 over total100: exactly30% evidence.
    result = score_hype(HypeComponents(freshness=100, view_velocity=0), minimum_coverage=0.3)
    assert (result.score, result.coverage) == (pytest.approx(100 / 3), 0.3)
    for field in fields(HypeComponents):
        result = score_hype(HypeComponents(**{field.name: 60}), weights(**{field.name: 1}))
        assert (result.score, result.coverage) == (60, 1)


@pytest.mark.parametrize(
    "name,coverage",
    [
        ("freshness", 0.10),
        ("view_velocity", 0.20),
        ("forward_velocity", 0.10),
        ("reaction_velocity", 0.10),
        ("cross_source_trend", 0.10),
        ("source_authority", 0.05),
        ("breaking_signals", 0.05),
        ("ai_importance", 0.05),
        ("channel_relevance", 0.10),
        ("topic_priority", 0.10),
        ("historical_performance", 0.05),
    ],
)
def test_each_default_weight_reports_its_actual_evidence_share(name, coverage):
    result = score_hype(HypeComponents(**{name: 50}), minimum_coverage=0)
    assert (result.score, result.coverage) == (50, coverage)


def test_coverage_boundary_disabled_unknowns_and_no_known_enabled_weight():
    policy = weights(freshness=1, view_velocity=1)
    components = HypeComponents(freshness=80, ai_importance=100)
    result = score_hype(components, policy)
    assert (result.score, result.coverage, result.reason) == (80, 0.5, "READY")
    result = score_hype(components, policy, minimum_coverage=0.50000001)
    assert (result.score, result.coverage, result.reason) == (None, 0.5, "INSUFFICIENT_EVIDENCE")
    assert score_hype(HypeComponents(ai_importance=100), policy, minimum_coverage=0).score is None


def test_known_zero_and_fractional_evidence_are_not_rounded_or_fabricated():
    policy = weights(view_velocity=1)
    zero = score_hype(HypeComponents(view_velocity=0), policy)
    assert (zero.score, zero.coverage) == (0, 1)
    precise = score_hype(HypeComponents(view_velocity=50.00000001), policy)
    assert precise.score == 50.00000001
    assert all(
        getattr(precise.components, name) is None
        for name in (
            "cross_source_trend",
            "source_authority",
            "breaking_signals",
            "ai_importance",
            "channel_relevance",
            "topic_priority",
            "historical_performance",
        )
    )


@pytest.mark.parametrize("value", [True, -1, 101, float("nan"), float("inf"), "50", 10**500])
def test_components_reject_invalid_scores(value):
    with pytest.raises(ValueError):
        HypeComponents(freshness=value)


@pytest.mark.parametrize("value", [True, -1, 1001, 1.0, None, float("nan"), float("inf")])
def test_weights_reject_non_integer_or_unbounded_values(value):
    with pytest.raises(ValueError):
        weights(freshness=value)


def test_zero_total_weights_rejected():
    with pytest.raises(ValueError):
        weights()


@pytest.mark.parametrize("value", [True, -0.1, 1.1, None, float("nan"), float("inf"), 10**500])
def test_minimum_coverage_always_validated(value):
    with pytest.raises(ValueError):
        score_hype(HypeComponents(), minimum_coverage=value)


def test_frozen_inputs_revalidated_and_outputs_immutable():
    components = HypeComponents(freshness=50)
    policy = HypeWeights()
    result = score_hype(components)
    for obj, name in ((components, "freshness"), (policy, "freshness"), (result, "score")):
        with pytest.raises(FrozenInstanceError):
            setattr(obj, name, 1)
    object.__setattr__(components, "freshness", float("nan"))
    with pytest.raises(ValueError):
        score_hype(components)
    object.__setattr__(policy, "freshness", True)
    with pytest.raises(ValueError):
        score_hype(HypeComponents(), policy)
    with pytest.raises(TypeError):
        score_hype(object())
    with pytest.raises(TypeError):
        score_hype(HypeComponents(), object())


@pytest.mark.parametrize("age, expected", [(0, 100), (30, 50), (60, 25), (100000, 0)])
def test_freshness_literal_half_life_values(age, expected):
    assert freshness_score(NOW, NOW + timedelta(minutes=age)) == expected


def test_freshness_aware_offsets_and_half_life_bounds():
    offset = timezone(timedelta(hours=3))
    assert (
        freshness_score(NOW.astimezone(offset), NOW + timedelta(minutes=1), half_life_minutes=1)
        == 50
    )
    assert freshness_score(NOW, NOW + timedelta(minutes=10080), half_life_minutes=10080) == 50
    with pytest.raises(ValueError):
        freshness_score(NOW.replace(tzinfo=None), NOW)
    with pytest.raises(ValueError):
        freshness_score(NOW, NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        freshness_score(NOW, NOW - timedelta(microseconds=1))
    assert freshness_score(datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC)) == 0


@pytest.mark.parametrize("value", [True, 0, 0.99, 10081, float("nan"), float("inf"), 10**500])
def test_freshness_rejects_invalid_half_life(value):
    with pytest.raises(ValueError):
        freshness_score(NOW, NOW, half_life_minutes=value)


@pytest.mark.parametrize(
    "ratio, expected", [(None, None), (0, 0), (0.5, 25), (1, 50), (2, 100), (1e308, 100)]
)
def test_relative_velocity_literal_scores_and_no_multiplication_overflow(ratio, expected):
    assert relative_velocity_score(ratio) == expected


@pytest.mark.parametrize("ratio", [True, -1, "1", float("nan"), float("inf"), 10**500])
def test_relative_velocity_rejects_invalid_or_overflowing_ratio(ratio):
    with pytest.raises(ValueError):
        relative_velocity_score(ratio)
