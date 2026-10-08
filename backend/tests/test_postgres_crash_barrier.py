"""Run the real PowerShell crash barrier against controlled Docker observations."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "newsflow-verification-crash-barrier-test"
CONTAINER = "a" * 64


@pytest.mark.parametrize(
    "scenario",
    [
        "delayed_exit",
        "foreign",
        "missing",
        "kill_failed",
        "inspect_failed",
        "wrong_exit",
        "timeout",
    ],
)
def test_actual_crash_barrier_waits_for_original_exit_and_refuses_invalid_targets(
    tmp_path, scenario
):
    # Removing the fresh post-kill reads must fail delayed_exit: Compose must not
    # resume while Docker still reports running. No real container/daemon is used.
    observations = tmp_path / "observations.json"
    observations.write_text(
        json.dumps(
            {
                "Config": {
                    "Labels": {
                        "com.docker.compose.project": "newsflow"
                        if scenario == "foreign"
                        else PROJECT,
                        "com.docker.compose.service": "postgres",
                    }
                },
                "State": {"Status": "running", "Running": True},
            }
        ),
        encoding="utf-8",
    )
    common = str(ROOT / "scripts/verification-postgres-crash.ps1").replace("'", "''")
    observed = str(observations).replace("'", "''")
    code = f"""
$ErrorActionPreference = 'Stop'
. '{common}'
$script:reads = 0
$script:killed = $false
function docker {{
    $global:LASTEXITCODE = 0
    $operation = $args -join ' '
    if ($operation -eq 'compose -p {PROJECT} ps -a -q postgres') {{
        if ('{scenario}' -ne 'missing') {{ Write-Output '{CONTAINER}' }}
    }} elseif ($operation -eq 'inspect {CONTAINER}') {{
        Get-Content -LiteralPath '{observed}' -Raw
    }} elseif ($operation -eq 'compose -p {PROJECT} kill -s SIGKILL postgres') {{
        if ('{scenario}' -eq 'foreign') {{ throw 'Foreign target mutated' }}
        $script:killed = $true
        if ('{scenario}' -eq 'kill_failed') {{ $global:LASTEXITCODE = 1 }}
    }} elseif ($operation -eq 'inspect -f {{{{json .State}}}} {CONTAINER}') {{
        if (-not $script:killed) {{ throw 'Observation made before crash' }}
        $script:reads++
        if ('{scenario}' -eq 'inspect_failed') {{ $global:LASTEXITCODE = 1; return }}
        if ($script:reads -lt 3 -or '{scenario}' -eq 'timeout') {{
            Write-Output '{{"Status":"running","Running":true,"ExitCode":0}}'
        }} else {{
            $exitCode = if ('{scenario}' -eq 'wrong_exit') {{ 0 }} else {{ 137 }}
            Write-Output ( '{{"Status":"exited","Running":false,"ExitCode":' + $exitCode + '}}' )
        }}
    }} else {{ throw 'Unexpected Docker operation' }}
}}
Invoke-SyntheticPostgresCrash -ComposeArgs @('compose', '-p', '{PROJECT}') -TimeoutSeconds 1
if ($script:reads -ne 3 -or -not $script:killed) {{ throw 'Crash barrier returned before exit' }}
Write-Output 'ORIGINAL_EXIT_VERIFIED'
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if scenario == "delayed_exit":
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == "ORIGINAL_EXIT_VERIFIED"
    else:
        assert result.returncode != 0
        assert "ORIGINAL_EXIT_VERIFIED" not in result.stdout
        expected = {
            "foreign": "Refusing foreign PostgreSQL crash target",
            "missing": "Exact original PostgreSQL container required",
            "kill_failed": "Synthetic PostgreSQL kill failed",
            "inspect_failed": "Synthetic PostgreSQL exit observation failed",
            "wrong_exit": "Unexpected synthetic PostgreSQL termination",
            "timeout": "Synthetic PostgreSQL exit barrier timed out",
        }[scenario]
        assert expected in result.stderr


@pytest.mark.parametrize("project", ["newsflow", "", "newsflow-verification-x; whoami"])
def test_crash_barrier_refuses_operational_project_before_any_docker_call(project):
    common = str(ROOT / "scripts/verification-postgres-crash.ps1").replace("'", "''")
    code = f"""
$ErrorActionPreference = 'Stop'
. '{common}'
function docker {{ throw 'Unexpected Docker access' }}
Invoke-SyntheticPostgresCrash -ComposeArgs @('compose', '-p', '{project}')
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "Isolated verification project required" in result.stderr
    assert "Unexpected Docker access" not in result.stderr
