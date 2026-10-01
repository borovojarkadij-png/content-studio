from dataclasses import dataclass

from newsflow.domain import pipeline
from newsflow.domain.editorial import EditorialGate
from newsflow.services.rewrite import RewriteService


@dataclass
class RecordingProvider:
    calls: int = 0

    def rewrite(self, text: str) -> str:
        self.calls += 1
        return text


def test_technical_rejection_skips_editorial_and_rewrite() -> None:
    provider = RecordingProvider()
    runner = pipeline.IngestionPipeline(EditorialGate(), RewriteService(provider))

    result = runner.process(
        text="A video post",
        content_type="video",
        protected_entities=["Russia"],
        sentiment="negative",
        framing="hostile",
    )

    assert result.status == "REJECTED_TECHNICAL"
    assert provider.calls == 0


def test_editorial_rejection_never_creates_a_rewrite_call() -> None:
    provider = RecordingProvider()
    runner = pipeline.IngestionPipeline(EditorialGate(), RewriteService(provider))

    result = runner.process(
        text="Hostile claim",
        content_type="text",
        protected_entities=["Belarus"],
        sentiment="negative",
        framing="hostile",
    )

    assert result.status == "REJECTED_EDITORIAL"
    assert result.rewrite_job_created is False
    assert provider.calls == 0


def test_exact_duplicate_skips_editorial_and_rewrite() -> None:
    provider = RecordingProvider()
    runner = pipeline.IngestionPipeline(EditorialGate(), RewriteService(provider))

    first = runner.process(
        text="Unique permitted news",
        content_type="text",
        protected_entities=[],
        sentiment="neutral",
        framing="neutral",
    )
    duplicate = runner.process(
        text="Unique permitted news",
        content_type="text",
        protected_entities=[],
        sentiment="neutral",
        framing="neutral",
    )

    assert first.status == "REWRITE_DISPATCHED"
    assert duplicate.status == "REJECTED_DUPLICATE"
    assert provider.calls == 1
