"""Durable SQLAlchemy ingestion repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.domain.ingestion import IngestionResult
from newsflow.persistence.models import ContentRevisionModel, IncomingPostModel, OutboxEventModel
from newsflow.providers.telegram import TelegramMessage


class SqlAlchemyIngestionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ingest(self, event: TelegramMessage, observed_at: datetime) -> IngestionResult:
        del observed_at
        post = self._find_post(event)
        source_key = f"{event.account_id}:{event.donor_identifier}:{event.message_id}"
        if post is None:
            post = IncomingPostModel(
                telegram_account_id=event.account_id,
                donor_channel_id=event.donor_identifier,
                telegram_message_id=event.message_id,
                state="RECEIVED",
            )
            self._session.add(post)
            self._session.flush()
            self._session.add(
                ContentRevisionModel(
                    incoming_post_id=post.id, revision_number=1, source_text=event.text
                )
            )
            self._session.add(
                OutboxEventModel(
                    event_type="incoming_post.created",
                    aggregate_key=source_key,
                    idempotency_key=f"incoming_post.created:{source_key}",
                )
            )
            return IngestionResult(True, source_key)

        latest_revision = self._session.scalar(
            select(ContentRevisionModel)
            .where(ContentRevisionModel.incoming_post_id == post.id)
            .order_by(ContentRevisionModel.revision_number.desc())
        )
        if (
            event.is_edit
            and latest_revision is not None
            and latest_revision.source_text != event.text
        ):
            next_number = latest_revision.revision_number + 1
            self._session.add(
                ContentRevisionModel(
                    incoming_post_id=post.id,
                    revision_number=next_number,
                    source_text=event.text,
                )
            )
            self._session.add(
                OutboxEventModel(
                    event_type="content_revision.created",
                    aggregate_key=source_key,
                    idempotency_key=f"content_revision.created:{source_key}:{next_number}",
                )
            )
        return IngestionResult(False, source_key)

    def candidate_revision_number(self, event: TelegramMessage) -> int | None:
        """Return the revision that would be persisted, or ``None`` for a duplicate."""
        post = self._find_post(event)
        if post is None:
            return 1
        latest_revision = self._latest_revision(post.id)
        if (
            latest_revision is None
            or not event.is_edit
            or latest_revision.source_text == event.text
        ):
            return None
        return latest_revision.revision_number + 1

    def current_revision_number(self, event: TelegramMessage) -> int | None:
        """Return the revision only for an exact delivery of the latest source text.

        A stale original delivery after a later Telegram edit must not fan out
        the newer revision to a mapping whose deterministic filter saw the old
        payload.
        """
        post = self._find_post(event)
        if post is None:
            return None
        latest_revision = self._latest_revision(post.id)
        if latest_revision is None or latest_revision.source_text != event.text:
            return None
        return latest_revision.revision_number

    def revision_texts(self, account_id: str, donor_channel_id: str, message_id: int) -> list[str]:
        post = self._session.scalar(
            select(IncomingPostModel).where(
                IncomingPostModel.telegram_account_id == account_id,
                IncomingPostModel.donor_channel_id == donor_channel_id,
                IncomingPostModel.telegram_message_id == message_id,
            )
        )
        if post is None:
            return []
        return list(
            self._session.scalars(
                select(ContentRevisionModel.source_text)
                .where(ContentRevisionModel.incoming_post_id == post.id)
                .order_by(ContentRevisionModel.revision_number)
            )
        )

    def set_state(self, event: TelegramMessage, state: str) -> None:
        post = self._find_post(event)
        if post is None:
            raise LookupError("Source observation has not been persisted")
        post.state = state

    def _find_post(self, event: TelegramMessage) -> IncomingPostModel | None:
        return self._session.scalar(
            select(IncomingPostModel)
            .where(
                IncomingPostModel.telegram_account_id == event.account_id,
                IncomingPostModel.donor_channel_id == event.donor_identifier,
                IncomingPostModel.telegram_message_id == event.message_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def _latest_revision(self, incoming_post_id: int) -> ContentRevisionModel | None:
        return self._session.scalar(
            select(ContentRevisionModel)
            .where(ContentRevisionModel.incoming_post_id == incoming_post_id)
            .order_by(ContentRevisionModel.revision_number.desc())
        )
