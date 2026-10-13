from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from newsflow.domain.engagement_sampling import advance_sampling

PUBLISHED = datetime(2030, 1, 1, tzinfo=UTC)


def test_delayed_discovery_and_late_scheduled_sample_skip_only_unfulfilled_windows():
    result = advance_sampling(
        PUBLISHED, PUBLISHED + timedelta(seconds=60), step=0, missed_windows=0
    )
    assert result.step == 2 and result.missed_windows == 1
    assert result.available_at == PUBLISHED + timedelta(seconds=300)
    late = advance_sampling(PUBLISHED, PUBLISHED + timedelta(seconds=601), step=1, missed_windows=0)
    assert late.step == 4 and late.missed_windows == 2


@pytest.mark.parametrize(
    "age,want_step,want_missed,want_available",
    [
        (59.999999, 1, 0, 60),
        (60, 2, 1, 300),
        (60.000001, 2, 1, 300),
        (299.999999, 2, 1, 300),
        (300, 3, 2, 600),
        (300.000001, 3, 2, 600),
        (599.999999, 3, 2, 600),
        (600, 4, 3, 1200),
        (600.000001, 4, 3, 1200),
        (1199.999999, 4, 3, 1200),
        (1200, 5, 4, 1800),
        (1200.000001, 5, 4, 1800),
        (1799.999999, 5, 4, 1800),
        (1800, 6, 5, 3600),
        (1800.000001, 6, 5, 3600),
        (3599.999999, 6, 5, 3600),
        (3600, 7, 6, 3600),
        (3600.000001, 7, 6, 3600.000001),
        (7200, 7, 6, 7200),
    ],
)
def test_discovery_threshold_boundaries(age, want_step, want_missed, want_available):
    result = advance_sampling(
        PUBLISHED, PUBLISHED + timedelta(seconds=age), step=0, missed_windows=0
    )
    assert (result.step, result.missed_windows) == (want_step, want_missed)
    assert result.available_at == PUBLISHED + timedelta(seconds=want_available)


@pytest.mark.parametrize(
    "step,age,missed,want_step,want_missed,want_available",
    [
        (1, 60, 0, 2, 0, 300),
        (1, 61, 0, 2, 0, 300),
        (1, 300, 0, 3, 1, 600),
        (2, 601, 1, 4, 2, 1200),
        (4, 1200, 2, 5, 2, 1800),
        (5, 1801, 2, 6, 2, 3600),
        (6, 3600, 2, 7, 2, 3600),
        (6, 7200, 6, 7, 6, 7200),
    ],
)
def test_scheduled_step_fulfills_itself_without_recounting(
    step, age, missed, want_step, want_missed, want_available
):
    result = advance_sampling(
        PUBLISHED, PUBLISHED + timedelta(seconds=age), step=step, missed_windows=missed
    )
    assert (result.step, result.missed_windows) == (want_step, want_missed)
    assert result.available_at == PUBLISHED + timedelta(seconds=want_available)


@pytest.mark.parametrize("step,age", [(1, 59), (2, 299), (3, 599), (4, 1199), (5, 1799), (6, 3599)])
def test_early_scheduled_observation_cannot_fulfill_future_window(step, age):
    with pytest.raises(ValueError):
        advance_sampling(PUBLISHED, PUBLISHED + timedelta(seconds=age), step=step, missed_windows=0)


@pytest.mark.parametrize("field", ["step", "missed_windows"])
@pytest.mark.parametrize("invalid", [True, False, -1, 7, 1.0, "1", None, 2**63])
def test_exact_bounded_input_counters(field, invalid):
    arguments = {"step": 0, "missed_windows": 0, field: invalid}
    with pytest.raises(ValueError):
        advance_sampling(PUBLISHED, PUBLISHED + timedelta(seconds=3600), **arguments)


@pytest.mark.parametrize("field", ["published_at", "observed_at"])
@pytest.mark.parametrize("invalid", [None, True, "2030-01-01", PUBLISHED.replace(tzinfo=None)])
def test_aware_timestamps_required(field, invalid):
    arguments = {"published_at": PUBLISHED, "observed_at": PUBLISHED, field: invalid}
    with pytest.raises(ValueError):
        advance_sampling(**arguments, step=0, missed_windows=0)


def test_future_publication_and_missed_counter_overflow_fail_closed():
    with pytest.raises(ValueError):
        advance_sampling(PUBLISHED, PUBLISHED - timedelta(microseconds=1), step=0, missed_windows=0)
    with pytest.raises(ValueError):
        advance_sampling(PUBLISHED, PUBLISHED + timedelta(seconds=3600), step=0, missed_windows=1)


def test_normalizes_offsets_and_returns_frozen_result():
    offset = timezone(timedelta(hours=3))
    result = advance_sampling(
        PUBLISHED.astimezone(offset),
        (PUBLISHED + timedelta(seconds=60)).astimezone(offset),
        step=1,
        missed_windows=0,
    )
    assert result.available_at == PUBLISHED + timedelta(seconds=300)
    assert result.available_at.tzinfo is UTC
    with pytest.raises(FrozenInstanceError):
        result.step = 6


def test_extreme_dates_and_schedule_overflow_fail_closed():
    earliest = datetime.min.replace(tzinfo=UTC)
    latest = datetime.max.replace(tzinfo=UTC)
    assert advance_sampling(
        earliest, earliest, step=0, missed_windows=0
    ).available_at == earliest + timedelta(seconds=60)
    result = advance_sampling(earliest, latest, step=0, missed_windows=0)
    assert (result.step, result.available_at, result.missed_windows) == (7, latest, 6)
    with pytest.raises(ValueError):
        advance_sampling(latest, latest, step=0, missed_windows=0)
    for value in (
        earliest.replace(tzinfo=timezone(timedelta(hours=3))),
        latest.replace(tzinfo=timezone(timedelta(hours=-3))),
    ):
        with pytest.raises(ValueError):
            advance_sampling(value, value, step=0, missed_windows=0)
