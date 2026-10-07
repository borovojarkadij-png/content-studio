import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command


def test_cursor_migration_preserves_configuration_and_refuses_recovery_history_loss(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'cursor.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "e93b0a4217d6")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO telegram_accounts (id,name,telegram_user_id,encrypted_session,health_status) VALUES (1,'synthetic',1001,'','DISCONNECTED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO donor_channels (id,telegram_account_id,telegram_channel_id,title) VALUES (1,1,-1001234567890,'synthetic')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO donor_ingestion_cursors (donor_channel_id,last_message_id,available_at) VALUES (1,42,'2030-01-01')"
            )
        )
    with pytest.raises(RuntimeError, match="recovery progress"):
        command.downgrade(config, "e93b0a4217d6")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT last_message_id FROM donor_ingestion_cursors")) == 42
        assert connection.scalar(text("SELECT title FROM donor_channels")) == "synthetic"
    engine.dispose()
