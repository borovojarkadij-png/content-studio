from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from alembic import command
from newsflow.migrate import runtime_migration_config
from newsflow.persistence.models import (
    ContentRevisionModel,
    IncomingPostModel,
    OutputChannel,
    RewriteJobModel,
    RewriteOutputModel,
    SemanticVerificationJobModel,
    SemanticVerifierReleaseModel,
    TelegramAccount,
)


def test_durable_semantic_migration_refuses_to_discard_attempt_history(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'isolated-semantic-job.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = runtime_migration_config()
    command.upgrade(config, "b7d2e904a613")
    command.upgrade(config, "head")
    command.check(config)
    engine = create_engine(url)
    with Session(engine) as session:
        account = TelegramAccount(name="synthetic", telegram_user_id=1001, encrypted_session="")
        session.add(account)
        session.flush()
        output = OutputChannel(
            telegram_account_id=account.id, telegram_channel_id=-1001888888999, title="synthetic"
        )
        post = IncomingPostModel(
            telegram_account_id="synthetic",
            donor_channel_id="@synthetic",
            telegram_message_id=1,
            state="RECEIVED",
        )
        release = SemanticVerifierReleaseModel(
            provider="OPENAI",
            model="synthetic",
            prompt_version="semantic-facts-v1",
            benchmark_version="semantic-facts-v1",
            report_sha256="a" * 64,
        )
        session.add_all([output, post, release])
        session.flush()
        revision = ContentRevisionModel(
            incoming_post_id=post.id, revision_number=1, source_text="synthetic"
        )
        job = RewriteJobModel(
            content_key="synthetic",
            output_channel_id=output.id,
            idempotency_key="synthetic",
            state="SUCCEEDED",
        )
        session.add_all([revision, job])
        session.flush()
        draft = RewriteOutputModel(
            rewrite_job_id=job.id,
            output_channel_id=output.id,
            content_key="synthetic",
            rewritten_text="synthetic",
            approval_state="PENDING",
        )
        session.add(draft)
        session.flush()
        session.add(
            SemanticVerificationJobModel(
                rewrite_output_id=draft.id,
                source_revision_id=revision.id,
                release_id=release.id,
                source_sha256="b" * 64,
                draft_sha256="c" * 64,
                release_sha256="d" * 64,
                state="QUEUED",
                available_at=datetime.now(UTC),
            )
        )
        session.commit()
    with pytest.raises(RuntimeError, match="Refusing"):
        command.downgrade(config, "b7d2e904a613")
    with Session(engine) as session:
        job = session.scalar(select(SemanticVerificationJobModel))
        assert job.state == "QUEUED" and job.attempts == 0
        assert session.scalar(select(RewriteOutputModel.rewritten_text)) == "synthetic"
    engine.dispose()
