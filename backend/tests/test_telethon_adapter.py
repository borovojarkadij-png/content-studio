import pytest

from newsflow.providers import telegram


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
