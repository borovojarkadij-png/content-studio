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
