"""Synthetic encrypted peer recovery through real PostgreSQL/container restart."""

import os
import sys
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from telethon.tl.types import InputPeerChannel

from newsflow.persistence.models import TelegramAccount, TelegramPeerModel
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider

CHANNEL = -1001234567890


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Peer probe requires isolated verification database")
    engine = create_engine(url, connect_args={"options": "-c lock_timeout=2000"})
    sessions = sessionmaker(engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with sessions.begin() as session:
        account = session.scalar(
            select(TelegramAccount).where(TelegramAccount.name == "synthetic-peer-restart")
        )
        if mode == "seed":
            if account is not None:
                raise RuntimeError("Use a fresh fixture; refusing to overwrite peer history")
            account = TelegramAccount(
                name="synthetic-peer-restart",
                telegram_user_id=500500,
                encrypted_session=cipher.encrypt("synthetic-peer-session-not-authorization"),
            )
            session.add(account)
            session.flush()
        elif mode != "verify" or account is None:
            raise RuntimeError("Invalid or missing peer fixture")
        account_id = account.id

    class Client:
        session = SimpleNamespace(save=lambda: "synthetic-peer-session-not-authorization")
        disconnected = False

        async def connect(self):
            pass

        async def is_user_authorized(self):
            return True

        async def get_me(self):
            return SimpleNamespace(id=500500)

        async def disconnect(self):
            self.disconnected = True

        def iter_dialogs(self, *, limit):
            if mode == "verify":
                raise AssertionError("Restart must reuse encrypted peer, not resolve dialogs again")
            assert limit == 100
            # Peer resolution must not retain an account lock over provider I/O.
            with sessions.begin() as session:
                session.get(TelegramAccount, account_id).health_status = "DISCONNECTED"

            async def items():
                yield SimpleNamespace(
                    id=CHANNEL, input_entity=InputPeerChannel(1234567890, 987654321)
                )

            return items()

        def iter_messages(self, peer, **kwargs):
            assert isinstance(peer, InputPeerChannel)
            assert (peer.channel_id, peer.access_hash) == (1234567890, 987654321)

            async def items():
                yield SimpleNamespace(
                    id=1, chat_id=CHANNEL, raw_text="Synthetic peer probe", media=None
                )

            return items()

    client = Client()
    provider = ConfiguredTelegramProvider(
        sessions, cipher=cipher, api_id=123, api_hash="a" * 32, client_factory=lambda _: client
    )
    messages = provider.history(str(account_id), str(CHANNEL), after_id=0, limit=5)
    assert messages[0].donor_identifier == str(CHANNEL)
    with sessions() as session:
        peer = session.get(TelegramPeerModel, (account_id, CHANNEL))
        assert peer is not None and "987654321" not in peer.encrypted_peer
        assert cipher.decrypt(peer.encrypted_peer)
    assert client.disconnected
    engine.dispose()
    print(f"Encrypted account-scoped Telegram peer {mode} PASS; network/send calls=0")


if __name__ == "__main__":
    main(sys.argv[1])
