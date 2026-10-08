import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def test_snapshot_upgrade_preserves_legacy_nonce_without_fabricating_request(tmp_path):
    url = f"sqlite:///{tmp_path / 'snapshot-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "a6d315c8fa04")
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
                "INSERT INTO outbox_events (event_type,aggregate_key,idempotency_key) VALUES ('publication.queued','1','publication:1:queued')"
            )
        )
    command.upgrade(config, "head")
    assert "publication_request_snapshots" in inspect(engine).get_table_names()
    command.check(config)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM publication_request_snapshots")) == 0
        assert connection.execute(
            text("SELECT request_nonce,state,attempts FROM publication_jobs")
        ).one() == (456, "QUEUED", 0)
    with pytest.raises(RuntimeError, match="intent/acknowledgement history"):
        command.downgrade(config, "a6d315c8fa04")
    assert "publication_request_snapshots" in inspect(engine).get_table_names()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO publication_request_snapshots (job_id,binding_sha256,encrypted_envelope) VALUES (1,:digest,'synthetic')"
            ),
            {"digest": "a" * 64},
        )
    for change in (
        "binding_sha256='short'",
        "encrypted_envelope=''",
        "encrypted_envelope=:oversized",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                text("UPDATE publication_request_snapshots SET " + change),
                {"oversized": "x" * 32769},
            )
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT idempotency_key FROM outbox_events"))
            == "publication:1:queued"
        )
    engine.dispose()
