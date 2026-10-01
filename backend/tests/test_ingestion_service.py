from datetime import UTC, datetime

from newsflow.domain.editorial import EditorialGate
from newsflow.domain.ingestion import IngestionService, InMemoryIngestionRepository
from newsflow.providers.telegram import TelegramMessage


def test_duplicate_provider_delivery_creates_one_post_and_one_outbox_event() -> None:
    repository = InMemoryIngestionRepository()
    service = IngestionService(repository)
    event = TelegramMessage("account-1", "@donor", 17, "source text")

    first = service.ingest(event, observed_at=datetime.now(UTC))
    second = service.ingest(event, observed_at=datetime.now(UTC))

    assert first.created is True
    assert second.created is False
    assert len(repository.posts) == 1
    assert len(repository.outbox_events) == 1


def test_edit_creates_new_revision_without_overwriting_original() -> None:
    repository = InMemoryIngestionRepository()
    service = IngestionService(repository)
    service.ingest(TelegramMessage("account-1", "@donor", 17, "original"), datetime.now(UTC))

    result = service.ingest(
        TelegramMessage("account-1", "@donor", 17, "corrected", is_edit=True), datetime.now(UTC)
    )

    assert result.created is False
    assert [revision.source_text for revision in repository.posts[0].revisions] == ["original", "corrected"]


def test_video_and_empty_content_are_rejected_before_persisting_or_outbox() -> None:
    repository = InMemoryIngestionRepository()
    service = IngestionService(repository, allowed_media_types={"text", "photo"})

    video = service.ingest(
        TelegramMessage("account-1", "@donor", 18, "video", media_type="video"), datetime.now(UTC)
    )
    empty = service.ingest(TelegramMessage("account-1", "@donor", 19, "   "), datetime.now(UTC))

    assert video.status == "REJECTED_TECHNICAL"
    assert empty.status == "REJECTED_TECHNICAL"
    assert repository.posts == []
    assert repository.outbox_events == []


def test_editorial_reject_creates_no_rewrite_outbox_event() -> None:
    repository = InMemoryIngestionRepository()
    service = IngestionService(repository, editorial_gate=EditorialGate())

    result = service.ingest(
        TelegramMessage("account-1", "@donor", 20, "hostile claim"),
        datetime.now(UTC),
        protected_entities=["Belarus"],
        sentiment="negative",
        framing="hostile",
    )

    assert result.status == "REJECTED_EDITORIAL"
    assert all(event.event_type != "rewrite.requested" for event in repository.outbox_events)


def test_exact_duplicate_skips_editorial_gate() -> None:
    class CountingGate(EditorialGate):
        def __init__(self) -> None:
            self.calls = 0

        def evaluate(self, **kwargs):
            self.calls += 1
            return super().evaluate(**kwargs)

    repository = InMemoryIngestionRepository()
    gate = CountingGate()
    service = IngestionService(repository, editorial_gate=gate)
    event = TelegramMessage("account-1", "@donor", 21, "source text")

    service.ingest(event, datetime.now(UTC))
    duplicate = service.ingest(event, datetime.now(UTC))

    assert duplicate.status == "INGESTED"
    assert gate.calls == 1
