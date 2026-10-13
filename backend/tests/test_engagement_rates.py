from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

NOW = datetime(2026, 10, 13, 12, tzinfo=UTC)


def observation(minutes=0, **changes):
    from newsflow.domain.engagement import TelegramEngagementObservation

    fields = {
        "account_id": "1",
        "donor_identifier": "-1001234567890",
        "message_id": 1,
        "published_at": NOW - timedelta(hours=1),
        "observed_at": NOW + timedelta(minutes=minutes),
        "views": 0,
        "forwards": 0,
        "reactions": 0,
    }
    fields.update(changes)
    return TelegramEngagementObservation(**fields)


def test_velocity_and_unequal_midpoint_acceleration_use_elapsed_minutes():
    from newsflow.domain.engagement import engagement_acceleration, engagement_velocity

    first, second = observation(), observation(2, views=100, forwards=4, reactions=2)
    equal = observation(6, views=300, forwards=12, reactions=6)
    rate = engagement_velocity(first, second)
    assert (rate.views_per_minute, rate.forwards_per_minute, rate.reactions_per_minute) == (
        50,
        2,
        1,
    )
    assert rate.reset_metrics == ()
    assert engagement_acceleration(first, second, equal).views_per_minute_squared == 0
    faster = observation(6, views=500, forwards=28, reactions=18)
    acceleration = engagement_acceleration(first, second, faster)
    assert acceleration.views_per_minute_squared == pytest.approx(50 / 3)
    assert acceleration.forwards_per_minute_squared == pytest.approx(4 / 3)
    assert acceleration.reactions_per_minute_squared == 1
    with pytest.raises(FrozenInstanceError):
        rate.views_per_minute = 1
    with pytest.raises(FrozenInstanceError):
        acceleration.views_per_minute_squared = 1


def test_missing_reset_and_equal_counters_preserve_uncertainty_per_metric():
    from newsflow.domain.engagement import engagement_acceleration, engagement_velocity

    first = observation(views=100, forwards=None, reactions=7)
    second = observation(2, views=50, forwards=3, reactions=7)
    rate = engagement_velocity(first, second)
    assert (rate.views_per_minute, rate.forwards_per_minute, rate.reactions_per_minute) == (
        None,
        None,
        0,
    )
    assert rate.reset_metrics == ("views",)
    third = observation(4, views=200, forwards=None, reactions=5)
    acceleration = engagement_acceleration(first, second, third)
    assert (
        acceleration.views_per_minute_squared,
        acceleration.forwards_per_minute_squared,
        acceleration.reactions_per_minute_squared,
    ) == (None, None, None)
    assert engagement_velocity(second, third).reset_metrics == ("reactions",)


@pytest.mark.parametrize(
    "change",
    [
        {"account_id": "2"},
        {"donor_identifier": "-1001234567891"},
        {"message_id": 2},
        {"published_at": NOW},
        {"observed_at": NOW},
        {"observed_at": NOW - timedelta(minutes=1)},
    ],
)
def test_rates_reject_foreign_content_or_non_increasing_observations(change):
    from newsflow.domain.engagement import engagement_acceleration, engagement_velocity

    first, second, third = observation(), observation(2), observation(4)
    invalid = replace(second, **change)
    with pytest.raises(ValueError):
        engagement_velocity(first, invalid)
    with pytest.raises(ValueError):
        engagement_acceleration(first, invalid, third)


@pytest.mark.parametrize("field", ["views", "forwards", "reactions"])
@pytest.mark.parametrize("value", [True, 1.0, -1, 2**63, "1"])
def test_observation_rejects_non_exact_or_unbounded_counters(field, value):
    with pytest.raises(ValueError):
        observation(**{field: value})


@pytest.mark.parametrize(
    "change",
    [
        {"account_id": "01"},
        {"account_id": str(2**63)},
        {"donor_identifier": "-1000000000000"},
        {"message_id": True},
        {"published_at": NOW.replace(tzinfo=None)},
        {"observed_at": NOW.replace(tzinfo=None)},
        {"published_at": NOW + timedelta(seconds=1)},
    ],
)
def test_observation_requires_canonical_identity_and_aware_ordered_time(change):
    with pytest.raises(ValueError):
        observation(**change)


def test_signed_boundaries_are_accepted_without_overflow():
    result = observation(
        account_id=str(2**63 - 1),
        donor_identifier=str(-(2**63)),
        message_id=2**31 - 1,
        views=2**63 - 1,
        forwards=None,
        reactions=0,
    )
    assert result.views == 9223372036854775807


def test_rates_reject_unvalidated_object_types():
    from newsflow.domain.engagement import engagement_velocity

    with pytest.raises(TypeError):
        engagement_velocity(object(), observation())
