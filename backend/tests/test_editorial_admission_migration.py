"""Additive migration sentinels, refusal before DDL, and row-local constraints."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import DatabaseError, IntegrityError

from alembic import command

PARENT = "c5e81b29a704"
HEAD = "d7b340a92e16"
NOW = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture
def migrated(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, PARENT)
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        for statement in (
            "INSERT INTO telegram_accounts(id,name,telegram_user_id,encrypted_session,health_status) VALUES(1,'synthetic',1,'','DISCONNECTED')",
            "INSERT INTO donor_channels(id,telegram_account_id,telegram_channel_id,title) VALUES(1,1,-1001234567890,'synthetic')",
            "INSERT INTO output_channels(id,telegram_account_id,telegram_channel_id,title) VALUES(1,1,-1001234567891,'synthetic')",
            "INSERT INTO channel_mappings(id,donor_channel_id,output_channel_id,intake_percent,target_mix_percent,eligibility_mode,delay_minutes,priority,media_policy) VALUES(1,1,1,100,100,'IMMEDIATE',0,0,'REUSE_SOURCE')",
            "INSERT INTO incoming_posts(id,telegram_account_id,donor_channel_id,telegram_message_id,state) VALUES(1,'1','-1001234567890',1,'MANUAL_REVIEW')",
            "INSERT INTO incoming_post_revisions(id,incoming_post_id,revision_number,source_text,media_type) VALUES(1,1,1,'legacy synthetic source','unknown')",
            "INSERT INTO editorial_decisions(id,content_key,status,rewrite_allowed,reason_codes,protected_entities,sentiment,framing) VALUES(1,'legacy','MANUAL_REVIEW',false,'','','unknown','unknown')",
            "INSERT INTO rewrite_jobs(id,content_key,idempotency_key,state) VALUES(1,'legacy','legacy-request','BLOCKED')",
            "INSERT INTO mapping_content_fingerprints(id,mapping_id,fingerprint) VALUES(1,'legacy-prototype','legacy-fingerprint')",
        ):
            connection.execute(text(statement))
    yield config, engine
    engine.dispose()


def sentinels(engine):
    with engine.connect() as connection:
        return {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
            for table in (
                "incoming_posts",
                "incoming_post_revisions",
                "editorial_decisions",
                "rewrite_jobs",
            )
        }


def test_additive_upgrade_preserves_legacy_and_empty_roundtrip(migrated):
    config, engine = migrated
    before = sentinels(engine)
    with engine.connect() as connection:
        fingerprint_before = connection.execute(
            text("SELECT id,mapping_id,fingerprint,created_at FROM mapping_content_fingerprints")
        ).one()
    command.upgrade(config, HEAD)
    command.check(config)
    assert sentinels(engine) == before
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT id,mapping_id,fingerprint,created_at FROM mapping_content_fingerprints"
                )
            ).one()
            == fingerprint_before
        )
        row = connection.execute(
            text("SELECT mapping_id,fingerprint,content_key FROM mapping_content_fingerprints")
        ).one()
        assert tuple(row) == ("legacy-prototype", "legacy-fingerprint", None)
        assert connection.scalar(text("SELECT count(*) FROM editorial_classifier_policy")) == 0
    command.downgrade(config, PARENT)
    assert sentinels(engine) == before
    command.upgrade(config, HEAD)
    command.check(config)
    assert sentinels(engine) == before


def job_values(**changes):
    return {
        "content_key": "legacy",
        "source_revision_id": 1,
        "mapping_id": 1,
        "editorial_decision_id": 1,
        "source_sha256": "a" * 64,
        "policy_sha256": "b" * 64,
        "mapping_sha256": "c" * 64,
        "prompt_version": "synthetic-v1",
        "provider": "OPENAI",
        "model": "synthetic",
        "idempotency_key": "d" * 64,
        "state": "QUEUED",
        "attempts": 0,
        "available_at": NOW.isoformat(),
        "created_at": NOW.isoformat(),
        **changes,
    }


def insert_job(connection, **changes):
    values = job_values(**changes)
    values = {
        name: value.isoformat() if isinstance(value, datetime) else value
        for name, value in values.items()
    }
    columns = ",".join(values)
    parameters = ",".join(":" + name for name in values)
    connection.execute(
        text(f"INSERT INTO editorial_classification_jobs({columns}) VALUES({parameters})"), values
    )


@pytest.mark.parametrize("populated", ["policy", "job"])
def test_populated_downgrade_refuses_before_ddl_and_preserves_history(migrated, populated):
    config, engine = migrated
    command.upgrade(config, HEAD)
    before = sentinels(engine)
    with engine.begin() as connection:
        if populated == "policy":
            connection.execute(
                text(
                    "INSERT INTO editorial_classifier_policy(id,provider,model,policy_version,protected_entities) VALUES(1,'OPENAI','synthetic','v1','[]')"
                )
            )
        else:
            insert_job(connection)
    with pytest.raises(RuntimeError, match="Refusing downgrade"):
        command.downgrade(config, PARENT)
    assert sentinels(engine) == before
    assert "editorial_classification_jobs" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        table = (
            "editorial_classifier_policy"
            if populated == "policy"
            else "editorial_classification_jobs"
        )
        assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 1
        if populated == "policy":
            assert connection.scalar(text("SELECT enabled FROM editorial_classifier_policy")) == 0


@pytest.mark.parametrize(
    "change",
    [
        {"state": "PASS"},
        {"provider": "OTHER"},
        {"attempts": -1},
        {"attempts": 3},
        {"state": "RUNNING"},
        {"claim_token": "x" * 36},
        {"lease_expires_at": NOW},
        {"state": "RUNNING", "claim_token": "x" * 36},
        {"source_sha256": "g" * 64},
        {"policy_sha256": "b" * 63},
        {"mapping_sha256": "C" * 64},
        {"idempotency_key": "d" * 65},
        {"model": ""},
        {"prompt_version": "x" * 65},
        {"content_key": "x" * 256},
        {"source_revision_id": 99999},
        {"mapping_id": 99999},
        {"editorial_decision_id": 99999},
    ],
)
def test_invalid_job_rows_are_refused(migrated, change):
    config, engine = migrated
    command.upgrade(config, HEAD)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert_job(connection, **change)


def test_binding_identity_unique_and_immutable_while_state_retains_history(migrated):
    config, engine = migrated
    command.upgrade(config, HEAD)
    with engine.begin() as connection:
        insert_job(connection)
        connection.execute(
            text(
                "UPDATE editorial_classification_jobs SET state='RUNNING',claim_token=:token,lease_expires_at=:now,attempts=1"
            ),
            {"token": "x" * 36, "now": NOW.isoformat()},
        )
        connection.execute(
            text(
                "UPDATE editorial_classification_jobs SET state='FAILED',claim_token=NULL,lease_expires_at=NULL"
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert_job(connection, idempotency_key="e" * 64)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        insert_job(connection, policy_sha256="f" * 64)
    with pytest.raises(DatabaseError, match="immutable"), engine.begin() as connection:
        connection.execute(
            text("UPDATE editorial_classification_jobs SET source_sha256=:digest"),
            {"digest": "e" * 64},
        )
    with engine.connect() as connection:
        assert tuple(
            connection.execute(
                text("SELECT state,attempts,source_sha256 FROM editorial_classification_jobs")
            ).one()
        ) == ("FAILED", 1, "a" * 64)


@pytest.mark.parametrize(
    "table", ["incoming_post_revisions", "channel_mappings", "editorial_decisions"]
)
def test_job_retains_referenced_history_with_restrict(migrated, table):
    config, engine = migrated
    command.upgrade(config, HEAD)
    with engine.begin() as connection:
        insert_job(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(f"DELETE FROM {table} WHERE id=1"))


@pytest.mark.parametrize(
    "changes",
    [
        {"id": 2},
        {"provider": "OTHER"},
        {"model": ""},
        {"model": "x" * 256},
        {"policy_version": ""},
        {"policy_version": "x" * 256},
    ],
)
def test_policy_singleton_provider_and_bounds_are_enforced(migrated, changes):
    config, engine = migrated
    command.upgrade(config, HEAD)
    values = {
        "id": 1,
        "provider": "OPENAI",
        "model": "synthetic",
        "policy_version": "v1",
        "protected_entities": "[]",
        **changes,
    }
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO editorial_classifier_policy(id,provider,model,policy_version,protected_entities) "
                "VALUES(:id,:provider,:model,:policy_version,:protected_entities)"
            ),
            values,
        )
