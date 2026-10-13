# Backup native-text allocation cap — diagnosis and contract

## Confirmed defect

The existing PostgreSQL-only backup/restore helper rejects native text longer
than 1,048,576 bytes, but only after an expandable MemoryStream has accumulated
the output. This is the deferred Minor from the accepted backup review, not a
new backup feature or a failure of the previously verified archive copy.

At source SHA256
`427E7A147A8B1062C5EBEA3CBB49D44FF95A597509554E2324794F4BE27BF40F`,
`Get-BackupNativeText` in `scripts/postgres-backup-common.ps1` allocates an
expandable buffer, invokes the native boundary, then checks Length. An isolated
PowerShell probe replaced only that boundary with 257 writes of 4,096 bytes.
The real helper rejected the output but its buffer had already grown to
2,097,152 bytes. Expected maximum was 1,048,576. The causal resource assertion
failed with native exit1. No child process, Docker, database, network, credential
or product mutation was involved; the source hash stayed unchanged.

Evidence retained outside product source:
`D:/Codex-Recovery/content-studio-20261008/backup-output-cap-20261013a/`,
`probe-backup-text-cap.ps1`, `01-resource-cap-red.log`, `01-native-exit.txt`.

## Required behavior

- Bound the native-text destination buffer capacity to 1,048,576 bytes before
  reading any output. Exact-limit valid UTF-8 remains accepted; one more byte
  is rejected without growing this destination. This is a destination-capacity
  bound, not a claim about whole-process RSS or all .NET pipe buffers.
- Decode strictly as UTF-8, preserving valid non-ASCII text and rejecting
  malformed byte sequences. Do not leak collected output/native diagnostics
  through backup/restore public errors.
- Preserve existing native nonzero-exit, concurrent stdout/stderr draining,
  timeout, exact owned-child kill and archive-list-only early-stdin-close
  semantics. No new dependency, C# production helper, process tree kill,
  generalized stream abstraction or backup-format change is needed.
- Overflow can fail through the existing bounded native timeout/owned-child
  termination path; do not claim immediate cancellation without runtime proof.
- Oversized inspect/version/preflight text must never lead to pg_dump,
  createdb or pg_restore after the refused boundary. Existing source data and
  destination absence/create-only behavior remain protected.

## Scope and safety

Only `scripts/postgres-backup-common.ps1` and
`backend/tests/test_windows_backup_restore.py` are product/test ownership for
this correction. Root owns this contract, the plan, evidence and integration
checkpoint. No operational backup/restore, credentials, real sessions, database
or container change is required. Tests use private PowerShell processes and the
existing deterministic native Docker shim only. Keep all previous assertions.

The invariant remains REJECT → rewrite_allowed=false → no new RewriteJob →
rewrite calls=0. This resource correction has no editorial/publication authority.
