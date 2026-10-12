# Windows Backup/Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make the approved Windows PostgreSQL backup/restore commands honest,
binary-safe, explicitly targeted and non-destructive.

**Architecture:** Thin existing PowerShell entry points share one focused helper
for inspected target identity, bounded native commands and bundle validation.
Restore creates a new database copy only; it never alters an existing database.

**Tech Stack:** PowerShell7/.NET, Docker CLI/PostgreSQL16 tools, pytest subprocess
contract harness. No new application/package dependency.

**Spec:** docs/BACKUP_RESTORE_DESIGN_20261013.md

## Global Constraints

Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
codex/dark-navy-ui; no merge/force/push by implementer.
PowerShell7 is required; no local Python dependency for user commands.
No existing destination/database overwrite/drop/--clean, no volume deletion.
No real credentials/session/media/operational DB/queue/worker changes.
REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
All native failures nonzero, private fixed errors, bounded processes, binary-safe.
No master/secrets generation or source data/credentials in logs/manifests.
Only new synthetic test fixtures; independent source review before root Docker.

---

### Task 1: Guarded paired backup/restore scripts and regression contracts

**Files:**
- Modify scripts/backup.ps1 and scripts/restore.ps1.
- Create scripts/postgres-backup-common.ps1.
- Create backend/tests/test_windows_backup_restore.py.
- Create docs/BACKUP_RESTORE.md.
- Own task-1-report.md in this plan's SDD workspace.

**Interfaces:**
Backup explicit parameters Destination, ContainerId, ProjectName, Database, User,
TimeoutSeconds(default120,1..1800). Restore explicit Source, ContainerId,
ProjectName, User, TargetDatabase, TimeoutSeconds(samebounds). Backup bundle
database.dump plus strict version1 manifest.json; both entrypoints invoke shared
helper, neither dot-source entrypoint executes work as helper. Root owns actual
Docker acceptance/CURRENT_STATE/IMPLEMENTATION_PLAN/exactCI. No UI/API/Compose/
workflow/pyproject changes in this task.

- [ ] Read spec and existing scripts/Compose exactly; reproduce old missing
  native handling with a deterministic fake native Docker child. Example test
  shape (use existing test subprocess conventions):
  ```python
  def test_dump_failure_cannot_create_success_manifest(tmp_path, fake_docker):
      fake_docker.fail_command("pg_dump", code=23)
      result = run_backup(tmp_path, fake_docker)
      assert result.returncode != 0
      assert not (tmp_path / "bundle" / "manifest.json").exists()
  ```
  The test helper must really execute pwsh/entrypoint/native shim and record its
  argv. Missing parameter/import/server startup is not a behavioral RED.
- [ ] Implement minimal guarded script/helper. Use full exact inspected ID/
  project/service/running and source PostgreSQL env binding before commands;
  reject path reparses/existing destination, stream bytes to a new archive,
  check dump native exit then pg_restore archive list, then write strict manifest.
  Native process shape:
  ```powershell
  $processInfo = [Diagnostics.ProcessStartInfo]::new()
  $processInfo.UseShellExecute = $false
  $processInfo.RedirectStandardOutput = $true
  $processInfo.RedirectStandardError = $true
  foreach ($argument in $arguments) { $processInfo.ArgumentList.Add($argument) }
  ```
  Implement stream draining/finite deadline/immediate exit checking around this
  boundary; stdout remains bytes, stderr never enters public errors. Reuse only
  owned process handle; no orphan-tree/process-name/container termination.
- [ ] Restore strictly validates source bundle/schema/hash/length/list before
  creating anything. It checks exact target container, rejects existing/source
  DB, creates copy exactly once, restores with --exit-on-error/no-owner/no-privileges
  and fails visibly on any native error without deleting partial copy. SQL target
  existence lookup uses safe validated literal/argument handling, never shell.
