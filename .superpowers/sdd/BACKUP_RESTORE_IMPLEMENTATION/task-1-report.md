# Task 1 implementation evidence

Status: DONE for source and synthetic Windows contract verification. Independent
source review and the root-owned actual Windows PostgreSQL copy/drift/release gate
remain separate. No production recovery, release, live-provider, or actual Docker
acceptance is claimed here.

Base: `cf3892987f78b36856996b92fe6eb06a44bce540`, branch `codex/dark-navy-ui`.
Source commit: `7861c4ae71a2ddaec40b8f76ec98453e57d0e037`
(`fix: guard Windows PostgreSQL backup and create-only restore`).
This report is committed separately after the source freeze so it can name that
immutable source commit without a circular self-reference.

## Scope and implementation

Owned source paths only:

- `scripts/backup.ps1`
- `scripts/restore.ps1`
- `scripts/postgres-backup-common.ps1`
- `backend/tests/test_windows_backup_restore.py`
- `docs/BACKUP_RESTORE.md`

This report is the sixth owned path. Root-owned CURRENT_STATE, design, plan,
requirements/ledger, and the operator fixture were not edited or staged by this
implementer. No UI/API/Compose/workflow/pyproject/dependency changes, no pushes,
subagents/reviewers, real Docker operations, secrets, provider calls, or network.

The scripts require explicit full container/project/database/role inputs. The
shared helper inspects exact ID, running state, Compose project/service labels,
and POSTGRES_DB/POSTGRES_USER before database commands. All native invocations use
ProcessStartInfo/ArgumentList with no shell. stdout archive bytes stream directly
to a CreateNew file; stderr drains concurrently into a discard sink. Each command
has a shared finite stream/process deadline (120s default, 1–1800s); timeout kills
only its owned process handle, never a process tree, unrelated process/container,
or server-side SQL command.

Backup refuses existing destinations and path reparses, preserves any new partial
archive, checks native dump exit, signature and native pg_restore list before
writing a strict version1 manifest. Restore validates exact bundle structure,
JSON types/keys/duplicate keys, provenance, positive length/hash, compatible major
version, actual target identity and archive list before any creation. It retains
one read-only archive handle through verification and restore. The explicit target
must differ from source and not exist; createdb runs once, then pg_restore uses
exit-on-error/no-owner/no-privileges. Native errors return1 and preserve partial
copies. No drop/clean/overwrite/retry/recreate/key generation/migration path exists.

The controller explicitly accepted the strict manifest fields and recovery into a
different explicit inspected container/project, with configured source database
and role matching the manifest. The tests cover that alternate recovery target.

## Environment and commands

Repository directory:
`C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2`.
Test commands below used its `backend` cwd unless stated otherwise.

Observed versions: Windows, Python3.12.10, pwsh7.6.5, pytest8.4.2, Ruff0.17.0.
The global Telethon is1.44.0; every pytest invocation explicitly set:

```powershell
$env:PYTHONPATH='D:/Codex-Recovery/content-studio-20261008/telethon-145'
```

The final explicit import reported `Telethon=1.45.0`. Shared conftest imports are
therefore checked under the requested version. No install or dependency edit.
The native fake is compiled by the test session using:

```text
C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe /nologo /r:System.Web.Extensions.dll /out:<test-temp>/native-docker0/docker.exe <test-temp>/native-docker0/FakeDocker.cs
```

The compiled native executable launches no child and has no Docker or network
dependency. It records argv, writes binary fixture bytes, drains stdin, records
immediate native return receipts, can flood stderr, exit23, or sleep. Every script
is executed in an actual pwsh subprocess with its cwd set to its unique fixture;
the fake executable is first on that subprocess's PATH. No PowerShell function
mock or text-level script assertion replaces the implementation.

## Genuine behavioral RED before source changes

Initial tests used valid old interfaces, explicit synthetic ambient role/database,
and the actual old entrypoints: backup `-Destination <tmp>/bundle`, restore `-Source
<tmp>/legacy.sql`. They verified native argv and exit23 receipts before asserting
the script exit. The test source was then updated for the new explicit interface.

