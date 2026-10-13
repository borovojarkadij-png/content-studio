# Task 1 report: fixed native-text destination capacity

Status: DONE. Base: `205199010669d1c2850e34cc8a0fb41cb67ac94d`.
Branch: `codex/dark-navy-ui`; origin: `https://github.com/borovojarkadij-png/content-studio.git`.

## Implementation and ownership

Changed only these two source/test files and this report:

- `scripts/postgres-backup-common.ps1`: within `Get-BackupNativeText`, replace
  the expandable destination with a writable, non-expandable 1,048,576-byte
  backing array and reset Length to zero before the native boundary. Retained
  the final size guard, strict UTF-8 decoder, disposal, signatures and lifecycle.
- `backend/tests/test_windows_backup_restore.py`: add six actual-helper cases
  and eight actual-entrypoint cases. Existing 83 cases/assertions are retained.
- `.superpowers/sdd/BACKUP_OUTPUT_CAP_IMPLEMENTATION/task-1-report.md`.

The actual helper is dot-sourced in private PS7 processes. Only
`Invoke-BackupNative` is replaced in the helper cases; the real destination,
guard and decoder execute. Chunk writes expose peak Capacity even when the
write throws. Cases cover empty, exact-limit ASCII, exact-limit valid multibyte
UTF-8, one byte over, chunked overflow and invalid UTF-8. Valid content is
checked through independently computed SHA256 of the returned text.

The existing native C# Docker shim gains only an explicit synthetic oversized
stdout mode with private markers on stdout/stderr. Backup and restore are
tested at both inspect and version preflight, with 257 writes of 4,096 bytes
and with 4,096 writes of 4,096 bytes (blocked writer). The latter cannot finish
after the fixed destination faults. Each test uses TimeoutSeconds=1, finishes
within eight seconds, proves the recorded owned PID has exited, and proves an
unrelated child remains alive. Trace assertions exclude later pg_dump,
createdb and pg_restore. Source bundle snapshots, source sentinel and absent
new destination are retained. No real Docker, database, provider, key, login,
publication or network operation was used.

## Runtime and evidence

Evidence root: `D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a`.
Python: 3.12.10. PS7: 7.6.5 at
`C:/Users/borov/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe`;
`pwsh` resolves there on PATH. Ruff: 0.17.0 at
`D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe`.
No machine-specific path was added to product or tests.

