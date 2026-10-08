import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command


def test_media_mode_migration_preserves_legacy_job_constraints_and_history(tmp_path):
    url = f"sqlite:///{tmp_path / 'source-job-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "e4b193a6d8f2")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO media_acquisition_jobs (candidate_id,binding_sha256,state,available_at) VALUES (1,:digest,'QUEUED','2026-10-08')"
            ),
            {"digest": "a" * 64},
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT acquisition_mode,license_code,attribution,attempts FROM media_acquisition_jobs"
            )
        ).one() == ("LICENSED_LIBRARY", None, None, 0)
    for update in (
        "attempts=3",
        "state='INVALID'",
        "binding_sha256='short'",
        "state='RUNNING'",
        "state='SUCCEEDED'",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text("UPDATE media_acquisition_jobs SET " + update))
    command.downgrade(config, "e4b193a6d8f2")
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE media_acquisition_jobs SET attempts=3"))
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE media_acquisition_jobs SET acquisition_mode='REUSE_SOURCE',license_code='PERMISSION',attribution='Explicit synthetic permission'"
            )
        )
    with pytest.raises(RuntimeError, match="rights/history"):
        command.downgrade(config, "e4b193a6d8f2")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT attribution FROM media_acquisition_jobs"))
            == "Explicit synthetic permission"
        )
    engine.dispose()
