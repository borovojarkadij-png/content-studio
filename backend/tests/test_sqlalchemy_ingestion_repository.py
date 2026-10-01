from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
from newsflow.persistence.models import Base
from newsflow.providers.telegram import TelegramMessage


def test_sql_repository_creates_one_post_and_preserves_edit_history() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        repository = SqlAlchemyIngestionRepository(session)
        created = repository.ingest(TelegramMessage("account-a", "channel-a", 5, "first"), datetime.now(UTC))
        edited = repository.ingest(
            TelegramMessage("account-a", "channel-a", 5, "updated", is_edit=True), datetime.now(UTC)
        )
        duplicated = repository.ingest(
            TelegramMessage("account-a", "channel-a", 5, "updated", is_edit=True), datetime.now(UTC)
        )
        session.commit()

        assert created.created is True
        assert edited.created is False
        assert duplicated.created is False
        assert repository.revision_texts("account-a", "channel-a", 5) == ["first", "updated"]
