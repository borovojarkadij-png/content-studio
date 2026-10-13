from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from newsflow.domain.donor_performance import EngagementWindow, donor_relative_performance
from newsflow.domain.engagement import TelegramEngagementObservation

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)


def window(message=1, *, published=None, start=10, end=20, before=0, after=200, **changes):
    published = published or NOW
    identity = {"account_id": "1", "donor_identifier": "-1001234567890", "message_id": message}
    identity.update(changes)
    return EngagementWindow(
        TelegramEngagementObservation(
            **identity,
            published_at=published,
            observed_at=published + timedelta(minutes=start),
            views=before,
            forwards=before,
            reactions=before,
        ),
        TelegramEngagementObservation(
            **identity,
            published_at=published,
            observed_at=published + timedelta(minutes=end),
            views=after,
            forwards=after,
            reactions=after,
        ),
    )


def history(**changes):
    return tuple(window(i, published=NOW - timedelta(days=i), **changes) for i in range(2, 7))


def test_baseline_uses_interval_median_and_donor_relative_fairness():
    small = donor_relative_performance(window(after=400), history())
    large = donor_relative_performance(window(after=40000), history(after=20000))
    assert (
        small.expected_views_per_minute,
        small.relative_views_velocity,
        small.views_samples,
    ) == (20, 2, 5)
    assert (
        large.expected_views_per_minute,
        large.relative_views_velocity,
        large.views_samples,
    ) == (2000, 2, 5)
    assert (
        small.expected_forwards_per_minute,
        small.relative_forwards_velocity,
        small.forwards_samples,
    ) == (20, 2, 5)
    assert (
        small.expected_reactions_per_minute,
        small.relative_reactions_velocity,
        small.reactions_samples,
    ) == (20, 2, 5)
    unequal = donor_relative_performance(window(start=8, after=240), history(after=200))
    assert (unequal.expected_views_per_minute, unequal.relative_views_velocity) == (20, 1)


def test_median_is_per_metric_and_counter_resets_do_not_poison_other_metrics():
    samples = list(history())
    samples[0] = replace(samples[0], current=replace(samples[0].current, views=1000, forwards=None))
    samples[1] = replace(samples[1], previous=replace(samples[1].previous, views=300))
    result = donor_relative_performance(window(), tuple(samples), minimum_samples=4)
    assert (result.expected_views_per_minute, result.views_samples) == (20, 4)
    assert (result.expected_forwards_per_minute, result.forwards_samples) == (20, 4)
    assert (result.expected_reactions_per_minute, result.reactions_samples) == (20, 5)
    result = donor_relative_performance(window(), tuple(samples))
    assert (result.expected_views_per_minute, result.relative_views_velocity) == (None, None)


def test_even_median_and_large_lifetime_counts_do_not_replace_interval_rates():
    samples = (
        window(2, published=NOW - timedelta(days=1), before=10000, after=10010),
        window(3, published=NOW - timedelta(days=1), before=0, after=30),
    )
    result = donor_relative_performance(
        window(before=90000, after=90040), samples, minimum_samples=2
    )
    assert (result.expected_views_per_minute, result.relative_views_velocity) == (2, 2)


def test_replays_and_multiple_windows_from_one_message_are_not_independent_evidence():
    first = history()[0]
    alternate = window(2, published=first.current.published_at, start=9, end=19, after=400)
    result = donor_relative_performance(window(), (first,) * 20 + (alternate,))
    assert (result.expected_views_per_minute, result.views_samples) == (None, 1)
    result = donor_relative_performance(window(), (first,) * 2000, minimum_samples=1)
    assert (result.expected_views_per_minute, result.views_samples) == (20, 1)


