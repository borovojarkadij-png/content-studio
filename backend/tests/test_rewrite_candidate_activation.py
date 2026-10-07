from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    Base,
    ChannelMappingModel,
    DonorChannel,
    EditorialDecisionModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.publication_candidate_activation import RewriteCandidateActivationService
from newsflow.services.rewrite_outputs import RewriteOutputService


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
            sentiment="neutral",
            framing="neutral",
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
        assert RewriteCandidateActivationService(session).activate(job_id) == 0
        output = RewriteOutputService(session).record_succeeded_output(job_id, "Rewritten text")
        assert output["approval_state"] == "PENDING"
        assert RewriteCandidateActivationService(session).activate(job_id) == 0
        RewriteOutputService(session).approve(output["id"])
        assert RewriteCandidateActivationService(session).activate(job_id) == 1
        assert session.scalar(select(PublicationCandidateModel)).state == "READY"


def test_ingestion_snapshots_delayed_mapping_delivery_policy_onto_candidate() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    observed_at = datetime(2026, 10, 7, 9, tzinfo=UTC)
    with Session(engine) as session:
        account = TelegramAccount(
            name="Primary",
            telegram_user_id=1001,
            encrypted_session="",
            health_status="DISCONNECTED",
        )
        session.add(account)
        session.flush()
        donor = DonorChannel(
            telegram_account_id=account.id,
            telegram_channel_id=-1001234567890,
            title="Source",
        )
        output = OutputChannel(
            telegram_account_id=account.id,
            telegram_channel_id=-1009876543210,
            title="Destination",
        )
        session.add_all((donor, output))
        session.flush()
        mapping = ChannelMappingModel(
            donor_channel_id=donor.id,
            output_channel_id=output.id,
            intake_percent=100,
            target_mix_percent=100,
            eligibility_mode="DELAYED",
            delay_minutes=45,
            priority=80,
            media_policy="LICENSED_LIBRARY",
        )
        session.add(mapping)
        session.flush()
        mapping_id = mapping.id
        output_id = output.id
        session.commit()

        result = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id=str(mapping_id), output_channel_id=output_id
            ),
        ).ingest(
            TelegramMessage("account-a", "@donor", 70, "permitted news"),
            observed_at=observed_at,
            sentiment="neutral",
            framing="neutral",
        )

        candidate = session.scalar(select(PublicationCandidateModel))
        assert result.status == "REWRITE_QUEUED"
        assert candidate is not None
        assert candidate.mapping_id == mapping_id
        assert candidate.priority == 80
        assert candidate.eligible_at.replace(tzinfo=UTC) == datetime(2026, 10, 7, 9, 45, tzinfo=UTC)
        assert candidate.media_policy == "LICENSED_LIBRARY"
        configured_mapping = session.get(ChannelMappingModel, mapping_id)
        assert configured_mapping is not None
        configured_mapping.priority = -10
        configured_mapping.media_policy = "REUSE_SOURCE"
        session.commit()
        session.refresh(candidate)
        assert candidate.priority == 80
        assert candidate.media_policy == "LICENSED_LIBRARY"


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
            sentiment="neutral",
            framing="neutral",
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
        ).ingest(event, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral")
        second = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-2", output_channel_id=second_output_id
            ),
        ).ingest(event, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral")

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
        rewritten = RewriteOutputService(session).record_succeeded_output(
            first_job_id, "First channel rewrite"
        )
        RewriteOutputService(session).approve(rewritten["id"])
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
            .ingest(event, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral")
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
        ).ingest(original, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral")
        edited = TelegramMessage(
            "account-a", "@donor", 11, "https://blocked.example altered", is_edit=True
        )
        DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-1", output_channel_id=first_output_id
            ),
        ).ingest(edited, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral")

        replay = DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id="mapping-2",
                output_channel_id=second_output_id,
                blocked_domains=frozenset({"blocked.example"}),
            ),
        ).ingest(original, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral")

        assert replay.status == "REJECTED_DUPLICATE"
        assert all(
            candidate.output_channel_id == first_output_id
            for candidate in session.scalars(select(PublicationCandidateModel))
        )
