"""Owned illustration controller refusal boundaries; no Docker mutations in guards."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "newsflow-verification-illustration-test"


def controller():
    path = ROOT / "scripts/illustration_restart_controller.py"
    assert path.exists(), "Owned illustration restart controller is not implemented"
    spec = importlib.util.spec_from_file_location("illustration_controller", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sources(root):
    import shutil

    for name in ("compose.yaml", "compose.illustration-review.yaml"):
        shutil.copyfile(ROOT / name, root / name)


@pytest.mark.parametrize(
    "project",
    [
        "newsflow",
        "newsflow-verification-unattended-test",
        "../newsflow",
        "newsflow-verification-illustration-TEST",
    ],
)
def test_refuses_foreign_project_before_any_command_or_file_write(tmp_path, project):
    module = controller()
    calls = []
    with pytest.raises(ValueError):
        module.Fixture(tmp_path, project, run=lambda args: calls.append(args))
    assert calls == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "kind", ["containers", "networks", "labeled-volume", "unlabeled-volume", "port", "artifact"]
)
def test_create_refusal_has_zero_file_or_docker_mutation(tmp_path, kind):
    module = controller()
    calls = []

    def run(args):
        calls.append(args)
        assert args[0] in {"ps", "network", "volume"}
        if kind == "containers" and args[0] == "ps":
            return "a" * 64
        if kind == "networks" and args[0] == "network":
            return "a" * 64
        if kind == "labeled-volume" and args[:2] == ["volume", "ls"]:
            return "retained"
        if kind == "unlabeled-volume" and args == ["volume", "ls", "--format", "{{.Name}}"]:
            return PROJECT + "_media_data"
        return ""

    fixture = module.Fixture(tmp_path, PROJECT, run=run)
    sources(tmp_path)
    if kind == "artifact":
        fixture.directory.mkdir(parents=True)
        (fixture.directory / "original").write_text("retain")
    before = tuple(tmp_path.rglob("*"))
    with pytest.raises(ValueError):
        fixture.create((18237, 15394, 18337), port_free=lambda _: kind != "port")
    assert tuple(tmp_path.rglob("*")) == before
    assert all(args[0] != "compose" for args in calls)


@pytest.mark.parametrize("damage", ["bool", "foreign", "extra", "duplicate", "corrupt"])
def test_invalid_ownership_manifest_refuses_before_docker(tmp_path, damage):
    module = controller()
    calls = []
    fixture = module.Fixture(tmp_path, PROJECT, run=lambda args: calls.append(args))
    fixture.directory.mkdir(parents=True)
    value = {
        "version": 1,
        "owner": "content-studio-illustration-v1",
        "project": PROJECT,
        "ports": [18237, 15394, 18337],
    }
    if damage == "bool":
        value["version"] = True
    elif damage == "foreign":
        value["project"] = "newsflow"
    elif damage == "extra":
        value["redirect"] = "production"
    raw = json.dumps(value)
    if damage == "duplicate":
        raw = raw.replace('"version": 1', '"version": 1, "version": 1')
    if damage == "corrupt":
        raw = "{"
    fixture.file("ownership.json").write_text(raw)
    before = fixture.file("ownership.json").read_bytes()
    with pytest.raises(ValueError):
        fixture.validate()
    assert calls == [] and fixture.file("ownership.json").read_bytes() == before


def test_redirected_artifact_parent_refuses_without_touching_target(tmp_path):
    module = controller()
    target = tmp_path / "retained"
    target.mkdir()
    # Windows junctions need no developer-mode symlink permission.
    import subprocess

    result = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            f"New-Item -ItemType {'Junction' if sys.platform == 'win32' else 'SymbolicLink'} -Path '{tmp_path / '.artifacts'}' -Target '{target}' | Out-Null",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    calls = []
    with pytest.raises(ValueError):
        module.Fixture(tmp_path, PROJECT, run=lambda args: calls.append(args))
    assert calls == [] and list(target.iterdir()) == []


def owned_config(module, fixture):
    env = fixture.environment([18237, 15394, 18337])
    cfg = {
        "name": PROJECT,
        "volumes": {name: {"name": PROJECT + "_" + name} for name in module.VOLUMES},
        "services": {name: {} for name in module.SERVICES},
        "secrets": {
            name: {"file": str(fixture.file(filename))}
            for name, filename in (
                ("newsflow_master_key", "synthetic-master-key"),
                ("illustration_reviewer", "synthetic-reviewer"),
            )
        },
    }
    for name in ("api", "worker", "migrations"):
        expected = dict(env)
        if name in ("api", "worker"):
            expected.update(
                NEWSFLOW_MASTER_KEY_FILE="/run/secrets/newsflow_master_key",
                NEWSFLOW_MEDIA_ROOT="/var/lib/newsflow/media",
            )
        if name == "api":
            expected["NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE"] = (
                "/run/secrets/illustration_reviewer"
            )
        cfg["services"][name]["environment"] = expected
        cfg["services"][name]["command"] = {
            "api": [
                "python",
                "-m",
                "uvicorn",
                "newsflow.app:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            "worker": ["python", "-m", "newsflow.worker"],
            "migrations": ["python", "-m", "newsflow.migrate"],
        }[name]
        cfg["services"][name]["secrets"] = [
            {"source": item, "target": item}
            for item in (
                {"newsflow_master_key", "illustration_reviewer"}
                if name == "api"
                else {"newsflow_master_key"}
                if name == "worker"
                else set()
            )
        ]
    cfg["services"]["postgres"] = {
        "image": "postgres:16-alpine",
        "environment": {
            key: env[key] for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
        },
        "volumes": [
            {
                "type": "volume",
                "source": "postgres_data",
                "target": "/var/lib/postgresql/data",
                "volume": {},
            }
        ],
    }
    for name in ("api", "worker"):
        cfg["services"][name]["volumes"] = [
            {
                "type": "volume",
                "source": "media_data",
                "target": "/var/lib/newsflow/media",
                "read_only": name == "api",
            }
        ]
    cfg["services"]["worker"]["volumes"].append(
        {
            "type": "bind",
            "source": str(fixture.root / "scripts/docker_illustration_probe.py"),
            "target": "/opt/verification/docker_illustration_probe.py",
            "read_only": True,
        }
    )
    for name, target, port in (
        ("api", 8000, 18237),
        ("web", 5173, 15394),
        ("web-production", 80, 18337),
    ):
        cfg["services"][name]["ports"] = [
            {"target": target, "published": str(port), "host_ip": "127.0.0.1"}
        ]
    return cfg


@pytest.mark.parametrize(
    "damage",
    [
        None,
        "password",
        "role",
        "host",
        "query",
        "enabled",
        "api_reviewer",
        "worker_reviewer",
        "master_path",
        "secret_target",
        "media",
        "volume",
        "mixed_ports",
        "extra_service",
        "command",
        "host_network",
    ],
)
def test_restart_refuses_unsafe_resolved_configuration_before_mutation(tmp_path, damage):
    module = controller()
    calls = []
    fixture = module.Fixture(tmp_path, PROJECT, run=lambda args: "")
    sources(tmp_path)
    fixture.create([18237, 15394, 18337], port_free=lambda _: True)
    cfg = owned_config(module, fixture)
    if damage in {"password", "role", "host", "query"}:
        cfg["services"]["api"]["environment"]["DATABASE_URL"] = {
            "password": module.URL.replace("synthetic-illustration-ci-only", "private"),
            "role": module.URL.replace("newsflow_fixture", "production"),
            "host": module.URL.replace("@postgres:", "@remote:"),
            "query": module.URL + "?options=-csearch_path=live",
        }[damage]
    elif damage == "enabled":
        cfg["services"]["worker"]["environment"][module.FLAGS[-1]] = "1"
    elif damage == "api_reviewer":
        cfg["services"]["api"]["environment"]["NEWSFLOW_ILLUSTRATION_REVIEWER_ID"] = "18"
    elif damage == "worker_reviewer":
        cfg["services"]["worker"]["secrets"].append({"source": "illustration_reviewer"})
    elif damage == "master_path":
        cfg["secrets"]["newsflow_master_key"]["file"] = str(tmp_path / "private")
    elif damage == "secret_target":
        cfg["services"]["api"]["secrets"][0]["target"] = "private_key"
    elif damage == "media":
        cfg["services"]["worker"]["volumes"][0]["source"] = "operational"
    elif damage == "volume":
        cfg["volumes"]["postgres_data"]["name"] = "operational"
    elif damage == "mixed_ports":
        cfg["services"]["api"]["ports"].append(
            {"host_ip": "0.0.0.0", "published": "8000", "target": 8000}
        )
    elif damage == "extra_service":
        cfg["services"]["foreign"] = {}
    elif damage == "command":
        cfg["services"]["worker"]["command"] = ["curl", "https://remote"]
    elif damage == "host_network":
        cfg["services"]["worker"]["network_mode"] = "host"

    def read_only(args):
        calls.append(args)
        assert args[-3:] == ["config", "--format", "json"], "Guard crossed mutation boundary"
        return json.dumps(cfg)

    fixture.run = read_only
    before = {p: p.read_bytes() for p in fixture.directory.iterdir()}
    if damage is None:
        fixture.validate()
        fixture.validate()
    else:
        with pytest.raises(ValueError):
            fixture.action(["down"])
    assert {p: p.read_bytes() for p in fixture.directory.iterdir()} == before


def test_real_compose_render_accepts_owned_packaged_configuration_without_start(tmp_path):
    import shutil
    import subprocess

    module = controller()
    for name in ("compose.yaml", "compose.illustration-review.yaml"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    for name in ("backend", "frontend", "scripts"):
        (tmp_path / name).mkdir()
    fixture = module.Fixture(tmp_path, PROJECT, run=lambda args: "")
    fixture.create([18237, 15394, 18337], port_free=lambda _: True)

    def render(args):
        assert args[-3:] == ["config", "--format", "json"]
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, check=False, timeout=30
        )
        assert result.returncode == 0, "Read-only isolated Compose render failed"
        return result.stdout

    fixture.run = render
    fixture.validate()


def test_crash_refusal_cannot_call_helper_or_mutate_docker(tmp_path, monkeypatch):
    module = controller()
    calls = []
    fixture = module.Fixture(tmp_path, PROJECT, run=lambda args: (calls.append(args), "")[1])
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: calls.append("helper"))
    with pytest.raises(FileNotFoundError):
        fixture.crash()
    assert calls == []


@pytest.mark.parametrize(
    "key,value",
    [
        ("COMPOSE_PROJECT_NAME", "newsflow"),
        ("COMPOSE_FILE", "production.yaml"),
        ("COMPOSE_ENV_FILES", "private.env"),
        ("COMPOSE_PROFILES", "telegram"),
        ("DATABASE_URL", "postgresql://private@production/newsflow_illustration_ci"),
        ("POSTGRES_PASSWORD", "private"),
        ("NEWSFLOW_ENV_FILE", "private.env"),
        ("NEWSFLOW_MASTER_KEY_SOURCE", "private-key"),
        ("NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_SOURCE", "private-reviewer"),
        ("NEWSFLOW_ILLUSTRATION_REVIEWER_ID", "999"),
        ("NEWSFLOW_API_PORT", "8000"),
        ("NEWSFLOW_BIND_HOST", "0.0.0.0"),
        ("NEWSFLOW_PUBLICATION_ENABLED", "1"),
        ("NEWSFLOW_REWRITE_ENABLED", "1"),
        ("NEWSFLOW_TELEGRAM_INGESTION_ENABLED", "1"),
    ],
)
def test_inherited_unsafe_overrides_refuse_before_file_or_docker_mutation(
    tmp_path, monkeypatch, key, value
):
    module = controller()
    calls = []
    monkeypatch.setenv(key, value)
    fixture = module.Fixture(tmp_path, PROJECT, run=lambda args: (calls.append(args), "")[1])
    with pytest.raises(ValueError):
        fixture.create([18237, 15394, 18337], port_free=lambda _: True)
    assert calls == [] and list(tmp_path.iterdir()) == []
    assert module.os.environ[key] == value


@pytest.mark.parametrize(
    "source,damage",
    [
        ("compose.yaml", "build_context"),
        ("compose.yaml", "dockerfile"),
        ("compose.yaml", "image"),
        ("compose.illustration-review.yaml", "reviewer_file"),
    ],
)
def test_changed_compose_sources_refuse_before_any_fixture_write(tmp_path, source, damage):
    import shutil

    module = controller()
    for name in ("compose.yaml", "compose.illustration-review.yaml"):
        shutil.copyfile(ROOT / name, tmp_path / name)
    path = tmp_path / source
    original = path.read_text()
    changed = {
        "build_context": original.replace(
            "build: ./backend", "build: https://remote/context.git", 1
        ),
        "dockerfile": original.replace(
            "build: ./backend", "build:\n      context: ./backend\n      dockerfile: Foreignfile", 1
        ),
        "image": original.replace("build: ./backend", "image: remote/private:latest", 1),
        "reviewer_file": original.replace(
            "file: ${NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_SOURCE",
            "file: ${PRIVATE_REVIEWER_SOURCE",
            1,
        ),
    }[damage]
    path.write_text(changed)
    calls = []
    fixture = module.Fixture(tmp_path, PROJECT, run=lambda args: calls.append(args))
    with pytest.raises(ValueError):
        fixture.create([18237, 15394, 18337], port_free=lambda _: True)
    assert calls == [] and not fixture.directory.exists()
    assert path.read_text() == changed


@pytest.mark.parametrize(
    "source",
    [
        r"C:\Users\fixture\repo\frontend",
        "C:/Users/fixture/repo/frontend",
        "/run/desktop/mnt/host/c/Users/fixture/repo/frontend",
    ],
)
def test_exact_owned_windows_desktop_mount_alias_and_order_are_equivalent(source):
    module = controller()
    assert hasattr(module, "canonical_runtime"), (
        "Owned Docker Desktop mount comparison not implemented"
    )
    original = {
        "web": {
            "image": "sha256:" + "a" * 64,
            "environment": ["PUBLIC=0"],
            "mounts": [
                {
                    "Type": "bind",
                    "Source": r"C:\Users\fixture\repo\frontend",
                    "Destination": "/app",
                    "RW": True,
                    "Mode": "rw",
                },
                {
                    "Type": "volume",
                    "Name": PROJECT + "_frontend_node_modules",
                    "Source": "/var/lib/docker/volumes/owned/_data",
                    "Destination": "/app/node_modules",
                    "RW": True,
                },
            ],
        }
    }
    current = json.loads(json.dumps(original))
    current["web"]["mounts"][0]["Source"] = source
    current["web"]["mounts"].reverse()
    owned = {r"C:\Users\fixture\repo\frontend"}
    assert module.canonical_runtime(current, owned) == module.canonical_runtime(original, owned)
    assert original["web"]["mounts"][0]["Source"] == r"C:\Users\fixture\repo\frontend"


@pytest.mark.parametrize(
    "damage",
    [
        "/run/desktop/mnt/host/c/Users/fixture/repo/frontend-other",
        "/run/desktop/mnt/host/d/Users/fixture/repo/frontend",
        "/run/desktop/mnt/host/c/Users/fixture/repo/other/../frontend",
        "/run/desktop/mnt/host/c/Users/fixture/repo/./frontend",
        "/run/desktop/mnt/host/c//Users/fixture/repo/frontend",
        "/mnt/c/Users/fixture/repo/frontend",
        r"C:\Users\foreign\repo\frontend",
        "rw",
        "destination",
        "type",
        "image",
        "environment",
    ],
)
def test_windows_mount_normalization_cannot_accept_foreign_or_changed_runtime(damage):
    module = controller()
    assert hasattr(module, "canonical_runtime"), (
        "Owned Docker Desktop mount comparison not implemented"
    )
    original = {
        "web": {
            "image": "sha256:" + "a" * 64,
            "environment": ["PUBLIC=0"],
            "mounts": [
                {
                    "Type": "bind",
                    "Source": r"C:\Users\fixture\repo\frontend",
                    "Destination": "/app",
                    "RW": True,
                }
            ],
        }
    }
    changed = json.loads(json.dumps(original))
    if damage == "rw":
        changed["web"]["mounts"][0]["RW"] = False
    elif damage == "destination":
        changed["web"]["mounts"][0]["Destination"] = "/foreign"
    elif damage == "type":
        changed["web"]["mounts"][0]["Type"] = "volume"
    elif damage in {"image", "environment"}:
        changed["web"][damage] = "changed"
    else:
        changed["web"]["mounts"][0]["Source"] = damage
    owned = {r"C:\Users\fixture\repo\frontend"}
    try:
        candidate = module.canonical_runtime(changed, owned)
    except ValueError:
        return
    assert candidate != module.canonical_runtime(original, owned)


def test_real_resource_guard_accepts_only_owned_alias_without_rewriting_original_manifest(tmp_path):
    module = controller()
    sources(tmp_path)
    fixture = module.Fixture(tmp_path, PROJECT, run=lambda args: "")
    fixture.create([18237, 15394, 18337], port_free=lambda _: True)
    records = [
        {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": PROJECT,
                    "com.docker.compose.service": name,
                },
                "Env": ["PUBLIC=0"],
            },
            "Image": "sha256:" + "a" * 64,
            "Mounts": [],
        }
        for name in sorted(module.SERVICES)
    ]
    web = next(
        record
        for record in records
        if record["Config"]["Labels"]["com.docker.compose.service"] == "web"
    )
    web["Mounts"] = [
        {"Type": "bind", "Source": str(tmp_path / "frontend"), "Destination": "/app", "RW": True},
        {
            "Type": "volume",
            "Source": "/owned/volume",
            "Destination": "/app/node_modules",
            "RW": True,
        },
    ]
    calls = []

    def inventory(args):
        calls.append(args)
        if args[:2] == ["volume", "inspect"]:
            name = args[2].removeprefix(PROJECT + "_")
            return json.dumps(
                [
                    {
                        "Name": args[2],
                        "Labels": {
                            "com.docker.compose.project": PROJECT,
                            "com.docker.compose.volume": name,
                        },
                    }
                ]
            )
        if args[0] == "ps":
            return "\n".join(format(i, "064x") for i in range(1, 8))
        if args[0] == "inspect":
            return json.dumps(records)
        if args[:2] == ["network", "inspect"]:
            return json.dumps([{"Labels": {"com.docker.compose.project": PROJECT}}])
        raise AssertionError("Unexpected Docker mutation")

    fixture.run = inventory
    fixture.write_new("runtime.json", json.dumps(fixture.validate_resources(capture=True)))
    original = fixture.file("runtime.json").read_bytes()
    source = (tmp_path / "frontend").as_posix()
    if sys.platform == "win32":
        source = "/run/desktop/mnt/host/" + source[0].lower() + "/" + source[3:]
    web["Mounts"][0]["Source"] = source
    web["Mounts"].reverse()
    fixture.validate_resources()
    fixture.validate_resources()
    assert fixture.file("runtime.json").read_bytes() == original
    web["Mounts"][1]["RW"] = False
    with pytest.raises(ValueError):
        fixture.validate_resources()
    assert fixture.file("runtime.json").read_bytes() == original