Command:

```powershell
python -m pytest tests/test_windows_backup_restore.py -q -p no:cacheprovider
```

Observed complete result summary and decisive assertions:

```text
FF [100%]
test_dump_native_failure_is_nonzero_and_has_no_success_manifest:
  traced pg_dump; receipts contained pg_dump exit=23
  assert result.returncode != 0
  E assert 0 != 0
  CompletedProcess returncode=0, stdout='', stderr='PRIVATE_DIAGNOSTIC_NEVER_PRINT'
test_restore_native_failure_is_nonzero:
  traced psql; receipts contained psql exit=23
  assert result.returncode != 0
  E assert 0 != 0
  CompletedProcess returncode=0, stdout='partial', stderr='PRIVATE_DIAGNOSTIC_NEVER_PRINT'
2 failed in 0.80s
```

Pytest's full stack merely locates those two assertions; neither failure involved
missing arguments, import errors, server startup, or the new interface. The
private diagnostic is a synthetic sentinel, never a real password.

Root cause: existing scripts invoke native docker without checking native exit;
PowerShell completes normally despite23. Backup uses text redirection and can
overwrite; restore text-pipes arbitrary SQL without ON_ERROR_STOP. Both leak native
stderr and select service/role/database from ambient context.

## Development failures and correction record

All nonzero development events are recorded here; none is omitted as a pass:

1. Discovery read of `docker-compose.yml` failed because the repository uses
   `compose.yaml`; read the actual Compose file completely next. An initial
   Get-Command discovery also returned nonzero for absent optional tools. No write.
2. Expanded preimplementation test command (same pytest command above):
   `36 failed, 21 passed in 47.10s`. The old implementation could not satisfy the
   explicit identity/bundle/refusal/output contract. Initial two-test native RED
   above is the causal proof; these additional failures are not substituted for it.
3. First patch request was rejected because delete+add targeted the same existing
   file twice. No change from that rejected patch; applied ordinary Update hunks.
4. First shared-helper implementation test run: `27 failed, 30 passed in 11.89s`.
   Parser inspection identified invalid PowerShell `-cjoin`; replaced with `-join`.
5. Next run: `27 failed, 30 passed in 15.21s`. Synthetic-only diagnostic invocation
   of the helper showed Process.Start trying a concatenated multi-match executable
   path. Get-Command returned the shim plus installed docker matches; selected the
   first PATH-resolved Application. No real executable started in those failures.
6. A status read incorrectly used `backend/backups` from backend cwd and failed
   path lookup; subsequent read used the verified absolute path. No write.
7. Native contracts then passed: `57 passed in 20.78s`.
8. Expanded cases passed `70 passed in 25.00s`, but first Ruff check returned I001
   for import ordering and format --check reported one unformatted file. Explicit
   Ruff0.17 check --fix/format corrected only this owned test file. Subsequent run:
   `70 passed in 25.29s`.
9. Added blocked-input timeout, malformed inspect and reparse-file cases:
   `7 passed, 70 deselected in 3.91s`, zero skips.
10. Full freeze run01: `77 passed in 28.73s`, but manual saved-receipt review found
    `System.Threading.Tasks.VoidTaskResult` emitted before success output. Added
    an exact public stdout assertion before fixing. Command:
    `python -m pytest tests/test_windows_backup_restore.py -q -p no:cacheprovider -k binary_roundtrip`.
    RED: `1 failed, 76 deselected in 0.84s`; expected `BACKUP_OK\n`, got
    `System.Threading.Tasks.VoidTaskResult\nBACKUP_OK\n`. Discarded async task return
    values explicitly with [void]. Full freeze run02 then reported
    `77 passed in 29.10s`, `pytest_exit=0`.

