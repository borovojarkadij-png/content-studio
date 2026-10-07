from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import Base, EditorialDecisionModel, RewriteJobModel
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.telegram_configuration import TelegramConfigurationService

NOW = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture
def filter_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'filters.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as session:
        service = TelegramConfigurationService(session)
        account = service.create_account("Synthetic", 1001)
        donor = service.create_donor(account["id"], -1001234567890, "Donor")
        output = service.create_output(account["id"], -1009876543210, "Output")
        service.create_mapping(donor["id"], output["id"], 100, 100)
    yield factory
    engine.dispose()


def configure(factory, **values):
    with factory() as session:
        return TelegramConfigurationService(session).configure_mapping_filters(
            1,
            **{
                "allowed_media_types": ["text", "photo"],
                "blocked_domains": [],
                "ad_markers": [],
                **values,
            },
        )


def test_mapping_filter_configuration_is_normalized_and_durable(filter_store):
    result = configure(
        filter_store,
        blocked_domains=["WWW.Example.ORG", "пример.рф"],
        ad_markers=["Спонсорский пост"],
    )
    assert result["blocked_domains"] == ["example.org", "xn--e1afmkfd.xn--p1ai"]
    with filter_store() as session:
        saved = TelegramConfigurationService(session).mapping_filters(1)
        assert saved == result
    assert "#реклама" in saved["effective_ad_markers"]


def test_persisted_forbidden_links_reject_before_editorial_and_rewrite(filter_store):
    configure(filter_store, blocked_domains=["example.org"])
    with filter_store() as session:
        result = DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Read https://news.example.org/deal"),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert (result.status, result.reason_code) == ("REJECTED_TECHNICAL", "FORBIDDEN_LINK")
        assert session.scalar(select(EditorialDecisionModel)) is None
        assert session.scalar(select(RewriteJobModel)) is None


@pytest.mark.parametrize(
    "domain",
    [
        "https://example.org",
        "*.example.org",
        "example.org/path",
        "example.org:443",
        "",
        "127.0.0.1",
    ],
)
def test_invalid_domain_policy_is_not_saved(filter_store, domain):
    with pytest.raises(ValueError):
        configure(filter_store, blocked_domains=[domain])


def test_stale_claim_rechecks_new_filters_before_constructing_rewrite_provider(filter_store):
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    with filter_store() as session:
        result = DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Read https://example.org/source"),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert result.status == "REWRITE_QUEUED"

    def forbidden(_):
        raise AssertionError("Changed technical policy reached AI")

    runner = DurableRewriteRunner(filter_store, provider_for_channel=forbidden, clock=lambda: NOW)
    claim = runner.claim_next(now=NOW)
    configure(filter_store, blocked_domains=["example.org"])
    assert runner.execute_claim(claim, now=NOW) == "BLOCKED_TECHNICAL"


def queued_source(factory):
    with factory() as session:
        return DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Read https://example.org/source"),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )


def test_policy_change_during_ai_cannot_record_a_draft(filter_store):
    from newsflow.persistence.models import RewriteOutputModel
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

    queued_source(filter_store)

    class Provider:
        def rewrite(self, text):
            configure(filter_store, blocked_domains=["example.org"])
            return text

    runner = DurableRewriteRunner(
        filter_store, provider_for_channel=lambda _: Provider(), clock=lambda: NOW
    )
    assert runner.run_next(now=NOW) == "BLOCKED_TECHNICAL"
    with filter_store() as session:
        assert session.scalar(select(RewriteOutputModel)) is None


def test_manual_review_cannot_override_current_mapping_filters(filter_store):
    from newsflow.persistence.models import RewriteOutputModel
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
    from newsflow.services.rewrite_outputs import RewriteOutputBlocked, RewriteOutputService

    queued_source(filter_store)

    class Provider:
        def rewrite(self, text):
            return text

    runner = DurableRewriteRunner(
        filter_store, provider_for_channel=lambda _: Provider(), clock=lambda: NOW
    )
    assert runner.run_next(now=NOW) == "SUCCEEDED"
    configure(filter_store, blocked_domains=["example.org"])
    with filter_store() as session:
        with pytest.raises(RewriteOutputBlocked, match="TECHNICAL"):
            RewriteOutputService(session).approve(1, activate_candidate=True)
        assert session.get(RewriteOutputModel, 1).approval_state == "PENDING"


def test_new_policy_blocks_existing_calendar_slot_without_erasing_history(filter_store):
    from newsflow.persistence.models import PlannedPublicationModel
    from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
    from newsflow.services.publication_planning import PublicationPlanningService
    from newsflow.services.rewrite_outputs import RewriteOutputService

    queued_source(filter_store)

    class Provider:
        def rewrite(self, text):
            return text

    assert (
        DurableRewriteRunner(
            filter_store, provider_for_channel=lambda _: Provider(), clock=lambda: NOW
        ).run_next(now=NOW)
        == "SUCCEEDED"
    )
    with filter_store() as session:
        RewriteOutputService(session).approve(1, activate_candidate=True)
        planning = PublicationPlanningService(session)
        plan = planning.configure_plan(
            1, mode="AUTOMATIC", daily_limit=1, slot_minutes=(600,), timezone="UTC"
        )
        assert len(planning.plan_day(plan["id"], NOW.date())) == 1
    configure(filter_store, blocked_domains=["example.org"])
    with filter_store() as session:
        assert PublicationPlanningService(session).plan_day(plan["id"], NOW.date()) == []
        assert session.get(PlannedPublicationModel, 1).state == "BLOCKED_TECHNICAL"


@pytest.mark.parametrize("link", ["https://пример.рф/news", "https://example.org./news"])
def test_unicode_and_trailing_dot_domains_do_not_bypass_policy(filter_store, link):
    configure(filter_store, blocked_domains=["пример.рф", "example.org"])
    with filter_store() as session:
        result = DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Read " + link),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert result.status == "REJECTED_TECHNICAL"
        assert session.scalar(select(EditorialDecisionModel)) is None
        assert session.scalar(select(RewriteJobModel)) is None


def test_direct_succeeded_draft_recording_cannot_bypass_current_filters(filter_store):
    from newsflow.services.rewrite_outputs import RewriteOutputBlocked, RewriteOutputService

    queued_source(filter_store)
    with filter_store.begin() as session:
        session.get(RewriteJobModel, 1).state = "SUCCEEDED"
    configure(filter_store, blocked_domains=["example.org"])
    with filter_store() as session, pytest.raises(RewriteOutputBlocked, match="TECHNICAL"):
        RewriteOutputService(session).record_succeeded_output(1, "Read https://example.org/source")
