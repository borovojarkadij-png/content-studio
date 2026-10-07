from datetime import UTC, datetime, timedelta

import pytest
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


def test_floodwait_survives_session_close_and_reloads_utc_cooldown(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'health.db'}")
    Base.metadata.create_all(engine)
    provider = FakeTelegramProvider()
    now = datetime(2026, 10, 1, tzinfo=UTC)
    with Session(engine) as session:
        account_id = _account(session).id  # Access starts SQLAlchemy's implicit transaction.
        provider.seed_floodwait(str(account_id), seconds=30)
        assert (
            AccountHealthService(session, provider).reconnect(account_id, now=now).status
            is AccountHealthStatus.COOLDOWN
        )
    with Session(engine) as session:
        account = session.get(TelegramAccount, account_id)
        assert account.health_status == "COOLDOWN"
        result = AccountHealthService(session, provider).reconnect(
            account_id, now=now + timedelta(seconds=10)
        )
        assert result.reconnect_attempted is False
    assert provider.session_probe_count(str(account_id)) == 1
    engine.dispose()


def test_cached_account_does_not_hide_external_cooldown(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'health.db'}")
    Base.metadata.create_all(engine)
    provider = FakeTelegramProvider()
    now = datetime(2026, 10, 1, tzinfo=UTC)
    with Session(engine) as session:
        account = _account(session)
        assert account.cooldown_until is None
        with Session(engine) as other:
            other.get(TelegramAccount, account.id).cooldown_until = now + timedelta(seconds=30)
            other.commit()
        result = AccountHealthService(session, provider).reconnect(account.id, now=now)
        assert result.reconnect_attempted is False
        assert provider.session_probe_count(str(account.id)) == 0
    engine.dispose()


def test_naive_reconnect_time_is_rejected_before_database_or_provider():
    provider = FakeTelegramProvider()
    with pytest.raises(ValueError, match="timezone-aware"):
        AccountHealthService(None, provider).reconnect(
            1, now=datetime(2026, 10, 1, tzinfo=UTC).replace(tzinfo=None)
        )
    assert provider.session_probe_count("1") == 0


def test_reconnect_does_not_hold_database_transaction_during_session_rpc():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        account_id = _account(session).id

        class Probe(FakeTelegramProvider):
            def verify_session(self, account_id):
                assert not session.in_transaction(), (
                    "Health lock would deadlock the session refresh callback"
                )
                super().verify_session(account_id)

        assert (
            AccountHealthService(session, Probe())
            .reconnect(account_id, now=datetime.now(UTC))
            .status
            is AccountHealthStatus.CONNECTED
        )
    engine.dispose()


def test_concurrent_floodwait_during_rpc_cannot_be_overwritten_by_connected_result(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent-health.db'}")
    Base.metadata.create_all(engine)
    now = datetime(2030, 1, 1, tzinfo=UTC)
    with Session(engine) as session:
        account_id = _account(session).id

        class Probe(FakeTelegramProvider):
            def verify_session(self, account):
                with Session(engine) as other:
                    current = other.get(TelegramAccount, account_id)
                    current.cooldown_until = now + timedelta(minutes=2)
                    current.health_status = "COOLDOWN"
                    current.health_checked_at = now
                    other.commit()

        result = AccountHealthService(session, Probe()).reconnect(account_id, now=now)
        assert result.status is AccountHealthStatus.COOLDOWN
        assert session.get(TelegramAccount, account_id).cooldown_until.replace(
            tzinfo=UTC
        ) == now + timedelta(minutes=2)
    engine.dispose()
