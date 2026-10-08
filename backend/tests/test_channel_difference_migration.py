import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def test_channel_cursor_migration_never_invents_checkpoint_and_preserves_deletions(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'channel-pts.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "d9a648fbcd37")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO source_deletions (telegram_account_id,donor_channel_id,telegram_message_id,latest_pts,observed_at) VALUES ('1','-1001234567890',20,11,'2026-10-08')"
            )
        )
    command.upgrade(config, "head")
    assert "channel_difference_cursors" in inspect(engine).get_table_names()
    command.check(config)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM channel_difference_cursors")) == 0
        assert connection.scalar(text("SELECT latest_pts FROM source_deletions")) == 11
    command.downgrade(config, "d9a648fbcd37")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO channel_difference_cursors (donor_channel_id,telegram_account_id,telegram_user_id,telegram_channel_id,pts,available_at) VALUES (1,1,1001,-1001234567890,10,'2026-10-08')"
            )
        )
    for field, value in (
        ("pts", 0),
        ("pts", 2147483648),
        ("telegram_user_id", 0),
        ("telegram_account_id", 0),
        ("telegram_channel_id", 123),
        ("claim_token", "partial-lease"),
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text(f"UPDATE channel_difference_cursors SET {field}=:value"), {"value": value}
            )
    with pytest.raises(RuntimeError, match="channel difference history"):
        command.downgrade(config, "d9a648fbcd37")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT pts FROM channel_difference_cursors")) == 10
        assert connection.scalar(text("SELECT latest_pts FROM source_deletions")) == 11
    engine.dispose()
