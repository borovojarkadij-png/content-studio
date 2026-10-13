### Task 1: Enforce the fixed-capacity native-text destination and Windows regressions

**Files:** Modify scripts/postgres-backup-common.ps1 only within Get-BackupNativeText. Modify backend/tests/test_windows_backup_restore.py for focused helper/native-boundary contracts. No other product source changes.
**Consumes:** Get-BackupNativeText([string[]]$Arguments,[int]$TimeoutSeconds), Invoke-BackupNative(...,-OutputStream...), existing private Docker shim and backup/restore entrypoints.
**Produces:** Same public signatures and outputs; preallocated non-expandable destination of exactly1,048,576 bytes, initially Length0; no output-growth beyond capacity. Existing UTF8Encoding(false,true) and caller privacy retained.

- [ ] Add an isolated PowerShell contract invoking the actual dot-sourced Get-BackupNativeText while replacing only Invoke-BackupNative with chunked synthetic bytes. Assert the destination's observed peak Capacity<=1048576 and oversized output rejects. Retain causal RED before changing the helper: the expected current result is rejected=true but Capacity2097152 for 257writes×4096, not an import/collection failure. Root's original probe may inform but does not replace a committed regression.
- [ ] Add real-helper cases for empty output, exactly1048576 ASCII bytes, exactly1048576 bytes of valid multibyte UTF-8, 1048577 bytes/chunked overflow and invalid UTF-8. Assert returned content or exception and no output diagnostic leakage. Use fixed synthetic chunks/byte counts, not a real Docker/provider process.
- [ ] Make the narrow fix, retaining the existing final size guard and strict decoder. Candidate implementation for the allocation line plus initial length:
```powershell
$buffer = [IO.MemoryStream]::new([byte[]]::new(1048576), 0, 1048576, $true, $true)
$buffer.SetLength(0)
```
  Verify actual PS7 constructor/write behavior; no generalized custom stream abstraction or change to Invoke-BackupNative.
- [ ] Extend the existing deterministic native shim with an explicit synthetic oversized text mode. Execute actual backup and restore entrypoints against oversized inspect/preflight output; assert failure/private diagnostics and trace contains no pg_dump/createdb/pg_restore beyond the refusal. Include a finite-deadline blocked-writer case if output exceeds pipe capacity; prove exact owned child terminates and sentinel/source data stay untouched. Native shim is never real Docker and launches no children.
- [ ] Run focused new cases to GREEN, then the complete test_windows_backup_restore.py module once on actual Windows PS7 with no SKIP. Run Ruff0.17/format/compile for the test module, parse all three backup PowerShell scripts and git diff --check. Preserve causal FAIL and any intermediate failures/native exits; no full backend repeat for this PowerShell-only correction.
- [ ] Self-review, freeze both source hashes, write exact commands/results/native exits/evidence paths/limitations to own task-1-report.md and commit only the two files plus own report. Return DONE/commit/one-line results/concerns. Root generates immutable task review package; source changes after review require scoped retest/re-review. Root then reruns the original resource probe, updates docs and exact-generation Windows GitHub checks without weakening any existing gate.
