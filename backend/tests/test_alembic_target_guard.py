"""Run real Alembic subprocesses against only temporary sentinel databases."""

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


def cli(tmp_path, monkeypatch, *, url=None):
    # An ini fallback must never silently migrate a user's working-directory DB.
    config = tmp_path / "alembic.ini"
    config.write_text(
        f"[alembic]\nscript_location = {Path('alembic').resolve().as_posix()}\n"
        "sqlalchemy.url = sqlite:///newsflow.db\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env = dict(os.environ)
    if url is not None:
        env["DATABASE_URL"] = url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(config), "upgrade", "head"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )


def test_cli_without_explicit_target_does_not_touch_local_database(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'newsflow.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("create table sentinel (value text)"))
        connection.execute(text("insert into sentinel values ('preserve me')"))
    result = cli(tmp_path, monkeypatch)
    assert result.returncode != 0
    assert "explicit" in result.stderr.lower()
    assert inspect(engine).get_table_names() == ["sentinel"]
    with engine.connect() as connection:
        assert connection.execute(text("select value from sentinel")).scalar() == "preserve me"
    engine.dispose()


def test_cli_environment_target_wins_over_legacy_ini_fallback(tmp_path, monkeypatch):
    target = tmp_path / "explicit.db"
    result = cli(tmp_path, monkeypatch, url=f"sqlite:///{target.as_posix()}")
    assert result.returncode == 0, result.stderr
    assert target.is_file()
    assert not (tmp_path / "newsflow.db").exists()
    engine = create_engine(f"sqlite:///{target.as_posix()}")
    assert "publication_jobs" in inspect(engine).get_table_names()
    engine.dispose()


def test_programmatic_explicit_url_remains_isolated_from_environment(tmp_path, monkeypatch):
    from alembic.config import Config

    from alembic import command

    explicit = tmp_path / "programmatic.db"
    unexpected = tmp_path / "environment.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{unexpected.as_posix()}")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{explicit.as_posix()}")
    command.upgrade(config, "head")
    assert explicit.exists()
    assert not unexpected.exists()
