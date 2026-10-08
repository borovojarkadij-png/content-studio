"""Opt-in test-only host controller; guarded script owns exact Compose targets."""

import re
import subprocess
from os import getenv
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from unattended_postgres import scoped_postgres_url, validate_postgres_target

# Only fixed policy codes may cross the captured subprocess boundary. Never
# print raw Compose output, paths, environment values or private exception text.
GUARD_CODES = {
    "Original persistent media storage is missing or redirected.": "MEDIA_STORAGE",
    "Original fixture ownership/config/key is missing or redirected; never recreate it.": "OWNERSHIP_FILES",
    "Invalid fixture ownership": "OWNERSHIP",
    "Invalid original fixture ports.": "PORTS",
    "Unexpected key; never replace or mount a real key.": "KEY",
    "Could not validate isolated Compose configuration.": "CONFIG",
    "Refusing unexpected full-stack services.": "SERVICES",
    "Refusing a non-synthetic database/volume target.": "DATABASE_VOLUME",
    "Refusing foreign PostgreSQL storage.": "POSTGRES_STORAGE",
    "Refusing a foreign service database.": "SERVICE_DATABASE",
    "Network/provider workers must remain disabled.": "NETWORK_FLAGS",
    "Refusing a foreign master key mount.": "KEY_MOUNT",
    "Refusing foreign media storage.": "MEDIA_MOUNT",
    "Explicit loopback synthetic PostgreSQL port required.": "POSTGRES_PORT",
    "Isolated Compose failed with exit code": "COMPOSE_COMMAND",
    "Isolated production proxy health failed after restart.": "PROXY_HEALTH",
}


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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        reason, location = "UNKNOWN", "UNKNOWN"
        if isinstance(error, subprocess.CalledProcessError) and isinstance(error.stderr, str):
            plain = re.sub(r"\x1b\[[0-9;]*m", "", error.stderr)
            reason = next((code for phrase, code in GUARD_CODES.items() if phrase in plain), reason)
            if isinstance(error.stdout, str):
                marker = re.search(
                    r"^UNATTENDED_FAILURE stage=(CONTEXT|OWNERSHIP|DOWN|UP|REDIS_WORKER|"
                    r"POSTGRES_CRASH|POSTGRES_RECOVERY|HEALTH) line=([0-9]{1,5})$",
                    error.stdout,
                    re.MULTILINE,
                )
                if marker:
                    location = f"{marker[1]}:{marker[2]}"
        elif isinstance(error, subprocess.TimeoutExpired):
            reason = "TIMEOUT"
        elif isinstance(error, OSError):
            reason = "PROCESS_UNAVAILABLE"
        raise RuntimeError(
            f"Isolated full-stack restart failed; reason={reason}; location={location}; "
            "preserve fixture and inspect CI"
        ) from None
    print("Synthetic full-stack down/up and PostgreSQL crash boundary verified")