All pytest commands ran from `<workspace>/backend`, with TEMP and TMP set to
`D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/temp`.
Each used this exact executable/import prefix, followed by the exact argument
list shown below (the list is the value passed to `pytest.main`):

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0', telethon.__version__; import pytest; sys.exit(pytest.main(ARGUMENT_LIST))"
```

Telethon injection is only runner setup before pytest/conftest imports; no SDK
or dependency change. Output of each invocation was piped with `2>&1 |
Tee-Object -FilePath '<evidence root>/<log name>'`. `$LASTEXITCODE` was captured
immediately after the pipeline, printed as `NATIVE_EXIT`, and used as the
shell exit. Native/helper statuses also remain in each basetemp directory.

## TDD RED and subsequent commands/results

1. Before changing production allocation:

```python
['-q','tests/test_windows_backup_restore.py','-k','native_text_destination and overflow_chunks','--basetemp=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/red-tmp','--junitxml=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/01-red.xml']
```

`01-red.log`, `01-red.xml`: native exit 1, **1 failed, 88 deselected** in
0.59s. This is the intended causal assertion failure, not import/collection
failure: rejected=true, error=`output size`, initialLength=0, writes=257,
peakCapacity=2097152. The actual PS helper subprocess exited 0 because the
test catches rejection and reports JSON; pytest correctly exited 1 on
`2097152 <= 1048576`. Raw JSON is retained at
`red-tmp/test_native_text_destination_c0/helper-status.json`. This committed
regression independently reproduces the root's earlier probe.

2. First focused run after the allocation correction:

```python
['-q','tests/test_windows_backup_restore.py','-k','native_text_destination or oversized_native_text','--basetemp=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/green-tmp','--junitxml=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/02-focused-green.xml']
```

`02-focused-green.log`, `02-focused-green.xml`: native exit 1, **12 passed,
83 deselected, 4 errors** in 10.36s. Pytest expanded large expected strings
into case IDs; Windows rejected PYTEST_CURRENT_TEST environment values above
32,767 characters during ASCII/multibyte setup and teardown. Added explicit
short IDs only; no behavior/assertion was weakened. Logs/JUnit and temporary
receipts, including this failed run, remain retained.

3. Focused GREEN with concise IDs:

```python
['-q','tests/test_windows_backup_restore.py','-k','native_text_destination or oversized_native_text','--basetemp=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/green2-tmp','--junitxml=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/03-focused-green.xml']
```

`03-focused-green.log`, `03-focused-green.xml`: native exit 0, **14 passed,
83 deselected** in 10.10s. No skips or warnings. Ruff format initially flagged
the newly added IDs line; wrapped that list to its requested format before
the full module run. This formatting-only correction changed no assertions.

4. Full Windows contract module, run once after the final test formatting:

```python
['-q','tests/test_windows_backup_restore.py','--basetemp=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/full-tmp','--junitxml=D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/04-full.xml']
```

`04-full.log`, `04-full.xml`: native exit 0, **97 passed in 44.35s**.
JUnit: tests=97, failures=0, errors=0, skipped=0. All 83 prior Windows cases
ran, plus 14 new cases. No full backend run was requested or performed.

Every helper case recorded peakCapacity=1048576 and initialLength=0. Both
overflows failed at the extra write with `Memory stream is not expandable`;
invalid UTF-8 failed at the actual strict decoder. Helper subprocess exits
are zero because expected rejections are caught, with empty stderr/private
marker absent. All eight oversized entrypoint invocations recorded exit 1,
empty stdout and generic private failure stderr; their status JSONL, PID,
trace, native receipts and synthetic bundles remain under `full-tmp`.

5. Static/compile/parser checks from the workspace root, retained in
`05-static.log`. Exact commands:

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check backend/tests/test_windows_backup_restore.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check backend/tests/test_windows_backup_restore.py
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/pycache'
python -m py_compile backend/tests/test_windows_backup_restore.py
& 'C:/Users/borov/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe' -NoProfile -NonInteractive -Command '$names = @("backup.ps1", "restore.ps1", "postgres-backup-common.ps1"); foreach ($name in $names) { $tokens = $null; $errors = $null; [void][Management.Automation.Language.Parser]::ParseFile((Join-Path (Get-Location) "scripts/$name"), [ref]$tokens, [ref]$errors); if ($errors.Count) { $errors; exit 1 }; Write-Output "PARSE_OK: $name" }'
git diff --check -- scripts/postgres-backup-common.ps1 backend/tests/test_windows_backup_restore.py
```

All five native exits 0; Ruff clean, one file already formatted, Python
compilation clean, all three PowerShell scripts parse. Git emitted only the
existing LF-to-CRLF working-copy notices; diff check exit 0.

## Self-review and source freeze

Read the complete scoped diff after all tests finished. Production change is
only two allocation/initialization lines inside Get-BackupNativeText. Existing
Invoke-BackupNative and all caller, archive, input-close and privacy behavior
are unchanged. Existing 83 tests and assertions are unchanged. No new
dependency, production custom stream, entrypoint or unrelated source edit.

SHA256 of final working-tree bytes, frozen after the 97-case run and static
checks, with no later source changes:

- `scripts/postgres-backup-common.ps1`:
  `2C79B0BC2AE32D10D2E8E6B4981FF6483D2BD5328AD9758DEF51CA9F646EB9C3`
- `backend/tests/test_windows_backup_restore.py`:
  `426297CB861524235AC660E72ED232844224402ACD47094DFF636087B4944C99`

Root's dirty documentation/ledger changes were preserved and excluded from
the task commit. No staging or commit occurred while tests were running.
Root owns immutable review packaging, original-probe recheck, documentation,
GitHub and exact-generation Windows integration evidence.

## Limits and concerns

No unresolved correctness concern found in scoped self-review. The guarantee
is destination Capacity, not whole-process RSS, decode allocation or pipe/task
buffer memory. Blocked overflow can wait for the existing finite native
deadline; no immediate cancellation claim. Tests use the deterministic shim,
not operational backup/restore. This work grants no editorial/publication
authority, and makes no whole-app backup, release or PHASE completion claim.
