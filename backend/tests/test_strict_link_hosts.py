"""Equivalent or ambiguous destinations cannot evade the cheap ingress gate."""

import pytest
from sqlalchemy import select
from test_persisted_mapping_filters import NOW, configure, queued_source
from test_persisted_mapping_filters import filter_store as _filter_store

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    OutboxEventModel,
    RewriteJobModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner

filter_store = _filter_store

DESTINATIONS = [
    ("https://%65xample.org/news", "FORBIDDEN_LINK"),
    ("https://news.example%2eorg/news", "FORBIDDEN_LINK"),
    ("//example.org/news", "FORBIDDEN_LINK"),
    ("//news.%65xample.org/news", "FORBIDDEN_LINK"),
    ("https://%79outube%2ecom/watch", "YOUTUBE_LINK"),
    ("//m.youtube.com/watch", "YOUTUBE_LINK"),
    ("https://example.org%2f.evil.test/news", "INVALID_LINK"),
    ("https://example.org%5c.evil.test/news", "INVALID_LINK"),
    ("https://example.org%40evil.test/news", "INVALID_LINK"),
    ("https://example.org%00.evil.test/news", "INVALID_LINK"),
    ("https://example.org%0a.evil.test/news", "INVALID_LINK"),
    ("https://%2565xample.org/news", "INVALID_LINK"),
    ("https://example%GG.org/news", "INVALID_LINK"),
    ("https://example.org\\@evil.test/news", "INVALID_LINK"),
]


@pytest.mark.parametrize("hidden", [False, True])
@pytest.mark.parametrize("destination,reason", DESTINATIONS)
def test_strict_hosts_precede_classifier_jobs_and_provider(
    filter_store, hidden, destination, reason
):
    configure(filter_store, blocked_domains=["example.org"])

    class NoClassification:
        def evaluate(self, **kwargs):
            pytest.fail("Excluded link reached classification")

    event = TelegramMessage(
        "1",
        "-1001234567890",
        1,
        "Read" if hidden else "Read " + destination,
        link_destinations=(destination,) if hidden else (),
    )
    with filter_store() as session:
        result = DurableIngestionWorkflow(
            session, configured_mapping_id=1, editorial_gate=NoClassification()
        ).ingest(event, observed_at=NOW, sentiment="neutral", framing="neutral")
        assert (result.status, result.reason_code) == ("REJECTED_TECHNICAL", reason)
        assert session.scalar(select(EditorialDecisionModel)) is None
        assert session.scalar(select(RewriteJobModel)) is None
        assert (
            session.scalar(
                select(OutboxEventModel).where(OutboxEventModel.event_type == "rewrite.requested")
            )
            is None
        )
    assert event.link_destinations == ((destination,) if hidden else ())

    def forbidden(_channel):
        pytest.fail("Excluded link constructed provider")

    assert (
        DurableRewriteRunner(
            filter_store, provider_for_channel=forbidden, clock=lambda: NOW
        ).run_next(now=NOW)
        == "IDLE"
    )


@pytest.mark.parametrize("destination", ["not a destination", "ftp://example.org/a", "https:///a"])
def test_unknown_hidden_destination_fails_closed(destination):
    event = TelegramMessage("1", "1", 1, "Read", link_destinations=(destination,))
    assert MappingTechnicalFilter("1").evaluate(event).accepted is False


@pytest.mark.parametrize(
    "destination", ["https://example.org.evil.test/a", "https://safe.test/a%2fb"]
)
def test_valid_unblocked_destination_remains_eligible(destination):
    event = TelegramMessage("1", "1", 1, "Read", link_destinations=(destination,))
    assert (
        MappingTechnicalFilter("1", blocked_domains=frozenset({"example.org"}))
        .evaluate(event)
        .accepted
    )


@pytest.mark.parametrize(
    "destination",
    ["https://%65xample.org/a", "//example.org/a", "https://example.org%2f.evil.test/a"],
)
def test_excluded_edit_retains_raw_source_observation_without_new_work(filter_store, destination):
    queued_source(filter_store)
    configure(filter_store, blocked_domains=["example.org"])
    with filter_store() as session:
        caption = session.scalar(select(ContentRevisionModel.source_text))
        initial_jobs = list(session.scalars(select(RewriteJobModel.id)))
    with filter_store() as session:
        result = DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
            TelegramMessage(
                "1", "-1001234567890", 1, caption, is_edit=True, link_destinations=(destination,)
            ),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        session.commit()
        assert result.status == "REJECTED_TECHNICAL"
    with filter_store() as session:
        latest = session.scalar(
            select(ContentRevisionModel).order_by(ContentRevisionModel.id.desc())
        )
        assert latest.source_text == caption
        assert latest.link_destinations == [destination]
        assert list(session.scalars(select(RewriteJobModel.id))) == initial_jobs
