"""Execute real PowerShell policy; replace only read-only Docker config boundary."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "newsflow-verification-unattended-test"
URL = "postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@postgres:5432/newsflow_unattended_ci"
FLAGS = (
    "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
    "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
    "NEWSFLOW_REWRITE_ENABLED",
    "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
    "NEWSFLOW_INTERNET_MEDIA_ENABLED",
    "NEWSFLOW_SOURCE_PHOTO_ENABLED",
    "NEWSFLOW_PUBLICATION_ENABLED",
)


def quoted(path):
    return "'" + str(path).replace("'", "''") + "'"


@pytest.mark.parametrize(
    "change",
    [
        None,
        "version_bool",
        "owner",
        "key",
        "database",
        "network",
        "foreign_url",
        "volume",
        "external",
        "media",
        "extra_service",
    ],
)
def test_actual_powershell_ownership_and_configuration_policy_is_read_only_and_fail_closed(
    tmp_path, change
):
    media = tmp_path / "media"
    media.mkdir()
    key = tmp_path / "synthetic-master-key"
    key.write_text(
        "private-key-do-not-print"
        if change == "key"
        else "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        encoding="utf-8",
    )
    owner = {
        "version": 1,
        "owner": "content-studio-unattended-v1",
        "project": PROJECT,
        "nonce": "a" * 32,
        "api_port": 18032,
        "web_port": 15199,
        "production_port": 18132,
    }
    if change == "version_bool":
        owner["version"] = True
    if change == "owner":
        owner["project"] = "newsflow"
    ownership = tmp_path / "ownership.json"
    ownership.write_text(json.dumps(owner), encoding="utf-8")
    env, override = tmp_path / "test.env", tmp_path / "compose.override.yaml"
    env.write_text("synthetic fixture only", encoding="utf-8")
    override.write_text("synthetic fixture only", encoding="utf-8")
    config = {
        "name": PROJECT,
        "services": {
            name: {}
            for name in (
                "api",
                "worker",
                "migrations",
                "postgres",
                "redis",
                "web",
                "web-production",
            )
        },
        "secrets": {"newsflow_master_key": {"file": str(key)}},
        "volumes": {"postgres_data": {"name": PROJECT + "_postgres_data", "external": False}},
    }
    for name in ("api", "worker", "migrations"):
        config["services"][name]["environment"] = {"DATABASE_URL": URL} | dict.fromkeys(FLAGS, "0")
    for name in ("api", "worker"):
        config["services"][name]["volumes"] = [
            {
                "type": "bind",
                "source": str(media),
                "target": "/var/lib/newsflow/media",
                "read_only": name == "api",
            }
        ]
    config["services"]["postgres"] = {
        "image": "postgres:16-alpine",
        "environment": {
            "POSTGRES_DB": "newsflow_unattended_ci",
            "POSTGRES_USER": "newsflow_fixture",
            "POSTGRES_PASSWORD": "synthetic-unattended-ci-only",
        },
        "volumes": [
            {"type": "volume", "source": "postgres_data", "target": "/var/lib/postgresql/data"}
        ],
        "ports": [{"host_ip": "127.0.0.1", "published": "5432", "target": 5432}],
    }
    if change == "database":
        config["services"]["postgres"]["environment"]["POSTGRES_DB"] = "production"
    elif change == "network":
        config["services"]["worker"]["environment"][FLAGS[-1]] = "1"
    elif change == "foreign_url":
        config["services"]["api"]["environment"]["DATABASE_URL"] = (
            "postgresql://private-credential-never-print@production/db"
        )
    elif change == "volume":
        config["volumes"]["postgres_data"]["name"] = "production_pgdata"
    elif change == "external":
        config["volumes"]["postgres_data"]["external"] = True
    elif change == "media":
        config["services"]["worker"]["volumes"][0]["source"] = str(tmp_path / "foreign-media")
    elif change == "extra_service":
        config["services"]["unexpected"] = {"image": "untrusted"}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    code = f"""
. {quoted(ROOT / "scripts/unattended-compose-common.ps1")}
function docker {{
    if (($args -join ' ') -notmatch 'config --format json$') {{ throw 'Unexpected Docker mutation' }}
    & python -c 'pass'
    Get-Content -LiteralPath {quoted(config_path)} -Raw
}}
$fixtureContext = [pscustomobject]@{{ Project='{PROJECT}'; Ownership={quoted(ownership)};
    EnvFile={quoted(env)}; Override={quoted(override)}; Key={quoted(key)}; Media={quoted(media)};
    ComposeArgs=@('compose', '-p', '{PROJECT}') }}
$null = Assert-UnattendedOwnership $fixtureContext
Write-Output 'VALIDATED'
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if change is None:
        assert result.returncode == 0 and result.stdout.strip() == "VALIDATED", result.stderr
    else:
        assert result.returncode != 0 and "VALIDATED" not in result.stdout
    assert "private-key-do-not-print" not in result.stdout + result.stderr
    assert "private-credential-never-print" not in result.stdout + result.stderr


@pytest.mark.parametrize("script", ["verify-unattended.ps1", "restart-unattended.ps1"])
def test_actual_script_refuses_operational_project_before_docker(script):
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(ROOT / "scripts" / script), "-Project", "newsflow"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "dedicated isolated unattended project family" in result.stderr


def test_actual_restart_requires_retained_ownership_before_docker():
    project = "newsflow-verification-unattended-" + uuid4().hex[:20]
    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-File",
            str(ROOT / "scripts/restart-unattended.ps1"),
            "-Project",
            project,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "missing or redirected" in result.stderr


def test_all_actual_unattended_scripts_parse_without_execution():
    names = ("unattended-compose-common.ps1", "verify-unattended.ps1", "restart-unattended.ps1")
    for name in names:
        code = f"$t=$null; $e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile({quoted(ROOT / 'scripts' / name)},[ref]$t,[ref]$e); if($e.Count) {{ $e; exit 1 }}"
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", code],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
