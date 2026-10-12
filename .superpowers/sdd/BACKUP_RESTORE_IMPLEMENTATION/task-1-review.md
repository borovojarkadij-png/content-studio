### Spec Compliance

- ❌ Issues found: archive listing can reject valid large bundles because an expected early stdin close becomes a failure before the native exit status is checked (`scripts/postgres-backup-common.ps1:57–66`).
- ✅ Required files and interfaces are present. Create-only destinations, exact container/configuration checks, strict manifest verification, binary streams, fixed native errors, and retained failed copies match the task (`scripts/backup.ps1:15–54`, `scripts/restore.ps1:15–50`, `scripts/postgres-backup-common.ps1:96–171`).
- ⚠️ Controller must verify actual Windows Docker recovery, restored rows including REJECT/zero-job invariants, read-only migration drift, final CI, frozen hashes, and repository/branch authorization. These are expressly deferred or cannot be established from this diff (`.superpowers/sdd/BACKUP_RESTORE_IMPLEMENTATION/task-1-report.md:312–315`).

### Strengths

- Restore keeps the validated archive open through hashing, listing, and restoration; creation happens once after validation and target-absence checks (`scripts/restore.ps1:25–45`).
- Native commands use argument arrays and concurrent byte-stream draining, suppress private diagnostics, and terminate only the owned process (`scripts/postgres-backup-common.ps1:35–77`).
- Tests execute actual PowerShell entrypoints against a compiled native executable and assert durable results, argv, binary fidelity, refusals, and timeout behavior (`backend/tests/test_windows_backup_restore.py:78–177`, `backend/tests/test_windows_backup_restore.py:265–350`).
- Operator documentation clearly explains trusted-archive custody, separate keys/media, partial copies, and acceptance limits (`docs/BACKUP_RESTORE.md:18–31`, `docs/BACKUP_RESTORE.md:81–87`, `docs/BACKUP_RESTORE.md:114–150`).

### Issues

#### Critical (Must Fix)

- None identified.

#### Important (Should Fix)

- `scripts/postgres-backup-common.ps1:57–66`: input copying must finish successfully before the helper examines native exit status. Real `pg_restore --list` reads the header/TOC and exits without consuming the archive’s data section; Docker’s stream handling can finish when output ends. For sufficiently large archives, pending input writes therefore encounter a closed pipe and the helper rejects a successful listing. Both backup and restore use this path (`scripts/postgres-backup-common.ps1:130–131`). The fake masks it by consuming all list input (`backend/tests/test_windows_backup_restore.py:56–60`). Handle process completion and input-copy errors separately, allowing expected early input closure specifically for successful listing while preserving other failure checks. Add a native regression that reads a prefix and exits zero with input larger than pipe buffers. Primary-source check: [PostgreSQL list execution](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/bin/pg_dump/pg_restore.c), [custom archive header/TOC reading](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/bin/pg_dump/pg_backup_custom.c), [Docker stream completion](https://raw.githubusercontent.com/docker/cli/master/cli/command/container/hijack.go).
- Focused verification of that risk: a read-only, in-memory invocation of the actual helper with a native PowerShell child reading one byte and exiting zero, supplied 16 MiB stdin, returned `early_exit_result=failed: native command failed`. No Docker action, filesystem edit, or suite rerun occurred.

#### Minor (Nice to Have)

- `scripts/postgres-backup-common.ps1:87–92`: the 1 MiB textual-output check runs after an unrestricted `MemoryStream` has collected everything. This limits accepted output, not memory consumption. Enforce the limit during copying to make the documented bound effective (`docs/BACKUP_RESTORE.md:104`).

### Assessment

**Task quality:** Needs fixes

**Reasoning:** The preservation and validation boundaries are strong, but the stdin lifecycle assumes successful consumers read the entire archive. That assumption conflicts with real archive listing and is absent from the synthetic coverage.
