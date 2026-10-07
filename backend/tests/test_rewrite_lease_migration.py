import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from newsflow.migrate import runtime_migration_config


def test_lease_migration_preserves_old_dispatched_jobs_and_refuses_loss_of_execution_history(
    tmp_path, monkeypatch
):
    url = f"sqlite:///{tmp_path / 'lease-migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    configuration = runtime_migration_config()
    command.upgrade(configuration, "e82a9c7b3061")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO rewrite_jobs (content_key, idempotency_key, state) "
                "VALUES ('synthetic', 'synthetic', 'DISPATCHED')"
            )
        )
    command.upgrade(configuration, "head")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT state, attempts FROM rewrite_jobs")).one() == (
            "DISPATCHED",
            0,
        )
        connection.execute(text("UPDATE rewrite_jobs SET attempts = 1"))
    with pytest.raises(RuntimeError, match="execution/recovery history"):
        command.downgrade(configuration, "e82a9c7b3061")
    assert "claim_token" in {
        column["name"] for column in inspect(engine).get_columns("rewrite_jobs")
    }
    with engine.begin() as connection:
        assert connection.execute(text("SELECT attempts FROM rewrite_jobs")).scalar_one() == 1
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE rewrite_jobs SET attempts = -1"))
    engine.dispose()
