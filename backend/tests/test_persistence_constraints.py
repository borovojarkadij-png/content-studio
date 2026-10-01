from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.persistence.models import Base, ContentRevision


def test_database_rejects_rejected_revision_with_rewrite_enabled() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            ContentRevision(
                source_key="account:1/channel:2/message:3/revision:1",
                editorial_status="REJECT",
                rewrite_allowed=True,
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("REJECT with rewrite_allowed=true must be invalid")