- [ ] Add positive and adversarial fake-native cases: binary non-UTF8 roundtrip,
  literal Unicode/spaced paths, exit23 dump, invalid list, createdb/restore nonzero,
  stopped/foreign/truncated-ID/wrongproject/service/role/db, malformed manifests,
  hash/length tamper, all existingdest/target refusals, reparses where supported,
  timeout with owned-child proof, no private stderr leak or destructive argv.
  Assert prior sentinel files/data survive all refusal paths. Safe copy is retained
  after restore failure, never reported as success.
- [ ] Run targeted file from backend cwd with explicit Telethon1.45 if imported,
  Ruff0.17 check/format, PowerShell parser on all3scripts, compile/test harness.
  Do not run full backend/UI/oldDocker suites for this script-only change.
- [ ] Write complete human docs with literal backup/restore commands and all
  spec limits; show private destination and separate key/media backup, no false
  production acceptance. Full report includes behavioralRED/GREEN actual commands/
  output/native statuses, failures, exact frozen owned hashes, trust boundaries,
  source self-review and owned commit. No secrets/full inspect output.
- [ ] Commit only owned code/docs/report; root source review and actual synthetic
  Windows archive/copy SQL/drift gate follows, then exact final CI. No source
  success alone promotes Windows runtime/release/live acceptance.

### Task 2: GitHub Windows native-contract gate

**Files:**
- Modify .github/workflows/ci.yml.
- Modify docs/BACKUP_RESTORE.md, continuous verification section only.
- Own task-2-report.md in this plan's SDD workspace.

**Interfaces:** Consumes reviewed Task1 actual Windows contract file, no script or
test changes. Produces a new independent job windows-backup-contracts, name
Windows PostgreSQL backup contracts, runs-on windows-latest, timeout-minutes10.
Existing nine jobs/commands/permissions/on triggers remain unchanged.

- [ ] Read existing workflow and contract prerequisite skips. Add checkoutv4,
  setup-pythonv5/python3.12, `python -m pip install -e ".[dev]"` from backend cwd.
  Preflight actual PowerShell Major>=7 and native compiler at
  `$env:WINDIR/Microsoft.NET/Framework64/v4.0.30319/csc.exe`; absent prerequisites
  must fail explicitly, never turn the entire job into successful skipped tests.
- [ ] Run the actual native contracts once with finite job budget and synthetic
  create-only fixture/evidence paths. Use this consumer shape in pwsh:
  ```powershell
  python -m pytest tests/test_windows_backup_restore.py -q -rs --junitxml=../.artifacts/windows-backup-contracts/junit.xml --basetemp=../.artifacts/windows-backup-contracts/fixtures
  $taskTestExit = $LASTEXITCODE
  if ($taskTestExit -ne 0) { exit $taskTestExit }
  [xml]$taskReport = Get-Content -LiteralPath '../.artifacts/windows-backup-contracts/junit.xml' -Raw
  $taskCases = @($taskReport.SelectNodes('//testcase'))
  $taskExecuted = @($taskCases | Where-Object { $null -eq $_.SelectSingleNode('skipped') })
  if ($taskExecuted.Count -eq 0) { throw 'No Windows native contracts executed.' }
  ```
  Retain terminal output in an artifact log without losing immediate native exit;
  don't change assertions/skips or silence native errors. No real docker command,
  service, secret, cache or provider activation. Don't set continue-on-error.
- [ ] Upload `.artifacts/windows-backup-contracts` using actions/upload-artifactv4,
  name windows-backup-contracts, if:always(), include-hidden-filestrue,14days.
  This contains only synthetic fixtures/argv/receipts/output/JUnit. No general
  workspace/env/credential upload. Update operator docs to distinguish hosted
  contract proof from Windows Docker Desktop restore and live acceptance.
- [ ] Validate YAML and PowerShell block syntax; execute the added consumer
  locally once to verify actual native receipts/JUnit counts/zero failures.
  Exercise its zero-executed XML refusal with a synthetic all-SKIP report without
  rerunning tests. No full backend/frontend/old Docker suites for this CI change.
- [ ] Complete report with exact commands/results/native statuses/source hashes/
  scoped diff/self-review and owned commit. No push or Actions dispatch by writer;
  root source review then authorized exact-head push/real hosted job tracking.
