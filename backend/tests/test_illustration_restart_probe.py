"""Probe manifest refusal, original-row reopen and configured fake transport contracts."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def probe():
    path = ROOT / "scripts/docker_illustration_probe.py"
    assert path.exists(), "Standalone illustration restart probe is not implemented"
    spec = importlib.util.spec_from_file_location("illustration_probe", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///newsflow_illustration_ci",
        "postgresql+psycopg://real:private@postgres:5432/newsflow_illustration_ci",
        "postgresql+psycopg://newsflow_fixture:synthetic-illustration-ci-only@production:5432/newsflow_illustration_ci",
        "postgresql+psycopg://newsflow_fixture:synthetic-illustration-ci-only@postgres:5432/newsflow_illustration_ci?options=-csearch_path=public",
    ],
)
def test_probe_refuses_complete_unsafe_database_identity_before_engine(monkeypatch, url):
    module = probe()
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_FIXTURE", "1")
    monkeypatch.setenv("DATABASE_URL", url)
    calls = []
    monkeypatch.setattr(module, "create_engine", lambda _: calls.append("engine"))
    with pytest.raises(ValueError):
        module.main("seed")
    assert calls == []


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"version": True},
        {"version": 1, "owner": "foreign"},
        {"version": 1, "owner": "content-studio-illustration-v1", "cases": []},
    ],
)
def test_corrupt_or_foreign_row_manifest_is_refused(value):
    with pytest.raises(ValueError):
        probe().validate_manifest(value)


def test_original_sql_reopen_and_fake_photo_receipt_use_authenticated_http(tmp_path, monkeypatch):
    """Dropping persisted bindings/audit or resending abandoned work must fail."""
    import json
    import socket
    import threading
    from datetime import UTC, datetime, timedelta

    import uvicorn
    from alembic.config import Config
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    from alembic import command
    from newsflow.app import app
    from newsflow.security.session_cipher import SessionCipher

    module = probe()
    database = f"sqlite:///{(tmp_path / 'original.db').as_posix()}"
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend/alembic"))
    monkeypatch.setenv("DATABASE_URL", database)
    command.upgrade(config, "head")
    media = tmp_path / "media"
    media.mkdir()
    secret = tmp_path / "reviewer"
    secret.write_text(module.TOKEN)
    monkeypatch.setenv("NEWSFLOW_MEDIA_ROOT", str(media))
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE", str(secret))
    monkeypatch.setenv("NEWSFLOW_ILLUSTRATION_REVIEWER_ID", "17")
    engine = create_engine(database)
    factory = sessionmaker(engine)
    monkeypatch.setattr("newsflow.persistence.database.configured_session_factory", lambda: factory)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    import time

    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    original_urlopen = module.urlopen

    def local_open(request, **kwargs):
        request.full_url = request.full_url.replace("http://api:8000", f"http://127.0.0.1:{port}")
        return original_urlopen(request, **kwargs)

    monkeypatch.setattr(module, "urlopen", local_open)
    cipher, now = SessionCipher(module.MASTER), datetime.now(UTC)
    try:
        module.seed(factory, media, cipher, now)
        manifest = json.loads((media / module.FILE).read_text())
        module.invalidate(factory, media, manifest, now)
        engine.dispose()
        reopened = create_engine(database)
        factory = sessionmaker(reopened)
        # This verification mode must issue no database writes on either reopen.
        writes = []
        event.listen(
            reopened,
            "before_cursor_execute",
            lambda _c, _u, statement, _p, _x, _m: (
                writes.append(statement)
                if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}
                else None
            ),
        )
        module.verify(factory, media, cipher, manifest, final=False)
        module.verify(factory, media, cipher, manifest, final=False)
        assert writes == []
        client = module.SyntheticPhotoClient(
            factory, cipher, now, manifest["account"], manifest["cases"]["approved"]["photo_hash"]
        )
        execution = module.runner(factory, media, cipher, now + timedelta(minutes=2), client)
        assert [execution.run_next(now=now + timedelta(minutes=2)) for _ in range(4)] == [
            "SUCCEEDED",
            "BLOCKED",
            "BLOCKED",
            "IDLE",
        ]
        assert len(client.uploaded) == len(client.requests) == 1
        assert execution.run_next(now=now + timedelta(minutes=2)) == "IDLE"
        module.write_new(
            media,
            "illustration-result.json",
            module.result_manifest(factory, manifest),
        )
        writes.clear()
        module.verify(factory, media, cipher, manifest, final=True)
        module.verify(factory, media, cipher, manifest, final=True)
        assert writes == []
        with pytest.raises(ValueError, match="never reseed"):
            module.seed(factory, media, cipher, now)
        assert writes == []
        for damage in (True, "1", 0):
            changed = json.loads((media / module.FILE).read_text())
            changed["cases"]["approved"]["job"] = damage
            with pytest.raises(ValueError):
                module.validate_manifest(changed)
        for filename in ("illustration-invalidated.json", "illustration-result.json"):
            changed = json.loads((media / filename).read_text())
            changed["version"] = True
            with pytest.raises(ValueError):
                module.validate_aux(changed, result=filename == "illustration-result.json")
        reopened.dispose()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        engine.dispose()
