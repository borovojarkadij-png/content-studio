"""Hidden destinations are source metadata, never extra rewrite prose."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from telethon.tl import types as tltypes
from telethon.tl.types import MessageEntityTextUrl, ReplyInlineMarkup
from test_mapping_fanout_dedup import mapping_store as _mapping_store
from test_persisted_mapping_filters import NOW, queued_source

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    RewriteJobModel,
)
from newsflow.providers.telegram import TelegramMessage, TelethonTelegramProvider
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.mapping_filters import output_technical_allowed
from newsflow.services.moderation_inbox import ModerationInboxReader

mapping_store = _mapping_store


KeyboardButtonRow = getattr(tltypes, "KeyboardInlineButtonRow", tltypes.KeyboardButtonRow)


def KeyboardButtonUrl(label, url):
    legacy = getattr(tltypes, "KeyboardButtonUrl", None)
    if legacy is not None:
        return legacy(label, url)
    return tltypes.KeyboardInlineButton(label, tltypes.InlineButtonTypeUrl(url))


@pytest.fixture
def filter_store(mapping_store):
    url, _mappings = mapping_store
    engine = create_engine(url)
    yield sessionmaker(engine)
    engine.dispose()


@pytest.mark.parametrize("kind", ["entity", "button"])
@pytest.mark.parametrize(
    "destination,reason",
    [
        ("https://youtu.be/abc", "YOUTUBE_LINK"),
        ("https://youtube.com\\watch?v=abc", "INVALID_LINK"),
    ],
)
def test_actual_sdk_hidden_youtube_destination_rejected_without_changing_caption(
    kind, destination, reason
):
    raw = SimpleNamespace(id=1, message="Read more", date=NOW)
    if kind == "entity":
        raw.entities = [MessageEntityTextUrl(offset=0, length=4, url=destination)]
    else:
        raw.reply_markup = ReplyInlineMarkup(
            [KeyboardButtonRow([KeyboardButtonUrl("Read more", destination)])]
        )
    event = TelethonTelegramProvider.normalize_message("1", "-1001234567890", raw)
    assert event.text == "Read more"
    assert event.link_destinations[0].startswith("https://")
    decision = MappingTechnicalFilter("1").evaluate(event)
    assert (decision.accepted, decision.reason_code) == (False, reason)


def test_provider_empty_links_are_observed_not_unknown():
    event = TelethonTelegramProvider.normalize_message(
        "1", "-1001234567890", SimpleNamespace(id=1, message="Plain", entities=None)
    )
    assert event.link_destinations == ()


@pytest.mark.parametrize("metadata", [None, ["https://youtu.be/abc"], ("",), (1,), ("x" * 2049,)])
def test_unknown_or_invalid_hidden_metadata_is_cheap_rejection(metadata):
    event = TelegramMessage("1", "-1001234567890", 1, "Read", link_destinations=metadata)
    assert not MappingTechnicalFilter("1").evaluate(event).accepted


def test_hidden_only_edit_persists_distinct_metadata_and_fences_old_task_after_reopen(filter_store):
    queued_source(filter_store)
    with filter_store.begin() as session:
        caption = session.scalar(select(ContentRevisionModel.source_text))
        event = TelegramMessage(
            "1",
            "-1001234567890",
            1,
            caption,
            is_edit=True,
            source_updated_at=NOW + timedelta(seconds=1),
            link_destinations=("https://youtu.be/abc",),
        )
        # Retain immutable metadata without fabricating a changed caption.
        SqlAlchemyIngestionRepository(session).ingest(event, NOW)
    with filter_store() as session:
        rows = session.scalars(select(ContentRevisionModel).order_by(ContentRevisionModel.id)).all()
        assert rows[-1].source_text == caption
        assert rows[-1].link_destinations == ["https://youtu.be/abc"]
        assert ModerationInboxReader(session).list_items()[0].rewrite_allowed is False


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        ["https://youtu.be/abc"],
        {"url": "https://youtu.be/a"},
        ["https://youtube.com\\watch?v=abc"],
    ],
)
def test_retained_hidden_links_or_unknown_metadata_block_legacy_job(filter_store, metadata):
    queued_source(filter_store)
    with filter_store.begin() as session:
        revision = session.scalar(select(ContentRevisionModel))
        revision.link_destinations = metadata
        job = session.scalar(select(RewriteJobModel))
        assert not output_technical_allowed(session, job.content_key, job.output_channel_id)
        assert ModerationInboxReader(session).list_items()[0].rewrite_allowed is False

    def forbidden(_channel):
        pytest.fail("Hidden link constructed rewrite provider")

    assert (
        DurableRewriteRunner(
            filter_store, provider_for_channel=forbidden, clock=lambda: NOW
        ).run_next(now=NOW)
        == "BLOCKED_TECHNICAL"
    )


def test_hidden_youtube_ingestion_never_classifies_or_creates_rewrite_work(filter_store):
    class NoEditorial:
        def evaluate(self, **_kwargs):
            pytest.fail("Hidden YouTube reached classification")

    with filter_store() as session:
        result = DurableIngestionWorkflow(
            session, editorial_gate=NoEditorial(), configured_mapping_id=1
        ).ingest(
            TelegramMessage(
                "1", "-1001234567890", 1, "Read", link_destinations=("https://youtu.be/a",)
            ),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert (result.status, result.reason_code) == ("REJECTED_TECHNICAL", "YOUTUBE_LINK")
        assert session.scalar(select(RewriteJobModel)) is None
        assert session.scalar(select(EditorialDecisionModel)) is None


def test_explicit_unknown_source_metadata_is_not_defaulted_to_empty_on_insert(filter_store):
    with filter_store.begin() as session:
        SqlAlchemyIngestionRepository(session).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Read", link_destinations=None), NOW
        )
    with filter_store() as session:
        assert session.scalar(select(ContentRevisionModel)).link_destinations is None
        assert (
            session.scalar(
                text("SELECT COUNT(*) FROM incoming_post_revisions WHERE link_destinations IS NULL")
            )
            == 1
        )


def test_mapping_custom_forbidden_domain_also_checks_hidden_destination():
    decision = MappingTechnicalFilter("1", blocked_domains=frozenset({"example.org"})).evaluate(
        TelegramMessage(
            "1", "-1001234567890", 1, "Read", link_destinations=("https://example.org/news",)
        )
    )
    assert (decision.accepted, decision.reason_code) == (False, "FORBIDDEN_LINK")


@pytest.mark.parametrize(
    "metadata",
    [
        {"entities": "corrupt"},
        {"entities": [SimpleNamespace(url="https://youtu.be/abc")]},
        {"entities": [MessageEntityTextUrl(0, 4, "x" * 2049)]},
        {"reply_markup": SimpleNamespace(rows=[])},
        {"reply_markup": ReplyInlineMarkup([KeyboardButtonRow([KeyboardButtonUrl("Read", None)])])},
        {
            "reply_markup": ReplyInlineMarkup(
                [KeyboardButtonRow([KeyboardButtonUrl("Read", "https://youtu.be/abc")])] * 21
            )
        },
    ],
)
def test_unknown_or_unbounded_sdk_link_metadata_never_becomes_empty(metadata):
    event = TelethonTelegramProvider.normalize_message(
        "1", "-1001234567890", SimpleNamespace(id=1, message="Read", **metadata)
    )
    assert event.link_destinations is None
    assert MappingTechnicalFilter("1").evaluate(event).reason_code == "SOURCE_LINKS_UNKNOWN"
