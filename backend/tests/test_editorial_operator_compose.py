"""Actual opt-in operator Compose rendering, with synthetic inputs and no daemon."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OPERATOR_SOURCE = "NEWSFLOW_EDITORIAL_OPERATOR_SECRET_SOURCE"
OPERATOR_ID = "NEWSFLOW_EDITORIAL_OPERATOR_ID"
OPERATOR_FILE = "NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE"
pytestmark = pytest.mark.skipif(shutil.which("docker") is None, reason="Compose CLI unavailable")


@pytest.fixture
def compose_inputs(tmp_path):
    environment = tmp_path / "synthetic.env"
    environment.write_text(
        "POSTGRES_PASSWORD=synthetic-only\nDATABASE_URL=sqlite:///synthetic.db\n", encoding="ascii"
    )
    child = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("NEWSFLOW_", "POSTGRES_"))
    }
    sources = {
        "newsflow_master_key": tmp_path / "uncreated-master-source",
        "editorial_operator": tmp_path / "uncreated-operator-source",
        "illustration_reviewer": tmp_path / "uncreated-reviewer-source",
    }
    child.update(
        NEWSFLOW_ENV_FILE=environment.as_posix(),
        NEWSFLOW_MASTER_KEY_SOURCE=sources["newsflow_master_key"].as_posix(),
        NEWSFLOW_EDITORIAL_OPERATOR_SECRET_SOURCE=sources["editorial_operator"].as_posix(),
        NEWSFLOW_EDITORIAL_OPERATOR_ID="29",
        NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_SOURCE=sources["illustration_reviewer"].as_posix(),
        NEWSFLOW_ILLUSTRATION_REVIEWER_ID="17",
    )
    return environment, child, sources


def render(inputs, profile, *, operator=True, reviewer=False):
    environment, child, _ = inputs
    command = [
        "docker",
        "compose",
        "--env-file",
        str(environment),
        "-f",
        str(ROOT / "compose.yaml"),
    ]
    if profile == "dev":
        command += ["-f", str(ROOT / "compose.dev.yaml")]
    if operator:
        command += ["-f", str(ROOT / "compose.editorial-operator.yaml")]
    if reviewer:
        command += ["-f", str(ROOT / "compose.illustration-review.yaml")]
    command += ["--profile", profile, "config", "--format", "json"]
    result = subprocess.run(
        command, env=child, capture_output=True, text=True, timeout=30, check=False
    )
    # Preserve native diagnostics and complete rendered synthetic JSON in pytest -s evidence.
    print("COMPOSE_COMMAND " + json.dumps(command))
    print(f"COMPOSE_NATIVE_EXIT {result.returncode}")
    print("COMPOSE_STDOUT_BEGIN\n" + result.stdout + "COMPOSE_STDOUT_END")
    print("COMPOSE_STDERR_BEGIN\n" + result.stderr + "COMPOSE_STDERR_END")
    return result


def mounts(service):
    return {item["source"] for item in service.get("secrets", [])}


def assert_sources_uncreated(inputs):
    assert all(not source.exists() for source in inputs[2].values())


@pytest.mark.parametrize("profile", ["dev", "production"])
def test_default_has_no_operator_dependency_even_with_external_inputs(compose_inputs, profile):
    result = render(compose_inputs, profile, operator=False)
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert "editorial_operator" not in parsed.get("secrets", {})
    for service in parsed["services"].values():
        assert "editorial_operator" not in mounts(service)
        assert not any(
            key.startswith("NEWSFLOW_EDITORIAL_OPERATOR_") for key in service.get("environment", {})
        )
    assert_sources_uncreated(compose_inputs)


@pytest.mark.parametrize("profile", ["dev", "production"])
@pytest.mark.parametrize("reviewer", [False, True])
def test_operator_mount_is_api_only_and_preserves_existing_secrets(
    compose_inputs, profile, reviewer
):
    result = render(compose_inputs, profile, reviewer=reviewer)
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    services = parsed["services"]
    api_environment = services["api"]["environment"]
    assert api_environment[OPERATOR_FILE] == "/run/secrets/editorial_operator"
    assert api_environment[OPERATOR_ID] == "29"
    assert (
        parsed["secrets"]["editorial_operator"]["file"]
        == compose_inputs[2]["editorial_operator"].as_posix()
    )
    assert {
        name for name, service in services.items() if "editorial_operator" in mounts(service)
    } == {"api"}
    assert any(
        item["source"] == "editorial_operator"
        and item["target"] == "/run/secrets/editorial_operator"
        for item in services["api"]["secrets"]
    )
    assert {
        name for name, service in services.items() if "newsflow_master_key" in mounts(service)
    } == {"api", "worker"}
    assert (
        parsed["secrets"]["newsflow_master_key"]["file"]
        == compose_inputs[2]["newsflow_master_key"].as_posix()
    )
    for name, service in services.items():
        environment = service.get("environment", {})
        assert OPERATOR_SOURCE not in environment
        assert compose_inputs[2]["editorial_operator"].as_posix() not in environment.values()
        assert all(
            volume.get("source") != compose_inputs[2]["editorial_operator"].as_posix()
            for volume in service.get("volumes", [])
        )
        if name != "api":
            assert not any(key.startswith("NEWSFLOW_EDITORIAL_OPERATOR_") for key in environment)
    if reviewer:
        assert {
            name for name, service in services.items() if "illustration_reviewer" in mounts(service)
        } == {"api"}
        assert (
            parsed["secrets"]["illustration_reviewer"]["file"]
            == compose_inputs[2]["illustration_reviewer"].as_posix()
        )
        assert (
            api_environment["NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE"]
            == "/run/secrets/illustration_reviewer"
        )
        assert api_environment["NEWSFLOW_ILLUSTRATION_REVIEWER_ID"] == "17"
    else:
        assert "illustration_reviewer" not in parsed["secrets"]
    assert_sources_uncreated(compose_inputs)


@pytest.mark.parametrize("profile", ["dev", "production"])
@pytest.mark.parametrize("setting", [OPERATOR_SOURCE, OPERATOR_ID])
@pytest.mark.parametrize("value", [None, ""], ids=["missing", "empty"])
def test_operator_override_refuses_missing_or_empty_inputs(compose_inputs, profile, setting, value):
    child = compose_inputs[1]
    if value is None:
        child.pop(setting)
    else:
        child[setting] = value
    result = render(compose_inputs, profile)
    assert result.returncode != 0
    assert setting in result.stderr
    assert not result.stdout.strip(), "Refused configuration must not acknowledge rendered JSON"
    assert_sources_uncreated(compose_inputs)