@pytest.mark.parametrize(
    "start,end", [(7.5, 15), (12.5, 25), (7.5, 20), (12.5, 20), (5, 15), (15, 25)]
)
def test_comparability_25_percent_boundaries_are_inclusive(start, end):
    sample = window(2, published=NOW - timedelta(days=1), start=start, end=end)
    result = donor_relative_performance(window(), (sample,), minimum_samples=1)
    assert result.views_samples == 1


@pytest.mark.parametrize(
    "start,end", [(4.999999, 14.999999), (15.000001, 25.000001), (7.499999, 20), (12.500001, 20)]
)
def test_comparability_just_outside_age_or_duration_is_excluded(start, end):
    sample = window(2, published=NOW - timedelta(days=1), start=start, end=end)
    assert donor_relative_performance(window(), (sample,), minimum_samples=1).views_samples == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"account_id": "2"},
        {"donor_identifier": "-1001234567891"},
        {"message": 1},
        {"published": NOW},
        {"published": NOW + timedelta(minutes=1)},
        {"published": NOW - timedelta(minutes=1), "start": 12, "end": 22},
    ],
)
def test_foreign_current_nonprior_and_future_observations_excluded(changes):
    params = {"message": 2, "published": NOW - timedelta(days=1)}
    params.update(changes)
    # The target-message exclusion uses the same publication to avoid an intentional conflict.
    if params["message"] == 1:
        params["published"] = NOW
    assert (
        donor_relative_performance(window(), (window(**params),), minimum_samples=1).views_samples
        == 0
    )


def test_selection_closest_age_then_duration_then_latest_end_is_order_independent():
    publication = NOW - timedelta(days=1)
    samples = (
        window(2, published=publication, start=9, end=19, after=100),
        window(2, published=publication, start=10, end=21, after=220),
        window(2, published=publication, start=11, end=21, before=1, after=220),
    )
    # Closest duration outranks the later end when age distance ties.
    assert (
        donor_relative_performance(
            window(), samples[:2], minimum_samples=1
        ).expected_views_per_minute
        == 10
    )
    # Last window wins: same age distance, duration10, latest end21 over end19.
    for candidates in (samples, samples[::-1]):
        result = donor_relative_performance(window(), candidates, minimum_samples=1)
        assert result.expected_views_per_minute == 21.9
    closer = window(2, published=publication, start=12, end=20, after=320)
    assert (
        donor_relative_performance(
            window(), samples + (closer,), minimum_samples=1
        ).expected_views_per_minute
        == 40
    )


def test_selection_does_not_replace_a_best_window_with_a_worse_one_for_missing_metric():
    publication = NOW - timedelta(days=1)
    best = window(2, published=publication, before=300, after=200)
    best = replace(best, current=replace(best.current, forwards=400, reactions=400))
    alternate = window(2, published=publication, start=9, end=19, after=200)
    result = donor_relative_performance(window(), (alternate, best), minimum_samples=1)
    assert (result.expected_views_per_minute, result.views_samples) == (None, 0)
    assert (result.expected_forwards_per_minute, result.forwards_samples) == (10, 1)


def test_conflicting_observation_or_publication_rejected_even_if_excluded():
    sample = history()[0]
    conflicting = replace(sample, current=replace(sample.current, views=201))
    with pytest.raises(ValueError):
        donor_relative_performance(window(), (sample, conflicting))
    different_publication = window(2, published=sample.current.published_at - timedelta(days=1))
    with pytest.raises(ValueError):
        donor_relative_performance(window(), (sample, different_publication))
    target_conflict = window(1, published=NOW - timedelta(days=1), account_id="1")
    with pytest.raises(ValueError):
        donor_relative_performance(window(), (target_conflict,))
    foreign = window(2, account_id="2", published=NOW - timedelta(days=1))
    with pytest.raises(ValueError):
        donor_relative_performance(
            window(), (foreign, replace(foreign, current=replace(foreign.current, views=201)))
        )


