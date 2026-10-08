"""User policy: video is filtered/manual only; YouTube never reaches rewrite."""

import pytest
from sqlalchemy import func, select
from test_persisted_mapping_filters import NOW, configure, queued_source
from test_persisted_mapping_filters import filter_store as _filter_store

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.domain.technical_filters import MappingTechnicalFilter
from newsflow.persistence.models import (
    ContentRevisionModel,
    EditorialDecisionModel,
    IncomingPostModel,
    MappingContentFingerprintModel,
    OutboxEventModel,
    PublicationCandidateModel,
    RewriteJobModel,
)
from newsflow.providers.telegram import TelegramMessage
from newsflow.services.durable_rewrite_runner import DurableRewriteRunner
from newsflow.services.mapping_filters import candidate_technical_allowed, output_technical_allowed
from newsflow.services.moderation_inbox import ModerationInboxReader

filter_store = _filter_store


@pytest.mark.parametrize(
    "link",
    [
        "https://youtube.com/watch?v=abc",
        "https://m.youtube.com/shorts/abc",
        "https://www.youtube.com./watch?v=abc",
        "https://youtu.be/abc",
        "https://www.youtube-nocookie.com/embed/abc",
        "HTTP://YOUTUBE.COM/watch?v=abc",
        "youtu.be/abc",
        "www.youtube.com/watch?v=abc",
        "//youtube.com/watch?v=abc",
        "https://%79outube.com/watch?v=abc",
        "https://ＹｏｕＴｕｂｅ.com/watch?v=abc",
        "https://youtube.com, then read",
        "youtube.com; then read",
        'https://youtube.com!"',
        "https://youtube.com\u3002",
        "https://youtube.com\uff0e",
        "https://youtube.com\uff61",
    ],
)
def test_youtube_is_mandatory_cheap_rejection_even_without_custom_domain_filters(
    filter_store, link
):
    class NoEditorial:
        def evaluate(self, **_kwargs):
            pytest.fail("YouTube link reached an editorial/LLM classification")

    with filter_store() as session:
        result = DurableIngestionWorkflow(
            session, editorial_gate=NoEditorial(), configured_mapping_id=1
        ).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Read " + link),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert (result.status, result.reason_code) == ("REJECTED_TECHNICAL", "YOUTUBE_LINK")
        for model in (
            EditorialDecisionModel,
            RewriteJobModel,
            MappingContentFingerprintModel,
            OutboxEventModel,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize(
    "text",
    [
        "Read https://notyoutube.com/news",
        "Read https://youtube.com.example.org/news",
        "Read https://example.org/youtube.com/watch",
        "Read https://youtube.com@example.org/news",
        "Read https://example.org/?next=youtube.com/watch",
        "Read about YouTube today",
    ],
)
def test_non_youtube_hosts_paths_and_plain_mentions_are_not_falsely_rejected(text):
    assert (
        MappingTechnicalFilter("1")
        .evaluate(TelegramMessage("1", "-1001234567890", 1, text))
        .accepted
    )


def test_default_mapping_discards_video_without_any_editorial_or_rewrite_work(filter_store):
    with filter_store() as session:
        result = DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Video caption", media_type="video"),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert (result.status, result.reason_code) == ("REJECTED_TECHNICAL", "UNSUPPORTED_MEDIA")
        assert session.scalar(select(RewriteJobModel)) is None
        assert session.scalar(select(EditorialDecisionModel)) is None


@pytest.mark.parametrize("caption", ["Video caption", ""])
def test_explicitly_included_video_is_retained_for_manual_review_never_rewrite(
    filter_store, caption
):
    configure(filter_store, allowed_media_types=["text", "photo", "video"])
    with filter_store() as session:
        for _ in range(2):
            result = DurableIngestionWorkflow(session, configured_mapping_id=1).ingest(
                TelegramMessage("1", "-1001234567890", 1, caption, media_type="video"),
                observed_at=NOW,
                sentiment="neutral",
                framing="neutral",
            )
            assert (result.status, result.reason_code) == (
                "MANUAL_REVIEW",
                "VIDEO_MANUAL_REVIEW_REQUIRED",
            )
        assert session.scalar(select(func.count()).select_from(IncomingPostModel)) == 1
        item = ModerationInboxReader(session).list_items()[0]
        assert item.state == "MANUAL_REVIEW" and item.rewrite_allowed is False
        assert item.editorial_status is None  # Technical hold, not a fabricated editorial verdict.
        for model in (
            EditorialDecisionModel,
            RewriteJobModel,
            MappingContentFingerprintModel,
        ):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        # Retained history has its normal source-created event, not rewrite work.
        assert session.scalars(select(OutboxEventModel.event_type)).all() == [
            "incoming_post.created"
        ]


@pytest.mark.parametrize("content", ["video", "youtube", "punctuation", "malformed", "unicode_dot"])
@pytest.mark.parametrize("candidate_kind", ["mapped", "legacy", "missing"])
def test_retained_old_task_cannot_bypass_mandatory_exclusions(
    filter_store, content, candidate_kind
):
    queued_source(filter_store)
    configure(filter_store, allowed_media_types=["text", "photo", "video"])
    with filter_store.begin() as session:
        revision = session.scalar(select(ContentRevisionModel))
        if content == "video":
            revision.media_type = "video"
        elif content == "punctuation":
            revision.source_text = "Read https://youtube.com, then stop"
        elif content == "malformed":
            revision.source_text = "Read https://[malformed"
        elif content == "unicode_dot":
            revision.source_text = "Read https://youtube.com\u3002"
        else:
            revision.source_text = "Read https://youtu.be/abc"
        candidate = session.scalar(select(PublicationCandidateModel))
        if candidate_kind == "legacy":
            candidate.mapping_id = None
        elif candidate_kind == "missing":
            session.delete(candidate)
        session.flush()
        job = session.scalar(select(RewriteJobModel))
        assert ModerationInboxReader(session).list_items()[0].rewrite_allowed is False
        assert not output_technical_allowed(session, job.content_key, job.output_channel_id)
        if candidate_kind != "missing":
            assert not candidate_technical_allowed(session, candidate)

    def forbidden(_channel):
        pytest.fail("Video/YouTube old task constructed an AI provider")

    expected = "SUPERSEDED" if candidate_kind == "missing" else "BLOCKED_TECHNICAL"
    assert (
        DurableRewriteRunner(
            filter_store, provider_for_channel=forbidden, clock=lambda: NOW
        ).run_next(now=NOW)
        == expected
    )


@pytest.mark.parametrize("link", ["https://[malformed", "https://a..com", "https://\uff0f.com"])
def test_malformed_visible_url_is_fixed_cheap_rejection_without_classifier(filter_store, link):
    class NoEditorial:
        def evaluate(self, **_kwargs):
            pytest.fail("Malformed URL reached classification")

    with filter_store() as session:
        result = DurableIngestionWorkflow(
            session, editorial_gate=NoEditorial(), configured_mapping_id=1
        ).ingest(
            TelegramMessage("1", "-1001234567890", 1, "Read " + link),
            observed_at=NOW,
            sentiment="neutral",
            framing="neutral",
        )
        assert (result.status, result.reason_code) == ("REJECTED_TECHNICAL", "INVALID_LINK")
        assert session.scalar(select(RewriteJobModel)) is None
        assert session.scalar(select(EditorialDecisionModel)) is None
