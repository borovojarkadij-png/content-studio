from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal
from itertools import permutations

import pytest

from newsflow.domain.intake_selection import (
    IntakeCandidate,
    IntakeSelectionDecision,
    IntakeSelectionPolicy,
    IntakeSelectionResult,
    select_intake_window,
)

WINDOW = "a" * 64
REVISION = "b" * 64


class IntSubclass(int):
    pass


class FloatSubclass(float):
    pass


class StrSubclass(str):
    pass


class CandidateSubclass(IntakeCandidate):
    pass


class PolicySubclass(IntakeSelectionPolicy):
    pass


class TupleSubclass(tuple):
    pass


def ten_rows():
    return tuple(IntakeCandidate(i, REVISION, i) for i in range(1, 11))


def test_hybrid_selects_top_stage_then_literal_random_pick():
    result = select_intake_window(
        ten_rows(), window_key=WINDOW, policy=IntakeSelectionPolicy(50, "HYBRID")
    )
    assert result.selected_ids == (10, 9, 8, 7, 3)
    assert result.eligible_count == 10
    assert result.quota == 5
    assert result.carry_out == 0
    assert result.decisions == (
        IntakeSelectionDecision(1, False, "NOT_SELECTED"),
        IntakeSelectionDecision(2, False, "NOT_SELECTED"),
        IntakeSelectionDecision(3, True, "SELECTED_RANDOM"),
        IntakeSelectionDecision(4, False, "NOT_SELECTED"),
        IntakeSelectionDecision(5, False, "NOT_SELECTED"),
        IntakeSelectionDecision(6, False, "NOT_SELECTED"),
        IntakeSelectionDecision(7, True, "SELECTED_TOP"),
        IntakeSelectionDecision(8, True, "SELECTED_TOP"),
        IntakeSelectionDecision(9, True, "SELECTED_TOP"),
        IntakeSelectionDecision(10, True, "SELECTED_TOP"),
    )


@pytest.mark.parametrize(
    "mode,expected,reason",
    [
        ("TOP_SCORE", (10, 9, 8, 7, 6), "SELECTED_TOP"),
        ("RANDOM", (8, 3, 7, 2, 1), "SELECTED_RANDOM"),
    ],
)
def test_modes_use_literal_selection_order(mode, expected, reason):
    result = select_intake_window(
        ten_rows(), window_key=WINDOW, policy=IntakeSelectionPolicy(50, mode)
    )
    assert result.selected_ids == expected
    assert (result.quota, result.carry_out) == (5, 0)
    assert {item.reason for item in result.decisions if item.selected} == {reason}


def test_top_score_selects_best_thirty_of_one_hundred():
    rows = tuple(IntakeCandidate(i, REVISION, i - 1) for i in range(1, 101))
    result = select_intake_window(
        rows, window_key=WINDOW, policy=IntakeSelectionPolicy(30, "TOP_SCORE")
    )
    assert result.selected_ids == (
        100,
        99,
        98,
        97,
        96,
        95,
        94,
        93,
        92,
        91,
        90,
        89,
        88,
        87,
        86,
        85,
        84,
        83,
        82,
        81,
        80,
        79,
        78,
        77,
        76,
        75,
        74,
        73,
        72,
        71,
    )
    assert (result.eligible_count, result.quota, result.carry_out) == (100, 30, 0)


@pytest.mark.parametrize(
    "percent,expected,reasons",
    [
        (0, (), ("NOT_SELECTED",) * 5),
        (20, (5,), ("NOT_SELECTED",) * 4 + ("SELECTED_TOP",)),
        (60, (5, 4, 3), ("NOT_SELECTED",) * 2 + ("SELECTED_TOP",) * 3),
        (100, (5, 4, 3, 2, 1), ("SELECTED_RANDOM",) + ("SELECTED_TOP",) * 4),
    ],
)
def test_hybrid_rounds_top_stage_up_and_never_pads_quota(percent, expected, reasons):
    rows = tuple(IntakeCandidate(i, REVISION, i) for i in range(1, 6))
    result = select_intake_window(rows, window_key=WINDOW, policy=IntakeSelectionPolicy(percent))
    assert result.selected_ids == expected
    assert tuple(item.reason for item in result.decisions) == reasons
    assert result.quota == len(expected)


