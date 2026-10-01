"""Idempotent provider-event ingestion with revision history and outbox records."""

from dataclasses import dataclass, field
from datetime import datetime

from newsflow.domain.editorial import EditorialGate, EditorialStatus
from newsflow.domain.telegram import ContentRevision, SourceIdentity
from newsflow.providers.telegram import TelegramMessage


@dataclass(slots=True)
class IncomingPost:
    identity: SourceIdentity
    revisions: list[ContentRevision]


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    event_type: str
    source_key: str


@dataclass(frozen=True, slots=True)
class IngestionResult:
    created: bool
    source_key: str
    status: str = "INGESTED"
    reason_code: str | None = None


@dataclass(slots=True)
class InMemoryIngestionRepository:
    posts: list[IncomingPost] = field(default_factory=list)
    outbox_events: list[OutboxEvent] = field(default_factory=list)

    def find(self, source_key: str) -> IncomingPost | None:
        return next((post for post in self.posts if post.identity.source_key == source_key), None)


class IngestionService:
    def __init__(
        self,
        repository: InMemoryIngestionRepository,
        allowed_media_types: set[str] | None = None,
        editorial_gate: EditorialGate | None = None,
    ) -> None:
        self._repository = repository
        self._allowed_media_types = allowed_media_types or {"text", "photo"}
        self._editorial_gate = editorial_gate

    def ingest(
        self,
        event: TelegramMessage,
        observed_at: datetime,
        protected_entities: list[str] | None = None,
        sentiment: str = "neutral",
        framing: str = "neutral",
    ) -> IngestionResult:
        identity = SourceIdentity(event.account_id, event.donor_identifier, event.message_id)
        if event.media_type not in self._allowed_media_types or not event.text.strip():
            return IngestionResult(False, identity.source_key, "REJECTED_TECHNICAL")
        post = self._repository.find(identity.source_key)
        if post is not None and (not event.is_edit or event.text == post.revisions[-1].source_text):
            return IngestionResult(False, identity.source_key)
        if self._editorial_gate is not None:
            decision = self._editorial_gate.evaluate(
                text=event.text,
                protected_entities=protected_entities or [],
                sentiment=sentiment,
                framing=framing,
            )
            if decision.status is EditorialStatus.REJECT:
                return IngestionResult(False, identity.source_key, "REJECTED_EDITORIAL")
        if post is None:
            revision = ContentRevision.new(identity, event.text, observed_at)
            self._repository.posts.append(IncomingPost(identity, [revision]))
            self._repository.outbox_events.append(OutboxEvent("incoming_post.created", identity.source_key))
            return IngestionResult(True, identity.source_key)
        if event.is_edit and event.text != post.revisions[-1].source_text:
            post.revisions.append(post.revisions[-1].next_revision(event.text, observed_at))
            self._repository.outbox_events.append(OutboxEvent("content_revision.created", identity.source_key))
        return IngestionResult(False, identity.source_key)
