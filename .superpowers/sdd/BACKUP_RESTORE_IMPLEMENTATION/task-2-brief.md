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
