import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command


def test_donor_resolution_history_is_preserved_and_downgrade_refuses_loss(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'resolution.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "c29f74e3b6d5")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO telegram_accounts (id,name,telegram_user_id,encrypted_session,health_status) VALUES (1,'Synthetic',1001,'','DISCONNECTED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO donor_imports (id,telegram_account_id,identifier,status) VALUES (1,1,'@synthetic_donor','PENDING_RESOLUTION')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT status FROM donor_imports")) == "PENDING_RESOLUTION"
        connection.execute(
            text(
                "INSERT INTO donor_import_resolution_jobs (donor_import_id,state,available_at,last_error_code) VALUES (1,'RETRY','2030-01-01','RETRY_PROVIDER')"
            )
        )
    with pytest.raises(RuntimeError, match="resolution history"):
        command.downgrade(config, "c29f74e3b6d5")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT last_error_code FROM donor_import_resolution_jobs"))
            == "RETRY_PROVIDER"
        )
    engine.dispose()
