import pytest

from newsflow.providers import telegram


def test_fake_provider_keeps_account_floodwait_isolated() -> None:
    provider = telegram.FakeTelegramProvider()
    provider.seed_floodwait("account-a", seconds=30)
    provider.seed_message("account-b", "@donor", 1, "Other account still works")

    with pytest.raises(telegram.FloodWait):
        provider.fetch_message("account-a", "@donor", 1)

    assert provider.fetch_message("account-b", "@donor", 1).text == "Other account still works"


def test_fake_provider_emits_duplicate_and_editable_events_deterministically() -> None:
    provider = telegram.FakeTelegramProvider()
    provider.seed_message("account-a", "@donor", 7, "original")
    provider.seed_edit("account-a", "@donor", 7, "corrected")

    events = list(provider.iter_events("account-a"))

    assert [event.is_edit for event in events] == [False, True]
    assert events[0].message_id == events[1].message_id == 7
    assert events[1].text == "corrected"
