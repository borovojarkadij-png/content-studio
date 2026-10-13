"""Real CLI parsing and provisioning with synthetic terminal/RPC boundaries."""

import asyncio
import importlib
import os
import subprocess
import sys
import warnings
from getpass import GetPassWarning
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from test_telegram_login import (
    KEY,
    PHONE,
    SESSION,
    Rpc,
    adapter,
    no_external_calls,  # noqa: F401 -- Reuse autouse network guard.
)

from alembic import command
from newsflow.migrate import runtime_migration_config
from newsflow.persistence.models import OutboxEventModel, TelegramAccount

ARGS = ["--enable-login", "--account-name", "Синтетический аккаунт", "--actor-id", "29"]


def test_explicit_cli_entrypoint_is_available():
    assert importlib.util.find_spec("newsflow.telegram_login") is not None


@pytest.fixture
def cli():
    return importlib.import_module("newsflow.telegram_login")


def forbidden(*args, **kwargs):
    pytest.fail("Guarded invocation touched configured runtime or private input")


@pytest.mark.parametrize(
    "args,status,output",
    [
        ([], 2, "LOGIN_DISABLED\n"),
        (["--phone", "private-phone"], 1, "LOGIN_FAILED\n"),
        (["--enable-login"], 1, "LOGIN_FAILED\n"),
        (ARGS + ["--password=private-password"], 1, "LOGIN_FAILED\n"),
        (ARGS[:-1] + ["private-invalid-actor"], 1, "LOGIN_FAILED\n"),
        (ARGS + ["--expected-user-id", "9223372036854775808"], 1, "LOGIN_FAILED\n"),
        (ARGS + ["--session", "private-session"], 1, "LOGIN_FAILED\n"),
        (ARGS + ["--code", "private-code"], 1, "LOGIN_FAILED\n"),
        (ARGS + ["--phone", "private-phone"], 1, "LOGIN_FAILED\n"),
        (ARGS + ["--actor-id", "0"], 1, "LOGIN_FAILED\n"),
        (["--enable-login", "--account-name", "a\n", "--actor-id", "29"], 1, "LOGIN_FAILED\n"),
    ],
)
def test_parse_refuses_without_runtime_or_argument_echo(
    cli, monkeypatch, capsys, args, status, output
):
    monkeypatch.setattr(cli, "_configured_service", forbidden)
    monkeypatch.setattr(cli.getpass, "getpass", forbidden)
    assert cli.main(args) == status
    captured = capsys.readouterr()
    assert captured.out + captured.err == output


def test_help_never_constructs_runtime(cli, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_configured_service", forbidden)
    assert cli.main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "--enable-login" in captured.out and captured.err == ""


@pytest.mark.parametrize("stdin_tty,stderr_tty", [(False, False), (False, True), (True, False)])
def test_non_tty_refuses_before_runtime(cli, monkeypatch, capsys, stdin_tty, stderr_tty):
    monkeypatch.setattr(
        cli,
        "sys",
        SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: stdin_tty),
            stderr=SimpleNamespace(isatty=lambda: stderr_tty),
        ),
    )
    monkeypatch.setattr(cli, "_configured_service", forbidden)
    assert cli.main(ARGS) == 1
    captured = capsys.readouterr()
    assert captured.out + captured.err == "LOGIN_FAILED\n"


@pytest.fixture
def configured(cli, tmp_path, monkeypatch, capsys):
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(runtime_migration_config(), "head")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    master = tmp_path / "master"
    master.write_text(KEY, encoding="utf-8")
    credentials = tmp_path / "credentials"
    credentials.write_text('{"api_id":123,"api_hash":"' + "a" * 32 + '"}', encoding="utf-8")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://synthetic:private-url@localhost/synthetic"
    )
    monkeypatch.setenv("NEWSFLOW_MASTER_KEY_FILE", str(master))
    monkeypatch.setenv("NEWSFLOW_TELEGRAM_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setattr(
        cli,
        "sys",
        SimpleNamespace(
            stdin=SimpleNamespace(isatty=lambda: True), stderr=SimpleNamespace(isatty=lambda: True)
        ),
    )
    monkeypatch.setattr("newsflow.persistence.database.configured_session_factory", lambda: factory)
    rpc = Rpc()
    monkeypatch.setattr(
        "newsflow.providers.telegram_login.TelethonLoginAdapter", lambda *a: adapter(rpc)
    )
    values = iter([PHONE, "12345", "synthetic-only-password"])
    reads = []

    def masked(prompt, **kwargs):
        reads.append(prompt)
        return next(values)

    monkeypatch.setattr(cli.getpass, "getpass", masked)
    yield factory, rpc, reads, master, credentials
    engine.dispose()


