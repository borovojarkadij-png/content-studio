import subprocess
from pathlib import Path

import pytest
from unattended_compose import restart_stack_before_stage, validated_restart_project
from unattended_postgres import scoped_postgres_url

BASE = "postgresql+psycopg://newsflow_fixture:synthetic-unattended-ci-only@127.0.0.1:5432/newsflow_unattended_ci"
PROJECT = "newsflow-verification-unattended-test"


def test_missing_restart_optin_never_touches_docker_or_database(monkeypatch):
    monkeypatch.delenv("NEWSFLOW_UNATTENDED_RESTART_PROJECT", raising=False)

    def forbidden(*_, **__):
        raise AssertionError("Disabled hook reached Docker")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert validated_restart_project() is None
    restart_stack_before_stage("sqlite:///synthetic.db")


@pytest.mark.parametrize(
    "project",
    [
        "",
        "newsflow",
        "newsflow-verification-ci",
        "newsflow-verification-unattended-../production",
        PROJECT + ";whoami",
    ],
)
def test_restart_hook_refuses_wrong_family_before_any_subprocess(monkeypatch, project):
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_RESTART_PROJECT", project)
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_POSTGRES_URL", BASE)
    with pytest.raises(ValueError):
        validated_restart_project()


@pytest.mark.parametrize(
    "url",
    [
        BASE,
        BASE.replace("newsflow_unattended_ci", "newsflow"),
        "sqlite:///fixture.db",
        BASE + "?options=-csearch_path%3Dpublic",
    ],
)
def test_restart_hook_requires_original_scoped_synthetic_sql_target(monkeypatch, url):
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_RESTART_PROJECT", PROJECT)
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_POSTGRES_URL", BASE)

    def forbidden(*_, **__):
        raise AssertionError("Invalid scoped target reached Docker")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(ValueError):
        restart_stack_before_stage(url)


def test_restart_hook_invokes_only_named_guarded_script_without_shell_or_reset(monkeypatch):
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_RESTART_PROJECT", PROJECT)
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_POSTGRES_URL", BASE)
    calls = []

    def controlled(args, **options):
        calls.append((args, options))
        return subprocess.CompletedProcess(args, 0, stdout="Synthetic completed", stderr="")

    monkeypatch.setattr(subprocess, "run", controlled)
    restart_stack_before_stage(
        scoped_postgres_url(BASE, "unattended_" + "a" * 32).render_as_string(hide_password=False)
    )
    args, options = calls[0]
    script = str(Path(__file__).resolve().parents[2] / "scripts" / "restart-unattended.ps1")
    assert args == ["pwsh", "-NoProfile", "-File", script, "-Project", PROJECT, "-CrashRecovery"]
    assert options == {"check": True, "capture_output": True, "text": True, "timeout": 300}


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.CalledProcessError(1, ["pwsh"], output="private-token"),
        subprocess.TimeoutExpired(["pwsh"], 300, output="private-token"),
        FileNotFoundError("private-token"),
    ],
)
def test_failed_restart_is_a_failure_without_private_subprocess_output(monkeypatch, failure):
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_RESTART_PROJECT", PROJECT)
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_POSTGRES_URL", BASE)

    def unavailable(*_, **__):
        raise failure

    monkeypatch.setattr(subprocess, "run", unavailable)
    with pytest.raises(RuntimeError) as error:
        restart_stack_before_stage(
            scoped_postgres_url(BASE, "unattended_" + "a" * 32).render_as_string(
                hide_password=False
            )
        )
    assert "private-token" not in str(error.value)


@pytest.mark.parametrize(
    "stderr, expected",
    [
        ("Refusing a foreign service database. private-token", "SERVICE_DATABASE"),
        ("Network/provider workers must remain disabled. private-token", "NETWORK_FLAGS"),
        ("Original persistent media storage is missing or redirected.", "MEDIA_STORAGE"),
        ("private-token UNKNOWN_FAILURE", "UNKNOWN"),
    ],
)
def test_failed_restart_reports_only_known_guard_code(monkeypatch, stderr, expected):
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_RESTART_PROJECT", PROJECT)
    monkeypatch.setenv("NEWSFLOW_UNATTENDED_POSTGRES_URL", BASE)

    def failed(*_, **__):
        raise subprocess.CalledProcessError(1, ["pwsh"], output="private-token", stderr=stderr)

    monkeypatch.setattr(subprocess, "run", failed)
    with pytest.raises(RuntimeError) as error:
        restart_stack_before_stage(
            scoped_postgres_url(BASE, "unattended_" + "a" * 32).render_as_string(
                hide_password=False
            )
        )
    assert f"reason={expected}" in str(error.value)
    assert "private-token" not in str(error.value)
