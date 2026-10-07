from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from test_telegram_peers import CHANNEL, PeerClient

from newsflow.providers import telegram


def photo(message_id, text="", **changes):
    return telegram.TelegramMessage(
        "1",
        "-1001234567890",
        message_id,
        text,
        media_type="photo",
        album_id="123456",
        source_updated_at=datetime(2026, 10, 8, tzinfo=UTC),
        **changes,
    )


def observe(messages, anchor_id=20):
    return telegram.observe_album_window(
        tuple(messages),
        account_id="1",
        donor_identifier="-1001234567890",
        anchor_id=anchor_id,
        lower_id=1,
        upper_id=100,
    )


def test_sparse_album_members_preserve_all_captions_in_message_order():
    # Unrelated messages may be interspersed; consecutive IDs are not membership.
    unrelated = replace(photo(21, "Other post"), album_id=None)
    result = observe([photo(29, "Second caption"), unrelated, photo(20, "First caption")])
    assert result.message_ids == (20, 29)
    assert result.text == "First caption\n\nSecond caption"
    assert result.media_types == ("photo", "photo")
    assert result.membership_complete is False
    assert result.rewrite_allowed is False


def test_album_window_does_not_silently_drop_captionless_members_or_video():
    result = observe([photo(20, "Caption"), replace(photo(24), media_type="video"), photo(30)])
    assert result.message_ids == (20, 24, 30)
    assert result.media_types == ("photo", "video", "photo")
    assert result.text == "Caption"
    assert result.rewrite_allowed is False


def test_identical_delivery_deduplicates_but_conflicting_same_id_fails_closed():
    result = observe([photo(20, "Caption"), photo(20, "Caption")])
    assert result.message_ids == (20,)
    with pytest.raises(ValueError):
        observe([photo(20, "Caption"), photo(20, "Changed caption")])


@pytest.mark.parametrize(
    "bad",
    [
        lambda m: replace(m, account_id="2"),
        lambda m: replace(m, donor_identifier="-1001234567891"),
        lambda m: replace(m, message_id=True),
        lambda m: replace(m, message_id=101),
        lambda m: replace(m, media_type="text"),
        lambda m: replace(m, album_id="bad"),
        lambda m: replace(
            m, source_updated_at=datetime(2026, 10, 8, tzinfo=UTC).replace(tzinfo=None)
        ),
    ],
)
def test_malformed_or_foreign_album_observation_never_becomes_rewriteable(bad):
    with pytest.raises((ValueError, TypeError)):
        observe([photo(20, "Caption"), bad(photo(25))])


def test_album_with_more_than_ten_members_is_not_truncated_into_a_valid_post():
    with pytest.raises(ValueError):
        observe([photo(i) for i in range(20, 31)])


def test_missing_anchor_or_ungrouped_anchor_cannot_invent_an_album():
    with pytest.raises(LookupError):
        observe([photo(21)])
    with pytest.raises(ValueError):
        observe([replace(photo(20), album_id=None)])


class AlbumClient(PeerClient):
    def __init__(self, messages):
        super().__init__()
        self.messages = messages
        self.read_ids = []

    async def get_messages(self, entity, *, ids):
        self.read_ids.append(ids)
        assert entity.channel_id == 1234567890
        return self.messages


def raw(message_id, *, caption="", grouped_id=123456, chat_id=CHANNEL):
    return SimpleNamespace(
        id=message_id,
        chat_id=chat_id,
        raw_text=caption,
        photo=object(),
        grouped_id=grouped_id,
        date=datetime(2026, 10, 8, tzinfo=UTC),
    )


def adapter(client):
    return telegram.TelethonTelegramProvider(
        api_id=123,
        api_hash="synthetic",
        sessions={"1": "synthetic session"},
        client_factory=lambda _: client,
        expected_user_id=1001,
    )


def test_read_only_album_fetch_is_bounded_and_keeps_sparse_members_and_missing_ids():
    client = AlbumClient([None, raw(20, caption="First"), raw(29, caption="Second")])
    result = adapter(client).album_window("1", str(CHANNEL), anchor_id=20)
    assert result.message_ids == (20, 29)
    assert result.text == "First\n\nSecond"
    assert result.membership_complete is False
    assert len(client.read_ids) == 1
    assert len(client.read_ids[0]) <= 100
    assert client.disconnected == 1


@pytest.mark.parametrize(
    "messages",
    [
        [raw(20, chat_id=CHANNEL - 1)],
        [raw(20), raw(999)],
        [raw(True)],
        [raw(20, grouped_id=True)],
        [raw(20)] * 101,
    ],
)
def test_live_album_boundary_refuses_foreign_unbounded_or_malformed_responses(messages):
    client = AlbumClient(messages)
    with pytest.raises((ValueError, TypeError)):
        adapter(client).album_window("1", str(CHANNEL), anchor_id=20)
    assert client.disconnected == 1


def test_fake_album_contract_uses_the_same_unknown_completeness_boundary():
    provider = telegram.FakeTelegramProvider()
    for member in (photo(20, "Caption"), photo(29)):
        provider._messages[(member.account_id, member.donor_identifier, member.message_id)] = member
    result = provider.album_window("1", str(CHANNEL), anchor_id=20)
    assert result.message_ids == (20, 29)
    assert result.rewrite_allowed is False


@pytest.mark.parametrize("grouped_id", [-(2**63), -77, 0, 2**63 - 1])
def test_album_identity_preserves_the_entire_telegram_signed_long_domain(grouped_id):
    client = AlbumClient([raw(20, grouped_id=grouped_id)])
    result = adapter(client).album_window("1", str(CHANNEL), anchor_id=20)
    assert result.album_id == str(grouped_id)
    assert result.membership_complete is False