@pytest.mark.parametrize("two_factor", [False, True])
def test_real_service_one_attempt_saves_unicode_and_private_output(
    cli, configured, capsys, caplog, tmp_path, two_factor
):
    factory, rpc, reads, _, _ = configured
    files_before = set(tmp_path.iterdir())
    rpc.two_factor = two_factor
    assert cli.main(ARGS + ["--expected-user-id", "1001"]) == 0
    captured = capsys.readouterr()
    assert captured.out + captured.err == "LOGIN_SAVED account_id=1\n"
    assert len(reads) == (3 if two_factor else 2)
    assert rpc.calls.count("send_code") == rpc.calls.count("code") == 1
    assert rpc.calls.count("password") == int(two_factor)
    assert not caplog.text
    with factory() as session:
        row = session.get(TelegramAccount, 1)
        assert row.name == "Синтетический аккаунт" and row.encrypted_session != SESSION
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 1
    prior_calls = list(rpc.calls)
    assert cli.main(ARGS) == 1
    assert rpc.calls == prior_calls
    assert len(reads) == (3 if two_factor else 2)  # Repeat refuses before phone.
    assert capsys.readouterr().out == "LOGIN_FAILED\n"
    assert set(tmp_path.iterdir()) == files_before


@pytest.mark.parametrize(
    "url",
    [
        "",
        "private-invalid-url",
        "sqlite:///private.db",
        "postgresql://role@host/db",
        "postgresql+psycopg://host/db",
        "postgresql+psycopg://role@host/",
    ],
)
def test_bad_database_url_refuses_before_factory_or_input(
    cli, configured, monkeypatch, capsys, url
):
    _, rpc, reads, _, _ = configured
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr("newsflow.persistence.database.configured_session_factory", forbidden)
    assert cli.main(ARGS) == 1
    captured = capsys.readouterr()
    assert captured.out + captured.err == "LOGIN_FAILED\n"
    assert reads == rpc.calls == []


@pytest.mark.parametrize(
    "secret", ["NEWSFLOW_MASTER_KEY_FILE", "NEWSFLOW_TELEGRAM_CREDENTIALS_FILE"]
)
@pytest.mark.parametrize("failure", ["absent", "missing", "invalid"])
def test_secret_prerequisites_refuse_before_input_or_rpc(
    cli, configured, monkeypatch, capsys, secret, failure
):
    _, rpc, reads, master, credentials = configured
    if failure == "absent":
        monkeypatch.delenv(secret)
    elif failure == "missing":
        monkeypatch.setenv(secret, "private-nonexistent-path")
    else:
        (master if secret.endswith("KEY_FILE") else credentials).write_text(
            "private-invalid-secret"
        )
    assert cli.main(ARGS) == 1
    captured = capsys.readouterr()
    assert captured.out + captured.err == "LOGIN_FAILED\n"
    assert reads == rpc.calls == []


@pytest.mark.parametrize("heads", [[], ["old-head"], ["wrong-head"], ["a", "b"]])
def test_schema_refuses_before_input_or_rpc(cli, configured, monkeypatch, capsys, heads):
    _, rpc, reads, _, _ = configured
    monkeypatch.setattr(
        "alembic.runtime.migration.MigrationContext.get_current_heads", lambda _: heads
    )
    assert cli.main(ARGS) == 1
    assert capsys.readouterr().out == "LOGIN_FAILED\n"
    assert reads == rpc.calls == []


