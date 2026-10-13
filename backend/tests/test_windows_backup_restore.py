"""Run actual PS7 entrypoints against a native, deterministic Docker boundary."""

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTAINER = "a" * 64
PROJECT = "synthetic-backup"
ARCHIVE = b"PGDMP\x00\xff\xfe\x80\r\n\x00synthetic ciphertext"
PRIVATE = "PRIVATE_DIAGNOSTIC_NEVER_PRINT"
pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Windows native executable and junction contract; run on Windows PS7"
)

# This native program has no Docker/network dependency and never launches children.
SHIM = r"""
using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
class FakeDocker {
    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    static extern IntPtr GetStdHandle(int n);
    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);
    static int Main(string[] args) {
        var json = new JavaScriptSerializer();
        if(args.Length==1 && args[0]=="--ready") {
            json.DeserializeObject("{\"ready\":true}");
            Console.Out.Write("SHIM_READY");
            return 0;
        }
        string dir = Environment.GetEnvironmentVariable("BACKUP_FAKE_DIR");
        var cfg = json.DeserializeObject(File.ReadAllText(Path.Combine(dir,"config.json")))
            as System.Collections.Generic.Dictionary<string,object>;
        File.AppendAllText(Path.Combine(dir,"trace.jsonl"),json.Serialize(args)+"\n");
        string command = "unknown";
        foreach(var a in args) if(a=="inspect" || a=="pg_dump" || a=="pg_restore" ||
            a=="createdb" || a=="psql") { command=a; break; }
        if(command=="pg_restore" && Array.IndexOf(args,"--list")>=0) command="list";
        if(cfg.ContainsKey("oversized") && (string)cfg["oversized"]==command) {
            File.WriteAllText(Path.Combine(dir,"oversized.pid"),
                System.Diagnostics.Process.GetCurrentProcess().Id.ToString());
            Console.Error.Write("PRIVATE_DIAGNOSTIC_NEVER_PRINT");
            var block=Encoding.UTF8.GetBytes(new string('x',4096));
            byte[] marker=Encoding.UTF8.GetBytes("PRIVATE_DIAGNOSTIC_NEVER_PRINT");
            Array.Copy(marker,block,marker.Length);
            var output=Console.OpenStandardOutput();
            int writes=cfg.ContainsKey("blocked_output") && (bool)cfg["blocked_output"] ? 4096 : 257;
            File.WriteAllText(Path.Combine(dir,"oversized.started"),writes.ToString());
            for(int n=0;n<writes;n++) output.Write(block,0,block.Length);
            File.WriteAllText(Path.Combine(dir,"oversized.completed"),"done");
            File.AppendAllText(Path.Combine(dir,"receipts.jsonl"),command+" exit=0\n");
            return 0;
        }
        if(cfg.ContainsKey("early") && (string)cfg["early"]==command) {
            int prefix=Console.OpenStandardInput().ReadByte();
            File.WriteAllBytes(Path.Combine(dir,command+".prefix"),new byte[]{(byte)prefix});
            CloseHandle(GetStdHandle(-10));
            if(cfg.ContainsKey("early_sleep") && (bool)cfg["early_sleep"]) {
                File.WriteAllText(Path.Combine(dir,"sleep.pid"),
                    System.Diagnostics.Process.GetCurrentProcess().Id.ToString());
                Thread.Sleep(30000);
                File.WriteAllText(Path.Combine(dir,"timeout-escaped"),"bad");
            }
            int code=cfg.ContainsKey("early_code") ? Convert.ToInt32(cfg["early_code"]) : 0;
            if(code!=0) Console.Error.Write("PRIVATE_DIAGNOSTIC_NEVER_PRINT");
            if(command=="list") Console.Out.Write("; synthetic TOC\n");
            File.AppendAllText(Path.Combine(dir,"receipts.jsonl"),command+" exit="+code+"\n");
            return code;
        }
        if(cfg.ContainsKey("sleep") && (string)cfg["sleep"]==command) {
            File.WriteAllText(Path.Combine(dir,"sleep.pid"),
                System.Diagnostics.Process.GetCurrentProcess().Id.ToString());
            Thread.Sleep(30000);
            File.WriteAllText(Path.Combine(dir,"timeout-escaped"),"bad");
        }
        if(cfg.ContainsKey("flood") && (string)cfg["flood"]==command)
            Console.Error.Write(new string('x',1024*1024));
        if(cfg.ContainsKey("fail") && (string)cfg["fail"]==command) {
            Console.Error.Write("PRIVATE_DIAGNOSTIC_NEVER_PRINT");
            Console.Out.Write("partial");
            File.AppendAllText(Path.Combine(dir,"receipts.jsonl"),command+" exit=23\n");
            return 23;
        }
        if(command=="inspect") Console.Out.Write(json.Serialize(cfg["inspect"]));
        else if(command=="pg_dump") {
            var b=Convert.FromBase64String((string)cfg["archive"]);
            Console.OpenStandardOutput().Write(b,0,b.Length);
            if(cfg.ContainsKey("large_dump") && (bool)cfg["large_dump"]) {
                var tail=new byte[16*1024*1024];
                Console.OpenStandardOutput().Write(tail,0,tail.Length);
            }
        }
        else if(command=="list" || command=="pg_restore") {
            using(var m=new MemoryStream()) {
                Console.OpenStandardInput().CopyTo(m);
                File.WriteAllBytes(Path.Combine(dir,command+".input"),m.ToArray());
            }
            if(command=="list") Console.Out.Write("; Archive created at synthetic time\n; TOC\n");
            else File.WriteAllText(Path.Combine(dir,"restored"),"copy");
        }
        else if(command=="createdb") File.WriteAllText(Path.Combine(dir,"created"),"copy");
        else if(command=="psql") {
            if(Array.IndexOf(args,"SHOW server_version;")>=0)
                Console.Out.Write(cfg.ContainsKey("version") ? (string)cfg["version"] : "16.4\n");
            else Console.Out.Write(cfg.ContainsKey("exists") && (bool)cfg["exists"] ? "1\n" : "0\n");
        }
        File.AppendAllText(Path.Combine(dir,"receipts.jsonl"),command+" exit=0\n");
        return 0;
    }
}
"""