@pytest.mark.parametrize("mode", ["TOP_SCORE", "RANDOM", "HYBRID"])
def test_blocked_unknown_below_threshold_and_equality_in_all_modes(mode):
    rows = (
        IntakeCandidate(5, REVISION, 100, False),
        IntakeCandidate(4, REVISION, None),
        IntakeCandidate(3, REVISION, 49.999),
        IntakeCandidate(2, REVISION, 50),
        IntakeCandidate(1, REVISION, None, False),
    )
    result = select_intake_window(
        rows, window_key=WINDOW, policy=IntakeSelectionPolicy(100, mode, 50), carry=99
    )
    selected_reason = "SELECTED_RANDOM" if mode == "RANDOM" else "SELECTED_TOP"
    assert result.selected_ids == (2,)
    assert (result.eligible_count, result.quota, result.carry_out) == (1, 1, 99)
    assert result.decisions == (
        IntakeSelectionDecision(1, False, "EXCLUDED"),
        IntakeSelectionDecision(2, True, selected_reason),
        IntakeSelectionDecision(3, False, "BELOW_THRESHOLD"),
        IntakeSelectionDecision(4, False, "UNKNOWN_SCORE"),
        IntakeSelectionDecision(5, False, "EXCLUDED"),
    )


def test_zero_is_known_and_none_does_not_consume_quota_or_carry():
    result = select_intake_window(
        (IntakeCandidate(1, REVISION, None), IntakeCandidate(2, REVISION, 0)),
        window_key=WINDOW,
        policy=IntakeSelectionPolicy(30),
        carry=90,
    )
    assert result.selected_ids == (2,)
    assert (result.eligible_count, result.quota, result.carry_out) == (1, 1, 20)


def test_empty_and_all_blocked_preserve_carry():
    for rows in (
        (),
        (IntakeCandidate(1, REVISION, 100, False),),
        (IntakeCandidate(1, REVISION, None),),
        (IntakeCandidate(1, REVISION, 0),),
    ):
        result = select_intake_window(
            rows, window_key=WINDOW, policy=IntakeSelectionPolicy(30, minimum_score=1), carry=90
        )
        assert result.selected_ids == ()
        assert (result.eligible_count, result.quota, result.carry_out) == (0, 0, 90)
        assert len(result.decisions) == len(rows)


def test_fractional_carry_accumulates_across_explicit_one_row_windows():
    rows = (IntakeCandidate(1, REVISION, 50),)
    carry = 0
    for expected_quota, expected_carry, expected_ids in (
        (0, 30, ()),
        (0, 60, ()),
        (0, 90, ()),
        (1, 20, (1,)),
    ):
        result = select_intake_window(
            rows, window_key=WINDOW, policy=IntakeSelectionPolicy(30), carry=carry
        )
        assert (result.quota, result.carry_out, result.selected_ids) == (
            expected_quota,
            expected_carry,
            expected_ids,
        )
        carry = result.carry_out


@pytest.mark.parametrize("mode", ["TOP_SCORE", "RANDOM", "HYBRID"])
def test_permutations_and_replays_preserve_the_entire_result(mode):
    rows = ten_rows()[:4]
    policy = IntakeSelectionPolicy(50, mode)
    original = select_intake_window(rows, window_key=WINDOW, policy=policy, carry=31)
    for reordered in permutations(rows):
        assert (
            select_intake_window(reordered, window_key=WINDOW, policy=policy, carry=31) == original
        )
    assert select_intake_window(rows, window_key=WINDOW, policy=policy, carry=31) == original


def test_top_score_ties_use_ascending_candidate_id():
    rows = tuple(IntakeCandidate(i, REVISION, 50) for i in (4, 2, 3, 1))
    result = select_intake_window(
        rows, window_key=WINDOW, policy=IntakeSelectionPolicy(50, "TOP_SCORE")
    )
    assert result.selected_ids == (1, 2)
    assert tuple(item.candidate_id for item in result.decisions) == (1, 2, 3, 4)


def test_digest_matches_independent_literal_canonical_payload():
    result = select_intake_window((IntakeCandidate(1, REVISION, 50),), window_key=WINDOW)
    assert result.algorithm_version == "intake-selection-v1"
    assert result.input_sha256 == "a96e4cd576b14e49d805b09ea4174093493a03dfd3ffa568512da412ee8e3a4d"
    assert result == select_intake_window(
        (IntakeCandidate(1, REVISION, 50.0),),
        window_key=WINDOW,
        policy=IntakeSelectionPolicy(100, "HYBRID", 0.0),
    )


