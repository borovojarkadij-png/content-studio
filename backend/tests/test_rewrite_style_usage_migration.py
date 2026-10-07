import pytest
from sqlalchemy import create_engine, text

from alembic import command
from newsflow.migrate import runtime_migration_config


def test_migration_keeps_channel_identity_defaults_neutral_and_refuses_style_loss(
    tmp_path, monkeypatch
):
    url = f"sqlite:///{tmp_path / 'isolated-style.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    configuration = runtime_migration_config()
    command.upgrade(configuration, "f6b20d8a9143")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO telegram_accounts (id,name,telegram_user_id,encrypted_session,health_status) VALUES (1,'synthetic',1001,'','DISCONNECTED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO output_channels (id,telegram_account_id,telegram_channel_id,title) VALUES (1,1,-1001234567890,'synthetic')"
            )
        )
    command.upgrade(configuration, "head")
    command.check(configuration)
    with engine.begin() as connection:
        assert connection.execute(
            text("SELECT telegram_channel_id,rewrite_style FROM output_channels")
        ).one() == (-1001234567890, "NEUTRAL")
        connection.execute(text("UPDATE output_channels SET rewrite_style='TABLOID'"))
    with pytest.raises(RuntimeError, match="Refusing"):
        command.downgrade(configuration, "f6b20d8a9143")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT rewrite_style FROM output_channels")) == "TABLOID"
    engine.dispose()
