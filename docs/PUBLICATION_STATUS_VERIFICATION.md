# Publication delivery status checkpoint

2026-10-08, `codex/dark-navy-ui`; real read-only API and Planner UI, not a send API.

## Verified locally

- Backend full gate: 646 tests, CI-directory Ruff, compile and targeted format PASS.
  With explicit Alembic target guard: fresh 649-test gate, lint/format and actual
  isolated D: migration round-trip/drift PASS. See ALEMBIC_TARGET_GUARD.md for the
  separately disclosed erroneous legacy CLI validation against local SQLite.
- Frontend: 55 unit tests, 23 browser tests, format/typecheck/build PASS;
  production dependency audit reports zero vulnerabilities.
- Real migrated isolated API: no-store GET returns persisted delivery history;
  POST is 405, missing plans 404. Reads neither create jobs nor send messages.
- Unknown delivery remains visible after editorial rejection. Untrusted persisted
  provider error text fails closed rather than leaking through the public API.
- UI separates receipt confirmation from approval/preparation, invalidates old
  confirmation after refresh errors and fences late channel/plan responses.
  Unknown outcomes have an accessible error warning and no retry/send control.
- Test-first fixes: untrusted error-code projection, warning semantics and joined
  receipt text. Actual browser checks cover reload, WCAG AA and narrow screens.
- A fresh browser rerun hit ENOSPC at context close (21 passed, two environment
  failures). Full rerun with temporary/output files on D: passed all 23 again;
  no assertions or tests were disabled. Traces off only for this local disk-limited
  rerun; committed CI still retains failure traces and all assertions.
- Screenshots visually inspected:
  `.artifacts/ui-dark-navy/live-delivery-1440.png` and
  `.artifacts/ui-dark-navy/live-delivery-390.png`.
- Retained isolated Windows Docker `newsflow-verification-publication20261008`
  rebuilt without reseeding: real status HTTP, API/worker restart, stored receipt,
  quarantine, blocked job, no-store/private-field exclusion and PostgreSQL drift
  PASS (session 21927). Stopped preserving all volumes and history.

## Environment failure, not operational verification

Operational update session 40773 failed while recreating the migrations container:
Docker containerd overlay metadata reported `read-only file system`. Subsequently
C: reached zero available bytes and the first attempt to write this report failed.
Current operational image/health acceptance is NOT VERIFIED / BLOCKED BY ENVIRONMENT;
the earlier publication-intent deployment success does not prove this new update.
No volumes, databases, keys or user media were deleted or rotated.

The generated pytest-317 fixture directory was archived on D: with tar listing
validation (1127 entries) and SHA256
`2DC2897114F9772D546F913EC0DDFE6569F7AF9A62B8804996934CC9B839A27B`:
`D:/Codex-Recovery/content-studio-20261008/pytest-317.tar.gz`.
The cross-drive move did not complete; do not claim reclaimed space or verified
restoration. New isolated test temporary files should use D:, not consume C:.

## Scope limits

Receipts in isolated fixtures are synthetic history. They do not prove live
Telegram authorization, permission, publication or difference reconciliation.
`live_publication_available=false` remains explicit; no public send endpoint or
authenticated sender exists at this checkpoint. No real AI calls or posts sent.
PHASE 1 remains incomplete. Continue guarded sender contract/offline tests after
preserving this checkpoint; retry operational deployment only after writable
Docker storage and sufficient host free space have been confirmed.
