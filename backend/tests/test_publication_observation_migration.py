import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def test_observation_upgrade_never_fabricates_receipts_or_loses_old_history(tmp_path):
    url = f"sqlite:///{tmp_path / 'observation-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "b7e426d9ab15")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO publication_jobs (planned_id,telegram_account_id,telegram_channel_id,request_nonce,binding_sha256,state,available_at) VALUES (1,1,-1001234567891,456,:digest,'QUEUED','2026-10-08')"
            ),
            {"digest": "a" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO publication_request_snapshots (job_id,binding_sha256,encrypted_envelope) VALUES (1,:digest,'old-encrypted-history')"
            ),
            {"digest": "a" * 64},
        )
    command.upgrade(config, "head")
    assert "publication_delivery_observations" in inspect(engine).get_table_names()
    command.check(config)
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT COUNT(*) FROM publication_delivery_observations")) == 0
        )
        assert (
            connection.scalar(text("SELECT encrypted_envelope FROM publication_request_snapshots"))
            == "old-encrypted-history"
        )
        assert connection.scalar(text("SELECT request_nonce FROM publication_jobs")) == 456
    with pytest.raises(RuntimeError, match="intent/acknowledgement history"):
        command.downgrade(config, "b7e426d9ab15")
    assert "publication_delivery_observations" in inspect(engine).get_table_names()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO publication_delivery_observations (job_id,encrypted_receipt) VALUES (1,'synthetic')"
            )
        )
    for value in ("", "x" * 4097):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("UPDATE publication_delivery_observations SET encrypted_receipt=:value"),
                {"value": value},
            )
    engine.dispose()
