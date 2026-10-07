from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    Base,
    EditorialDecisionModel,
    OutboxEventModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
)
from newsflow.providers.openrouter import ProviderUnavailable
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.telegram_configuration import TelegramConfigurationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture
def rewrite_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rewrite-runner.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        configuration = TelegramConfigurationService(session)
        account = configuration.create_account("Synthetic", 1001)
        donor = configuration.create_donor(account["id"], -1001234567890, "Synthetic donor")
        for number in (1, 2):
            output = configuration.create_output(
                account["id"], -1001234567890 - number, str(number)
            )
            mapping = configuration.create_mapping(donor["id"], output["id"], 50, 50)
            DurableIngestionWorkflow(
                session,
                technical_filter=MappingTechnicalFilter(
                    mapping_id=str(mapping["id"]), output_channel_id=output["id"]
                ),
            ).ingest(
                TelegramMessage("synthetic", "@donor", 1, "Открыто 10 объектов"), observed_at=NOW
            )
    yield factory
    engine.dispose()


class SafeSyntheticProvider:
    def __init__(self, result=None, unavailable=False):
        self.calls = 0
        self.result = result
        self.unavailable = unavailable

    def rewrite(self, text):
        self.calls += 1
        if self.unavailable:
            raise ProviderUnavailable("synthetic-private-error-not-for-storage")
        return self.result or f"Переписано: {text}"


