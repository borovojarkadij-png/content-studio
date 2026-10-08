import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def test_publication_migration_preserves_existing_state_and_refuses_history_loss(tmp_path):
    url = f"sqlite:///{tmp_path / 'publication-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "f5c204b7e903")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO outbox_events (event_type,aggregate_key,idempotency_key) VALUES ('synthetic.history','before','synthetic:before')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, "f5c204b7e903")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO publication_jobs (planned_id,telegram_account_id,telegram_channel_id,request_nonce,binding_sha256,state,available_at) VALUES (1,1,-1001234567891,456,:digest,'QUEUED','2026-10-08')"
            ),
            {"digest": "a" * 64},
        )
    for update in (
        "attempts=3",
        "state='INVALID'",
        "request_nonce=0",
        "state='SENDING'",
        "state='SUCCEEDED'",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("UPDATE publication_jobs SET " + update))
    with pytest.raises(RuntimeError, match="intent/acknowledgement history"):
        command.downgrade(config, "f5c204b7e903")
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT request_nonce,state,attempts FROM publication_jobs")
        ).one() == (456, "QUEUED", 0)
        assert (
            connection.scalar(text("SELECT idempotency_key FROM outbox_events"))
            == "synthetic:before"
        )
    engine.dispose()
