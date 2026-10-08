"""Offline human-review contract; never model qualification or permission to send."""

import importlib
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

NOW = datetime(2030, 1, 1, tzinfo=UTC)


def domain():
    return importlib.import_module("newsflow.domain.illustration_relevance")


def binding(**overrides):
    return domain().IllustrationBinding(
        **{
            "candidate_id": 11,
            "output_channel_id": 12,
            "mapping_id": 13,
            "content_key": "account:channel:14:revision:1",
            "source_revision_id": 15,
            "source_sha256": "a" * 64,
            "rewrite_output_id": 16,
            "draft_sha256": "b" * 64,
            "media_asset_id": 17,
            "media_sha256": "c" * 64,
            "asset_metadata_sha256": "d" * 64,
            **overrides,
        }
    )


def review(**overrides):
    module = domain()
    return module.HumanIllustrationReview(
        **{
            "binding": binding(),
            "reviewer_id": 21,
            "verdict": module.IllustrationVerdict.APPROVED_ILLUSTRATION,
            "illustration_acknowledged": True,
            "review_note": "Синтетическая иллюстрация, не фотография описанного события.",
            "reviewed_at": NOW,
            "revoked_at": None,
            **overrides,
        }
    )


def assess(value, current=None, now=NOW):
    return domain().assess_illustration_review(value, current=current or binding(), now=now)


def test_explicit_human_illustration_review_matches_only_its_exact_current_binding():
    result = assess(review())
    assert result.allowed is True
    assert result.reason_code == "CURRENT_HUMAN_ILLUSTRATION_REVIEW"
    # This result certifies a narrow review, not editorial/fact/source/rights
    # readiness and not that the image depicts the actual event.
    assert not hasattr(result, "publication_allowed")
    assert not hasattr(result, "fact_preserved")


@pytest.mark.parametrize(
    "field,value",
    [
        ("candidate_id", 31),
        ("output_channel_id", 32),
        ("mapping_id", 33),
        ("content_key", "account:channel:14:revision:2"),
        ("source_revision_id", 35),
        ("source_sha256", "e" * 64),
        ("rewrite_output_id", 36),
        ("draft_sha256", "f" * 64),
        ("media_asset_id", 37),
        ("media_sha256", "0" * 64),
        ("asset_metadata_sha256", "1" * 64),
    ],
)
def test_review_cannot_follow_a_new_channel_source_draft_asset_or_rights(field, value):
    result = assess(review(), current=replace(binding(), **{field: value}))
    assert result.allowed is False
    assert result.reason_code == "ILLUSTRATION_REVIEW_BINDING_CHANGED"


@pytest.mark.parametrize("verdict", ["REJECTED", "UNCERTAIN"])
def test_rejected_or_uncertain_human_judgment_never_grants_use(verdict):
    result = assess(review(verdict=domain().IllustrationVerdict[verdict]))
    assert result.allowed is False
    assert result.reason_code == "ILLUSTRATION_REVIEW_NOT_APPROVED"


def test_topic_match_without_explicit_illustration_acknowledgment_never_grants_use():
    result = assess(review(illustration_acknowledged=False))
    assert result.allowed is False
    assert result.reason_code == "ILLUSTRATION_ACKNOWLEDGMENT_REQUIRED"


@pytest.mark.parametrize("value", [None, True, {}, {"verdict": "APPROVED_ILLUSTRATION"}])
def test_absent_raw_or_boolean_review_is_not_trusted_human_evidence(value):
    result = assess(value)
    assert result.allowed is False
    assert result.reason_code == "HUMAN_ILLUSTRATION_REVIEW_REQUIRED"


def test_structurally_similar_model_evidence_cannot_be_cast_to_human_review():
    evidence = SimpleNamespace(
        **{
            name: getattr(review(), name)
            for name in (
                "binding",
                "reviewer_id",
                "verdict",
                "illustration_acknowledged",
                "review_note",
                "reviewed_at",
                "revoked_at",
            )
        },
        provider="OPENAI",
        model="synthetic",
        qualified=True,
    )
    assert assess(evidence).allowed is False


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_any_recorded_revocation_blocks_even_if_its_timestamp_is_future(delta):
    result = assess(review(revoked_at=NOW + timedelta(seconds=delta)))
    assert result.allowed is False
    assert result.reason_code == "ILLUSTRATION_REVIEW_REVOKED"