def test_zero_median_unknown_and_reset_target_rates_remain_honest():
    zero = donor_relative_performance(window(), history(after=0))
    assert (zero.expected_views_per_minute, zero.relative_views_velocity, zero.views_samples) == (
        0,
        None,
        5,
    )
    target = window(before=100, after=0)
    result = donor_relative_performance(target, history())
    assert (result.expected_views_per_minute, result.relative_views_velocity) == (20, None)
    target = replace(window(), current=replace(window().current, views=None))
    assert donor_relative_performance(target, history()).relative_views_velocity is None
    assert donor_relative_performance(window(after=0), history()).relative_views_velocity == 0


def test_windows_validate_identity_publication_and_advancing_aware_time():
    valid = window()
    for changes in (
        {"message_id": 2},
        {"published_at": NOW - timedelta(minutes=1)},
        {"observed_at": valid.previous.observed_at},
    ):
        with pytest.raises(ValueError):
            EngagementWindow(valid.previous, replace(valid.current, **changes))
    with pytest.raises(TypeError):
        EngagementWindow(object(), valid.current)
    forged = replace(valid.current)
    object.__setattr__(forged, "observed_at", forged.observed_at.replace(tzinfo=None))
    with pytest.raises(ValueError):
        EngagementWindow(valid.previous, forged)
    offset = timezone(timedelta(hours=3))
    normalized = EngagementWindow(
        replace(valid.previous, observed_at=valid.previous.observed_at.astimezone(offset)),
        replace(valid.current, observed_at=valid.current.observed_at.astimezone(offset)),
    )
    assert normalized == valid


def test_every_window_revalidated_before_exclusion_and_results_frozen():
    target = window()
    foreign = window(2, account_id="2", published=NOW - timedelta(days=1))
    object.__setattr__(foreign.current, "views", True)
    with pytest.raises(ValueError):
        donor_relative_performance(target, (foreign,))
    forged = window()
    object.__setattr__(forged, "current", forged.previous)
    with pytest.raises(ValueError):
        donor_relative_performance(forged, ())
    result = donor_relative_performance(target, history())
    with pytest.raises(FrozenInstanceError):
        result.views_samples = 0
    with pytest.raises(FrozenInstanceError):
        target.current = target.previous


@pytest.mark.parametrize(
    "field,value",
    [
        ("views", -1),
        ("forwards", float("nan")),
        ("reactions", float("inf")),
        ("message_id", True),
        ("account_id", "0"),
        ("published_at", NOW.replace(tzinfo=None)),
    ],
)
def test_forged_excluded_observations_still_reject_invalid_counter_identity_and_time(field, value):
    sample = window(2, account_id="2", published=NOW - timedelta(days=1))
    object.__setattr__(sample.current, field, value)
    with pytest.raises(ValueError):
        donor_relative_performance(window(), (sample,))


@pytest.mark.parametrize("minimum", [True, 0, 201, 1.0, None, float("inf")])
def test_minimum_samples_rejects_non_integer_and_out_of_bounds(minimum):
    with pytest.raises(ValueError):
        donor_relative_performance(window(), (), minimum_samples=minimum)


def test_sample_tuple_bounds_types_and_maximum_minimum():
    target = window()
    sample = history()[0]
    for samples in ([sample], iter((sample,)), None):
        with pytest.raises(TypeError):
            donor_relative_performance(target, samples)
    with pytest.raises(ValueError):
        donor_relative_performance(target, (sample,) * 2001)
    with pytest.raises(TypeError):
        donor_relative_performance(target, (object(),))
    with pytest.raises(TypeError):
        donor_relative_performance(object(), ())
    result = donor_relative_performance(target, (), minimum_samples=200)
    assert (result.expected_views_per_minute, result.views_samples) == (None, 0)
    samples = tuple(window(i, published=NOW - timedelta(days=1)) for i in range(2, 202))
    result = donor_relative_performance(target, samples, minimum_samples=200)
    assert (result.expected_views_per_minute, result.views_samples) == (20, 200)
