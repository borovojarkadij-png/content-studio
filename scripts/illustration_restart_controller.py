"""Test-only create-only illustration fixture controller. Never operational targets."""

import argparse
import json
import os
import re
import socket
import stat
import subprocess
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

MASTER = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
REVIEWER = "synthetic-illustration-restart-review-token-0001"
URL = "postgresql+psycopg://newsflow_fixture:synthetic-illustration-ci-only@postgres:5432/newsflow_illustration_ci"
FLAGS = (
    "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
    "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
    "NEWSFLOW_REWRITE_ENABLED",
    "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
    "NEWSFLOW_INTERNET_MEDIA_ENABLED",
    "NEWSFLOW_SOURCE_PHOTO_ENABLED",
    "NEWSFLOW_PUBLICATION_ENABLED",
)
SERVICES = {"api", "worker", "migrations", "postgres", "redis", "web", "web-production"}
VOLUMES = ("postgres_data", "redis_data", "frontend_node_modules", "media_data")
COMPOSE_DIGESTS = {
    "compose.yaml": "cd9a0584e84219478832649a82e6c6701f46a5ab14cb9f30367d2cc258af683f",
    "compose.illustration-review.yaml": "df830434bcf85bb92185622cbecd37094679ed39bf2ee0ade7d896d3f6b6c209",
}


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate fixture field")
            result[key] = value
        return result

    try:
        return json.loads(raw, object_pairs_hook=pairs)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Corrupt fixture manifest; preserve original") from None


def canonical_runtime(runtime, owned_bind_paths):
    """Compare exact owned binds across one documented Docker Desktop alias.

    Do not resolve arbitrary paths or discard any mount metadata. Volumes and
    every image/environment/RW/destination/type field retain exact comparison.
    The retained original manifest is never rewritten.
    """
    aliases = {}
    for path in owned_bind_paths:
        canonical = str(path).replace("\\", "/")
        aliases[canonical] = canonical
        windows = re.fullmatch(r"([A-Za-z]):/(.+)", canonical)
        if windows:
            aliases[
                "/run/desktop/mnt/host/" + windows[1].lower() + "/" + windows[2]
            ] = canonical
    if type(runtime) is not dict:
        raise ValueError("Invalid immutable runtime manifest")
    result = json.loads(json.dumps(runtime))
    for service in result.values():
        if (
            type(service) is not dict
            or set(service) != {"image", "mounts", "environment"}
            or type(service["mounts"]) is not list
        ):
            raise ValueError("Invalid immutable runtime manifest")
        for mount in service["mounts"]:
            if type(mount) is not dict or mount.get("Type") not in {"bind", "volume"}:
                raise ValueError("Invalid immutable runtime mount")
            if mount["Type"] == "bind":
                source = mount.get("Source")
                if type(source) is not str:
                    raise ValueError("Foreign immutable bind source")
                # Backslashes are Windows separators only on a drive path.
                if re.match(r"^[A-Za-z]:[\\/]", source):
                    source = source.replace("\\", "/")
                if source not in aliases:
                    raise ValueError("Foreign immutable bind source")
                mount["Source"] = aliases[source]
        service["mounts"].sort(key=lambda value: json.dumps(value, sort_keys=True))
    return result


def docker(args):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=600, check=False
    )
    scoped_mutation = args[0] == "compose" and any(
        command in args for command in ("up", "down", "exec")
    )
    if scoped_mutation and result.stderr:
        print(result.stderr[:262144], end="", flush=True)
        if len(result.stderr) > 262144:
            print(
                "Scoped Docker stderr exceeded transcript bound; inspect retained Docker logs",
                flush=True,
            )
    if result.returncode:
        if scoped_mutation:
            print(result.stdout, end="", flush=True)
        # Exact volume existence is checked against the complete read-only inventory,
        # avoiding an inspect-not-found failure being confused with daemon failure.
        raise ValueError(
            "Docker command failed; preserve fixture and inspect transcript"
        )
    return result.stdout


def port_free(port):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def safe_path(path):
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if item.is_symlink() or getattr(info, "st_file_attributes", 0) & getattr(
                stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024
            ):
                raise ValueError("Fixture path must not redirect to other storage")


