"""Historical upgrade, no-drift, append-only SQL and diagnostic receipt bounds."""

from uuid import uuid4

import pytest
import test_editorial_admission_migration as admission_tests
from sqlalchemy import inspect, text
from sqlalchemy.exc import DatabaseError, IntegrityError
from test_editorial_admission_migration import (
    NOW,
    insert_job,
    sentinels,
)

from alembic import command

PARENT = "d7b340a92e16"
HEAD = "f6a42c91b805"


migrated = admission_tests.migrated


def prepare(migrated):
    config, engine = migrated
    command.upgrade(config, PARENT)
    with engine.begin() as connection:
        insert_job(connection)
        connection.execute(
            text(
                "INSERT INTO editorial_classifier_policy(id,provider,model,policy_version,protected_entities) VALUES(1,'OPENAI','synthetic','v1','[]')"
            )
        )
        connection.execute(
            text("UPDATE mapping_content_fingerprints SET content_key='retained-owner'")
        )
    return config, engine


def history(engine):
    with engine.connect() as connection:
        return {
            name: connection.execute(text(f"SELECT * FROM {name} ORDER BY id")).all()
            for name in (
                "editorial_classification_jobs",
                "editorial_classifier_policy",
                "mapping_content_fingerprints",
            )
        }


def claim(connection, **changes):
    values = {
        "id": 1,
        "classification_job_id": 1,
        "attempt": 1,
        "claim_token": str(uuid4()),
        "created_at": NOW.isoformat(),
        **changes,
    }
    insert(connection, "editorial_classification_claims", values)


def receipt(connection, **changes):
    values = {
        "id": 1,
        "claim_id": 1,
        "outcome": "REVIEW",
        "reason_codes": '["REAL_MODEL_NOT_QUALIFIED"]',
        "created_at": NOW.isoformat(),
        **changes,
    }
    insert(connection, "editorial_classification_attempts", values)


def insert(connection, table, values):
    connection.execute(
        text(
            f"INSERT INTO {table}({','.join(values)}) VALUES({','.join(':' + name for name in values)})"
        ),
        values,
    )


def test_additive_upgrade_and_empty_roundtrip_preserve_all_old_data_without_drift(migrated):
    config, engine = prepare(migrated)
    before, before_history = sentinels(engine), history(engine)
    command.upgrade(config, HEAD)
    # Autogenerate compares current metadata, while HEAD remains the historical
    # migration boundary whose additive/empty roundtrip this test protects.
    command.upgrade(config, "head")
    command.check(config)
    command.downgrade(config, HEAD)
    assert sentinels(engine) == before
    assert history(engine) == before_history
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM editorial_classification_claims")) == 0
        assert (
            connection.scalar(text("SELECT count(*) FROM editorial_classification_attempts")) == 0
        )
    command.downgrade(config, PARENT)
    assert history(engine) == before_history
    command.upgrade(config, HEAD)
    command.upgrade(config, "head")
    command.check(config)
    assert history(engine) == before_history


@pytest.mark.parametrize("populated", ["claim", "receipt"])
def test_populated_history_blocks_downgrade_before_ddl_and_keeps_all_rows(migrated, populated):
    config, engine = prepare(migrated)
    command.upgrade(config, HEAD)
    before = history(engine)
    with engine.begin() as connection:
        claim(connection)
        if populated == "receipt":
            receipt(connection)
    with pytest.raises(RuntimeError, match="Refusing downgrade"):
        command.downgrade(config, PARENT)
    assert history(engine) == before
    assert "editorial_classification_attempts" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        assert connection.scalar(text("SELECT count(*) FROM editorial_classification_claims")) == 1
        assert connection.scalar(
            text("SELECT count(*) FROM editorial_classification_attempts")
        ) == (populated == "receipt")


@pytest.mark.parametrize(
    "changes",
    [
        {"attempt": 0},
        {"attempt": 3},
        {"attempt": 1.5},
        {"claim_token": "x" * 36},
        {"claim_token": "A" * 8 + "-1111-1111-1111-111111111111"},
        {"claim_token": "a" * 32},
        {"classification_job_id": 999},
    ],
)
def test_invalid_claim_sql_is_refused(migrated, changes):
    config, engine = prepare(migrated)
    command.upgrade(config, HEAD)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        claim(connection, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"outcome": "PASS"},
        {"diagnostic_status": "SUCCEEDED"},
        {"reason_codes": "{}"},
        {"reason_codes": "null"},
        {"reason_codes": None},
        {"claim_id": 999},
        {"input_tokens": 1},
        {"estimated_cost_usd": 0},
        {"usage_observed": True},
        {"usage_observed": True, "input_tokens": 10, "cached_tokens": 11, "output_tokens": 1},
        {"usage_observed": True, "input_tokens": -1, "cached_tokens": 0, "output_tokens": 0},
        {"usage_observed": True, "input_tokens": 1.5, "cached_tokens": 0, "output_tokens": 0},
        {
            "usage_observed": True,
            "input_tokens": 1,
            "cached_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": -1,
        },
        {
            "usage_observed": True,
            "input_tokens": 1,
            "cached_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": float("inf"),
        },
        {"evidence_json": "界" * 87382},
        {"response_model": "x" * 256},
        {"response_model": " "},
    ],
)
def test_invalid_receipt_sql_is_refused(migrated, changes):
    config, engine = prepare(migrated)
    command.upgrade(config, HEAD)
    with engine.begin() as connection:
        claim(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        receipt(connection, **changes)


@pytest.mark.parametrize(
    "table", ["editorial_classification_claims", "editorial_classification_attempts"]
)
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "REPLACE"])
def test_sql_mutation_and_replace_refused_even_without_fk_enforcement(migrated, table, operation):
    config, engine = prepare(migrated)
    command.upgrade(config, HEAD)
    with engine.begin() as connection:
        claim(connection)
        receipt(
            connection,
            usage_observed=True,
            input_tokens=10,
            cached_tokens=2,
            output_tokens=1,
            estimated_cost_usd="0.000001",
        )
    with engine.connect() as connection:
        before = connection.execute(text(f"SELECT * FROM {table}")).all()
    with pytest.raises(DatabaseError, match="append-only"), engine.begin() as connection:
        if operation == "UPDATE":
            connection.execute(text(f"UPDATE {table} SET id=id"))
        elif operation == "DELETE":
            connection.execute(text(f"DELETE FROM {table}"))
        else:
            connection.execute(text(f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"))
    with engine.connect() as connection:
        assert connection.execute(text(f"SELECT * FROM {table}")).all() == before


def test_history_unique_keys_and_parent_restriction(migrated):
    config, engine = prepare(migrated)
    command.upgrade(config, HEAD)
    with engine.begin() as connection:
        claim(connection)
        receipt(connection)
    with pytest.raises(DatabaseError), engine.begin() as connection:
        claim(connection, id=2)
    with pytest.raises(DatabaseError), engine.begin() as connection:
        receipt(connection, id=2)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("DELETE FROM editorial_classification_jobs WHERE id=1"))