@pytest.mark.parametrize("stage", ["phone", "code", "password"])
@pytest.mark.parametrize(
    "error", [EOFError, KeyboardInterrupt, asyncio.CancelledError, GetPassWarning]
)
def test_masking_failure_or_abort_never_saves(cli, configured, monkeypatch, capsys, stage, error):
    factory, rpc, _, _, _ = configured
    rpc.two_factor = True
    values = iter([PHONE, "12345", "synthetic-only-password"])
    counter = []

    def masked(prompt, **kwargs):
        current = ["phone", "code", "password"][len(counter)]
        counter.append(current)
        if current == stage:
            if error is GetPassWarning:
                warnings.warn("private-masking-warning", GetPassWarning)
            else:
                raise error("private-abort")
        return next(values)

    monkeypatch.setattr(cli.getpass, "getpass", masked)
    assert cli.main(ARGS) != 0
    expected = "LOGIN_FAILED\n" if error is GetPassWarning else "LOGIN_CANCELLED\n"
    captured = capsys.readouterr()
    assert captured.out + captured.err == expected
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(TelegramAccount)) == 0
        assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 0
    assert rpc.calls.count("send_code") == (0 if stage == "phone" else 1)


@pytest.mark.parametrize("stage", ["sql", "sdk", "configuration"])
def test_secret_bearing_exceptions_are_sanitized(
    cli, configured, monkeypatch, capsys, caplog, stage
):
    _, rpc, _, _, _ = configured

    def fail(*args, **kwargs):
        raise RuntimeError("private-phone-code-password-session-db-url")

    if stage == "sql":
        monkeypatch.setattr("sqlalchemy.orm.Session.connection", fail)
    elif stage == "sdk":
        rpc.stage, rpc.failure = "send_code", RuntimeError("private-sdk-session")
    else:
        monkeypatch.setattr(
            "newsflow.services.telegram_provider_factory.load_telegram_credentials", fail
        )
    assert cli.main(ARGS) == 1
    captured = capsys.readouterr()
    assert captured.out + captured.err == "LOGIN_FAILED\n"
    assert not caplog.text


def test_actual_getpass_fallback_stops_before_echoed_input(cli, configured, monkeypatch, capsys):
    _, rpc, reads, _, _ = configured
    monkeypatch.setattr(cli.getpass, "getpass", cli.getpass.fallback_getpass)
    monkeypatch.setattr(cli.getpass, "_raw_input", forbidden)
    assert cli.main(ARGS) == 1
    captured = capsys.readouterr()
    assert captured.out + captured.err == "LOGIN_FAILED\n"
    assert reads == rpc.calls == []


@pytest.mark.parametrize(
    "args,exit_code,status",
    [([], 2, "LOGIN_DISABLED"), (["--help"], 0, None), (ARGS, 1, "LOGIN_FAILED")],
)
def test_real_module_subprocess_zero_io_sentinels(tmp_path, args, exit_code, status):
    root = Path(__file__).resolve().parents[1]
    master, credentials, database = [tmp_path / name for name in ("master", "credentials", "db")]
    for file in (master, credentials, database):
        file.write_bytes(b"private-sentinel")
    before = {file: file.read_bytes() for file in (master, credentials, database)}
    env = dict(
        os.environ,
        PYTHONPATH=str(root / "src"),
        DATABASE_URL=f"sqlite:///{database}",
        NEWSFLOW_MASTER_KEY_FILE=str(master),
        NEWSFLOW_TELEGRAM_CREDENTIALS_FILE=str(credentials),
    )
    guard = (
        "import runpy,socket,sys; "
        "sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); "
        "socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network')); "
        "socket.create_connection=socket.socket.connect; "
        "sys.argv=['newsflow.telegram_login',*sys.argv[1:]]; "
        "runpy.run_module('newsflow.telegram_login',run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", guard, *args],
        check=False,
        env=env,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == exit_code
    assert result.stderr == ""
    assert (result.stdout == status + "\n") if status else "--enable-login" in result.stdout
    assert {file: file.read_bytes() for file in before} == before
    assert set(tmp_path.iterdir()) == set(before)
