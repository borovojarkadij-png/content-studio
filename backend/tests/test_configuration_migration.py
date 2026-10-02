from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_configuration_schema_upgrade_creates_pending_import_storage(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'configuration-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert {
            "donor_imports",
            "publication_plans",
            "publication_candidates",
            "planned_publications",
        } <= set(inspector.get_table_names())
        columns = {column["name"] for column in inspector.get_columns("donor_imports")}
        assert columns == {"id", "telegram_account_id", "identifier", "status"}
        assert any(
            index["column_names"] == ["telegram_account_id"]
            for index in inspector.get_indexes("donor_imports")
        )
        assert any(
            index["column_names"] == ["output_channel_id"]
            for index in inspector.get_indexes("publication_plans")
        )
        rewrite_job_columns = {column["name"] for column in inspector.get_columns("rewrite_jobs")}
        assert "output_channel_id" in rewrite_job_columns
        assert any(
            index["column_names"] == ["output_channel_id"]
            for index in inspector.get_indexes("rewrite_jobs")
        )
    finally:
        engine.dispose()

    command.downgrade(config, "a2c5e8f1b7d4")
    command.upgrade(config, "head")


def test_rewrite_job_scope_migration_preserves_a_legacy_unmapped_job(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'rewrite-job-scope.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "f51c8a04b2de")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO rewrite_jobs (content_key, idempotency_key, state) "
                    "VALUES ('legacy:1', 'rewrite.requested:legacy:1', 'DISPATCHED')"
                )
            )
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT content_key, output_channel_id FROM rewrite_jobs")
            ).one()
        assert row == ("legacy:1", None)
    finally:
        engine.dispose()

    command.downgrade(config, "f51c8a04b2de")
