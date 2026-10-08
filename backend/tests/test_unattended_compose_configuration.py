"""Read-only real Compose CLI characterization; never contact a Docker daemon."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("docker") is None, reason="Compose CLI unavailable")
def test_scoped_host_migration_url_does_not_rebind_packaged_compose_database(tmp_path):
    environment = tmp_path / "synthetic.env"
    key = tmp_path / "synthetic-key"
    key.write_text("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", encoding="utf-8")
    environment.write_text(
        "POSTGRES_DB=newsflow_unattended_ci\n"
        "POSTGRES_USER=newsflow_fixture\n"
        "POSTGRES_PASSWORD=synthetic-unattended-ci-only\n"
        "DATABASE_URL=postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@postgres:5432/newsflow_unattended_ci\n"
        f"NEWSFLOW_ENV_FILE={environment.as_posix()}\n"
        f"NEWSFLOW_MASTER_KEY_SOURCE={key.as_posix()}\n",
        encoding="utf-8",
    )
    child = os.environ.copy()
    child["DATABASE_URL"] = (
        "postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@127.0.0.1:5432/"
        "newsflow_unattended_ci?options=-csearch_path%3Dunattended_" + "a" * 32
    )
    # The fixture owns the interpolation inputs; do not read operational .env.
    child["NEWSFLOW_ENV_FILE"] = environment.as_posix()
    child["NEWSFLOW_MASTER_KEY_SOURCE"] = key.as_posix()
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "newsflow-verification-unattended-config",
            "--env-file",
            str(environment),
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(ROOT / "compose.dev.yaml"),
            "--profile",
            "dev",
            "--profile",
            "production",
            "config",
            "--format",
            "json",
        ],
        env=child,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "Read-only synthetic Compose configuration failed"
    config = json.loads(result.stdout)
    for service in ("api", "worker", "migrations"):
        assert config["services"][service]["environment"]["DATABASE_URL"] == (
            "postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@postgres:5432/"
            "newsflow_unattended_ci"
        )
