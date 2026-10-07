import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command


def test_configured_filter_downgrade_refuses_policy_loss(tmp_path):
    config = Config("alembic.ini")
    url = f"sqlite:///{tmp_path / 'filter-migration.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    command.check(config)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO telegram_accounts (id,name,telegram_user_id,encrypted_session,health_status) VALUES (1,'Synthetic',1001,'','DISCONNECTED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO donor_channels (id,telegram_account_id,telegram_channel_id,title) VALUES (1,1,-1001234567890,'Donor')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO output_channels (id,telegram_account_id,telegram_channel_id,title) VALUES (1,1,-1009876543210,'Output')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO channel_mappings (id,donor_channel_id,output_channel_id,intake_percent,target_mix_percent) VALUES (1,1,1,100,100)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO mapping_filter_policies (mapping_id,allowed_media_types,blocked_domains,ad_markers) VALUES (1,'[\"text\"]','[\"example.org\"]','[]')"
            )
        )
    with pytest.raises(RuntimeError, match="configured mapping filters"):
        command.downgrade(config, "b18e63d2a5c4")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT blocked_domains FROM mapping_filter_policies"))
            == '["example.org"]'
        )
    engine.dispose()
