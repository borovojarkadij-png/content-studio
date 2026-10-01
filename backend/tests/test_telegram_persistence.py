import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from newsflow.persistence.models import Base, ContentRevision, TelegramAccount


def test_telegram_account_user_id_is_unique_per_installation() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                TelegramAccount(name="Primary", telegram_user_id=1001, encrypted_session="ciphertext-a"),
                TelegramAccount(name="Duplicate", telegram_user_id=1001, encrypted_session="ciphertext-b"),
            ]
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        else:
            raise AssertionError("Telegram user identity must be unique")


def test_content_revision_source_identity_is_unique() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            ContentRevision(
                source_key="account:donor:7",
                editorial_status="PASS",
                rewrite_allowed=True,
            )
        )
        session.commit()
        session.add(
            ContentRevision(
                source_key="account:donor:7",
                editorial_status="PASS",
                rewrite_allowed=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