def test_review_from_the_future_never_grants_use():
    result = assess(review(reviewed_at=NOW + timedelta(microseconds=1)))
    assert result.allowed is False
    assert result.reason_code == "ILLUSTRATION_REVIEW_TIME_INVALID"


def test_later_dst_fold_review_is_future_despite_identical_local_wall_time():
    zone = ZoneInfo("America/New_York")
    earlier = datetime(2030, 11, 3, 1, 30, tzinfo=zone, fold=0)
    later = datetime(2030, 11, 3, 1, 30, tzinfo=zone, fold=1)
    # Hand-checked distinct UTC instants, not a mirror of the guard's logic.
    assert earlier.astimezone(UTC) == datetime(2030, 11, 3, 5, 30, tzinfo=UTC)
    assert later.astimezone(UTC) == datetime(2030, 11, 3, 6, 30, tzinfo=UTC)
    result = assess(review(reviewed_at=later), now=earlier)
    assert result.allowed is False
    assert result.reason_code == "ILLUSTRATION_REVIEW_TIME_INVALID"
    assert assess(review(reviewed_at=earlier), now=later).allowed is True


def test_binding_and_human_review_are_immutable_values():
    evidence = review()
    with pytest.raises(FrozenInstanceError):
        evidence.binding.media_asset_id = 999
    with pytest.raises(FrozenInstanceError):
        evidence.verdict = domain().IllustrationVerdict.REJECTED


@pytest.mark.parametrize(
    "field",
    [
        "candidate_id",
        "output_channel_id",
        "mapping_id",
        "source_revision_id",
        "rewrite_output_id",
        "media_asset_id",
    ],
)
@pytest.mark.parametrize("invalid", [True, 0, -1, "11", None])
def test_invalid_or_boolean_identity_cannot_enter_binding(field, invalid):
    with pytest.raises(ValueError):
        binding(**{field: invalid})


@pytest.mark.parametrize(
    "field",
    [
        "source_sha256",
        "draft_sha256",
        "media_sha256",
        "asset_metadata_sha256",
    ],
)
@pytest.mark.parametrize("invalid", [None, True, "a" * 63, "G" * 64, "A" * 64])
def test_missing_malformed_or_noncanonical_digest_cannot_enter_binding(field, invalid):
    with pytest.raises(ValueError):
        binding(**{field: invalid})


@pytest.mark.parametrize("invalid", [None, True, "", " x", "x ", "x\n", "x" * 256])
def test_ambiguous_empty_or_unbounded_source_identity_is_rejected(invalid):
    with pytest.raises(ValueError):
        binding(content_key=invalid)


@pytest.mark.parametrize(
    "field,invalid",
    [
        ("binding", None),
        ("binding", {}),
        ("reviewer_id", True),
        ("reviewer_id", 0),
        ("reviewer_id", "21"),
        ("verdict", "APPROVED_ILLUSTRATION"),
        ("verdict", "UNKNOWN"),
        ("verdict", True),
        ("illustration_acknowledged", 1),
        ("illustration_acknowledged", "true"),
        ("review_note", ""),
        ("review_note", "  "),
        ("review_note", "x" * 2049),
        ("review_note", None),
        ("review_note", "x\x00y"),
        ("reviewed_at", NOW.replace(tzinfo=None)),
        ("reviewed_at", "2030-01-01"),
        ("revoked_at", NOW.replace(tzinfo=None)),
    ],
)
def test_malformed_human_review_is_rejected_at_construction(field, invalid):
    with pytest.raises(ValueError):
        review(**{field: invalid})


@pytest.mark.parametrize("invalid", [None, True, {}, SimpleNamespace(candidate_id=11)])
def test_missing_or_untrusted_current_binding_fails_closed(invalid):
    result = domain().assess_illustration_review(review(), current=invalid, now=NOW)
    assert result.allowed is False
    assert result.reason_code == "CURRENT_ILLUSTRATION_BINDING_REQUIRED"


@pytest.mark.parametrize("invalid", [None, "2030-01-01", NOW.replace(tzinfo=None)])
def test_missing_or_naive_execution_time_never_grants_use(invalid):
    assert assess(review(), now=invalid).allowed is False
