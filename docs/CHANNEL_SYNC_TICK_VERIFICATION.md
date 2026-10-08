# Bounded default-disabled deletion-first worker seam

2026-10-08; `codex/dark-navy-ui`, parent
`7215570b932e9000d485be5beb249930e0c1ad87`; origin
`borovojarkadij-png/content-studio`.

## Ordering and safety

`worker.run_channel_sync_tick` exposes an internal default-disabled facade:
new-only authenticated baseline → one deletion-first difference chunk → history
only after validated final completion → bounded exact retained-observation replay.
Legacy, foreign baseline, non-final, TooLong, missing/invalid session or failed
sync has **no history fallback**. Disabled does not read DB/credentials or construct
providers. Enabled requires an explicit boolean, stable cipher and provisioned
credentials (or a deliberately injected test provider); no regeneration or login.

Selection scans at most four eligible mapped donors with CONNECTED sessions and
due/expired durable cursor leases. A fair scan cursor wraps at the end; one legacy
donor does not starve later donors. Durable progress/leases/error/delay and replay
obligations remain SQL-owned. Current server retry/cooldown is respected; old pts
is never reset to a latest snapshot. Deletions precede historical reads and stop
deleted history before classification. Unknown stays MANUAL_REVIEW, zero rewrite.

The seam is deliberately **not** called by the main loop yet. Existing operational
flags remain unchanged. Main-loop opt-in requires durable legacy quarantine to
prevent downstream rewrite/publication continuing on unsynchronized old data;
the presence of this tested facade alone does not satisfy that prerequisite.

## Evidence

- Eight missing worker-contract failures RED after correcting a test-only Fake
  seed signature; then GREEN through real existing services.
- Seven-donor fairness regression reproduced duplicate `(5,5)` output. Actual SQL
  compilation showed ORM implicit join used `telegram_accounts.id =
  channel_difference_cursors.telegram_account_id`. Fixed explicit donor-id join;
  fair bounded/wrap test GREEN, no DISTINCT masking or removed assertion.
- 17 dedicated tick tests / combined tick and replay **29 PASS**.
- Actual encrypted factory + authentic Telethon TL requests for full channel and
  difference, session/peer persistence, disconnect, history and guarded ingestion
  exercised with synthetic network only. No real Telegram session/send/download.
- Independent SQL reopen preserves original baseline and poll/source identity;
  subsequent diff starts at retained pts, does not re-bootstrap, duplicate source
  or create rewrite. Gap retry skips early RPC and later retains original start pts.
- Fresh complete backend **935 PASS**, exec session 23980, unique D: temp tree;
  exact CI Ruff / changed-file format / compile PASS. Explicit isolated D:
  Alembic upgrade/drift PASS; no operational DB migration or activation.
- Frontend unchanged: preceding actual 65-unit / 26-browser gate is historical
  evidence, not a new UI rerun in this increment.

## Pending

Durable legacy synchronization quarantine, explicit legacy resync authorization
and optional main-loop/Compose configuration; current Windows Docker/storage
acceptance and manual live Telegram authorization remain NOT VERIFIED. No live
keys, flags, data or volumes were modified; PHASE 1 remains incomplete.
