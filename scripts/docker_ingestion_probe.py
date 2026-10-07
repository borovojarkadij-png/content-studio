"""Synthetic donor partial-ingress/down-up recovery; no Telegram/AI network calls."""

import os
import sys
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    ChannelMappingModel,
    ContentRevisionModel,
    DonorChannel,
    DonorIngestionCursorModel,
    EditorialDecisionModel,
    IncomingPostModel,
    PublicationCandidateModel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.providers.telegram import FakeTelegramProvider, TelegramMessage
from newsflow.services.donor_ingestion_runner import (
    DonorIngestionRunner,
    DonorPollClaim,
)
from newsflow.services.moderation_inbox import ModerationInboxReader
from newsflow.services.source_revisions import source_is_current, source_revision
from newsflow.services.telegram_configuration import TelegramConfigurationService

NAME = "synthetic-durable-ingestion"
CHANNEL = -1001888777000


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Ingestion probe requires isolated verification database")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    now = datetime.now(UTC)
    if mode == "seed":
        with factory() as session:
            if (
                session.scalar(select(TelegramAccount.id).where(TelegramAccount.name == NAME))
                is not None
            ):
                raise RuntimeError("Use a fresh fixture; refusing to replace ingestion history")
            config = TelegramConfigurationService(session)
            account = config.create_account(NAME, 300300)
            donor = config.create_donor(account["id"], CHANNEL, NAME)
            for n in (1, 2):
                output = config.create_output(
                    account["id"], CHANNEL - n, f"Synthetic ingestion {n}"
                )
                config.create_mapping(donor["id"], output["id"], 100, 50)
    with factory() as session:
        account = session.scalars(select(TelegramAccount).where(TelegramAccount.name == NAME)).one()
        donor = session.scalars(
            select(DonorChannel).where(DonorChannel.telegram_account_id == account.id)
        ).one()
        account_id, donor_id = account.id, donor.id
        mappings = session.scalars(
            select(ChannelMappingModel)
            .where(ChannelMappingModel.donor_channel_id == donor_id)
            .order_by(ChannelMappingModel.id)
        ).all()
        mapping_id, output_id = mappings[0].id, mappings[0].output_channel_id
    provider = FakeTelegramProvider()
    provider.seed_message(str(account_id), str(CHANNEL), 1, "Synthetic permitted source")
    provider.seed_message(str(account_id), str(CHANNEL), 2, "Synthetic hostile source")
    provider.seed_message(str(account_id), str(CHANNEL), 3, "Unclassified source")
    album_members = (
        TelegramMessage(
            str(account_id), str(CHANNEL), 4, "Album caption", media_type="photo", album_id="777"
        ),
        TelegramMessage(str(account_id), str(CHANNEL), 5, "", media_type="video", album_id="777"),
    )
    for member in album_members:
        provider._messages[(member.account_id, member.donor_identifier, member.message_id)] = member
    poller = DonorIngestionRunner(factory, provider=provider)
    if mode == "seed":
        assert poller.claim(donor_id, now=now) is not None
        # Simulate process exit after one mapping committed, before progress advanced.
        with factory() as session:
            workflow = DurableIngestionWorkflow(
                session,
                technical_filter=MappingTechnicalFilter(
                    mapping_id=str(mapping_id), output_channel_id=output_id
                ),
            )
            assert (
                workflow.ingest(
                    TelegramMessage(str(account_id), str(CHANNEL), 1, "Synthetic permitted source"),
                    observed_at=now,
                    sentiment="neutral",
                    framing="neutral",
                ).status
                == "REWRITE_QUEUED"
            )
            assert (
                workflow.ingest(
                    TelegramMessage(str(account_id), str(CHANNEL), 2, "Synthetic hostile source"),
                    observed_at=now,
                    protected_entities=("Belarus",),
                    sentiment="negative",
                    framing="hostile",
                ).status
                == "REJECTED_EDITORIAL"
            )
        for member in album_members:
            with factory() as session:
                result = DurableIngestionWorkflow(session, configured_mapping_id=mapping_id).ingest(
                    member, observed_at=now, sentiment="neutral", framing="neutral"
                )
                assert result.status == "REJECTED_TECHNICAL"
    elif mode == "recover":
        with factory() as session:
            cursor = session.get(DonorIngestionCursorModel, donor_id)
            assert cursor.last_message_id == 0
            old = DonorPollClaim(donor_id, account_id, CHANNEL, 0, cursor.claim_token)
        claim = poller.claim(donor_id, now=now)
        assert claim is not None and claim.token != old.token
        assert poller.execute(old) == "STALE_CLAIM"
        assert provider.session_probe_count(str(account_id)) == 0
        assert poller.execute(claim) == "POLL_COMPLETE"
    elif mode == "edit":
        with factory() as session:
            changed = TelegramMessage(
                str(account_id),
                str(CHANNEL),
                1,
                "Synthetic permitted source",
                is_edit=True,
                media_type="video",
                album_id="synthetic-album-55",
                source_updated_at=now,
            )
            assert (
                DurableIngestionWorkflow(session, configured_mapping_id=mapping_id)
                .ingest(changed, observed_at=now)
                .status
                == "REJECTED_TECHNICAL"
            )
    elif mode not in {"verify", "verify-edit"}:
        raise ValueError("Unsupported probe mode")
    # Check the observation seam after stale-owner zero-RPC assertions, not
    # before: this explicitly authorized fake read increments its session probe.
    album = provider.album_window(str(account_id), str(CHANNEL), anchor_id=4)
    assert album.message_ids == (4, 5) and album.media_types == ("photo", "video")
    assert not album.membership_complete and not album.rewrite_allowed
    with factory() as session:
        cursor = session.get(DonorIngestionCursorModel, donor_id)
        prefix = f"{account_id}:{CHANNEL}:"
        jobs = session.scalars(
            select(RewriteJobModel).where(RewriteJobModel.content_key.startswith(prefix))
        ).all()
        candidates = session.scalars(
            select(PublicationCandidateModel).where(
                PublicationCandidateModel.content_key.startswith(prefix)
            )
        ).all()
        assert len(jobs) == len(candidates) == (1 if mode == "seed" else 2)
        assert all(job.content_key == f"{prefix}1:revision:1" for job in jobs)
        rejected = session.scalars(
            select(EditorialDecisionModel).where(
                EditorialDecisionModel.content_key == f"{prefix}2:revision:1"
            )
        ).one()
        assert rejected.status == "REJECT" and not rejected.rewrite_allowed
        if mode != "seed":
            assert cursor.last_message_id == 5 and cursor.claim_token is None
            items = [
                item
                for item in ModerationInboxReader(session).list_items()
                if item.source_key.startswith(prefix)
            ]
            assert len(items) == 5
            assert (
                next(item for item in items if item.source_key == f"{prefix}3").editorial_status
                == "MANUAL_REVIEW"
            )
            assert (
                len(
                    session.scalars(
                        select(IncomingPostModel).where(
                            IncomingPostModel.telegram_account_id == str(account_id)
                        )
                    ).all()
                )
                == 5
            )
            for message_id in (4, 5):
                item = next(item for item in items if item.source_key == f"{prefix}{message_id}")
                assert item.state == "REJECTED_TECHNICAL" and item.editorial_status is None
                revision = source_revision(session, f"{prefix}{message_id}:revision:1")
                assert revision.album_id == "777"
        if mode in {"edit", "verify-edit"}:
            assert not source_is_current(session, f"{prefix}1:revision:1")
            revision = source_revision(session, f"{prefix}1:revision:2")
            assert revision.media_type == "video" and revision.album_id == "synthetic-album-55"
            assert revision.source_updated_at is not None
            assert (
                session.scalar(
                    select(EditorialDecisionModel.id).where(
                        EditorialDecisionModel.content_key == f"{prefix}1:revision:2"
                    )
                )
                is None
            )
            assert (
                len(
                    session.scalars(
                        select(ContentRevisionModel).where(
                            ContentRevisionModel.incoming_post_id == revision.incoming_post_id
                        )
                    ).all()
                )
                == 2
            )
    engine.dispose()
    print(
        f"Synthetic ingestion {mode} PASS: cursor/partial fan-out/reject/manual review; external calls=0"
    )


if __name__ == "__main__":
    main(sys.argv[1])
