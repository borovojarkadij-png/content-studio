import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command


def test_observation_migration_preserves_legacy_unknowns_and_refuses_identity_loss(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'observation.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "f04c8b31d9a2")
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
    with engine.begin() as connection:
        assert (
            connection.scalar(text("SELECT media_type FROM incoming_post_revisions")) == "unknown"
        )
        assert (
            connection.scalar(text("SELECT source_updated_at FROM incoming_post_revisions")) is None
        )
        connection.execute(
            text(
                "INSERT INTO incoming_post_revisions (incoming_post_id,revision_number,source_text,media_type,album_id,source_updated_at) VALUES (1,2,'New photo','photo','77','2030-01-01')"
            )
        )
    with pytest.raises(RuntimeError, match="observation identity"):
        command.downgrade(config, "f04c8b31d9a2")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM incoming_post_revisions")) == 2
        assert (
            connection.scalar(
                text("SELECT album_id FROM incoming_post_revisions WHERE revision_number=2")
            )
            == "77"
        )
    engine.dispose()
