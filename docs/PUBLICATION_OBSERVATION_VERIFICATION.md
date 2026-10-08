# Exact response observations and no-resend recovery

2026-10-08; branch `codex/dark-navy-ui`, parent
`eda7574c64910cb59471f91d27d3f12db7ad1977`; origin
`borovojarkadij-png/content-studio`. Current Windows Docker is environment-blocked.

## Implemented contract

After the trusted configured adapter validates an exact nonce/channel/message/
caption/media acknowledgement and the execution guard passed, the runner commits
an authenticated encrypted DIRECT_RESPONSE receipt observation before committing
terminal delivery state. Snapshot, job, account/channel/nonce, binding and attempt
must agree. Duplicate identical observations do not overwrite ciphertext. Two
different trusted message IDs preserve the first observation, durably quarantine
the job as PUBLICATION_OBSERVATION_CONFLICT and fence automatic reconciliation.
There is no public observation-ingestion, reconciliation or resend endpoint.

Enabled ticks scan a bounded, fair batch of observed expired SENDING or
SEND_OUTCOME_UNKNOWN jobs, restore the original encrypted request and complete at
most one exact historical delivery without invoking a provider. Main loop carries
a separate recovery cursor; cursors optimize scanning only, not durable truth.
Active sender leases are excluded. Completion rechecks the original plan,
candidate, output/content identities and job/attempt/nonce/binding under locks.
Receipt/job/plan/candidate/delivered outbox completion remains atomic and duplicate
recovery cannot produce a second outbox or send.

An acknowledgement of an already performed, previously allowed send remains
historical delivery truth even if editorial/source/draft policy changes later.
This does not authorize another rewrite/send or reverse a rejection. Missing,
invalid, wrong-key or conflicting evidence stays quarantined and retains quota.
If the process dies before the receipt observation commits, delivery is still
unknown: a matching text/time/history message is never accepted as a receipt.

Migration c8f537eabc26 adds a bounded encrypted observation table only. It does
not manufacture receipts for old intents and refuses downgrade with any
publication history. The separately mounted stable master key is unchanged.

## Verification actually performed

- Initial recovery regressions: expected RED (no reconciliation/ledger).
  Fair tick cursor, conflicting-receipt quarantine, public safe reason and React
  conflict warning each had a reproduced RED before implementation/fix.
- Real isolated SQL + synthetic transport: crash after durable acknowledgement,
  late rejection/edit, absent receipt, corrupt nonce/ciphertext/plan identity,
  active lease, fair bounded scanning, idempotent/conflicting observations PASS.
- Actual SQLite INSERT-abort triggers at observation and delivered-outbox
  boundaries prove rollback/quarantine and evidence-dependent restart recovery.
- A test assertion initially assumed success in the deliberately missing-evidence
  branch (1 failed/748 passed). Assertion was corrected to require quarantine and
  no outbox there; fresh full backend run **750 PASS**, session 3604.
- Exact CI lint, targeted format, compile PASS; explicit isolated D: empty
  Alembic upgrade/check/downgrade/re-upgrade/check PASS (eed524).
- Frontend **58 unit**, format/typecheck/build PASS; browser previous final run
  **24 PASS** (40428), including HTTP-injected conflict warning, refresh, no resend,
  WCAG AA and narrow layout. Final copy-only rerun: 24 PASS (17486).
  npm audit: zero vulnerabilities (33867).
- Screenshot `.artifacts/ui-dark-navy/live-delivery-conflict-390.png` visually
  inspected; existing eight-section/real API screenshots refreshed by browser QA.
- Actual Windows packaged migration/recovery/live authorization/send:
  **NOT VERIFIED / BLOCKED BY ENVIRONMENT**. No operational flag/key/session/
  volume changes and no real Telegram sends or AI calls occurred.

This is direct-response observation recovery, **not** complete Telegram
getDifference/getChannelDifference recovery. Update gaps/deletions and externally
missing random-ID mappings remain pending; lack of a mapping cannot prove a
message was not sent. Next extend the create-only synthetic PostgreSQL/Docker
publication probe to exercise encrypted snapshot/observed-ack down/up recovery,
then continue independent approved PHASE 1 work while Windows Docker is blocked.
