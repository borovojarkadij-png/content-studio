### Spec Compliance

- ✅ Spec compliant. `scripts/postgres-backup-common.ps1:103` allocates the fixed 1,048,576-byte destination; line 104 resets its length. Lines 106–109 retain the native boundary, final size guard, strict UTF-8 decoding and disposal.
- ✅ Required helper cases cover empty output, exact-limit ASCII and multibyte UTF-8, one-byte overflow, chunked overflow and invalid UTF-8 (`backend/tests/test_windows_backup_restore.py:229`). Capacity and returned-content assertions exercise the actual helper (`:248`, `:318`, `:323`).
- ✅ Both actual entrypoints reject oversized inspect/version output, including blocked writers, before database work; tests verify bounded completion, owned-process exit, unrelated-process survival and preserved source data (`backend/tests/test_windows_backup_restore.py:327`).
- ✅ The immutable diff contains only the two requested source/test files and task report; existing test bodies remain unchanged.
- ⚠️ Root’s original resource-probe rerun and exact-generation Windows CI remain controller follow-up work, as documented in `.superpowers/sdd/BACKUP_OUTPUT_CAP_IMPLEMENTATION/task-1-report.md:152`.

### Strengths

- `scripts/postgres-backup-common.ps1:103` solves the allocation defect directly without introducing another stream abstraction or changing public signatures.
- `backend/tests/test_windows_backup_restore.py:248` measures actual destination capacity even when writes throw, distinguishing bounded allocation from rejection after growth.
- `backend/tests/test_windows_backup_restore.py:330` verifies refusal and process ownership through real PowerShell entrypoints using synthetic native output.
- `.superpowers/sdd/BACKUP_OUTPUT_CAP_IMPLEMENTATION/task-1-report.md:57` preserves causal RED evidence and the intermediate Windows environment failure instead of hiding unsuccessful runs.

### Issues

#### Critical (Must Fix)

- None found.

#### Important (Should Fix)

- None found.

#### Minor (Nice to Have)

- None found.

### Assessment

**Task quality:** Approved.

**Reasoning:** The fixed destination enforces the requested capacity while preserving valid exact-limit output and existing failure handling. The focused behavioral regressions cover the resource defect and its native-entrypoint consequences without weakening prior assertions.

- Check performed: completed the diff’s cut-off `Invoke-BackupNative` context to evaluate overflow cleanup; its existing deadline and owned-handle termination support bounded blocked-writer failure (`scripts/postgres-backup-common.ps1:49`, `:68`, `:83`).
- Check performed: completed the cut-off fixture context to confirm entrypoint privacy, empty failure stdout and sentinel preservation are asserted centrally (`backend/tests/test_windows_backup_restore.py:170`, `:192`, `:200`).
- Evidence inspected: retained `01-red.log` shows the causal 2,097,152-byte capacity failure; `04-full.log` shows 97 passed in 44.35 seconds; `05-static.log` records successful Ruff, formatting, compilation, PowerShell parsing and diff checks. No tests rerun.
