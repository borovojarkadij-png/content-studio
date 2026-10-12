# Task 2: Windows native backup contract CI gate

Status: implemented, self-reviewed, locally verified once; ready for independent
source review and controller-owned exact-head hosted verification.

Base: `6b96be1f3e994490a9f633b24c0f571c8b3861e0`.
Source/docs commit: `81920abdda0068d3a94068cc2294ab77fbc2f5d2`
(`ci: gate Windows native PostgreSQL backup contracts`). This report is committed
separately so it can identify the immutable implementation commit.

## Scope and prerequisites

Read the complete task-2 brief, current workflow, contract prerequisites/harness,
backend pyproject/conftest, backup operator docs, and applicable executing-plans,
verification-before-completion, using-git-worktrees, and finishing-a-development-
branch skills. using-superpowers explicitly excludes dispatched subagents.
No applicable AGENTS.md was found in the scoped tree or workspace ancestors.
The task's explicit current-checkout, sole-writer, targeted-test, local-commit-only
instructions override broader generic workflow suggestions. No helper/reviewer
agents were spawned.

Verified branch `codex/dark-navy-ui`, HEAD equal to BASE, and origin
`https://github.com/borovojarkadij-png/content-studio.git`. The unrelated legacy
remote was only listed by `git remote -v`; it was not contacted or changed.
Root-owned dirty docs were preserved. No merge, force, push, dispatch, real Docker
command, service, provider, credential/session/media, operational DB, queue, or
worker changes occurred. REJECT -> rewrite_allowed=false -> no new RewriteJob ->
rewrite calls=0 behavior is untouched: no application source was modified.

The baseline has eight YAML job definitions, including a two-entry
docker-persistence matrix, hence nine existing job executions. Controller was
informed of that precise interpretation. Every existing definition/command,
trigger, and permission remains unchanged.

## Implementation

Only `.github/workflows/ci.yml` and the final continuous-verification section of
`docs/BACKUP_RESTORE.md` changed in the implementation commit (44 workflow lines;
docs +22/-4; total +66/-4). This report is the third owned path.

Added independent `windows-backup-contracts`, named `Windows PostgreSQL backup
contracts`, `windows-latest`, ten-minute timeout, backend cwd, pwsh shell,
checkout@v4, setup-python@v5/Python 3.12, and required
`python -m pip install -e ".[dev]"`. Preflight checks actual PowerShell major >=7
and `$env:WINDIR/Microsoft.NET/Framework64/v4.0.30319/csc.exe` as a leaf; missing
prerequisites throw explicitly.

The consumer refuses an existing evidence directory before pytest can delete or
reuse a basetemp. It retains pytest terminal streams with Tee-Object, captures
`$LASTEXITCODE` immediately, exits with nonzero pytest status before parsing JUnit,
and refuses zero non-skipped testcases. PSNativeCommandUseErrorActionPreference
is explicitly false so native status can be captured by the prescribed gate;
ErrorActionPreference Stop still fails filesystem/XML/pipeline errors. It has no
continue-on-error, secrets, services, caches, or environment activation.

The always-attempted upload-artifact@v4 uploads only the new synthetic evidence
directory, with hidden files, artifact name `windows-backup-contracts`, retention
14 days. Fixture configuration contains synthetic values/diagnostic sentinels,
not operational secrets. There is no general workspace/environment upload.
Docs distinguish this synthetic native boundary proof from Windows Docker Desktop
recovery, SQL/ciphertext/original-key/drift checks, live acceptance, and release.

## Exact verification commands and results

All commands below ran with PowerShell 7.6.5. Local Python is 3.12.10, pytest
8.4.2, PyYAML 6.0.3. The existing local shared harness imports Telethon; only its
child-shell PYTHONPATH was set to the supplied explicit Telethon 1.45 installation.
No local dependency installation or full backend/UI/old Docker suite was needed.