def test_runner_creates_independent_per_channel_pending_drafts_and_completion_outbox(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    providers = {1: SafeSyntheticProvider(), 2: SafeSyntheticProvider()}
    runner = DurableRewriteRunner(rewrite_store, provider_for_channel=providers.__getitem__)
    assert runner.run_next(now=NOW) == "SUCCEEDED"
    assert runner.run_next(now=NOW) == "SUCCEEDED"
    assert runner.run_next(now=NOW) == "IDLE"
    with rewrite_store() as session:
        assert session.scalar(select(func.count()).select_from(RewriteOutputModel)) == 2
        assert set(session.scalars(select(RewriteOutputModel.approval_state))) == {"PENDING"}
        assert set(session.scalars(select(PublicationCandidateModel.state))) == {"AWAITING_REWRITE"}
        assert (
            session.scalar(
                select(func.count())
                .select_from(OutboxEventModel)
                .where(OutboxEventModel.event_type == "rewrite.completed")
            )
            == 2
        )
    assert [providers[key].calls for key in (1, 2)] == [1, 1]


def test_claim_survives_crash_and_expired_owner_cannot_execute_or_complete_it(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    provider = SafeSyntheticProvider()
    runner = DurableRewriteRunner(rewrite_store, provider_for_channel=lambda _: provider)
    abandoned = runner.claim_next(now=NOW)
    other = DurableRewriteRunner(rewrite_store, provider_for_channel=lambda _: provider)
    # A later owner first handles another output; it cannot steal the active lease.
    assert other.run_next(now=NOW + timedelta(seconds=1)) == "SUCCEEDED"
    assert other.claim_next(now=NOW + timedelta(seconds=1)) is None
    recovered = other.claim_next(now=NOW + timedelta(seconds=61))
    assert recovered.job_id == abandoned.job_id and recovered.token != abandoned.token
    assert runner.execute_claim(abandoned, now=NOW + timedelta(seconds=61)) == "STALE_CLAIM"
    assert other.execute_claim(recovered, now=NOW + timedelta(seconds=61)) == "SUCCEEDED"
    assert provider.calls == 2


def test_stale_editorial_reject_blocks_claimed_job_without_constructing_provider(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    def forbidden_factory(_):
        raise AssertionError("Rejected material reached provider configuration")

    runner = DurableRewriteRunner(rewrite_store, provider_for_channel=forbidden_factory)
    claimed = runner.claim_next(now=NOW)
    with rewrite_store() as session:
        decision = session.scalar(select(EditorialDecisionModel))
        decision.status, decision.rewrite_allowed = "REJECT", False
        session.commit()
    assert runner.execute_claim(claimed, now=NOW) == "BLOCKED_EDITORIAL"
    assert runner.run_next(now=NOW) == "BLOCKED_EDITORIAL"
    with rewrite_store() as session:
        assert session.scalar(select(func.count()).select_from(RewriteOutputModel)) == 0


def test_retry_is_durable_delayed_bounded_and_does_not_persist_provider_errors(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    provider = SafeSyntheticProvider(unavailable=True)
    runner = DurableRewriteRunner(
        rewrite_store, provider_for_channel=lambda _: provider, max_attempts=2
    )
    assert runner.run_next(now=NOW) == "RETRY"
    assert runner.run_next(now=NOW) == "RETRY"
    assert runner.run_next(now=NOW) == "IDLE"
    assert runner.run_next(now=NOW + timedelta(seconds=31)) == "FAILED"
    with rewrite_store() as session:
        first = session.get(RewriteJobModel, 1)
        assert first.attempts == 2
        assert first.last_error_code == "PROVIDER_UNAVAILABLE"
    assert provider.calls == 3


def test_changed_facts_are_terminal_and_cannot_create_a_review_draft(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    provider = SafeSyntheticProvider(result="Открыто 20 объектов")
    runner = DurableRewriteRunner(rewrite_store, provider_for_channel=lambda _: provider)
    assert runner.run_next(now=NOW) == "FAILED_FACTS"
    with rewrite_store() as session:
        assert session.scalar(select(func.count()).select_from(RewriteOutputModel)) == 0
        assert session.get(RewriteJobModel, 1).last_error_code == "FACT_PRESERVATION_BLOCKED"
    assert provider.calls == 1


def test_superseded_source_revision_is_not_rewritten(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    with rewrite_store() as session:
        DurableIngestionWorkflow(
            session, technical_filter=MappingTechnicalFilter(mapping_id="1", output_channel_id=1)
        ).ingest(
            TelegramMessage("synthetic", "@donor", 1, "Открыто 11 объектов", is_edit=True),
            observed_at=NOW,
        )
    provider = SafeSyntheticProvider()
    runner = DurableRewriteRunner(rewrite_store, provider_for_channel=lambda _: provider)
    assert runner.run_next(now=NOW) == "SUPERSEDED"
    assert provider.calls == 0


def test_naive_clock_is_rejected_before_claiming(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    runner = DurableRewriteRunner(
        rewrite_store, provider_for_channel=lambda _: SafeSyntheticProvider()
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        runner.run_next(now=NOW.replace(tzinfo=None))


def test_attempt_budget_is_persisted_before_external_operation_even_if_worker_crashes(
    rewrite_store,
):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    runner = DurableRewriteRunner(
        rewrite_store, provider_for_channel=lambda _: SafeSyntheticProvider()
    )
    claimed = runner.claim_next(now=NOW)
    with rewrite_store() as session:
        assert session.get(RewriteJobModel, claimed.job_id).attempts == 1


def test_result_after_expired_lease_cannot_create_a_draft(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    provider = SafeSyntheticProvider()
    runner = DurableRewriteRunner(
        rewrite_store,
        provider_for_channel=lambda _: provider,
        clock=lambda: NOW + timedelta(seconds=61),
    )
    assert runner.run_next(now=NOW) == "STALE_CLAIM"
    with rewrite_store() as session:
        assert session.scalar(select(func.count()).select_from(RewriteOutputModel)) == 0
    assert provider.calls == 1


def test_repeated_crashed_claims_exhaust_the_budget_without_more_provider_calls(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    provider = SafeSyntheticProvider()
    runner = DurableRewriteRunner(
        rewrite_store, provider_for_channel=lambda _: provider, max_attempts=1
    )
    abandoned = runner.claim_next(now=NOW)
    recovered = runner.claim_next(now=NOW + timedelta(seconds=61))
    assert recovered.job_id == abandoned.job_id
    assert runner.execute_claim(recovered, now=NOW + timedelta(seconds=61)) == "FAILED"
    assert provider.calls == 0


def test_late_provider_error_cannot_transition_an_expired_claim(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    provider = SafeSyntheticProvider(unavailable=True)
    runner = DurableRewriteRunner(
        rewrite_store,
        provider_for_channel=lambda _: provider,
        clock=lambda: NOW + timedelta(seconds=61),
    )
    assert runner.run_next(now=NOW) == "STALE_CLAIM"
    with rewrite_store() as session:
        assert session.get(RewriteJobModel, 1).state == "RUNNING"


def test_forged_pass_with_hostile_protected_entity_cannot_construct_provider(rewrite_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    def forbidden_factory(_):
        raise AssertionError("Inconsistent editorial policy reached provider configuration")

    with rewrite_store() as session:
        policy = session.scalar(select(EditorialDecisionModel))
        policy.protected_entities = "Protected"
        policy.sentiment, policy.framing = "negative", "hostile"
        session.commit()
    runner = DurableRewriteRunner(rewrite_store, provider_for_channel=forbidden_factory)
    assert runner.run_next(now=NOW) == "BLOCKED_EDITORIAL"


def test_forged_pass_is_not_approvable_or_schedulable_and_cannot_dispatch_new_work(rewrite_store):
    from datetime import date

    from newsflow.domain.editorial import EditorialGate
    from newsflow.domain.sql_editorial import DurableEditorialService
    from newsflow.services.publication_planning import PublicationPlanningService
    from newsflow.services.rewrite_outputs import RewriteOutputService

    with rewrite_store() as session:
        job = session.get(RewriteJobModel, 1)
        job.state = "SUCCEEDED"
        session.commit()
        draft = RewriteOutputService(session).record_succeeded_output(job.id, "Открыто 10 объектов")
        policy = session.scalar(select(EditorialDecisionModel))
        policy.protected_entities = "Protected"
        policy.sentiment, policy.framing = "negative", "hostile"
        session.commit()
        assert RewriteOutputService(session).list_outputs(1)[0]["approve_allowed"] is False
        with pytest.raises(PermissionError, match="EDITORIAL"):
            RewriteOutputService(session).approve(draft["id"], activate_candidate=True)
        candidate = session.get(PublicationCandidateModel, 1)
        candidate.state = "READY"  # Deliberately malformed legacy task; planner must recheck.
        session.commit()
        planner = PublicationPlanningService(session)
        plan = planner.configure_plan(1, "AUTOMATIC", 1, (540,), "UTC")
        assert planner.plan_day(plan["id"], date(2030, 1, 1)) == []
        policy = session.scalar(select(EditorialDecisionModel))
        assert (
            DurableEditorialService(session, EditorialGate()).create_rewrite_job(
                policy, output_channel_id=1
            )
            is None
        )
