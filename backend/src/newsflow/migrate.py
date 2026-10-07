"""Run packaged Alembic upgrades against the explicit runtime database only."""

from os import getenv
from pathlib import Path

from alembic.config import Config

from alembic import command


def runtime_migration_config() -> Config:
    database_url = getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise ValueError("DATABASE_URL is required; refusing a local SQLite fallback")
    config_path = Path(getenv("NEWSFLOW_ALEMBIC_CONFIG", "alembic.ini")).resolve(strict=True)
    config = Config(str(config_path))
    config.set_main_option("script_location", str(config_path.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_runtime_database() -> None:
    command.upgrade(runtime_migration_config(), "head")


if __name__ == "__main__":
    upgrade_runtime_database()
