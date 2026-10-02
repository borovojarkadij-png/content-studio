from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_configuration_schema_upgrade_creates_pending_import_storage(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'configuration-migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert "donor_imports" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("donor_imports")}
        assert columns == {"id", "telegram_account_id", "identifier", "status"}
        assert any(
            index["column_names"] == ["telegram_account_id"]
            for index in inspector.get_indexes("donor_imports")
        )
    finally:
        engine.dispose()

    command.downgrade(config, "a2c5e8f1b7d4")
    command.upgrade(config, "head")
