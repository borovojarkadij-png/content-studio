"""Synthetic semantic approval persistence; refuses operational databases."""

import os
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
    SemanticEvidenceModel,
    SemanticVerificationJobModel,
    SemanticVerificationUsageModel,
    SemanticVerifierReleaseModel,
    TelegramAccount,
)
from newsflow.providers.openai_rewrite import RewriteUsage
from newsflow.services.automatic_approval import AutomaticApprovalPolicyService, approval_is_current
from newsflow.services.durable_semantic_runner import DurableSemanticRunner, SemanticClaim
from newsflow.services.publication_planning import PublicationPlanningService

KEY = "synthetic-semantic:@synthetic_semantic:910:revision:1"
SOURCE = "Synthetic factory opened 3 lines."
DRAFT = "3 lines opened at the synthetic factory."


class SyntheticVerifier:
    provider = "OPENAI"
    model = "synthetic-semantic-model"
    prompt_version = "semantic-facts-v1"
    calls = 0
    last_usage = RewriteUsage(model, 100, 40, 20, None)

    def verify(self, source, draft):
        assert (source, draft) == (SOURCE, DRAFT)
        self.calls += 1
        return {
            "verdict": "PRESERVED",
            "source_complete": True,
            "draft_complete": True,
            "claims": [{"source_quote": source, "draft_quote": draft, "relation": "SUPPORTED"}],
        }


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Semantic probe requires the isolated verification database")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    day = datetime.now(UTC).date() + timedelta(days=1)
    if mode == "seed":
        with factory() as session:
            if (
                session.scalar(select(RewriteJobModel.id).where(RewriteJobModel.content_key == KEY))
                is not None
            ):
                raise RuntimeError(
                    "Use a fresh isolated fixture; refusing to replace semantic history"
                )
            account = TelegramAccount(
                name="synthetic-semantic", telegram_user_id=200200, encrypted_session=""
            )
            session.add(account)
            session.flush()
            channel = OutputChannel(
                telegram_account_id=account.id,
                telegram_channel_id=-1001888888999,
                title="Synthetic semantic only",
            )
            post = IncomingPostModel(
                telegram_account_id="synthetic-semantic",
                donor_channel_id="@synthetic_semantic",
                telegram_message_id=910,
                state="RECEIVED",
            )
            # This is a synthetic test qualification, NEVER a real model release.
            release = SemanticVerifierReleaseModel(
                provider="OPENAI",
                model=SyntheticVerifier.model,
                prompt_version=SyntheticVerifier.prompt_version,
                benchmark_version="semantic-facts-v1",
                report_sha256="f" * 64,
                active=True,
            )
            session.add_all(
                [
                    channel,
                    post,
                    release,
                    EditorialDecisionModel(
                        content_key=KEY,
                        status="PASS",
                        rewrite_allowed=True,
                        sentiment="neutral",
                        framing="neutral",
                    ),
                ]
            )
            session.flush()
            session.add(
                ContentRevisionModel(
                    incoming_post_id=post.id, revision_number=1, source_text=SOURCE
                )
            )
            job = RewriteJobModel(
                content_key=KEY,
                output_channel_id=channel.id,
                idempotency_key="synthetic-semantic-rewrite",
                state="SUCCEEDED",
            )
            session.add(job)
            session.flush()
            draft = RewriteOutputModel(
                rewrite_job_id=job.id,
                output_channel_id=channel.id,
                content_key=KEY,
                rewritten_text=DRAFT,
                approval_state="PENDING",
            )
            session.add_all(
                [
                    draft,
                    PublicationCandidateModel(
                        output_channel_id=channel.id,
                        content_key=KEY,
                        priority=0,
                        state="AWAITING_REWRITE",
                    ),
                ]
            )
            session.commit()
            channel_id, release_id = channel.id, release.id
            AutomaticApprovalPolicyService(session).configure(channel_id, "VERIFIED", release_id)
        verifier = SyntheticVerifier()
        execution = DurableSemanticRunner(factory, verifier_for_release=lambda _: verifier)
        assert execution.enqueue_pending(now=datetime.now(UTC)) == 1
        claim = execution.claim_next(now=datetime.now(UTC))
        assert claim is not None and claim.attempt == 1
        assert verifier.calls == 0
    elif mode == "recover":
        verifier = SyntheticVerifier()
        execution = DurableSemanticRunner(factory, verifier_for_release=lambda _: verifier)
        with factory() as session:
            job = session.scalars(select(SemanticVerificationJobModel)).one()
            old = SemanticClaim(job.id, job.claim_token, job.attempts)
        recovered = execution.claim_next(now=datetime.now(UTC))
        assert recovered is not None and recovered.job_id == old.job_id and recovered.attempt == 2
        assert execution.execute(old) == "LOST_LEASE"
        assert execution.execute(recovered) == "SUCCEEDED"
        assert verifier.calls == 1
        with factory() as session:
            draft = session.scalars(
                select(RewriteOutputModel).where(RewriteOutputModel.content_key == KEY)
            ).one()
            planner = PublicationPlanningService(session)
            plan = planner.configure_plan(draft.output_channel_id, "AUTOMATIC", 1, (720,), "UTC")
            assert len(planner.plan_day(plan["id"], day)) == 1
    elif mode in {"verify", "revoke"}:
        with factory() as session:
            draft = session.scalars(
                select(RewriteOutputModel).where(RewriteOutputModel.content_key == KEY)
            ).one()
            evidence = session.scalars(
                select(SemanticEvidenceModel).where(
                    SemanticEvidenceModel.rewrite_output_id == draft.id
                )
            ).one()
            assert evidence.verdict == "PRESERVED"
            assert draft.approval_method == "AUTOMATIC"
            assert approval_is_current(session, draft) is True
            job = session.scalars(select(SemanticVerificationJobModel)).one()
            usage = session.scalars(select(SemanticVerificationUsageModel)).one()
            assert job.state == "SUCCEEDED" and job.attempts == 2
            assert job.claim_token is None and job.evidence_id == evidence.id
            assert usage.attempt == 2 and usage.input_tokens == 100
            if mode == "revoke":
                session.get(SemanticVerifierReleaseModel, evidence.release_id).active = False
                session.commit()
                assert approval_is_current(session, draft) is False
                planner = PublicationPlanningService(session)
                plan = next(
                    plan
                    for plan in planner.list_plans()
                    if plan["output_channel_id"] == draft.output_channel_id
                )
                assert planner.plan_day(plan["id"], day) == []
                assert planner.list_publications(plan["id"], day)[0]["state"] == "BLOCKED_REVIEW"
    else:
        raise ValueError("Unknown semantic verification mode")
    engine.dispose()
    print(f"Synthetic semantic {mode} passed; no network provider or publication")


if __name__ == "__main__":
    main(sys.argv[1])