Structural YAML check (repo cwd; exit 0):

```powershell
python -c "import pathlib,subprocess,yaml; p=pathlib.Path('.github/workflows/ci.yml'); old=yaml.safe_load(subprocess.check_output(['git','show','HEAD:.github/workflows/ci.yml'],text=True)); new=yaml.safe_load(p.read_text()); original_jobs=new['jobs'].copy(); job=original_jobs.pop('windows-backup-contracts'); assert original_jobs==old['jobs']; new_without_job=new.copy(); new_without_job['jobs']=original_jobs; assert new_without_job==old; assert job['runs-on']=='windows-latest' and job['timeout-minutes']==10; assert job['defaults']['run']=={'shell':'pwsh','working-directory':'backend'}; print('YAML PASS: all 8 original definitions / 9 matrix-expanded executions and triggers/permissions unchanged; one independent Windows job'); print('Bounded job steps:',len(job['steps']))"
```

Output: `YAML PASS: all 8 original definitions / 9 matrix-expanded executions and triggers/permissions unchanged; one independent Windows job`; `Bounded job steps: 6`.

PowerShell parse plus actual preflight and import check (repo cwd; exit 0):

```powershell
$taskBlocks = python -c "import pathlib,json,yaml; w=yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text()); print(json.dumps([s['run'] for s in w['jobs']['windows-backup-contracts']['steps'] if 'run' in s]))" | ConvertFrom-Json
foreach ($taskBlock in $taskBlocks) {
    $taskTokens=$null; $taskErrors=$null
    [void][System.Management.Automation.Language.Parser]::ParseInput($taskBlock,[ref]$taskTokens,[ref]$taskErrors)
    if ($taskErrors.Count) { $taskErrors; throw 'PowerShell parse failed' }
}
Write-Output "PowerShell AST PASS: $($taskBlocks.Count) run blocks"
& ([scriptblock]::Create($taskBlocks[0]))
Write-Output "Native prerequisites PASS: PowerShell $($PSVersionTable.PSVersion), compiler $taskCompiler"
$env:PYTHONPATH='D:/Codex-Recovery/content-studio-20261008/telethon-145'
python -c "import telethon; assert telethon.__version__=='1.45.0'; print('Local shared harness Telethon='+telethon.__version__)"
```

Output: `PowerShell AST PASS: 3 run blocks`; `Native prerequisites PASS:
PowerShell 7.6.5, compiler `; `Local shared harness Telethon=1.45.0`.
The compiler variable is scoped inside the invoked preflight scriptblock, so the
outer diagnostic prints a blank value; the actual leaf check succeeded. A direct
`Test-Path -LiteralPath "$env:WINDIR/Microsoft.NET/Framework64/v4.0.30319/csc.exe"`
also returned `True` during prerequisite inspection, and fixture compilation
succeeded in the actual run.

Original workflow text preservation (repo cwd before source commit; exit 0):

```powershell
python -c "import pathlib,subprocess; old=subprocess.check_output(['git','show','HEAD:.github/workflows/ci.yml'],text=True); new=pathlib.Path('.github/workflows/ci.yml').read_text(); start=new.index('  windows-backup-contracts:'); end=new.index('  backend:',start); assert new[:start]+new[end:]==old; print('Byte-equivalent original workflow text PASS after excluding added block')"
```

Output: `Byte-equivalent original workflow text PASS after excluding added block`.

Actual consumer run, **once only**, from backend cwd, extracted directly from
the edited YAML. Only the evidence path is substituted to a fresh unique external
D: directory; shell, pytest argv, log/native exit gate, XML gate are unchanged:

```powershell
$env:PYTHONPATH='D:/Codex-Recovery/content-studio-20261008/telethon-145'
$taskConsumer = python -c "import pathlib,yaml; w=yaml.safe_load(pathlib.Path('../.github/workflows/ci.yml').read_text()); print(next(s['run'] for s in w['jobs']['windows-backup-contracts']['steps'] if s.get('name')=='Run native backup and restore contracts once'))"
if ($LASTEXITCODE -ne 0) { throw 'Consumer extraction failed' }
$taskConsumer = ($taskConsumer -join "`n").Replace('../.artifacts/windows-backup-contracts','D:/Codex-Recovery/content-studio-20261008/task2-windows-backup-contracts-20261013-05bf94a4')
Write-Output 'Executing added consumer once with fresh external evidence: D:/Codex-Recovery/content-studio-20261008/task2-windows-backup-contracts-20261013-05bf94a4'
& ([scriptblock]::Create($taskConsumer))
```

Resolved actual pytest command:

```powershell
python -m pytest tests/test_windows_backup_restore.py -q -rs --junitxml=D:/Codex-Recovery/content-studio-20261008/task2-windows-backup-contracts-20261013-05bf94a4/junit.xml --basetemp=D:/Codex-Recovery/content-studio-20261008/task2-windows-backup-contracts-20261013-05bf94a4/fixtures 2>&1 | Tee-Object -FilePath "$taskEvidence/pytest.log"
```

Actual output and consumer exit:

```text
........................................................................ [ 86%]
...........                                                              [100%]
- generated xml file: D:\Codex-Recovery\content-studio-20261008\task2-windows-backup-contracts-20261013-05bf94a4\junit.xml -
83 passed in 34.08s
Windows native contracts executed: 83/83
exit=0
```

Independent retained XML inspection: 83 testcases, zero failures, zero errors,
zero skips. Evidence is retained intact at the named D: path. No existing fixture
was overwritten/deleted, and the suite was not replayed.

Synthetic all-SKIP negative, repo cwd, same consumer XML gate with an in-memory
all-skipped XML document substituted for its Get-Content report load. No pytest
statement is included in this extracted suffix:

```powershell
$taskConsumer = python -c "import pathlib,yaml; w=yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text()); print(next(s['run'] for s in w['jobs']['windows-backup-contracts']['steps'] if s.get('name')=='Run native backup and restore contracts once'))"
$taskConsumer = $taskConsumer -join "`n"
$taskGate = $taskConsumer.Substring($taskConsumer.IndexOf('[xml]$taskReport'))
$taskGate = $taskGate.Replace("Get-Content -LiteralPath '../.artifacts/windows-backup-contracts/junit.xml' -Raw", "'<testsuites><testsuite tests=""2"" skipped=""2""><testcase name=""synthetic-skip-1""><skipped /></testcase><testcase name=""synthetic-skip-2""><skipped /></testcase></testsuite></testsuites>'")
$taskNegativeOutput = pwsh -NoProfile -NonInteractive -Command $taskGate 2>&1
$taskNegativeExit = $LASTEXITCODE
$taskNegativeOutput
if ($taskNegativeExit -eq 0 -or ($taskNegativeOutput -join "`n") -notmatch 'No Windows native contracts executed') { throw 'All-SKIP refusal did not hold' }
Write-Output "All-SKIP negative PASS: actual consumer XML gate refused 0/2 executed with exit=$taskNegativeExit; no tests replayed"
```

Output includes `Exception: No Windows native contracts executed.`;
`All-SKIP negative PASS: actual consumer XML gate refused 0/2 executed with exit=1; no tests replayed`.
The negative verifier itself exits 0 only because the expected child failure was
confirmed. The actual consumer suffix exits 1.

## Native retained receipts and coverage

Inspected `entrypoint-status.jsonl` and `receipts.jsonl` recursively beneath only
the new evidence `fixtures` directory with Get-ChildItem/Get-Content/ConvertFrom-
Json/Group-Object. There are 82 entrypoint receipts and 112 native receipts;
parse/dot-source tests do not create entrypoint harness receipts.

| Entrypoint | exit | count | exact stdout |
|---|---:|---:|---|
| backup.ps1 | 0 | 2 | `BACKUP_OK\n` |
| backup.ps1 | 1 | 30 | empty |
| restore.ps1 | 0 | 3 | `RESTORE_OK: new database copy created.\n` |
| restore.ps1 | 1 | 47 | empty |

| Native command | exit 0 | exit 23 |
|---|---:|---:|
| inspect | 44 | 2 |
| psql | 30 | 2 |
| pg_dump | 7 | 1 |
| list | 10 | 4 |
| createdb | 6 | 1 |
| pg_restore | 4 | 1 |

All 11 deliberately nonzero native receipts remain exit 23; script-level refusal
receipts remain exit 1. Timeout processes intentionally do not reach final native
receipt writes. Success/negative stdout checks independently confirmed exact
strings above. Assertions also cover private diagnostic redaction, original
sentinels, exact argv, binary roundtrip, create-only refusals, identity/bundle/
version/input/reparse checks, large early-list success/nonzero, strict early
restore input, blocked input and owned timeout PID behavior. No assertion, skip,
script, or test source changed. These results are native synthetic boundary proof,
not a claim of real Docker/operational recovery.

## Frozen source hashes and self-review

Working-file SHA256 values captured after the run:

```text
.github/workflows/ci.yml 2ebedefc7e1348d82461f540f1ba81b714473e93652f2be227ac8e1943e5ee3d
docs/BACKUP_RESTORE.md 7c10da5dd1185d9ae6d1626343fe2ab0ad34c15bb73524fb7490ba5803b0afd2
scripts/backup.ps1 8cbbab19b20fe19d9c207507c796124b0e91a3d6c3d7df18be4f5aeee2c5eb65
scripts/restore.ps1 acf8c5bd529bfcf4d9a92e903c2c9b05796bf256993a38a5f79d1f256e967a17
scripts/postgres-backup-common.ps1 427e7a147a8b1062c5ebea3cbb49d44ff95a597509554e2324794f4be27bf40f
backend/tests/test_windows_backup_restore.py 47c0ed72db7c90a0393783ad5e04458c047395d8357e492a961f6e17efcf341e
```

The four frozen script/test hashes exactly match the reviewed Task1 fix freeze.
`git diff --exit-code -- scripts/backup.ps1 scripts/restore.ps1 scripts/postgres-backup-common.ps1 backend/tests/test_windows_backup_restore.py`
returned 0. `git diff --check -- .github/workflows/ci.yml docs/BACKUP_RESTORE.md`
and `git diff --cached --check` returned 0. Git emitted only expected configured
LF-to-CRLF working-copy notices. The report cannot contain its own stable hash.

Self-review read the complete scoped diff and checked every brief requirement:
bounded independent job, exact actions/versions/cwd/install, explicit prerequisite
refusal, one native run, create-only paths, Tee log and immediate native exit,
zero-executed negative, narrowly scoped always-upload, and operator proof limits.
No source defect or unresolved local test failure found. Local pytest native
statuses were verified above, rather than inferred from JUnit alone.

Source commit commands (repo cwd):

```powershell
git add -- .github/workflows/ci.yml docs/BACKUP_RESTORE.md
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git commit -m "ci: gate Windows native PostgreSQL backup contracts"
git rev-parse HEAD
```

The staged path list contained exactly the two implementation paths; commit
reported two files, 66 insertions, four deletions and the hash above.
Report commit uses only `git add -f -- .superpowers/sdd/BACKUP_RESTORE_IMPLEMENTATION/task-2-report.md`,
then staged check and `git commit -m "docs: record Windows backup contract CI evidence"`.

Remaining concern/gate: no hosted Actions execution or hosted pip install is
claimed by this local run. Controller must perform independent source review,
authorized exact-head push, and track the real hosted job. This writer did not
push or dispatch. Root-owned documentation changes and all retained evidence
remain intact for that next step.
