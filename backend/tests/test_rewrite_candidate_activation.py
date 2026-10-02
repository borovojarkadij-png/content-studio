from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.publication_candidate_activation import RewriteCandidateActivationService


def test_passing_mapped_ingestion_creates_awaiting_rewrite_candidate_then_activates_it() -> None:
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
            telegram_account_id=account.id, telegram_channel_id=-1001234567890, title="Destination"
        )
        session.add(output)
        session.flush()
        output_id = output.id
        session.commit()
        workflow = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1", output_channel_id=output_id
            ),
        )

        result = workflow.ingest(
            TelegramMessage("account-a", "@donor", 7, "permitted news"),
            observed_at=datetime.now(UTC),
        )
        candidate = session.scalar(select(PublicationCandidateModel))
        assert result.status == "REWRITE_QUEUED"
        assert candidate is not None
        assert candidate.state == "AWAITING_REWRITE"

        job = session.scalar(select(RewriteJobModel))
        assert job is not None
        job.state = "SUCCEEDED"
        job_id = job.id
        session.commit()
        assert RewriteCandidateActivationService(session).activate(job_id) == 1
        assert session.scalar(select(PublicationCandidateModel)).state == "READY"


def test_editorial_reject_never_creates_or_activates_a_candidate() -> None:
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
            telegram_account_id=account.id, telegram_channel_id=-1001234567890, title="Destination"
        )
        session.add(output)
        session.flush()
        output_id = output.id
        session.commit()
        result = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1", output_channel_id=output_id
            ),
        ).ingest(
            TelegramMessage("account-a", "@donor", 8, "hostile claim"),
            observed_at=datetime.now(UTC),
            protected_entities=["Belarus"],
            sentiment="negative",
            framing="hostile",
        )
        assert result.status == "REJECTED_EDITORIAL"
        assert session.scalars(select(PublicationCandidateModel)).all() == []
        assert session.scalar(select(EditorialDecisionModel)).rewrite_allowed is False
        assert session.scalars(select(RewriteJobModel)).all() == []


def test_stale_editorial_reject_blocks_candidate_after_rewrite_completes() -> None:
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
            telegram_account_id=account.id, telegram_channel_id=-1001234567890, title="Destination"
        )
        session.add(output)
        session.flush()
        output_id = output.id
        session.commit()

        DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1", output_channel_id=output_id
            ),
        ).ingest(
            TelegramMessage("account-a", "@donor", 9, "permitted news"),
            observed_at=datetime.now(UTC),
        )
        decision = session.scalar(select(EditorialDecisionModel))
        job = session.scalar(select(RewriteJobModel))
        assert decision is not None
        assert job is not None
        decision.status = "REJECT"
        decision.rewrite_allowed = False
        job.state = "SUCCEEDED"
        job_id = job.id
        session.commit()

        assert RewriteCandidateActivationService(session).activate(job_id) == 0
        assert session.scalar(select(PublicationCandidateModel)).state == "BLOCKED_EDITORIAL"


def test_same_source_fans_out_to_each_mapping_without_repeat_rewrite_dispatch() -> None:
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
        first_output = OutputChannel(
            telegram_account_id=account.id, telegram_channel_id=-1001234567890, title="First"
        )
        second_output = OutputChannel(
            telegram_account_id=account.id, telegram_channel_id=-1009876543210, title="Second"
        )
        session.add_all((first_output, second_output))
        session.flush()
        first_output_id = first_output.id
        second_output_id = second_output.id
        session.commit()

        event = TelegramMessage("account-a", "@donor", 10, "shared source")
        first = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1", output_channel_id=first_output_id
            ),
        ).ingest(event, observed_at=datetime.now(UTC))
        second = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-2", output_channel_id=second_output_id
            ),
        ).ingest(event, observed_at=datetime.now(UTC))

        assert first.status == second.status == "REWRITE_QUEUED"
        assert [
            candidate.output_channel_id
            for candidate in session.scalars(
                select(PublicationCandidateModel).order_by(
                    PublicationCandidateModel.output_channel_id
                )
            )
        ] == [first_output_id, second_output_id]
        jobs = session.scalars(
            select(RewriteJobModel).order_by(RewriteJobModel.output_channel_id)
        ).all()
        assert [job.output_channel_id for job in jobs] == [first_output_id, second_output_id]
        assert len(jobs) == 2
        jobs[0].state = "SUCCEEDED"
        first_job_id = jobs[0].id
        session.commit()
        assert RewriteCandidateActivationService(session).activate(first_job_id) == 1
        candidates = session.scalars(
            select(PublicationCandidateModel).order_by(PublicationCandidateModel.output_channel_id)
        ).all()
        assert [candidate.state for candidate in candidates] == ["READY", "AWAITING_REWRITE"]
        session.commit()
        assert (
            DurableIngestionWorkflow(
                session,
                technical_filter=MappingTechnicalFilter(
                    mapping_id="mapping-2", output_channel_id=second_output_id
                ),
            )
            .ingest(event, observed_at=datetime.now(UTC))
            .status
            == "REJECTED_DUPLICATE"
        )


def test_stale_source_replay_cannot_fan_out_newer_edited_revision() -> None:
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
        first_output = OutputChannel(
            telegram_account_id=account.id, telegram_channel_id=-1001234567890, title="First"
        )
        second_output = OutputChannel(
            telegram_account_id=account.id, telegram_channel_id=-1009876543210, title="Second"
        )
        session.add_all((first_output, second_output))
        session.flush()
        first_output_id = first_output.id
        second_output_id = second_output.id
        session.commit()

        original = TelegramMessage("account-a", "@donor", 11, "permitted news")
        DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1", output_channel_id=first_output_id
            ),
        ).ingest(original, observed_at=datetime.now(UTC))
        edited = TelegramMessage(
            "account-a", "@donor", 11, "https://blocked.example altered", is_edit=True
        )
        DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1", output_channel_id=first_output_id
            ),
        ).ingest(edited, observed_at=datetime.now(UTC))

        replay = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-2",
                output_channel_id=second_output_id,
                blocked_domains=frozenset({"blocked.example"}),
            ),
        ).ingest(original, observed_at=datetime.now(UTC))

        assert replay.status == "REJECTED_DUPLICATE"
        assert all(
            candidate.output_channel_id == first_output_id
            for candidate in session.scalars(select(PublicationCandidateModel))
        )
