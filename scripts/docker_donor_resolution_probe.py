"""Real durable import restart recovery; Telegram RPC is injected, never live."""

import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from telethon.tl.types import Channel, ChatPhotoEmpty

from newsflow.persistence.models import (
    DonorChannel,
    DonorImportModel,
    DonorImportResolutionJobModel,
    OutboxEventModel,
    TelegramAccount,
    TelegramPeerModel,
)
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.donor_import_resolution import (
    DonorImportResolutionRunner,
    DonorResolutionClaim,
)
from newsflow.services.telegram_configuration import TelegramConfigurationService
from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Resolution probe requires isolated verification database")
    engine = create_engine(url, connect_args={"options": "-c lock_timeout=2000"})
    sessions = sessionmaker(engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    path = Path(os.getenv("NEWSFLOW_MEDIA_ROOT", "/data/media")) / "synthetic-import-claim.json"
    if mode == "seed":
        with sessions() as session:
            if (
                session.scalar(
                    select(TelegramAccount.id).where(
                        TelegramAccount.name == "synthetic-import-recovery"
                    )
                )
                is not None
                or path.exists()
            ):
                raise RuntimeError("Use a fresh fixture; refusing to replace import history")
            config = TelegramConfigurationService(session)
            account = config.create_account("synthetic-import-recovery", 700700)
            config.bulk_import_donors(account["id"], "@synthetic_donor\n@alias_donor")
            session.get(TelegramAccount, account["id"]).encrypted_session = cipher.encrypt(
                "synthetic-import-session-not-authorization"
            )
            session.commit()
            import_id = session.scalar(
                select(DonorImportModel.id)
                .where(DonorImportModel.telegram_account_id == account["id"])
                .order_by(DonorImportModel.id)
            )
        runtime = DonorImportResolutionRunner(sessions, provider=None)
        claim = runtime.claim(import_id, now=datetime.now(UTC))
        assert claim is not None
        with path.open("x", encoding="utf-8") as file:
            json.dump(asdict(claim), file)
    elif mode in {"recover", "verify"}:
        old = DonorResolutionClaim(**json.loads(path.read_text(encoding="utf-8")))

        class Client:
            session = SimpleNamespace(save=lambda: "synthetic-import-session-not-authorization")

            async def connect(self):
                pass

            async def disconnect(self):
                pass

            async def is_user_authorized(self):
                return True

            async def get_me(self):
                return SimpleNamespace(id=700700)

            async def get_entity(self, identifier):
                assert identifier in {"@synthetic_donor", "@alias_donor"}
                # Reintroduced account locks over RPC must fail promptly.
                with sessions.begin() as session:
                    assert (
                        session.scalar(
                            select(TelegramAccount.id)
                            .where(TelegramAccount.id == old.account_id)
                            .with_for_update()
                        )
                        == old.account_id
                    )
                return Channel(
                    1234567890,
                    "Synthetic resolved donor",
                    ChatPhotoEmpty(),
                    datetime.now(UTC),
                    broadcast=True,
                    access_hash=777888,
                    username=identifier[1:],
                )

        configured = ConfiguredTelegramProvider(
            sessions,
            cipher=cipher,
            api_id=123,
            api_hash="a" * 32,
            client_factory=lambda _: Client(),
        )
        runtime = DonorImportResolutionRunner(sessions, provider=configured)
        if mode == "recover":
            assert runtime.execute(old) == "STALE_CLAIM"
            with sessions() as session:
                ids = list(
                    session.scalars(
                        select(DonorImportModel.id)
                        .where(DonorImportModel.telegram_account_id == old.account_id)
                        .order_by(DonorImportModel.id)
                    )
                )
            assert [runtime.run_import(item, now=datetime.now(UTC)) for item in ids] == [
                "RESOLVED",
                "RESOLVED",
            ]
        with sessions() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(DonorChannel)
                    .where(DonorChannel.telegram_account_id == old.account_id)
                )
                == 1
            )
            states = list(
                session.scalars(
                    select(DonorImportResolutionJobModel.state)
                    .join(DonorImportModel)
                    .where(DonorImportModel.telegram_account_id == old.account_id)
                )
            )
            assert states == ["RESOLVED", "RESOLVED"]
            peer = session.get(TelegramPeerModel, (old.account_id, -1001234567890))
            assert peer is not None and "777888" not in peer.encrypted_peer
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(OutboxEventModel)
                    .where(OutboxEventModel.event_type == "donor.import.resolved")
                )
                == 2
            )
    else:
        raise ValueError("Expected seed, recover or verify")
    engine.dispose()
    print(f"Durable donor resolution {mode} PASS; Telegram network/AI/send calls=0")


if __name__ == "__main__":
    main(sys.argv[1])
