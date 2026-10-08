"""Run the real PowerShell crash barrier against controlled Docker observations."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "newsflow-verification-crash-barrier-test"
CONTAINER = "a" * 64


@pytest.mark.parametrize(
    "scenario",
    [
        "delayed_exit",
        "cold_delayed_exit",
        "foreign",
        "missing",
        "kill_failed",
        "inspect_failed",
        "wrong_exit",
        "timeout",
        "late_inspect",
    ],
)
def test_actual_crash_barrier_waits_for_original_exit_and_refuses_invalid_targets(
    tmp_path, scenario
):
    # Removing the fresh post-kill reads must fail delayed_exit: Compose must not
    # resume while Docker still reports running. No real container/daemon is used.
    # Ordering is not a one-second cold PowerShell/JIT performance requirement.
    # Keep the real default budget for state cases, and one second ONLY for the
    # timeout/late-success regressions. Slow initial inspection exercises this
    # distinction without weakening the actual helper or skipping a boundary.
    timeout_seconds = 1 if scenario in {"timeout", "late_inspect"} else 30
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
$script:completedObservation = ''
function Invoke-VerificationDocker {{
    param([string[]]$Arguments, [int]$TimeoutMilliseconds)
    if ($TimeoutMilliseconds -lt 1 -or $TimeoutMilliseconds -gt {timeout_seconds * 1000}) {{ throw 'Invalid command deadline' }}
    $operation = $Arguments -join ' '
    if ($operation -eq 'ps -aq --no-trunc --filter label=com.docker.compose.project={PROJECT} --filter label=com.docker.compose.service=postgres') {{
        if ('{scenario}' -ne 'missing') {{ Write-Output '{CONTAINER}' }}
    }} elseif ($operation -eq 'inspect {CONTAINER}') {{
        if ('{scenario}' -eq 'cold_delayed_exit') {{ Start-Sleep -Milliseconds 1200 }}
        Get-Content -LiteralPath '{observed}' -Raw
    }} elseif ($operation -eq 'kill -s SIGKILL {CONTAINER}') {{
        if ('{scenario}' -eq 'foreign') {{ throw 'Foreign target mutated' }}
        $script:killed = $true
        if ('{scenario}' -eq 'kill_failed') {{ throw 'Controlled kill failure' }}
    }} elseif ($operation -eq 'inspect -f {{{{json .State}}}} {CONTAINER}') {{
        if (-not $script:killed) {{ throw 'Observation made before crash' }}
        $script:reads++
        if ('{scenario}' -eq 'late_inspect') {{
            Start-Sleep -Milliseconds 1200
            $script:completedObservation = 'LATE_EXIT_OBSERVATION_COMPLETED'
            Write-Output '{{"Status":"exited","Running":false,"ExitCode":137}}'
            return
        }}
        if ('{scenario}' -eq 'inspect_failed') {{ throw 'Controlled inspect failure' }}
        if ($script:reads -lt 3 -or '{scenario}' -eq 'timeout') {{
            $script:completedObservation = 'RUNNING_EXIT_OBSERVATION_COMPLETED'
            Write-Output '{{"Status":"running","Running":true,"ExitCode":0}}'
        }} else {{
            $exitCode = if ('{scenario}' -eq 'wrong_exit') {{ 0 }} else {{ 137 }}
            Write-Output ( '{{"Status":"exited","Running":false,"ExitCode":' + $exitCode + '}}' )
        }}
    }} else {{ throw 'Unexpected Docker operation' }}
}}
if ('{scenario}' -in @('timeout', 'late_inspect')) {{
    # Prime only cmdlet/JSON initialization outside the targeted timing budget.
    # This is not a Docker observation and grants no state/permission.
    $null = Get-Content -LiteralPath '{observed}' -Raw | ConvertFrom-Json
}}
try {{
    Invoke-SyntheticPostgresCrash -ComposeArgs @('compose', '-p', '{PROJECT}') -TimeoutSeconds {timeout_seconds}
}} catch {{
    # A pre-kill timeout must NOT satisfy a post-kill late-result/loop regression.
    if ($script:killed -and $script:reads -gt 0 -and $script:completedObservation) {{
        Write-Output $script:completedObservation
    }}
    throw
}}
if ($script:reads -ne 3 -or -not $script:killed) {{ throw 'Crash barrier returned before exit' }}
Write-Output 'ORIGINAL_EXIT_VERIFIED'
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    if scenario in {"delayed_exit", "cold_delayed_exit"}:
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
            "late_inspect": "Synthetic PostgreSQL exit barrier timed out",
        }[scenario]
        assert expected in result.stderr
        if scenario == "late_inspect":
            assert result.stdout.strip() == "LATE_EXIT_OBSERVATION_COMPLETED"
        elif scenario == "timeout":
            assert result.stdout.strip() == "RUNNING_EXIT_OBSERVATION_COMPLETED"


@pytest.mark.parametrize("project", ["newsflow", "", "newsflow-verification-x; whoami"])
def test_crash_barrier_refuses_operational_project_before_any_docker_call(project):
    common = str(ROOT / "scripts/verification-postgres-crash.ps1").replace("'", "''")
    code = f"""
$ErrorActionPreference = 'Stop'
. '{common}'
function Invoke-VerificationDocker {{ throw 'Unexpected Docker access' }}
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


@pytest.mark.parametrize("scenario", ["success", "blocked", "failure"])
def test_real_verification_process_deadline_and_redaction(scenario):
    common = str(ROOT / "scripts/verification-postgres-crash.ps1").replace("'", "''")
    executable = sys.executable.replace("'", "''")
    child = {
        "success": 'print("bounded-result")',
        "blocked": 'import time; print("private-child-output", flush=True); time.sleep(5)',
        "failure": 'import sys; print("private-child-output"); sys.exit(7)',
    }[scenario]
    timeout = 200 if scenario == "blocked" else 3000
    code = f"""
$ErrorActionPreference = 'Stop'
. '{common}'
$result = Invoke-VerificationProcess -FilePath '{executable}' -Arguments @('-c', '{child}') -TimeoutMilliseconds {timeout}
Write-Output $result
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if scenario == "success":
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "bounded-result"
    else:
        assert result.returncode != 0
        expected = "timed out" if scenario == "blocked" else "command failed"
        assert expected in result.stderr
        assert "private-child-output" not in result.stdout + result.stderr


def test_docker_wrapper_selects_one_application_when_resolution_has_multiple_matches():
    common = str(ROOT / "scripts/verification-postgres-crash.ps1").replace("'", "''")
    executable = sys.executable.replace("'", "''")
    code = f"""
$ErrorActionPreference = 'Stop'
. '{common}'
function Get-Command {{
    [pscustomobject]@{{ Source='{executable}' }}
    [pscustomobject]@{{ Source='nonexistent-secondary-application' }}
}}
Invoke-VerificationDocker -Arguments @('-c', 'print("first-application-result")') -TimeoutMilliseconds 3000
"""
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "first-application-result"
