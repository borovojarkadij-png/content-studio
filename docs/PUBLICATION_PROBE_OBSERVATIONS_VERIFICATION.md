# Publication snapshot / observed-ack recovery probe

2026-10-08, `codex/dark-navy-ui`, parent HEAD
`33757e6c873d108b6db1fcdce2eb28f1732a3c2a`, correct origin
`borovojarkadij-png/content-studio`.

## Probe changes

The create-only publication fixture now uses its explicit public synthetic cipher
for snapshots and trusted fake receipts. It never loads an operational session,
master key or Telegram sender. CLI remains restricted to the explicitly flagged
`newsflow_verification` database; an existing fixture account is never reseeded.
Version-2 manifests identify the new recovery procedure. Old manifests are
rejected with instructions to retain history and create a fresh fixture, not
backfilled, reset or silently declared verified.

`recover` fences the old CLAIMED owner, quarantines evidence-free SENDING, then
allows one injected synthetic receipt and deliberately interrupts the post-ledger
terminal transaction. The first job remains SENDING with an encrypted exact
observation; a third rejected job is blocked without a second transport call.
Quota includes observed SENDING and the other unknown/cancelled reservation.

PowerShell sequence now checks `verify-pending` after worker restart, performs
full down/up, and only then `verify` restores/decrypts all original requests and
the first exact observation and reconciles without a provider. A final worker
restart/verify checks duplicate recovery. No additional real 65-second wait was
added: only the synthetic recovery scan clock advances beyond its retained lease.
HTTP statuses distinguish pending SENDING from confirmed receipt and forbid POST.
Persistent volumes/history are retained as before.

## Actual evidence

- New consumer test initially RED on the missing versioned recovery contract.
  Actual fixture seed/recover and independently reopened isolated SQL store now
  verify snapshot identity, observed-ack completion, old-owner/unknown/reject
  fencing, one delivered outbox, no resend, legacy refusal and no reseeding.
- Fresh full backend **751 PASS**, session 22862, unique D: temp storage.
- Exact CI Ruff scope, targeted format, compile: PASS.
- PowerShell parser: PASS; parsing is not Docker execution evidence.
- Previous observation checkpoint frontend: 58 unit / 24 browser plus
  format/typecheck/build and accessibility PASS, unchanged by this probe increment.
- Snapshot checkpoint eda7574 CI 37712575263: all four jobs SUCCESS (actual gh view).
  This predates this extended probe. Observation checkpoint CI 37713401088:
  backend/frontend SUCCESS, both Docker jobs still in progress at inspection.
- **New extended PostgreSQL/Docker probe: NOT VERIFIED yet**, awaiting its own
  pushed checkpoint CI and an eventual Windows Docker Desktop run. Current host
  C: near full / Docker unavailable/read-only is an external environment blocker.

Next independent implementation: bounded read-only Telegram channel update-
difference provider contract and deletion observations, using synthetic Telethon
responses. Full durable gap/deletion application and live authorization remain
pending. Never infer publication delivery or safe resend from matching text/time
or from the absence of a random-ID mapping in difference responses.
