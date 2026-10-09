"""Opt-in reviewer configuration using actual Compose CLI, without daemon."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("docker") is None, reason="Compose CLI unavailable")
def test_reviewer_secret_mount_is_api_only_explicit_and_default_disabled(tmp_path):
    environment = tmp_path / "synthetic.env"
    environment.write_text(
        "POSTGRES_PASSWORD=synthetic-only\nDATABASE_URL=sqlite:///synthetic.db\n", encoding="ascii"
    )
    child = os.environ.copy()
    for name in tuple(child):
        if name.startswith("NEWSFLOW_ILLUSTRATION_REVIEW"):
            child.pop(name)
    child["NEWSFLOW_ENV_FILE"] = environment.as_posix()
    child["NEWSFLOW_MASTER_KEY_SOURCE"] = (tmp_path / "synthetic-master-source").as_posix()
    child["NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_SOURCE"] = (
        tmp_path / "uncreated-review-secret"
    ).as_posix()
    command = [
        "docker",
        "compose",
        "--env-file",
        str(environment),
        "-f",
        str(ROOT / "compose.yaml"),
    ]

    def config(override=False):
        args = command + (
            ["-f", str(ROOT / "compose.illustration-review.yaml")] if override else []
        )
        return subprocess.run(
            args + ["--profile", "dev", "--profile", "production", "config", "--format", "json"],
            env=child,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    default = config()
    assert default.returncode == 0
    assert (
        "NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE"
        not in json.loads(default.stdout)["services"]["api"]["environment"]
    )
    assert config(True).returncode != 0  # Explicit reviewer identity also required.
    child["NEWSFLOW_ILLUSTRATION_REVIEWER_ID"] = "17"
    enabled = config(True)
    assert enabled.returncode == 0, enabled.stderr
    parsed = json.loads(enabled.stdout)
    assert (
        parsed["services"]["api"]["environment"]["NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE"]
        == "/run/secrets/illustration_reviewer"
    )
    assert parsed["services"]["api"]["environment"]["NEWSFLOW_ILLUSTRATION_REVIEWER_ID"] == "17"
    assert any(s["source"] == "illustration_reviewer" for s in parsed["services"]["api"]["secrets"])
    for name, service in parsed["services"].items():
        if name != "api":
            assert all(s["source"] != "illustration_reviewer" for s in service.get("secrets", []))
    assert not (tmp_path / "uncreated-review-secret").exists()
