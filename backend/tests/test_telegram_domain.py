from datetime import UTC, datetime

import pytest

from newsflow.domain import telegram


def test_source_identity_is_immutable_and_revisioned() -> None:
    identity = telegram.SourceIdentity(
        telegram_account_id="account-1",
        donor_channel_id="donor-1",
        telegram_message_id=42,
    )
    revision = telegram.ContentRevision.new(identity, "First source text", datetime.now(UTC))

    assert revision.revision_number == 1
    assert revision.source_key == "account-1:donor-1:42"
    with pytest.raises((AttributeError, TypeError)):
        identity.telegram_message_id = 43  # type: ignore[misc]

    updated = revision.next_revision("Corrected source text", datetime.now(UTC))
    assert updated.revision_number == 2
    assert updated.source_key == revision.source_key
    assert revision.source_text == "First source text"


def test_manual_review_cannot_enter_rewrite_without_explicit_approval() -> None:
    state = telegram.IncomingPostState.MANUAL_REVIEW

    with pytest.raises(telegram.InvalidStateTransition):
        telegram.transition_incoming_post(state, telegram.IncomingPostState.REWRITE_QUEUED)

    assert (
        telegram.transition_incoming_post(state, telegram.IncomingPostState.ELIGIBLE)
        is telegram.IncomingPostState.ELIGIBLE
    )


def test_mapping_requires_independent_intake_and_target_mix() -> None:
    mapping = telegram.ChannelMapping(
        donor_channel_id="donor-1",
        output_channel_id="output-1",
        intake_percent=25,
        target_mix_percent=40,
    )

    assert mapping.intake_percent == 25
    assert mapping.target_mix_percent == 40


def test_bulk_import_parses_supported_telegram_identifiers_and_reports_invalid_lines() -> None:
    result = telegram.parse_donor_import("t.me/channel_a\n@channel_b\n-100123456789\nnot a link")

    assert [entry.canonical_identifier for entry in result.accepted] == [
        "@channel_a",
        "@channel_b",
        "-100123456789",
    ]
    assert result.rejected == ("not a link",)