class Fixture:
    def __init__(self, root, project, *, run=docker):
        if len(project) > 64 or not re.fullmatch(
            r"newsflow-verification-illustration-[a-z0-9]+(?:-[a-z0-9]+)*", project
        ):
            raise ValueError("Dedicated isolated illustration project required")
        self.root, self.project, self.run = Path(root).absolute(), project, run
        self.directory = self.root / ".artifacts" / "docker-verification" / project
        safe_path(self.directory)

    def file(self, name):
        path = self.directory / name
        safe_path(path)
        return path

    def compose(self):
        return [
            "compose",
            "-p",
            self.project,
            "--env-file",
            str(self.file("test.env")),
            "-f",
            str(self.root / "compose.yaml"),
            "-f",
            str(self.root / "compose.illustration-review.yaml"),
            "-f",
            str(self.file("compose.override.yaml")),
            "--profile",
            "dev",
            "--profile",
            "production",
        ]

    def write_new(self, name, content):
        with self.file(name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)

    def absent(self):
        for args in (
            [
                "ps",
                "-aq",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ],
            [
                "network",
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ],
            [
                "volume",
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ],
        ):
            if self.run(args).strip():
                raise ValueError(
                    "Refusing retained Docker project; preserve and reopen"
                )
        named = set(self.run(["volume", "ls", "--format", "{{.Name}}"]).splitlines())
        if any(f"{self.project}_{name}" in named for name in VOLUMES):
            raise ValueError("Refusing exact named volume, including unlabeled storage")
        # Names can survive without labels as well.
        names = set(self.run(["ps", "-a", "--format", "{{.Names}}"]).splitlines())
        networks = set(
            self.run(["network", "ls", "--format", "{{.Name}}"]).splitlines()
        )
        if (
            any(
                name.startswith((self.project + "-", self.project + "_"))
                for name in names
            )
            or self.project + "_default" in networks
        ):
            raise ValueError("Refusing unlabeled fixture container/network")

    @staticmethod
    def ports(values):
        if (
            type(values) not in (tuple, list)
            or len(values) != 3
            or len(set(values)) != 3
            or any(
                type(p) is not int or not 1024 <= p <= 65535 or p == 5432
                for p in values
            )
        ):
            raise ValueError("Distinct isolated non-PostgreSQL ports required")

    def environment(self, ports):
        return {
            "POSTGRES_DB": "newsflow_illustration_ci",
            "POSTGRES_USER": "newsflow_fixture",
            "POSTGRES_PASSWORD": "synthetic-illustration-ci-only",
            "DATABASE_URL": URL,
            "REDIS_URL": "redis://redis:6379/0",
            "NEWSFLOW_ENV_FILE": self.file("test.env").as_posix(),
            "NEWSFLOW_MASTER_KEY_SOURCE": self.file("synthetic-master-key").as_posix(),
            "NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_SOURCE": self.file(
                "synthetic-reviewer"
            ).as_posix(),
            "NEWSFLOW_ILLUSTRATION_REVIEWER_ID": "17",
            "NEWSFLOW_API_PORT": str(ports[0]),
            "NEWSFLOW_WEB_PORT": str(ports[1]),
            "NEWSFLOW_PROD_WEB_PORT": str(ports[2]),
            "NEWSFLOW_BIND_HOST": "127.0.0.1",
            **dict.fromkeys(FLAGS, "0"),
        }

    def override(self):
        return json.dumps(
            {
                "services": {
                    "worker": {
                        "volumes": [
                            {
                                "type": "bind",
                                "source": (
                                    self.root / "scripts/docker_illustration_probe.py"
                                ).as_posix(),
                                "target": "/opt/verification/docker_illustration_probe.py",
                                "read_only": True,
                            }
                        ]
                    }
                }
            },
            sort_keys=True,
        )

    def create(self, ports, *, port_free=port_free):
        self.ports(ports)
        self.prewrite_policy(ports)
        if self.directory.exists():
            raise ValueError("Create-only fixture already exists; never reseed")
        self.absent()
        if not all(port_free(p) for p in ports):
            raise ValueError("Verification port already in use")
        self.directory.mkdir(parents=True)
        self.write_new("synthetic-master-key", MASTER)
        self.write_new("synthetic-reviewer", REVIEWER)
        self.write_new(
            "test.env",
            "\n".join(f"{k}={v}" for k, v in self.environment(ports).items()) + "\n",
        )

        self.write_new("compose.override.yaml", self.override())
        self.write_new(
            "ownership.json",
            json.dumps(
                {
                    "version": 1,
                    "owner": "content-studio-illustration-v1",
                    "project": self.project,
                    "ports": list(ports),
                }
            ),
        )

    def prewrite_policy(self, ports):
        expected = self.environment(ports)
        expected.update(
            COMPOSE_PROJECT_NAME=self.project,
            NEWSFLOW_MASTER_KEY_FILE="/run/secrets/newsflow_master_key",
            NEWSFLOW_MEDIA_ROOT="/var/lib/newsflow/media",
            NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE="/run/secrets/illustration_reviewer",
        )
        for key, value in os.environ.items():
            if (
                (key in expected and value != expected[key])
                or (key.startswith("COMPOSE_") and key not in expected)
                or key
                in {
                    "NEWSFLOW_MASTER_KEY",
                    "NEWSFLOW_TELEGRAM_API_ID",
                    "NEWSFLOW_TELEGRAM_API_HASH",
                    "OPENAI_API_KEY",
                    "OPENROUTER_API_KEY",
                }
            ):
                raise ValueError(
                    "Unsafe inherited fixture override; preserve operator environment"
                )
        # This dedicated acceptance owns an immutable source graph. Deliberate
        # Compose changes require reviewed digest updates and covering tests.
        # Normalize newlines so the same graph is accepted on Windows/Linux.
        for name, expected_hash in COMPOSE_DIGESTS.items():
            path = self.root / name
            safe_path(path)
            if (
                not path.is_file()
                or sha256(path.read_text(encoding="utf-8").encode()).hexdigest()
                != expected_hash
            ):
                raise ValueError(
                    "Original Compose source changed/redirected; refuse before writes"
                )

    def validate(self, *, resources=False):
        owner = strict_json(self.file("ownership.json").read_text(encoding="utf-8"))
        if (
            type(owner) is not dict
            or set(owner) != {"version", "owner", "project", "ports"}
            or type(owner["version"]) is not int
            or owner["version"] != 1
            or owner["owner"] != "content-studio-illustration-v1"
            or owner["project"] != self.project
        ):
            raise ValueError("Invalid original fixture ownership")
        self.ports(owner["ports"])
        self.prewrite_policy(owner["ports"])
        env = self.environment(owner["ports"])
        expected = "\n".join(f"{k}={v}" for k, v in env.items()) + "\n"
        if (
            self.file("test.env").read_text() != expected
            or self.file("compose.override.yaml").read_text() != self.override()
            or self.file("synthetic-master-key").read_text() != MASTER
            or self.file("synthetic-reviewer").read_text() != REVIEWER
        ):
            raise ValueError("Original config/secret changed; never regenerate")
        config = strict_json(self.run(self.compose() + ["config", "--format", "json"]))
        self.validate_config(config, env, owner["ports"])
        if resources:
            self.validate_resources()
        return owner

    def validate_config(self, cfg, env, ports):
        if cfg.get("name") != self.project or set(cfg.get("services", {})) != SERVICES:
            raise ValueError("Foreign Compose services/project")
        for name in VOLUMES:
            volume = cfg.get("volumes", {}).get(name, {})
            if (
                volume.get("name") != self.project + "_" + name
                or volume.get("external")
                or volume.get("driver_opts")
            ):
                raise ValueError("Foreign volume configuration")
        pg = cfg["services"]["postgres"]
        if (
            pg.get("image") != "postgres:16-alpine"
            or pg.get("command")
            or pg.get("entrypoint")
            or pg.get("ports")
            or pg.get("environment")
            != {
                k: env[k] for k in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
            }
        ):
            raise ValueError("Foreign database configuration")
        if pg.get("volumes") != [
            {
                "type": "volume",
                "source": "postgres_data",
                "target": "/var/lib/postgresql/data",
                "volume": {},
            }
        ]:
            raise ValueError("Foreign PostgreSQL storage")
        for name in ("api", "worker", "migrations"):
            service = cfg["services"][name]
            commands = {
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
            }
            # The base packaged API command comes from the immutable image CMD.
            if (
                service.get("command")
                not in (commands[name], None if name == "api" else commands[name])
                or service.get("network_mode")
                or service.get("devices")
                or service.get("cap_add")
            ):
                raise ValueError("Foreign service execution target")
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
            if (
                service.get("environment") != expected
                or service.get("entrypoint")
                or service.get("privileged")
            ):
                raise ValueError("Foreign service environment/worker flags")
            secrets = service.get("secrets", [])
            if {s["source"] for s in secrets} != (
                {"newsflow_master_key", "illustration_reviewer"}
                if name == "api"
                else {"newsflow_master_key"}
                if name == "worker"
                else set()
            ):
                raise ValueError("Reviewer must be API-only")
            if any(
                s.get("target", s["source"])
                not in (s["source"], "/run/secrets/" + s["source"])
                for s in secrets
            ):
                raise ValueError("Foreign secret target")
        for name, filename in (
            ("newsflow_master_key", "synthetic-master-key"),
            ("illustration_reviewer", "synthetic-reviewer"),
        ):
            secret = cfg["secrets"][name]
            if Path(secret.get("file", "")).absolute() != self.file(
                filename
            ) or secret.get("external"):
                raise ValueError("Foreign secret mount")
        for name, target, port in (
            ("api", 8000, ports[0]),
            ("web", 5173, ports[1]),
            ("web-production", 80, ports[2]),
        ):
            bindings = cfg["services"][name].get("ports", [])
            if (
                len(bindings) != 1
                or bindings[0].get("host_ip") != "127.0.0.1"
                or str(bindings[0].get("published")) != str(port)
                or bindings[0].get("target") != target
            ):
                raise ValueError("Foreign/mixed port target")
        for name in ("api", "worker"):
            mounts = cfg["services"][name].get("volumes", [])
            media = [m for m in mounts if m.get("target") == "/var/lib/newsflow/media"]
            if (
                len(media) != 1
                or media[0].get("type") != "volume"
                or media[0].get("source") != "media_data"
                or bool(media[0].get("read_only")) != (name == "api")
            ):
                raise ValueError("Foreign media mount")
            if name == "api" and len(mounts) != 1:
                raise ValueError("Unexpected API mounts")
            if name == "worker":
                probe = [
                    m
                    for m in mounts
                    if m.get("target")
                    == "/opt/verification/docker_illustration_probe.py"
                ]
                if (
                    len(mounts) != 2
                    or len(probe) != 1
                    or probe[0].get("type") != "bind"
                    or not probe[0].get("read_only")
                    or Path(probe[0].get("source", "")).absolute()
                    != self.root / "scripts/docker_illustration_probe.py"
                ):
                    raise ValueError("Foreign probe mount")

    def validate_resources(self, *, capture=False):
        for name in VOLUMES:
            records = strict_json(
                self.run(["volume", "inspect", self.project + "_" + name])
            )
            if (
                len(records) != 1
                or records[0].get("Name") != self.project + "_" + name
                or records[0].get("Labels", {}).get("com.docker.compose.project")
                != self.project
                or records[0].get("Labels", {}).get("com.docker.compose.volume") != name
                or records[0].get("Options")
            ):
                raise ValueError("Foreign retained volume")
        ids = self.run(
            [
                "ps",
                "-aq",
                "--no-trunc",
                "--filter",
                f"label=com.docker.compose.project={self.project}",
            ]
        ).splitlines()
        if len(ids) != len(SERVICES) or any(
            not re.fullmatch("[a-f0-9]{64}", value) for value in ids
        ):
            raise ValueError("Exact owned service containers required")
        records = strict_json(self.run(["inspect", *ids]))
        names = [
            r["Config"]["Labels"].get("com.docker.compose.service") for r in records
        ]
        if set(names) != SERVICES or len(names) != len(set(names)):
            raise ValueError("Foreign/duplicate service containers")
        current = {
            r["Config"]["Labels"]["com.docker.compose.service"]: {
                "image": r["Image"],
                "mounts": r["Mounts"],
                "environment": sorted(r["Config"]["Env"]),
            }
            for r in records
        }
        baseline = self.file("runtime.json")
        if not baseline.exists() and not capture:
            raise ValueError(
                "Original immutable runtime manifest missing; preserve partial fixture"
            )
        if baseline.exists():
            owned_binds = {
                self.root / "frontend",
                self.root / "scripts/docker_illustration_probe.py",
                self.file("synthetic-master-key"),
                self.file("synthetic-reviewer"),
            }
            if canonical_runtime(
                strict_json(baseline.read_text()), owned_binds
            ) != canonical_runtime(current, owned_binds):
                raise ValueError("Retained immutable image/mount/environment changed")
        networks = strict_json(
            self.run(["network", "inspect", self.project + "_default"])
        )
        if (
            len(networks) != 1
            or networks[0].get("Labels", {}).get("com.docker.compose.project")
            != self.project
        ):
            raise ValueError("Foreign retained network")
        return current

    def action(self, args):
        self.validate(resources=True)
        print(self.run(self.compose() + args), end="", flush=True)

    def probe(self, mode):
        self.action(
            [
                "exec",
                "-T",
                "-e",
                "NEWSFLOW_ILLUSTRATION_FIXTURE=1",
                "worker",
                "python",
                "/opt/verification/docker_illustration_probe.py",
                mode,
            ]
        )

    def restart(self):
        self.action(["down"])
        # Config and secrets still validated while containers are absent.
        self.validate()
        print(
            self.run(self.compose() + ["up", "-d", "--wait", "--wait-timeout", "180"]),
            end="",
            flush=True,
        )
        self.validate(resources=True)
        self.health()

    def health(self):
        owner = self.validate(resources=True)
        for port in (owner["ports"][0], owner["ports"][2]):
            with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=15) as response:
                if response.status != 200:
                    raise ValueError("Isolated health failed")
        print("Packaged API and production proxy health: PASS", flush=True)

    def crash(self):
        self.validate(resources=True)
        helper = str(self.root / "scripts/verification-postgres-crash.ps1").replace(
            "'", "''"
        )
        script = f". '{helper}'; Invoke-SyntheticPostgresCrash -ComposeArgs @('compose', '-p', '{self.project}')"
        subprocess.run(
            ["pwsh", "-NoProfile", "-Command", script], check=True, timeout=60
        )
        self.validate(resources=True)
        print(
            self.run(self.compose() + ["up", "-d", "--wait", "--wait-timeout", "180"]),
            end="",
            flush=True,
        )
        self.health()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("create", "verify", "restart", "preflight", "crash")
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--ports", nargs=3, type=int, default=[18237, 15394, 18337])
    args = parser.parse_args()
    fixture = Fixture(Path(__file__).resolve().parents[1], args.project)
    if args.mode == "preflight":
        fixture.ports(args.ports)
        fixture.prewrite_policy(args.ports)
        if fixture.directory.exists() or not all(port_free(p) for p in args.ports):
            raise ValueError("Candidate artifact/ports not absent")
        fixture.absent()
    elif args.mode == "create":
        fixture.create(args.ports)
        fixture.validate()
        print(
            fixture.run(
                fixture.compose()
                + ["up", "-d", "--build", "--wait", "--wait-timeout", "180"]
            ),
            end="",
            flush=True,
        )
        fixture.write_new(
            "runtime.json",
            json.dumps(fixture.validate_resources(capture=True), sort_keys=True),
        )
        fixture.health()
        fixture.action(["exec", "-T", "worker", "python", "-m", "alembic", "check"])
        fixture.probe("seed")
        fixture.probe("invalidate")
        fixture.probe("verify-pending")
        fixture.restart()
        fixture.probe("verify-pending")
        fixture.crash()
        fixture.probe("verify-pending")
        fixture.probe("execute")
        fixture.restart()
        fixture.probe("verify-final")
        fixture.action(["exec", "-T", "worker", "python", "-m", "alembic", "check"])
    elif args.mode == "restart":
        fixture.restart()
    elif args.mode == "crash":
        fixture.crash()
    else:
        fixture.probe("verify-final")
        fixture.probe("verify-final")
    print(
        f"Synthetic illustration {args.mode}: PASS; retained project={args.project}; live acceptance=SKIP"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        reason = {
            "Retained immutable image/mount/environment changed": "RUNTIME_BINDING",
            "Foreign immutable bind source": "MOUNT_SOURCE",
            "Unsafe inherited fixture override; preserve operator environment": "ENVIRONMENT",
            "Original Compose source changed/redirected; refuse before writes": "SOURCE_GRAPH",
            "Docker command failed; preserve fixture and inspect transcript": "DOCKER_COMMAND",
        }.get(str(error), "GUARD_OR_RUNTIME")
        print(
            f"Illustration fixture refused/failed; reason={reason}; preserve all original evidence and resources",
            flush=True,
        )
        raise SystemExit(1) from None
