from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import Base, TelegramAccount
from newsflow.providers.telegram import SessionUnavailable
from newsflow.security.session_cipher import SessionCipher

KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def test_factory_decrypts_current_session_and_persists_rpc_refresh_encrypted(tmp_path):
    from test_telethon_rpc import Client

    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    engine = create_engine(f"sqlite:///{tmp_path / 'session.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    cipher = SessionCipher(KEY)
    with factory() as session:
        session.add(
            TelegramAccount(
                name="synthetic", telegram_user_id=1001, encrypted_session=cipher.encrypt("initial")
            )
        )
        session.commit()
    client = Client()
    client.session = SimpleNamespace(save=lambda: "refreshed")
    provider = ConfiguredTelegramProvider(
        factory, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    provider.verify_session("1")
    with factory() as session:
        stored = session.get(TelegramAccount, 1).encrypted_session
        assert stored != "refreshed"
        assert cipher.decrypt(stored) == "refreshed"
    engine.dispose()


def test_missing_session_never_constructs_provider_client(tmp_path):
    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as session:
        session.add(TelegramAccount(name="synthetic", telegram_user_id=1001, encrypted_session=""))
        session.commit()

    def forbidden(_):
        raise AssertionError("No unprovisioned client")

    with pytest.raises(SessionUnavailable):
        ConfiguredTelegramProvider(
            factory,
            cipher=SessionCipher(KEY),
            api_id=123,
            api_hash="a" * 32,
            client_factory=forbidden,
        ).verify_session("1")
    engine.dispose()


@pytest.mark.parametrize(
    "raw",
    [
        '{"api_id":1,"api_id":2,"api_hash":"' + "a" * 32 + '"}',
        '{"api_id":2147483648,"api_hash":"' + "a" * 32 + '"}',
    ],
)
def test_credential_file_rejects_ambiguous_or_out_of_range_values_without_echoing_secret(
    tmp_path, raw
):
    from newsflow.services.telegram_provider_factory import (
        TelegramCredentialsUnavailable,
        load_telegram_credentials,
    )

    path = tmp_path / "credentials.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(TelegramCredentialsUnavailable) as error:
        load_telegram_credentials(path)
    assert "a" * 32 not in str(error.value)


def test_concurrent_session_replacement_cannot_be_overwritten_by_an_old_rpc_refresh(tmp_path):
    from test_telethon_rpc import Client

    from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent-session.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    cipher = SessionCipher(KEY)
    with factory() as session:
        session.add(
            TelegramAccount(
                name="synthetic", telegram_user_id=1001, encrypted_session=cipher.encrypt("initial")
            )
        )
        session.commit()

    class ConcurrentClient(Client):
        async def is_user_authorized(self):
            with factory() as session:
                session.get(TelegramAccount, 1).encrypted_session = cipher.encrypt(
                    "new manual session"
                )
                session.commit()
            return True

    client = ConcurrentClient()
    client.session = SimpleNamespace(save=lambda: "obsolete refreshed session")
    provider = ConfiguredTelegramProvider(
        factory, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    with pytest.raises(ConnectionError, match="changed concurrently"):
        provider.verify_session("1")
    with factory() as session:
        assert (
            cipher.decrypt(session.get(TelegramAccount, 1).encrypted_session)
            == "new manual session"
        )
    assert client.disconnected == 1
    engine.dispose()
