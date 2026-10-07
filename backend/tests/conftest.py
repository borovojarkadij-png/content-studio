"""Shared isolated synthetic semantic store; no live-model qualifications."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
    SemanticVerifierReleaseModel,
    TelegramAccount,
)
from newsflow.services.automatic_approval import AutomaticApprovalPolicyService

SOURCE = "Завод открыл 3 линии."
DRAFT = "Открыты 3 линии на заводе."
KEY = "synthetic:@semantic:1:revision:1"


@pytest.fixture
def semantic_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'semantic.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as session:
        account = TelegramAccount(name="synthetic", telegram_user_id=1001, encrypted_session="")
        session.add(account)
        session.flush()
        channels = [
            OutputChannel(
                telegram_account_id=account.id,
                telegram_channel_id=-1000000000000 - n,
                title=f"synthetic-{n}",
            )
            for n in (1, 2)
        ]
        post = IncomingPostModel(
            telegram_account_id="synthetic",
            donor_channel_id="@semantic",
            telegram_message_id=1,
            state="RECEIVED",
        )
        release = SemanticVerifierReleaseModel(
            provider="OPENAI",
            model="synthetic-model",
            prompt_version="semantic-facts-v1",
            benchmark_version="semantic-facts-v1",
            report_sha256="f" * 64,
            active=True,
        )
        session.add_all(
            [
                *channels,
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
            ContentRevisionModel(incoming_post_id=post.id, revision_number=1, source_text=SOURCE)
        )
        for channel in channels:
            job = RewriteJobModel(
                content_key=KEY,
                output_channel_id=channel.id,
                idempotency_key=f"synthetic-{channel.id}",
                state="SUCCEEDED",
            )
            session.add(job)
            session.flush()
            session.add_all(
                [
                    RewriteOutputModel(
                        rewrite_job_id=job.id,
                        output_channel_id=channel.id,
                        content_key=KEY,
                        rewritten_text=DRAFT,
                        approval_state="PENDING",
                    ),
                    PublicationCandidateModel(
                        output_channel_id=channel.id,
                        content_key=KEY,
                        priority=10,
                        state="AWAITING_REWRITE",
                    ),
                ]
            )
        session.commit()
        for channel in channels:
            AutomaticApprovalPolicyService(session).configure(channel.id, "VERIFIED", release.id)
    yield factory
    engine.dispose()
