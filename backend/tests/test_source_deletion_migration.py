import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def test_deletion_migration_retains_history_and_refuses_populated_downgrade(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'deletions.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "c8f537eabc26")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO incoming_posts (telegram_account_id,donor_channel_id,telegram_message_id,state) VALUES ('1','-1001234567890',20,'RECEIVED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO incoming_post_revisions (incoming_post_id,revision_number,source_text) VALUES (1,1,'retained source')"
            )
        )
    command.upgrade(config, "head")
    assert "source_deletions" in inspect(engine).get_table_names()
    command.check(config)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM source_deletions")) == 0
        assert (
            connection.scalar(text("SELECT source_text FROM incoming_post_revisions"))
            == "retained source"
        )
    command.downgrade(config, "c8f537eabc26")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source_deletions (telegram_account_id,donor_channel_id,telegram_message_id,latest_pts,observed_at) VALUES ('1','-1001234567890',20,11,'2026-10-08')"
            )
        )
    for field, value in (
        ("latest_pts", 0),
        ("latest_pts", 2147483648),
        ("telegram_message_id", 0),
        ("telegram_message_id", 2147483648),
        ("telegram_account_id", ""),
        ("donor_channel_id", ""),
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(f"UPDATE source_deletions SET {field}=:value"), {"value": value}
            )
    with pytest.raises(RuntimeError, match="deletion history"):
        command.downgrade(config, "c8f537eabc26")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT latest_pts FROM source_deletions")) == 11
        assert (
            connection.scalar(text("SELECT source_text FROM incoming_post_revisions"))
            == "retained source"
        )
    engine.dispose()
