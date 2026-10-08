"""Legacy unknown metadata is preserved, never backfilled as empty/safe."""

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from test_persisted_mapping_filters import NOW

from alembic import command
from newsflow.domain.sql_ingestion import SqlAlchemyIngestionRepository
from newsflow.providers.telegram import TelegramMessage


def test_link_migration_preserves_unknown_history_and_refuses_populated_downgrade(tmp_path):
    url = f"sqlite:///{tmp_path / 'source-links.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "eab7590cde48")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incoming_posts (id,telegram_account_id,donor_channel_id,telegram_message_id,state) VALUES (1,'synthetic','-100123',1,'RECEIVED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO incoming_post_revisions (incoming_post_id,revision_number,source_text) VALUES (1,1,'Legacy source')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT source_text,link_destinations FROM incoming_post_revisions")
        ).one() == ("Legacy source", None)
    with Session(engine) as session, session.begin():
        SqlAlchemyIngestionRepository(session).ingest(
            TelegramMessage("synthetic", "-100123", 2, "Observed unknown", link_destinations=None),
            NOW,
        )
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM incoming_post_revisions WHERE link_destinations IS NULL")
            )
            == 2
        )
    command.downgrade(config, "eab7590cde48")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE incoming_post_revisions SET link_destinations=:links"),
            {"links": '["https://youtu.be/abc"]'},
        )
    with pytest.raises(RuntimeError, match="source link metadata"):
        command.downgrade(config, "eab7590cde48")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT source_text FROM incoming_post_revisions"))
            == "Legacy source"
        )
        assert (
            connection.scalar(text("SELECT link_destinations FROM incoming_post_revisions"))
            == '["https://youtu.be/abc"]'
        )
    engine.dispose()
