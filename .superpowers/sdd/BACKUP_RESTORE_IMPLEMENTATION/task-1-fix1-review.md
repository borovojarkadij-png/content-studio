- **Successful archive listing rejected after early stdin closure — ADDRESSED.** `scripts/postgres-backup-common.ps1:58–80` retains input faults separately, waits for native completion, drains output, and requires exit zero before accepting only the specified Windows closed-pipe errors without cancellation. The exception is enabled only for listing (`scripts/postgres-backup-common.ps1:145–146`); restore remains strict.

- **Regression coverage — sufficient for this amendment.** The native shim reads one byte and closes stdin. Added cases exercise 16 MiB input, successful listing through both entrypoints, nonzero listing, strict restore rejection, and timeout with owned-process termination (`backend/tests/test_windows_backup_restore.py:731–811`).

- **New breakage in the fix diff — None identified.** No new Critical, Important, or Minor findings.

- **Out-of-scope observations —** Previously deferred Minor text-output allocation issue remains ledgered; this amendment does not address it. Actual Docker recovery, database invariants, drift, CI, and release acceptance remain controller gates.

- **Verification checked —** The fix report names covering commands and records causal RED, six focused GREEN cases, `83 passed`, native receipts, and static-check output. Independently computed SHA256 values for all five frozen owned files match the report. No tests rerun; no checkout, index, Git, Docker, or database mutations performed.

- **Spec assessment — Pass for this amendment.** The fix resolves the listing lifecycle defect while preserving native nonzero/timeout failure, binary streaming, private errors, strict restore input handling, and owned-only termination.

- **Quality assessment — Pass for this amendment.** The change is focused, and its native regression directly reproduces the previously masked failure.

- **Fix round — All findings addressed, no new Critical/Important breakage.**