Old dot-sourcing during preimplementation tests wrote an empty untracked
`backend/backups/newsflow.sql` using the old default. The controller spotted that
workspace side effect. Its SHA256 was
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`; verified exact
path and length0, moved (did not delete) it to
`D:/Codex-Recovery/content-studio-20261008/backup-restore-task1-20261013-red/legacy-dot-source-newsflow.sql`.
CreationTimeUtc observed2026-10-12T23:24:19; LastWriteTimeUtc2026-10-12T23:22:13.
The empty backend/backups directory remains. All subsequent script subprocesses
run inside their fixture. Neither entrypoint now executes or prompts when loaded
by dot-sourcing.

## Final GREEN and static verification

Final source/test freeze command (after exact argv assertions and stdout fix):

```powershell
if (Test-Path -LiteralPath 'D:/Codex-Recovery/content-studio-20261008/backup-restore-task1-final-20261013-03') { throw 'Final fixture path already exists' }
python -m pytest tests/test_windows_backup_restore.py -q -p no:cacheprovider -rs --basetemp 'D:/Codex-Recovery/content-studio-20261008/backup-restore-task1-final-20261013-03'
[Console]::WriteLine('pytest_exit='+$LASTEXITCODE)
```

Final output:

```text
........................................................................ [ 93%]
..... [100%]
77 passed in 28.93s
pytest_exit=0
```

Static commands from repository cwd:

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check backend/tests/test_windows_backup_restore.py
[Console]::WriteLine('ruff_check_exit='+$LASTEXITCODE)
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check backend/tests/test_windows_backup_restore.py
[Console]::WriteLine('ruff_format_exit='+$LASTEXITCODE)
python -m py_compile backend/tests/test_windows_backup_restore.py
[Console]::WriteLine('py_compile_exit='+$LASTEXITCODE)
$verificationScripts=@('scripts/backup.ps1','scripts/restore.ps1','scripts/postgres-backup-common.ps1')
foreach ($verificationScript in $verificationScripts) {
  $parseTokens=$null; $parseErrors=$null
  [void][Management.Automation.Language.Parser]::ParseFile((Resolve-Path -LiteralPath $verificationScript),[ref]$parseTokens,[ref]$parseErrors)
  [Console]::WriteLine($verificationScript+' parser_errors='+$parseErrors.Count)
  if ($parseErrors.Count) { exit 1 }
}
git diff --check -- scripts/backup.ps1 scripts/restore.ps1
[Console]::WriteLine('diff_check_exit='+$LASTEXITCODE)
```

Observed output:

```text
All checks passed!
ruff_check_exit=0
1 file already formatted
ruff_format_exit=0
py_compile_exit=0
scripts/backup.ps1 parser_errors=0
scripts/restore.ps1 parser_errors=0
scripts/postgres-backup-common.ps1 parser_errors=0
diff_check_exit=0
```

Git additionally prints its existing autocrlf notices for the two tracked scripts
(`LF will be replaced by CRLF the next time Git touches it`); no whitespace error.

Windows tests use a module-level explicit Windows skip reason on non-Windows:
`Windows native executable and junction contract; run on Windows PS7`.
Missing Windows pwsh/compiler also skips explicitly. Ubuntu CI does not pretend to
exercise a Windows native shim. No CI configuration changed. This host ran all77
cases, including file symlinks, with zero skips. Full backend, UI, historical
Docker suites and actual Docker runtime were deliberately not run in this scoped
task, as requested.

## Native and durable evidence

Final synthetic receipts/artifacts are retained under the final-03 path above.
Each executed fixture retains `trace.jsonl` (literal argv), `receipts.jsonl`
(native return immediately before exit), and `entrypoint-status.jsonl` (actual
PowerShell exit/stdout/stderr). Timeout fixtures additionally retain the native PID;
binary fixtures retain exact archive and stdin bytes, manifest and copy markers.
No full inspect environment or actual credentials are included here.

Actual final receipts were read from the retained final-03 files, in addition to
the assertions. The selected fixture outputs were:

```text
backup success: inspect0, psql0, pg_dump0, list0; script0 stdout=BACKUP_OK
restore success: inspect0, psql0, list0, psql0, createdb0, pg_restore0;
                 script0 stdout=RESTORE_OK: new database copy created.
dump failure: inspect0, psql0, pg_dump23; script1, no manifest
restore failure: inspect0, psql0, list0, psql0, createdb0, pg_restore23;
                 script1, created copy retained, no restored marker
inspect/psql/list/createdb failures: command23, script1, no later creation/restore
timeout dump: native PID starts then is absent; script1, partial archive retained;
              unrelated pwsh process remains running
timeout restore: >2MiB binary stdin blocks, script1 under8s; created copy retained
```

The final external owned-PID check also reported `owned_pid=8108 running=False`
for blocked-input restore and `owned_pid=21528 running=False` for dump timeout.
Success stderr was empty; failure stdout was empty and stderr contained only the
fixed BACKUP_FAILED or RESTORE_FAILED message. Full native argv/receipt files remain
at the retained synthetic fixture path for independent inspection.

Tests assert exact dump/list/createdb/restore and target-lookup argv, no drop/clean/
shell/destructive argv on any case, original sentinel bytes survive every run,
bundle sentinels survive all refusals, binary non-UTF8 bytes survive roundtrip,
private stderr never reaches public output, and successful public output is exact.

## Frozen owned source hashes (SHA256 of working files)

```text
scripts/backup.ps1 8cbbab19b20fe19d9c207507c796124b0e91a3d6c3d7df18be4f5aeee2c5eb65
scripts/restore.ps1 acf8c5bd529bfcf4d9a92e903c2c9b05796bf256993a38a5f79d1f256e967a17
scripts/postgres-backup-common.ps1 9120ad72349638ff07ded48b4f54a18fb2485ab9f5bf4f8e536fa229955e526f
backend/tests/test_windows_backup_restore.py 8a77129ad6cd817a39cc02c57a49d400f33a04bcfda2ffaa1d83049917a392c5
docs/BACKUP_RESTORE.md ab257b497603bd7704d6173616aace03e86e7330fcc0c941da2c919d811df5d6
```

The report cannot contain its own stable hash; root can hash its committed version
independently. Source hashes above identify the exact files tested for root review.

## Trust boundaries, self-review and remaining gates

Assets: original database/volumes, prior backups, stable master key and media,
private database rows and diagnostics, new recovery copy. Inputs controlled by the
operator/untrusted bundle are paths, names, manifest/archives, container/project
identity. Boundaries are local filesystem/reparse resolution, JSON parsing,
PowerShell-to-native byte streams/argv, Docker identity, and PostgreSQL SQL restore.

Source self-review read the complete helper, entrypoint diff, test file and operator
docs; checked contract against the binding spec and all five owned path diffs.
Caught/fixed async return leakage, first-PATH native application selection, strict
manifest duplicate/type checking, preservation of partial copies, and PS7 baseline
API compatibility (no Path.Exists/HashData/ToHexString/WaitForExitAsync dependency).
The final extra argv assertions verify the literal SQL target lookup and exact
create-only template0 command. No unrelated refactor or observed remaining source
defect. Independent root review is still required.

SHA256 is self-consistency, not authenticity. Only a trusted own archive is safe
to execute; pg_restore list does not sanitize malicious SQL. Local private ACLs
must prevent concurrent hostile parent/bundle modification; path checks are not
a filesystem transaction against a privileged local attacker. The helper resolves
the first Docker Application on PATH, so executable/runtime PATH integrity is an
operator boundary. Native textual output is accepted only at<=1MiB after draining;
stderr/list output is discarded; custom archives stream to disk. Keys/media remain
separate; ciphertext is not decrypted or key-generated. Timeout kills the owned
CLI only; server SQL may continue, so no rollback/atomicity guarantee is made.

The methods used from TDD/systematic debugging required causal reproduction before
fixes; recovery/security methods required preserve-and-fail boundaries and trusted
archive documentation; verification required actual command receipts before claims.
No skill expanded authorization beyond the assigned synthetic/source task.

Remaining: controller's independent immutable source review; then controller-only
actual synthetic Windows backup/newDB restore, row comparison and read-only Alembic
drift/native status/hash checks; then exact final CI/release evidence. This report
does not substitute synthetic byte replay for any of those acceptance gates.
