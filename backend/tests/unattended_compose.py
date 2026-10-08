"""Opt-in test-only host controller; guarded script owns exact Compose targets."""

import re
import subprocess
from os import getenv
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from unattended_postgres import scoped_postgres_url, validate_postgres_target


def validated_restart_project():
    project = getenv("NEWSFLOW_UNATTENDED_RESTART_PROJECT")
    if project is None:
        return None
    if (
        len(project) > 64
        or re.fullmatch(r"newsflow-verification-unattended-[a-z0-9]+(?:-[a-z0-9]+)*", project)
        is None
    ):
        raise ValueError("Explicit isolated unattended restart project required")
    validate_postgres_target(getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL"))
    return project


def restart_stack_before_stage(raw):
    project = validated_restart_project()
    if project is None:
        return
    base = validate_postgres_target(getenv("NEWSFLOW_UNATTENDED_POSTGRES_URL"))
    try:
        url = make_url(raw)
    except (ArgumentError, ValueError, TypeError):
        raise ValueError("Original scoped synthetic PostgreSQL identity required") from None
    options = url.query.get("options")
    if not isinstance(options, str) or not options.startswith("-csearch_path="):
        raise ValueError("Original scoped synthetic PostgreSQL identity required")
    schema = options.removeprefix("-csearch_path=")
    if url != scoped_postgres_url(base.render_as_string(hide_password=False), schema):
        raise ValueError("Original scoped synthetic PostgreSQL identity required")
    script = Path(__file__).resolve().parents[2] / "scripts" / "restart-unattended.ps1"
    try:
        subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(script), "-Project", project, "-CrashRecovery"],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        raise RuntimeError(
            "Isolated full-stack restart failed; preserve fixture and inspect CI"
        ) from None
    print("Synthetic full-stack down/up and PostgreSQL crash boundary verified")