@pytest.mark.parametrize(
    "change",
    [
        {"candidate_id": 2},
        {"revision_sha256": "c" * 64},
        {"score": 51},
        {"score": None},
        {"eligible": True},
    ],
)
def test_digest_binds_excluded_evidence(change):
    row = IntakeCandidate(1, REVISION, 50, False)
    original = select_intake_window((row,), window_key=WINDOW)
    modified = select_intake_window((replace(row, **change),), window_key=WINDOW)
    assert original.input_sha256 != modified.input_sha256


@pytest.mark.parametrize(
    "kwargs",
    [
        {"window_key": "c" * 64},
        {"carry": 1},
        {"policy": IntakeSelectionPolicy(99)},
        {"policy": IntakeSelectionPolicy(mode="RANDOM")},
        {"policy": IntakeSelectionPolicy(minimum_score=1)},
    ],
)
def test_digest_binds_window_carry_and_every_policy_field_even_when_empty(kwargs):
    original = select_intake_window((), window_key=WINDOW)
    arguments = {"window_key": WINDOW, **kwargs}
    assert select_intake_window((), **arguments).input_sha256 != original.input_sha256


def test_digest_binds_membership_including_excluded_rows():
    original = select_intake_window((), window_key=WINDOW)
    excluded = select_intake_window((IntakeCandidate(1, REVISION, None, False),), window_key=WINDOW)
    assert excluded.input_sha256 != original.input_sha256


@pytest.mark.parametrize("value", [True, False, 0, -1, 2**63, 1.0, "1", None, IntSubclass(1)])
def test_candidate_rejects_non_exact_positive_signed64_identity(value):
    with pytest.raises(ValueError):
        IntakeCandidate(value, REVISION, 50)


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        "",
        "b" * 63,
        "b" * 65,
        "B" * 64,
        "g" * 64,
        "b" * 63 + "\n",
        StrSubclass(REVISION),
    ],
)
def test_candidate_rejects_noncanonical_revision_hash(value):
    with pytest.raises(ValueError):
        IntakeCandidate(1, value, 50)


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        -1,
        101,
        float("nan"),
        float("inf"),
        -float("inf"),
        "50",
        10**500,
        Decimal(50),
        IntSubclass(50),
        FloatSubclass(50),
    ],
)
def test_candidate_rejects_invalid_score_even_when_excluded(value):
    with pytest.raises(ValueError):
        IntakeCandidate(1, REVISION, value, False)


@pytest.mark.parametrize("value", [0, 1, None, "true", [], object()])
def test_candidate_requires_exact_bool_eligibility(value):
    with pytest.raises(ValueError):
        IntakeCandidate(1, REVISION, 50, value)


@pytest.mark.parametrize("value", [True, False, -1, 101, 30.0, "30", None, IntSubclass(30)])
def test_policy_requires_exact_bounded_integer_percent(value):
    with pytest.raises(ValueError):
        IntakeSelectionPolicy(value)


@pytest.mark.parametrize(
    "value", [None, True, 1, "random", "TOP", "HYBRID ", [], StrSubclass("HYBRID")]
)
def test_policy_requires_literal_mode(value):
    with pytest.raises(ValueError):
        IntakeSelectionPolicy(mode=value)


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        -1,
        101,
        float("nan"),
        float("inf"),
        -float("inf"),
        "50",
        10**500,
        Decimal(50),
        IntSubclass(50),
        FloatSubclass(50),
    ],
)
def test_policy_rejects_invalid_threshold(value):
    with pytest.raises(ValueError):
        IntakeSelectionPolicy(minimum_score=value)


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        "",
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
        "a" * 63 + "\n",
        StrSubclass(WINDOW),
    ],
)
def test_selector_rejects_invalid_window_key_before_empty_return(value):
    with pytest.raises(ValueError):
        select_intake_window((), window_key=value)


@pytest.mark.parametrize("value", [True, False, -1, 100, 1.0, "0", None, IntSubclass(0)])
def test_selector_requires_exact_bounded_carry_before_empty_return(value):
    with pytest.raises(ValueError):
        select_intake_window((), window_key=WINDOW, carry=value)


