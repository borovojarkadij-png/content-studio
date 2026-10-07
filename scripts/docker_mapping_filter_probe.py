"""Actual PostgreSQL policy/job down-up guard; all content and claims synthetic."""

import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import (
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner, RewriteClaim
from newsflow.services.telegram_configuration import TelegramConfigurationService


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Mapping filter probe requires isolated verification database")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    now = datetime.now(UTC)
    if mode == "seed":
        with factory() as session:
            if session.scalar(
                select(TelegramAccount.id).where(
                    TelegramAccount.name == "synthetic-mapping-filters"
                )
            ):
                raise RuntimeError("Use a fresh fixture; refusing to replace filter history")
            config = TelegramConfigurationService(session)
            account = config.create_account("synthetic-mapping-filters", 600600)
            donor = config.create_donor(account["id"], -1006006006006, "Synthetic filter donor")
            output = config.create_output(account["id"], -1006006006007, "Synthetic filter output")
            mapping = config.create_mapping(donor["id"], output["id"], 100, 100)
            config.configure_mapping_filters(
                mapping["id"],
                allowed_media_types=["text"],
                blocked_domains=["initial.example"],
                ad_markers=["sponsored sample"],
            )
        with factory() as session:
            result = DurableIngestionWorkflow(session, configured_mapping_id=mapping["id"]).ingest(
                TelegramMessage(
                    str(account["id"]), "-1006006006006", 1, "Synthetic https://example.org/source"
                ),
                observed_at=now,
                sentiment="neutral",
                framing="neutral",
            )
            assert result.status == "REWRITE_QUEUED"
        with factory() as session:
            config = TelegramConfigurationService(session)
            config.configure_mapping_filters(
                mapping["id"],
                allowed_media_types=["text"],
                blocked_domains=["example.org"],
                ad_markers=["sponsored sample"],
            )
    elif mode == "verify":
        with factory() as session:
            account = session.scalar(
                select(TelegramAccount).where(TelegramAccount.name == "synthetic-mapping-filters")
            )
            if account is None:
                raise RuntimeError("Missing mapping filter fixture")
            key = f"{account.id}:-1006006006006:1:revision:1"
            candidate = session.scalar(
                select(PublicationCandidateModel).where(
                    PublicationCandidateModel.content_key == key
                )
            )
            policy = TelegramConfigurationService(session).mapping_filters(candidate.mapping_id)
            assert policy["blocked_domains"] == ["example.org"]
            assert policy["allowed_media_types"] == ["text"]
            job = session.scalar(select(RewriteJobModel).where(RewriteJobModel.content_key == key))
            assert job.state == "DISPATCHED"
            # A controlled synthetic owner isolates this job from older fixture
            # jobs; production claim-next/recovery is verified by the other drill.
            job.state, job.claim_token = "RUNNING", str(uuid4())
            job.attempts, job.lease_expires_at = 1, now + timedelta(seconds=60)
            claim = RewriteClaim(job.id, job.claim_token)
            session.commit()

        def forbidden(_):
            raise AssertionError("Persisted forbidden link reached rewrite provider")

        assert (
            DurableRewriteRunner(
                factory, provider_for_channel=forbidden, clock=lambda: now
            ).execute_claim(claim, now=now)
            == "BLOCKED_TECHNICAL"
        )
        with factory() as session:
            assert session.get(RewriteJobModel, claim.job_id).state == "BLOCKED_TECHNICAL"
            assert (
                session.scalar(
                    select(RewriteOutputModel.id).where(RewriteOutputModel.content_key == key)
                )
                is None
            )
    else:
        raise ValueError("Expected seed or verify")
    engine.dispose()
    print(f"Persistent mapping filter {mode} PASS; AI rewrite/publication calls=0")


if __name__ == "__main__":
    main(sys.argv[1])
