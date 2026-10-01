from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from newsflow.providers import telegram


@dataclass
class TelethonLikeMessage:
    id: int
    raw_text: str
    photo: object | None = None
    video: object | None = None
    grouped_id: int | None = None
    edit_date: datetime | None = None


def test_telethon_adapter_refuses_to_connect_without_a_provisioned_session() -> None:
    adapter = telegram.TelethonTelegramProvider(api_id=123, api_hash="hash")

    with pytest.raises(telegram.SessionUnavailable):
        adapter.require_session("account-a")


def test_telethon_adapter_builds_an_isolated_client_from_the_account_session() -> None:
    adapter = telegram.TelethonTelegramProvider(
        api_id=123,
        api_hash="hash",
        sessions={"account-a": ""},
    )

    client = adapter.build_client("account-a")

    assert client.session is not None


def test_telethon_adapter_normalizes_photo_album_edits_without_a_live_connection() -> None:
    raw = TelethonLikeMessage(
        id=77,
        raw_text="corrected caption",
        photo=object(),
        grouped_id=901,
        edit_date=datetime(2026, 10, 1, tzinfo=UTC),
    )

    message = telegram.TelethonTelegramProvider.normalize_message("account-a", "@donor", raw)

    assert message.account_id == "account-a"
    assert message.donor_identifier == "@donor"
    assert message.message_id == 77
    assert message.text == "corrected caption"
    assert message.media_type == "photo"
    assert message.album_id == "901"
    assert message.is_edit is True


def test_telethon_adapter_normalizes_video_without_a_live_connection() -> None:
    raw = TelethonLikeMessage(id=78, raw_text="clip", video=object())

    message = telegram.TelethonTelegramProvider.normalize_message("account-a", "@donor", raw)

    assert message.media_type == "video"
    assert message.album_id is None
