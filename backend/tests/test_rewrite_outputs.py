from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutputChannel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.services.rewrite_outputs import RewriteOutputService


def test_rewrite_output_is_scoped_to_one_output_and_requires_explicit_approval() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        account = TelegramAccount(
            name="Primary",
            telegram_user_id=1001,
            encrypted_session="",
            health_status="DISCONNECTED",
        )
        session.add(account)
        session.flush()
        output = OutputChannel(
            telegram_account_id=account.id,
            telegram_channel_id=-1001234567890,
            title="Destination",
        )
        session.add(output)
        session.flush()
        session.add(
            EditorialDecisionModel(
                content_key="source:revision:1",
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
        )
        session.add(
            RewriteJobModel(
                content_key="source:revision:1",
                output_channel_id=output.id,
                idempotency_key="rewrite.requested:source:revision:1:1",
                state="SUCCEEDED",
            )
        )
        session.commit()
        job_id = session.scalar(select(RewriteJobModel.id))
        assert job_id is not None

        service = RewriteOutputService(session)
        draft = service.record_succeeded_output(job_id, "Переписанный текст")

        assert draft["approval_state"] == "PENDING"
        assert draft["output_channel_id"] == output.id
        approved = service.approve(draft["id"])
        assert approved["approval_state"] == "APPROVED"


def test_stale_editorial_reject_blocks_rewrite_output_approval() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        account = TelegramAccount(
            name="Primary",
            telegram_user_id=1001,
            encrypted_session="",
            health_status="DISCONNECTED",
        )
        session.add(account)
        session.flush()
        output = OutputChannel(
            telegram_account_id=account.id,
            telegram_channel_id=-1001234567890,
            title="Destination",
        )
        session.add(output)
        session.flush()
        decision = EditorialDecisionModel(
            content_key="source:revision:2",
            status="PASS",
            rewrite_allowed=True,
            sentiment="neutral",
            framing="neutral",
        )
        session.add(decision)
        job = RewriteJobModel(
            content_key=decision.content_key,
            output_channel_id=output.id,
            idempotency_key="rewrite.requested:source:revision:2:1",
            state="SUCCEEDED",
        )
        session.add(job)
        session.commit()
        draft = RewriteOutputService(session).record_succeeded_output(job.id, "Draft")
        decision.status = "REJECT"
        decision.rewrite_allowed = False
        session.commit()

        try:
            RewriteOutputService(session).approve(draft["id"])
        except PermissionError as exc:
            assert "EDITORIAL" in str(exc)
        else:
            raise AssertionError("Stale editorial reject must block rewrite approval")
