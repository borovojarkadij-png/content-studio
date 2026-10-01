from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsflow.persistence.models import Base, TelegramAccount
from newsflow.providers.telegram import FakeTelegramProvider
from newsflow.services.account_health import AccountHealthService, AccountHealthStatus


def _account(session: Session) -> TelegramAccount:
    account = TelegramAccount(name="Primary", telegram_user_id=1001, encrypted_session="ciphertext")
    session.add(account)
    session.commit()
    return account


def test_reconnect_marks_account_connected_when_its_session_is_available() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        account = _account(session)
        provider = FakeTelegramProvider()
        service = AccountHealthService(session, provider)

        result = service.reconnect(account.id, now=datetime(2026, 10, 1, tzinfo=UTC))

        assert result.status is AccountHealthStatus.CONNECTED
        assert result.reconnect_attempted is True
        assert account.health_status == "CONNECTED"


def test_floodwait_cooldown_prevents_another_reconnect_attempt() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        account = _account(session)
        provider = FakeTelegramProvider()
        provider.seed_floodwait(str(account.id), seconds=30)
        service = AccountHealthService(session, provider)
        now = datetime(2026, 10, 1, tzinfo=UTC)

        first = service.reconnect(account.id, now=now)
        retry = service.reconnect(account.id, now=now + timedelta(seconds=10))

        assert first.status is AccountHealthStatus.COOLDOWN
        assert retry.status is AccountHealthStatus.COOLDOWN
        assert retry.reconnect_attempted is False
        assert provider.session_probe_count(str(account.id)) == 1


def test_unavailable_session_requires_reauthentication_without_a_retry_loop() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        account = _account(session)
        provider = FakeTelegramProvider()
        provider.seed_session_unavailable(str(account.id))
        service = AccountHealthService(session, provider)

        result = service.reconnect(account.id, now=datetime(2026, 10, 1, tzinfo=UTC))

        assert result.status is AccountHealthStatus.SESSION_INVALID
        assert account.health_status == "SESSION_INVALID"
