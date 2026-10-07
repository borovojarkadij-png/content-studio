"""Synthetic acceptance probe, hard-restricted to the isolated verification DB.

Pipe into the verification worker's `python - seed|verify`. Never uses Telegram
or AI providers. Reports only booleans/counts, never plaintext/encrypted secrets.
"""

import json
import os
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    ChannelMappingModel,
    MediaAssetModel,
    OutboxEventModel,
    PublicationCandidateModel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.security.master_key import load_runtime_master_key
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.media_selection import LocalMediaSelectionService
from newsflow.services.publication_planning import PublicationPlanningService
from newsflow.services.telegram_configuration import TelegramConfigurationService


def main() -> None:
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Probe is restricted to the isolated verification database")
    cipher = SessionCipher(load_runtime_master_key())
    root = Path(os.environ["NEWSFLOW_MEDIA_ROOT"])
    file = root / "synthetic-persistence-fixture.png"
    content = b"\x89PNG\r\n\x1a\nsynthetic-persistence-only-photo"
    engine = create_engine(url)
    with Session(engine) as session:
        if sys.argv[1] == "seed":
            config = TelegramConfigurationService(session)
            account = config.create_account("Synthetic persistence account", 990000000001)
            donor = config.create_donor(account["id"], -100990000000001, "Synthetic donor")
            output = config.create_output(account["id"], -100990000000002, "Synthetic output")
            mapping = config.create_mapping(
                donor["id"],
                output["id"],
                50,
                50,
                eligibility_mode="DELAYED",
                delay_minutes=30,
                priority=42,
                media_policy="REUSE_SOURCE",
            )
            record = session.get(TelegramAccount, account["id"])
            record.encrypted_session = cipher.encrypt(
                "synthetic-telegram-session-not-an-authorization"
            )
            session.commit()
            workflow = DurableIngestionWorkflow(
                session,
                technical_filter=MappingTechnicalFilter(
                    mapping_id=str(mapping["id"]), output_channel_id=output["id"]
                ),
            )
            result = workflow.ingest(
                TelegramMessage(
                    "synthetic-persistence",
                    "@synthetic_donor",
                    1,
                    "Permitted synthetic news",
                    media_type="photo",
                ),
                observed_at=datetime.now(UTC),
            )
            assert result.status in {"REWRITE_QUEUED", "DEDUPLICATED"}
            file.write_bytes(content)
            LocalMediaSelectionService(session, root).register_asset(
                file.name,
                origin="SOURCE",
                license_code="OWNED",
                attribution="",
                tags=("synthetic",),
                source_content_key="synthetic-persistence:@synthetic_donor:1:revision:1",
            )
            PublicationPlanningService(session).configure_plan(
                output["id"], "AUTOMATIC", 2, (540, 900), "Europe/Minsk"
            )
        elif sys.argv[1] != "verify":
            raise ValueError("Expected seed or verify")
        account = session.scalar(
            select(TelegramAccount).where(TelegramAccount.name == "Synthetic persistence account")
        )
        assert account is not None
        assert (
            cipher.decrypt(account.encrypted_session)
            == "synthetic-telegram-session-not-an-authorization"
        )
        assert account.encrypted_session != "synthetic-telegram-session-not-an-authorization"
        mapping = session.scalar(select(ChannelMappingModel))
        assert mapping.delay_minutes == 30 and mapping.priority == 42
        assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 1
        assert session.scalar(select(RewriteJobModel.state)) == "DISPATCHED"
        assert session.scalar(select(PublicationCandidateModel.state)) == "AWAITING_REWRITE"
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 2
        assert (
            session.scalar(
                select(func.count())
                .select_from(OutboxEventModel)
                .where(OutboxEventModel.event_type == "rewrite.requested")
            )
            == 1
        )
        asset = session.scalar(select(MediaAssetModel))
        assert asset.sha256 == sha256(file.read_bytes()).hexdigest() == sha256(content).hexdigest()
        plans = PublicationPlanningService(session).list_plans()
        assert plans[0]["daily_limit"] == 2 and plans[0]["timezone"] == "Europe/Minsk"
        print(
            json.dumps(
                {
                    "encrypted_session_decryptable": True,
                    "configuration_preserved": True,
                    "unfinished_job_preserved": True,
                    "outbox_preserved": True,
                    "media_preserved": True,
                    "provider_calls": 0,
                    "telegram_publications": 0,
                }
            )
        )
    engine.dispose()


if __name__ == "__main__":
    main()
