from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import (
    Base,
    ContentRevisionModel,
    IncomingPostModel,
    OutboxEventModel,
)


def test_incoming_post_identity_is_unique_and_revision_history_is_append_only() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        post = IncomingPostModel(
            telegram_account_id="account-a",
            donor_channel_id="channel-a",
            telegram_message_id=42,
            state="RECEIVED",
        )
        session.add(post)
        session.flush()
        session.add_all(
            [
                ContentRevisionModel(incoming_post_id=post.id, revision_number=1, source_text="original"),
                OutboxEventModel(
                    event_type="incoming_post.created",
                    aggregate_key="account-a:channel-a:42",
                    idempotency_key="incoming_post.created:account-a:channel-a:42",
                ),
            ]
        )
        session.commit()

        session.add(ContentRevisionModel(incoming_post_id=post.id, revision_number=2, source_text="edited"))
        session.commit()

        revisions = session.scalars(
            select(ContentRevisionModel).order_by(ContentRevisionModel.revision_number)
        ).all()
        assert [revision.source_text for revision in revisions] == ["original", "edited"]
