"""Actual PostgreSQL health/session-refresh lock regression; injected RPC only."""

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import TelegramAccount
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.account_health import AccountHealthService, AccountHealthStatus
from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider


def main():
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Health probe requires isolated verification database")
    # A reintroduced health-row lock must fail promptly, not freeze the drill.
    engine = create_engine(url, connect_args={"options": "-c lock_timeout=2000"})
    factory = sessionmaker(engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    now = datetime.now(UTC)
    with factory() as session:
        if (
            session.scalar(
                select(TelegramAccount.id).where(
                    TelegramAccount.name == "synthetic-rpc-health-lock"
                )
            )
            is not None
        ):
            raise RuntimeError("Use a fresh fixture; refusing to replace health history")
        account = TelegramAccount(
            name="synthetic-rpc-health-lock",
            telegram_user_id=400400,
            encrypted_session=cipher.encrypt("synthetic-initial-not-authorization"),
        )
        session.add(account)
        session.commit()
        account_id = account.id

    class SyntheticClient:
        session = SimpleNamespace(save=lambda: "synthetic-refreshed-not-authorization")
        disconnected = False

        async def connect(self):
            pass

        async def is_user_authorized(self):
            # Another transaction, during the RPC, records a longer account wait.
            with factory() as other, other.begin():
                current = other.get(TelegramAccount, account_id)
                current.health_status = "COOLDOWN"
                current.health_checked_at = now
                current.cooldown_until = now + timedelta(seconds=120)
            return True

        async def disconnect(self):
            self.disconnected = True

    client = SyntheticClient()
    provider = ConfiguredTelegramProvider(
        factory, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    with factory() as session:
        result = AccountHealthService(session, provider).reconnect(account_id, now=now)
        assert result.status is AccountHealthStatus.COOLDOWN
    with factory() as session:
        stored = session.get(TelegramAccount, account_id)
        assert cipher.decrypt(stored.encrypted_session) == "synthetic-refreshed-not-authorization"
        assert stored.cooldown_until == now + timedelta(seconds=120)
    assert client.disconnected
    engine.dispose()
    print(
        "PostgreSQL health lock/session refresh/concurrent cooldown PASS; Telegram network calls=0"
    )


if __name__ == "__main__":
    main()