@pytest.fixture(scope="session")
def native_docker(tmp_path_factory):
    compiler = Path("C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe")
    if not shutil.which("pwsh") or not compiler.is_file():
        pytest.skip("Windows PS7 and .NET Framework C# compiler required for native shim")
    directory = tmp_path_factory.mktemp("native-docker")
    source = directory / "FakeDocker.cs"
    source.write_text(SHIM, encoding="utf-8")
    exe = directory / "docker.exe"
    result = subprocess.run(
        [str(compiler), "/nologo", "/r:System.Web.Extensions.dll", f"/out:{exe}", str(source)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # Assert native startup before one-second lifecycle cases spend their deadline.
    env = os.environ.copy()
    env.pop("BACKUP_FAKE_DIR", None)
    start = time.monotonic()
    ready = subprocess.run(
        [str(exe), "--ready"],
        env=env,
        cwd=directory,
        capture_output=True,
        timeout=30,
        check=False,
    )
    (directory / "readiness-status.json").write_text(
        json.dumps(
            {
                "exit": ready.returncode,
                "stdout": ready.stdout.decode("utf-8", errors="backslashreplace"),
                "stderr": ready.stderr.decode("utf-8", errors="backslashreplace"),
                "elapsed": time.monotonic() - start,
            }
        ),
        encoding="utf-8",
    )
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert ready.stdout == b"SHIM_READY"
    assert ready.stderr == b""
    return directory


def test_native_shim_readiness_does_not_require_config(tmp_path, native_docker):
    env = os.environ.copy()
    env.pop("BACKUP_FAKE_DIR", None)
    result = subprocess.run(
        [str(native_docker / "docker.exe"), "--ready"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        timeout=30,
        check=False,
    )
    receipt = tmp_path / "readiness-status.json"
    receipt.write_text(
        json.dumps(
            {
                "exit": result.returncode,
                "stdout": result.stdout.decode("utf-8", errors="backslashreplace"),
                "stderr": result.stderr.decode("utf-8", errors="backslashreplace"),
            }
        ),
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == b"SHIM_READY"
    assert result.stderr == b""
    assert list(tmp_path.iterdir()) == [receipt]


@pytest.fixture
def fake(tmp_path, native_docker):
    import base64

    inspect = [
        {
            "Id": CONTAINER,
            "State": {"Running": True},
            "Config": {
                "Labels": {
                    "com.docker.compose.project": PROJECT,
                    "com.docker.compose.service": "postgres",
                },
                "Env": [
                    "POSTGRES_DB=source_db",
                    "POSTGRES_USER=fixture_user",
                    "POSTGRES_PASSWORD=" + PRIVATE,
                ],
            },
        }
    ]
    cfg = {"inspect": inspect, "archive": base64.b64encode(ARCHIVE).decode()}
    env = os.environ | {
        "PATH": str(native_docker) + os.pathsep + os.environ["PATH"],
        "BACKUP_FAKE_DIR": str(tmp_path),
        "POSTGRES_USER": "fixture_user",
        "POSTGRES_DB": "source_db",
    }
    sentinel = tmp_path / "original-database-sentinel"
    sentinel.write_bytes(b"retain original data")

    def run(script, **parameters):
        (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        args = [
            "pwsh",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "scripts" / script),
        ]
        for name, value in parameters.items():
            args.extend(["-" + name, str(value)])
        result = subprocess.run(
            args,
            env=env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=40,
            check=False,
        )
        assert PRIVATE not in result.stdout + result.stderr
        expected_stdout = ""
        if result.returncode == 0:
            expected_stdout = (
                "BACKUP_OK\n"
                if script == "backup.ps1"
                else "RESTORE_OK: new database copy created.\n"
            )
        assert result.stdout == expected_stdout
        assert sentinel.read_bytes() == b"retain original data"
        assert not any(
            arg in {"dropdb", "--clean", "rm", "down", "kill", "sh", "-c"}
            for call in trace(tmp_path)
            for arg in call
        )
        with (tmp_path / "entrypoint-status.jsonl").open("a", encoding="utf-8") as receipt:
            receipt.write(
                json.dumps(
                    {
                        "script": script,
                        "exit": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
                )
                + "\n"
            )
        return result

    return cfg, run


def trace(tmp_path):
    path = tmp_path / "trace.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize(
    "case,expected,rejected",
    [
        ("empty", "", False),
        ("ascii", "A" * 1048576, False),
        ("multibyte", "é" * 524288, False),
        ("overflow_one", None, True),
        ("overflow_chunks", None, True),
        ("invalid_utf8", None, True),
    ],
    ids=[
        "empty",
        "ascii_limit",
        "multibyte_limit",
        "overflow_one",
        "overflow_chunks",
        "invalid_utf8",
    ],
)
def test_native_text_destination_capacity_and_strict_utf8(tmp_path, case, expected, rejected):
    # Reverting to an expandable destination must fail even when the final size guard rejects.
    helper = str(ROOT / "scripts" / "postgres-backup-common.ps1").replace("'", "''")
    code = (
        f". '{helper}'\n$case = '{case}'\n"
        + r"""
$ErrorActionPreference = 'Stop'
$script:peakCapacity = 0
$script:initialLength = -1
$script:writes = 0
function Invoke-BackupNative([string[]]$Arguments, [int]$TimeoutSeconds,
    [IO.Stream]$OutputStream) {
    $script:initialLength = $OutputStream.Length
    $script:peakCapacity = $OutputStream.Capacity
    $block = [Text.Encoding]::UTF8.GetBytes(('A' * 4096))
    $count = 256
    switch ($case) {
        'empty' { $count = 0 }
        'multibyte' { $block = [Text.Encoding]::UTF8.GetBytes(([string][char]0xE9 * 2048)) }
        'overflow_chunks' { $count = 257 }
        'invalid_utf8' { $count = 1; $block = [byte[]]@(0xC3, 0x28) }
    }
    if ($case -like 'overflow*') {
        $marker = [Text.Encoding]::UTF8.GetBytes('PRIVATE_DIAGNOSTIC_NEVER_PRINT')
        [Array]::Copy($marker, $block, $marker.Length)
    }
    try {
        for ($n = 0; $n -lt $count; $n++) {
            try { $OutputStream.Write($block, 0, $block.Length); $script:writes++ }
            finally { $script:peakCapacity = [Math]::Max($script:peakCapacity, $OutputStream.Capacity) }
        }
        if ($case -eq 'overflow_one') {
            try { $OutputStream.WriteByte(65); $script:writes++ }
            finally { $script:peakCapacity = [Math]::Max($script:peakCapacity, $OutputStream.Capacity) }
        }
    } finally { $script:peakCapacity = [Math]::Max($script:peakCapacity, $OutputStream.Capacity) }
}
$rejected = $false
$errorText = ''
$text = $null
try { $text = Get-BackupNativeText @('synthetic') 1 }
catch { $rejected = $true; $errorText = $_.Exception.Message }
$digest = $null
if (-not $rejected) {
    $bytes = [Text.Encoding]::UTF8.GetBytes([string]$text)
    $digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
}
@{ rejected=$rejected; peakCapacity=$script:peakCapacity; initialLength=$script:initialLength;
   writes=$script:writes; digest=$digest; error=$errorText } | ConvertTo-Json -Compress
"""
    )
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    (tmp_path / "helper-status.json").write_text(
        json.dumps({"exit": result.returncode, "stdout": result.stdout, "stderr": result.stderr}),
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert PRIVATE not in result.stdout + result.stderr
    observed = json.loads(result.stdout)
    assert observed["rejected"] is rejected, observed
    assert observed["initialLength"] == 0, observed
    assert observed["peakCapacity"] <= 1048576, observed
    if rejected:
        assert observed["digest"] is None
        assert observed["error"]
    else:
        assert observed["digest"] == hashlib.sha256(expected.encode("utf-8")).hexdigest()
        assert observed["error"] == ""


@pytest.mark.parametrize("operation", ["backup", "restore"])
@pytest.mark.parametrize("command", ["inspect", "psql"])
@pytest.mark.parametrize("blocked", [False, True], ids=["overflow", "blocked_writer"])
def test_oversized_native_text_refuses_before_database_changes(
    tmp_path, fake, operation, command, blocked
):
    cfg, run = fake
    cfg.update(oversized=command, blocked_output=blocked)
    source = bundle(tmp_path) if operation == "restore" else None
    before = {p.name: p.read_bytes() for p in source.iterdir()} if source else None
    with subprocess.Popen(["pwsh", "-NoProfile", "-Command", "Start-Sleep -Seconds 20"]) as other:
        start = time.monotonic()
        result = (
            backup(run, tmp_path / "new", TimeoutSeconds=1)
            if operation == "backup"
            else restore(run, source, TimeoutSeconds=1)
        )
        assert time.monotonic() - start < 8
        assert result.returncode == 1
        assert result.stderr.startswith(operation.upper() + "_FAILED:")
        assert other.poll() is None
        other.terminate()
    pid = int((tmp_path / "oversized.pid").read_text())
    check = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 1 }}",
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert check.returncode == 0
    assert (tmp_path / "oversized.started").read_text() == ("4096" if blocked else "257")
    if blocked:
        assert not (tmp_path / "oversized.completed").exists()
    calls = trace(tmp_path)
    assert calls[0] == ["inspect", CONTAINER]
    assert len(calls) == (1 if command == "inspect" else 2)
    if command == "psql":
        assert calls[1][-2:] == ["--command", "SHOW server_version;"]
    assert not any(arg in {"pg_dump", "createdb", "pg_restore"} for call in calls for arg in call)
    assert not (tmp_path / "new").exists()
    assert_no_creation(tmp_path)
    if source:
        assert {p.name: p.read_bytes() for p in source.iterdir()} == before


def backup(run, destination, **overrides):
    return run(
        "backup.ps1",
        **(
            {
                "Destination": destination,
                "ContainerId": CONTAINER,
                "ProjectName": PROJECT,
                "Database": "source_db",
                "User": "fixture_user",
            }
            | overrides
        ),
    )


def restore(run, source, **overrides):
    return run(
        "restore.ps1",
        **(
            {
                "Source": source,
                "ContainerId": CONTAINER,
                "ProjectName": PROJECT,
                "User": "fixture_user",
                "TargetDatabase": "recovered_copy",
            }
            | overrides
        ),
    )


def bundle(tmp_path):
    path = tmp_path / "bundle"
    path.mkdir()
    (path / "database.dump").write_bytes(ARCHIVE)
    manifest = {
        "version": 1,
        "format": "postgresql-custom",
        "archive": "database.dump",
        "sourceContainerId": CONTAINER,
        "sourceProject": PROJECT,
        "sourceDatabase": "source_db",
        "sourceUser": "fixture_user",
        "postgresVersion": "16.4",
        "sha256": hashlib.sha256(ARCHIVE).hexdigest(),
        "byteLength": len(ARCHIVE),
    }
    (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def assert_no_creation(tmp_path):
    assert not (tmp_path / "created").exists()
    assert not (tmp_path / "restored").exists()
    assert not any("createdb" in call or "pg_dump" in call for call in trace(tmp_path))


def test_dump_native_failure_is_nonzero_and_has_no_success_manifest(tmp_path, fake):
    cfg, run = fake
    cfg["fail"] = "pg_dump"
    result = backup(run, tmp_path / "bundle")
    assert any("pg_dump" in call for call in trace(tmp_path))
    assert "pg_dump exit=23" in (tmp_path / "receipts.jsonl").read_text()
    assert result.returncode != 0, result.stdout + result.stderr
    assert not (tmp_path / "bundle" / "manifest.json").exists()


def test_restore_native_failure_is_nonzero(tmp_path, fake):
    cfg, run = fake
    cfg["fail"] = "pg_restore"
    result = restore(run, bundle(tmp_path))
    assert any("pg_restore" in call for call in trace(tmp_path))
    assert "pg_restore exit=23" in (tmp_path / "receipts.jsonl").read_text()
    assert result.returncode != 0, result.stdout + result.stderr
    assert (tmp_path / "created").read_text() == "copy"
    assert not (tmp_path / "restored").exists()


def test_binary_roundtrip_literal_unicode_spaced_path_and_exact_argv(tmp_path, fake):
    cfg, run = fake
    cfg["flood"] = "pg_dump"
    destination = tmp_path / "копия [literal] ' space"
    result = backup(run, destination)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (destination / "database.dump").read_bytes() == ARCHIVE
    manifest = json.loads((destination / "manifest.json").read_text())
    assert manifest == {
        "version": 1,
        "format": "postgresql-custom",
        "archive": "database.dump",
        "sourceContainerId": CONTAINER,
        "sourceProject": PROJECT,
        "sourceDatabase": "source_db",
        "sourceUser": "fixture_user",
        "postgresVersion": "16.4",
        "sha256": hashlib.sha256(ARCHIVE).hexdigest(),
        "byteLength": len(ARCHIVE),
    }
    result = restore(run, destination)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "list.input").read_bytes() == ARCHIVE
    assert (tmp_path / "pg_restore.input").read_bytes() == ARCHIVE
    calls = trace(tmp_path)
    assert ["inspect", CONTAINER] in calls
    assert [
        "exec",
        CONTAINER,
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--username=fixture_user",
        "--dbname=source_db",
    ] in calls
    assert [
        "exec",
        "-i",
        CONTAINER,
        "pg_restore",
        "--exit-on-error",
        "--no-owner",
        "--no-privileges",
        "--username=fixture_user",
        "--dbname=recovered_copy",
    ] in calls
    assert [
        "exec",
        CONTAINER,
        "createdb",
        "--username=fixture_user",
        "--maintenance-db=postgres",
        "--template=template0",
        "--",
        "recovered_copy",
    ] in calls
    assert [
        "exec",
        CONTAINER,
        "psql",
        "--no-psqlrc",
        "--tuples-only",
        "--no-align",
        "--set=ON_ERROR_STOP=1",
        "--username=fixture_user",
        "--dbname=postgres",
        "--command",
        "SELECT count(*) FROM pg_database WHERE datname = 'recovered_copy';",
    ] in calls
    assert sum("createdb" in call for call in calls) == 1
    assert not any(
        arg in {"dropdb", "--clean", "rm", "down", "kill", "sh", "-c"}
        for call in calls
        for arg in call
    )


@pytest.mark.parametrize("command", ["inspect", "psql", "list"])
def test_backup_native_failures_never_write_manifest(tmp_path, fake, command):
    cfg, run = fake
    cfg["fail"] = command
    destination = tmp_path / "bundle"
    result = backup(run, destination)
    assert result.returncode != 0
    assert f"{command} exit=23" in (tmp_path / "receipts.jsonl").read_text()
    assert not (destination / "manifest.json").exists()


@pytest.mark.parametrize("command", ["inspect", "psql", "list", "createdb"])
def test_restore_native_failures_are_create_only(tmp_path, fake, command):
    cfg, run = fake
    cfg["fail"] = command
    source = bundle(tmp_path)
    result = restore(run, source)
    assert result.returncode != 0
    assert f"{command} exit=23" in (tmp_path / "receipts.jsonl").read_text()
    assert not (tmp_path / "created").exists()
    assert not (tmp_path / "restored").exists()
    assert (source / "database.dump").read_bytes() == ARCHIVE


@pytest.mark.parametrize(
    "change",
    ["id", "stopped", "project", "service", "role", "database", "missing_env", "duplicate_env"],
)
@pytest.mark.parametrize("operation", ["backup", "restore"])
def test_inspected_identity_is_required_before_database_commands(tmp_path, fake, change, operation):
    cfg, run = fake
    item = cfg["inspect"][0]
    if change == "id":
        item["Id"] = "b" * 64
    elif change == "stopped":
        item["State"]["Running"] = False
    elif change in {"project", "service"}:
        item["Config"]["Labels"]["com.docker.compose." + change] = "foreign"
    elif change == "role":
        item["Config"]["Env"][1] = "POSTGRES_USER=foreign"
    elif change == "database":
        item["Config"]["Env"][0] = "POSTGRES_DB=foreign"
    elif change == "missing_env":
        item["Config"]["Env"] = []
    else:
        item["Config"]["Env"].append("POSTGRES_DB=source_db")
    result = (
        backup(run, tmp_path / "new") if operation == "backup" else restore(run, bundle(tmp_path))
    )
    assert result.returncode != 0
    assert trace(tmp_path) == [["inspect", CONTAINER]]
    assert not (tmp_path / "new").exists()
    assert_no_creation(tmp_path)


@pytest.mark.parametrize(
    "values",
    [
        {"ContainerId": "a" * 12},
        {"ProjectName": "x;echo bad"},
        {"User": "x';select 1;--"},
        {"Database": "x y"},
        {"TimeoutSeconds": 0},
        {"TimeoutSeconds": 1801},
    ],
)
def test_backup_refuses_invalid_explicit_inputs_before_native(tmp_path, fake, values):
    _, run = fake
    result = backup(run, tmp_path / "new", **values)
    assert result.returncode != 0
    assert trace(tmp_path) == []
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("kind", ["directory", "file"])
def test_existing_destination_sentinel_is_preserved(tmp_path, fake, kind):
    _, run = fake
    destination = tmp_path / "existing"
    sentinel = destination
    if kind == "directory":
        destination.mkdir()
        sentinel = destination / "prior"
    sentinel.write_bytes(b"existing backup data")
    result = backup(run, destination)
    assert result.returncode != 0
    assert sentinel.read_bytes() == b"existing backup data"
    assert trace(tmp_path) == []


@pytest.mark.parametrize(
    "change",
    [
        "boolean_version",
        "unknown",
        "missing",
        "bad_hash",
        "length",
        "format",
        "archive_path",
        "id",
        "source_name",
        "version_string",
        "zero",
        "duplicate",
        "malformed",
        "extra_file",
        "raw_sql",
        "tampered",
    ],
)
def test_invalid_bundle_refused_before_any_native_or_creation(tmp_path, fake, change):
    _, run = fake
    source = bundle(tmp_path)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    changes = {
        "boolean_version": {"version": True},
        "unknown": {"password": PRIVATE},
        "bad_hash": {"sha256": "0" * 64},
        "length": {"byteLength": len(ARCHIVE) + 1},
        "format": {"format": "sql"},
        "archive_path": {"archive": "../original"},
        "id": {"sourceContainerId": "a" * 12},
        "source_name": {"sourceDatabase": "x';--"},
        "version_string": {"version": "1"},
        "zero": {"byteLength": 0},
    }
    manifest.update(changes.get(change, {}))
    if change == "missing":
        del manifest["sourceUser"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    if change == "duplicate":
        manifest_path.write_text('{"version":1,' + json.dumps(manifest)[1:])
    elif change == "malformed":
        manifest_path.write_text('{"version":')
    elif change == "extra_file":
        (source / "unrelated").write_text("retain")
    elif change == "raw_sql":
        source = tmp_path / "legacy.sql"
        source.write_text("SELECT 1;")
    elif change == "tampered":
        (source / "database.dump").write_bytes(b"Z" * len(ARCHIVE))
    before = {p.name: p.read_bytes() for p in source.iterdir()} if source.is_dir() else {}
    result = restore(run, source)
    assert result.returncode != 0
    assert trace(tmp_path) == []
    assert_no_creation(tmp_path)
    if source.is_dir():
        assert {p.name: p.read_bytes() for p in source.iterdir()} == before


@pytest.mark.parametrize("target", ["source_db", "x'; DROP DATABASE source_db;--", "postgres"])
def test_refuses_source_unsafe_or_existing_target(tmp_path, fake, target):
    cfg, run = fake
    cfg["exists"] = True
    result = restore(run, bundle(tmp_path), TargetDatabase=target)
    assert result.returncode != 0
    assert_no_creation(tmp_path)


def test_timeout_stops_only_owned_native_child_and_retains_partial_bundle(tmp_path, fake):
    cfg, run = fake
    cfg["sleep"] = "pg_dump"
    with subprocess.Popen(["pwsh", "-NoProfile", "-Command", "Start-Sleep -Seconds 20"]) as other:
        start = time.monotonic()
        result = backup(run, tmp_path / "new", TimeoutSeconds=1)
        assert time.monotonic() - start < 8
        assert result.returncode != 0
        assert other.poll() is None
        other.terminate()
    pid = int((tmp_path / "sleep.pid").read_text())
    check = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 1 }}",
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert check.returncode == 0
    assert not (tmp_path / "timeout-escaped").exists()
    assert (tmp_path / "new" / "database.dump").exists()
    assert not (tmp_path / "new" / "manifest.json").exists()


@pytest.mark.parametrize("operation", ["backup", "restore"])
def test_reparse_ancestor_cannot_redirect_storage(tmp_path, fake, operation):
    _, run = fake
    original = tmp_path / "original"
    original.mkdir()
    sentinel = original / "prior"
    sentinel.write_text("unchanged")
    link = tmp_path / "redirect"
    code = f"New-Item -ItemType Junction -Path '{link}' -Target '{original}' | Out-Null"
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    result = backup(run, link / "new") if operation == "backup" else restore(run, link)
    assert result.returncode != 0
    assert trace(tmp_path) == []
    assert sentinel.read_text() == "unchanged"
    assert list(original.iterdir()) == [sentinel]


def test_dot_sourcing_entrypoints_does_not_execute_or_prompt():
    for name in ["backup.ps1", "restore.ps1", "postgres-backup-common.ps1"]:
        code = f". '{ROOT / 'scripts' / name}'; Write-Output 'LOADED'"
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-NonInteractive", "-Command", code],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0 and result.stdout.strip() == "LOADED", result.stderr


def test_restore_accepts_different_explicit_running_container_project(tmp_path, fake):
    cfg, run = fake
    cfg["inspect"][0]["Id"] = "b" * 64
    cfg["inspect"][0]["Config"]["Labels"]["com.docker.compose.project"] = "synthetic-recovery"
    result = restore(run, bundle(tmp_path), ContainerId="b" * 64, ProjectName="synthetic-recovery")
    assert result.returncode == 0, result.stdout + result.stderr
    assert ["inspect", "b" * 64] in trace(tmp_path)


@pytest.mark.parametrize("version", ["17.1", "16.4\nPRIVATE_DIAGNOSTIC_NEVER_PRINT"])
def test_restore_refuses_incompatible_or_untrusted_version_before_creation(tmp_path, fake, version):
    cfg, run = fake
    cfg["version"] = version
    result = restore(run, bundle(tmp_path))
    assert result.returncode != 0
    assert_no_creation(tmp_path)


@pytest.mark.parametrize("archive", [b"", b"SELECT 1;", b"PGDM"])
def test_dump_empty_or_noncustom_bytes_have_no_success_manifest(tmp_path, fake, archive):
    import base64

    cfg, run = fake
    cfg["archive"] = base64.b64encode(archive).decode()
    destination = tmp_path / "new"
    result = backup(run, destination)
    assert result.returncode != 0
    assert (destination / "database.dump").read_bytes() == archive
    assert not (destination / "manifest.json").exists()


@pytest.mark.parametrize(
    "values",
    [
        {"ContainerId": "a" * 12},
        {"ProjectName": "x;echo bad"},
        {"User": "x';select 1;--"},
        {"TargetDatabase": "x y"},
        {"TimeoutSeconds": 0},
        {"TimeoutSeconds": 1801},
    ],
)
def test_restore_refuses_invalid_explicit_inputs_before_native(tmp_path, fake, values):
    _, run = fake
    result = restore(run, bundle(tmp_path), **values)
    assert result.returncode != 0
    assert trace(tmp_path) == []
    assert_no_creation(tmp_path)


def test_entrypoints_and_shared_helper_parse():
    for name in ["backup.ps1", "restore.ps1", "postgres-backup-common.ps1"]:
        code = (
            "$tokens=$null; $errors=$null; "
            "[void][Management.Automation.Language.Parser]::ParseFile("
            f"'{ROOT / 'scripts' / name}',[ref]$tokens,[ref]$errors); "
            "if ($errors.Count) { $errors; exit 1 }"
        )
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-Command", code],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_restore_timeout_with_blocked_binary_input_retains_new_copy(tmp_path, fake):
    cfg, run = fake
    cfg["sleep"] = "pg_restore"
    source = bundle(tmp_path)
    # Larger than an OS pipe buffer, so timeout must also cancel a pending write.
    data = ARCHIVE + b"\x00\xff" * (1024 * 1024)
    (source / "database.dump").write_bytes(data)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(byteLength=len(data), sha256=hashlib.sha256(data).hexdigest())
    manifest_path.write_text(json.dumps(manifest))
    start = time.monotonic()
    result = restore(run, source, TimeoutSeconds=1)
    assert time.monotonic() - start < 8
    assert result.returncode != 0
    assert (tmp_path / "created").read_text() == "copy"
    assert not (tmp_path / "restored").exists()
    assert not (tmp_path / "timeout-escaped").exists()
    assert (source / "database.dump").read_bytes() == data


@pytest.mark.parametrize("value", [[], {}, [{"Id": CONTAINER}], [None]])
def test_malformed_inspect_response_never_reaches_database(tmp_path, fake, value):
    cfg, run = fake
    cfg["inspect"] = value
    result = backup(run, tmp_path / "new")
    assert result.returncode != 0
    assert trace(tmp_path) == [["inspect", CONTAINER]]
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("name", ["database.dump", "manifest.json"])
def test_bundle_reparse_file_refused_where_supported(tmp_path, fake, name):
    _, run = fake
    source = bundle(tmp_path)
    original = source / name
    retained = tmp_path / ("retained-" + name)
    original.rename(retained)
    code = f"New-Item -ItemType SymbolicLink -Path '{original}' -Target '{retained}' | Out-Null"
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip("Windows file symlink creation unavailable without local privilege")
    before = retained.read_bytes()
    result = restore(run, source)
    assert result.returncode != 0
    assert trace(tmp_path) == []
    assert retained.read_bytes() == before


def large_bundle(tmp_path):
    source = bundle(tmp_path)
    data = ARCHIVE + b"\x00" * (16 * 1024 * 1024)
    (source / "database.dump").write_bytes(data)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(byteLength=len(data), sha256=hashlib.sha256(data).hexdigest())
    manifest_path.write_text(json.dumps(manifest))
    return source, data


@pytest.mark.parametrize("operation", ["backup", "restore"])
def test_list_prefix_early_zero_accepts_large_archive(tmp_path, fake, operation):
    cfg, run = fake
    cfg["early"] = "list"
    if operation == "backup":
        cfg["large_dump"] = True
        source = tmp_path / "new"
        result = backup(run, source)
        data = ARCHIVE + b"\x00" * (16 * 1024 * 1024)
    else:
        source, data = large_bundle(tmp_path)
        result = restore(run, source)
    assert (tmp_path / "list.prefix").read_bytes() == b"P"
    assert "list exit=0" in (tmp_path / "receipts.jsonl").read_text()
    assert result.returncode == 0, result.stdout + result.stderr
    if operation == "restore":
        assert (tmp_path / "created").read_text() == "copy"
        assert (tmp_path / "pg_restore.input").read_bytes() == data
    assert (source / "database.dump").read_bytes() == data
    assert (
        json.loads((source / "manifest.json").read_text())["sha256"]
        == hashlib.sha256(data).hexdigest()
    )


@pytest.mark.parametrize("operation", ["backup", "restore"])
def test_list_prefix_early_nonzero_rejects_large_archive(tmp_path, fake, operation):
    cfg, run = fake
    cfg.update(early="list", early_code=23)
    if operation == "backup":
        cfg["large_dump"] = True
        source = tmp_path / "new"
        result = backup(run, source)
        assert not (source / "manifest.json").exists()
    else:
        source, data = large_bundle(tmp_path)
        result = restore(run, source)
        assert_no_creation(tmp_path)
        assert (source / "database.dump").read_bytes() == data
    assert (tmp_path / "list.prefix").read_bytes() == b"P"
    assert "list exit=23" in (tmp_path / "receipts.jsonl").read_text()
    assert result.returncode != 0


def test_restore_prefix_early_zero_remains_input_strict_and_retains_copy(tmp_path, fake):
    cfg, run = fake
    cfg["early"] = "pg_restore"
    source, data = large_bundle(tmp_path)
    result = restore(run, source)
    assert (tmp_path / "pg_restore.prefix").read_bytes() == b"P"
    assert "pg_restore exit=0" in (tmp_path / "receipts.jsonl").read_text()
    assert result.returncode != 0
    assert (tmp_path / "created").read_text() == "copy"
    assert not (tmp_path / "restored").exists()
    assert (source / "database.dump").read_bytes() == data


def test_list_prefix_does_not_bypass_deadline_or_creation_gate(tmp_path, fake):
    cfg, run = fake
    cfg.update(early="list", early_sleep=True)
    source, data = large_bundle(tmp_path)
    start = time.monotonic()
    result = restore(run, source, TimeoutSeconds=1)
    assert time.monotonic() - start < 8
    assert result.returncode != 0
    assert (tmp_path / "list.prefix").read_bytes() == b"P"
    assert_no_creation(tmp_path)
    assert (source / "database.dump").read_bytes() == data
    pid = int((tmp_path / "sleep.pid").read_text())
    check = subprocess.run(
        [
            "pwsh",
            "-NoProfile",
            "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 1 }}",
        ],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert check.returncode == 0
    assert not (tmp_path / "timeout-escaped").exists()