def test_selector_rejects_non_tuple_without_traversing_arbitrary_iterables():
    class NeverTraverse:
        def __iter__(self):
            pytest.fail("arbitrary iterable traversed")

    for value in ([], {}, None, object(), iter(()), NeverTraverse(), TupleSubclass()):
        with pytest.raises(TypeError):
            select_intake_window(value, window_key=WINDOW)


def test_selector_requires_exact_candidate_and_policy_types():
    for value in (object(), None, {"candidate_id": 1}, CandidateSubclass(1, REVISION, 50)):
        with pytest.raises(TypeError):
            select_intake_window((value,), window_key=WINDOW)
    for value in (False, 0, {}, object(), PolicySubclass()):
        with pytest.raises(TypeError):
            select_intake_window((), window_key=WINDOW, policy=value)


def test_duplicate_identity_rejected_even_for_excluded_rows():
    with pytest.raises(ValueError):
        select_intake_window(
            (IntakeCandidate(1, REVISION, 0), IntakeCandidate(1, "c" * 64, None, False)),
            window_key=WINDOW,
            policy=IntakeSelectionPolicy(0),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("candidate_id", True),
        ("revision_sha256", "invalid"),
        ("score", float("nan")),
        ("eligible", 0),
    ],
)
def test_selector_revalidates_frozen_candidate_fields_before_zero_quota(field, value):
    row = IntakeCandidate(1, REVISION, 50, False)
    object.__setattr__(row, field, value)
    with pytest.raises(ValueError):
        select_intake_window((row,), window_key=WINDOW, policy=IntakeSelectionPolicy(0))


@pytest.mark.parametrize(
    "field,value", [("intake_percent", True), ("mode", "invalid"), ("minimum_score", float("nan"))]
)
def test_selector_revalidates_policy_before_empty_return(field, value):
    policy = IntakeSelectionPolicy()
    object.__setattr__(policy, field, value)
    with pytest.raises(ValueError):
        select_intake_window((), window_key=WINDOW, policy=policy)


def test_window_size_is_bounded_at_one_thousand_without_silent_truncation():
    rows = tuple(IntakeCandidate(i, REVISION, 50) for i in range(1, 1002))
    result = select_intake_window(
        rows[:1000], window_key=WINDOW, policy=IntakeSelectionPolicy(1, "TOP_SCORE")
    )
    assert result.selected_ids == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert (result.eligible_count, result.quota, result.carry_out) == (1000, 10, 0)
    with pytest.raises(ValueError):
        select_intake_window(rows, window_key=WINDOW)


def test_valid_numeric_boundaries_and_fractional_scores_remain_exact():
    rows = (
        IntakeCandidate(2**63 - 1, REVISION, 100),
        IntakeCandidate(1, REVISION, 0),
        IntakeCandidate(2, REVISION, 50.00000001),
        IntakeCandidate(3, REVISION, 50),
    )
    result = select_intake_window(
        rows,
        window_key=WINDOW,
        policy=IntakeSelectionPolicy(100, "TOP_SCORE", 50.00000001),
        carry=99,
    )
    assert result.selected_ids == (9223372036854775807, 2)
    assert (result.eligible_count, result.quota, result.carry_out) == (2, 2, 99)


def test_inputs_and_outputs_are_frozen_slotted_and_preserved_without_authority():
    rows = ten_rows()
    policy = IntakeSelectionPolicy(50)
    before = tuple((row.candidate_id, row.revision_sha256, row.score, row.eligible) for row in rows)
    result = select_intake_window(rows, window_key=WINDOW, policy=policy)
    assert type(result) is IntakeSelectionResult
    assert type(result.selected_ids) is tuple
    assert type(result.decisions) is tuple
    assert (
        tuple((row.candidate_id, row.revision_sha256, row.score, row.eligible) for row in rows)
        == before
    )
    assert policy == IntakeSelectionPolicy(50)
    for obj in (rows[0], policy, result, result.decisions[0]):
        assert not hasattr(obj, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(obj, fields(obj)[0].name, None)
    assert {field.name for field in fields(result)} == {
        "algorithm_version",
        "input_sha256",
        "selected_ids",
        "decisions",
        "eligible_count",
        "quota",
        "carry_out",
    }
    assert {field.name for field in fields(result.decisions[0])} == {
        "candidate_id",
        "selected",
        "reason",
    }
