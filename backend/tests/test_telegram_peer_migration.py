import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command


def test_peer_migration_preserves_accounts_and_blocks_populated_downgrade(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'peer-migration.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "a07d92e1b4f3")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO telegram_accounts (id,name,telegram_user_id,encrypted_session,health_status) VALUES (1,'Legacy',1001,'legacy-ciphertext','DISCONNECTED')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        assert (
            connection.scalar(text("SELECT encrypted_session FROM telegram_accounts"))
            == "legacy-ciphertext"
        )
        connection.execute(
            text(
                "INSERT INTO telegram_peers (telegram_account_id,telegram_channel_id,encrypted_peer) VALUES (1,-1001234567890,'synthetic-encrypted-peer')"
            )
        )
    with pytest.raises(RuntimeError, match="peer recovery data"):
        command.downgrade(config, "a07d92e1b4f3")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT encrypted_peer FROM telegram_peers"))
            == "synthetic-encrypted-peer"
        )
    engine.dispose()
