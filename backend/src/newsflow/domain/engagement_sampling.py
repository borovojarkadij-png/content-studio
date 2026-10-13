"""Clock-free advancement of the retained Telegram sampling schedule."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from newsflow.domain.engagement import utc_timestamp

THRESHOLD_SECONDS = (60, 300, 600, 1200, 1800, 3600)


@dataclass(frozen=True, slots=True)
class SamplingAdvance:
    step: int
    available_at: datetime
    missed_windows: int


def advance_sampling(
    published_at, observed_at, *, step: int, missed_windows: int
) -> SamplingAdvance:
    """Fulfill the current acquisition and skip only elapsed later thresholds."""
    if type(step) is not int or not 0 <= step <= 6:
        raise ValueError("Invalid sampling step")
    if type(missed_windows) is not int or not 0 <= missed_windows <= 6:
        raise ValueError("Invalid sampling missed windows")
    published, observed = utc_timestamp(published_at), utc_timestamp(observed_at)
    age = observed - published
    if age < timedelta(0) or (step and age < timedelta(seconds=THRESHOLD_SECONDS[step - 1])):
        raise ValueError("Invalid sampling observation time")
    skipped = sum(
        age >= timedelta(seconds=seconds)
        for index, seconds in enumerate(THRESHOLD_SECONDS, 1)
        if index > step
    )
    missed = missed_windows + skipped
    if missed > 6:
        raise ValueError("Invalid accumulated sampling missed windows")
    for index, seconds in enumerate(THRESHOLD_SECONDS, 1):
        if index > step and age < timedelta(seconds=seconds):
            try:
                available = published + timedelta(seconds=seconds)
            except OverflowError:
                raise ValueError("Sampling schedule is outside UTC bounds") from None
            return SamplingAdvance(index, available, missed)
    return SamplingAdvance(7, observed, missed)
