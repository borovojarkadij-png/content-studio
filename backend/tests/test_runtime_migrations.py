import pytest
from sqlalchemy import create_engine, inspect


def test_runtime_migrations_use_explicit_database_and_are_restart_safe(tmp_path, monkeypatch):
    from newsflow.migrate import upgrade_runtime_database

    url = f"sqlite:///{tmp_path / 'isolated-runtime.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    upgrade_runtime_database()
    upgrade_runtime_database()
    engine = create_engine(url)
    assert "media_assets" in inspect(engine).get_table_names()
    engine.dispose()


def test_runtime_migrations_never_fall_back_to_local_sqlite(monkeypatch):
    from newsflow.migrate import upgrade_runtime_database

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        upgrade_runtime_database()


def test_migration_config_accepts_percent_encoded_password_without_interpolation(monkeypatch):
    from newsflow.migrate import runtime_migration_config

    url = "postgresql+psycopg://test:synthetic%25password@postgres/test"
    monkeypatch.setenv("DATABASE_URL", url)
    assert runtime_migration_config().get_main_option("sqlalchemy.url") == url
