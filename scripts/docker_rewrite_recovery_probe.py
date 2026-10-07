"""Isolated synthetic runner acceptance, never a network provider or Telegram send."""

import io
import json
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import (
    OutboxEventModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
    RewriteUsageModel,
    TelegramAccount,
)
from newsflow.security.master_key import load_runtime_master_key
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner, RewriteClaim
from newsflow.services.rewrite_provider_factory import ConfiguredRewriteProviderFactory
from newsflow.services.rewrite_provider_settings import RewriteProviderSettingsService
from newsflow.services.telegram_configuration import TelegramConfigurationService

CONTENT_KEY = "synthetic-persistence:@synthetic_donor:1:revision:1"


class SyntheticHttp:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request, *, timeout):
        self.calls += 1
        payload = json.loads(request.data)
        assert request.full_url == "https://api.openai.com/v1/responses"
        assert payload["model"] == "synthetic-model"
        assert payload["input"][1]["content"] == "Permitted synthetic news"
        assert "tabloid" in payload["input"][0]["content"].lower()
        return io.BytesIO(
            json.dumps(
                {
                    "status": "completed",
                    "error": None,
                    "output": [
                        {
                            "type": "message",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": json.dumps(
                                        {
                                            "rewritten_text": "Synthetic rewrite: Permitted synthetic news"
                                        }
                                    ),
                                }
                            ],
                        }
                    ],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                        "input_tokens_details": {"cached_tokens": 40},
                    },
                }
            ).encode()
        )


def main() -> None:
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Recovery probe requires the isolated verification database")
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    cipher = SessionCipher(load_runtime_master_key())
    with factory() as session:
        account = session.scalar(
            select(TelegramAccount).where(TelegramAccount.name == "Synthetic persistence account")
        )
        assert account is not None
        assert (
            cipher.decrypt(account.encrypted_session)
            == "synthetic-telegram-session-not-an-authorization"
        )
        job = session.scalars(
            select(RewriteJobModel).where(RewriteJobModel.content_key == CONTENT_KEY)
        ).one()
        job_id = job.id
        previous_token = job.claim_token
        if sys.argv[1] == "claim":
            channel_id = job.output_channel_id
            RewriteProviderSettingsService(session, cipher=cipher).configure_openai(
                api_key="synthetic-not-a-real-credential", model="synthetic-model"
            )
            TelegramConfigurationService(session).configure_rewrite_style(channel_id, "TABLOID")
    provider = SyntheticHttp()
    configured = ConfiguredRewriteProviderFactory(factory, cipher=cipher, opener=provider)
    runner = DurableRewriteRunner(factory, provider_for_channel=configured)
    now = datetime.now(UTC)
    if sys.argv[1] == "claim":
        claimed = runner.claim_next(now=now)
        assert claimed is not None and claimed.job_id == job_id
        with factory() as session:
            job = session.get(RewriteJobModel, job_id)
            assert job.state == "RUNNING" and job.attempts == 1
            print(
                json.dumps(
                    {
                        "claim_persisted": True,
                        "lease_expires_at": job.lease_expires_at.isoformat(),
                        "network_calls": 0,
                    }
                )
            )
    elif sys.argv[1] == "recover":
        assert previous_token is not None
        recovered = runner.claim_next(now=now)
        assert recovered is not None and recovered.job_id == job_id, (
            "Lease must expire before recovery"
        )
        assert recovered.token != previous_token
        assert runner.execute_claim(RewriteClaim(job_id, previous_token), now=now) == "STALE_CLAIM"
        assert provider.calls == 0
        assert runner.execute_claim(recovered, now=now) == "SUCCEEDED"
        assert provider.calls == 1
        verify(factory, job_id)
        assert runner.run_next(now=now) == "IDLE"
        print(
            json.dumps(
                {
                    "expired_claim_recovered": True,
                    "old_owner_fenced": True,
                    "synthetic_rewrite_calls": 1,
                    "network_calls": 0,
                    "telegram_publications": 0,
                }
            )
        )
    elif sys.argv[1] == "verify":
        verify(factory, job_id)
        print(
            json.dumps(
                {
                    "completed_draft_persisted": True,
                    "approval_pending": True,
                    "network_calls": 0,
                    "telegram_publications": 0,
                }
            )
        )
    else:
        raise ValueError("Expected claim, recover or verify")
    engine.dispose()


def verify(factory, job_id: int) -> None:
    with factory() as session:
        job = session.get(RewriteJobModel, job_id)
        assert job.state == "SUCCEEDED" and job.attempts == 2
        assert job.claim_token is None and job.lease_expires_at is None
        output = session.scalars(
            select(RewriteOutputModel).where(RewriteOutputModel.rewrite_job_id == job_id)
        ).one()
        assert output.approval_state == "PENDING"
        assert output.rewritten_text == "Synthetic rewrite: Permitted synthetic news"
        candidate = session.scalars(
            select(PublicationCandidateModel).where(
                PublicationCandidateModel.content_key == CONTENT_KEY
            )
        ).one()
        assert candidate.state == "AWAITING_REWRITE"
        usage = session.scalars(
            select(RewriteUsageModel).where(RewriteUsageModel.rewrite_job_id == job_id)
        ).one()
        assert (usage.attempt, usage.input_tokens, usage.output_tokens) == (2, 100, 20)
        assert usage.style == "TABLOID" and usage.estimated_cost_usd is None
        assert (
            session.scalar(
                select(func.count())
                .select_from(OutboxEventModel)
                .where(OutboxEventModel.idempotency_key == f"rewrite.completed:{job_id}")
            )
            == 1
        )


if __name__ == "__main__":
    main()
