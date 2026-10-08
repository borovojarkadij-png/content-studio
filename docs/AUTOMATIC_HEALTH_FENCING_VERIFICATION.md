# Automatic reconnect authorization fencing

2026-10-08, `codex/dark-navy-ui`, correct origin
`https://github.com/borovojarkadij-png/content-studio.git`.

## Reproduced boundary failures

AccountHealthService released SQL locks before verify_session (correct), but
applied its result afterward using only `health_checked_at > now`. An independent
writer could invalidate or replace authorization at the same timestamp. A late
successful response changed SESSION_INVALID to CONNECTED; failure/FloodWait for
an old session could instead clear or extend the replacement's cooldown. Twelve
actual interleaving regressions failed before the fix, including success,
SessionUnavailable and FloodWait against invalidation, ciphertext replacement,
user replacement and session removal. No real provider is used.

Bounded sync scanning also needed an atomic eligibility recheck: a row selected
earlier must not authorize a later probe after becoming invalid/unprovisioned.
Five test-first cases demonstrated the missing cooldown-only contract. Six
canonical input cases failed before SQL validation was added.

## Current contract

- Automatic tick calls health reconnect with explicit `cooldown_only=True`.
  Fresh row-locked COOLDOWN, provisioned session and known cooldown are required
  before RPC. Manual existing callers keep their explicit reconnect behavior.
- Snapshot user identity, exact encrypted session, health and checked timestamp
  before releasing the transaction. Reload and lock after RPC; any identity or
  health change preserves the fresh writer's state, with no cooldown/checked-time
  mutation. Same-time newer health writes are fenced as well as later timestamps.
- An RPC is not authorization for a different session. Legitimate provider
  refresh conservatively leaves the account paused for a fresh next-tick probe.
  Actual ConfiguredTelegramProvider + Telethon adapter synthetic client test
  verifies encrypted refresh persistence and subsequent CONNECTED recovery.
- Default-disabled behavior, unchanged encrypted factory/CAS, no login/code/send
  capability, no provider error bodies/keys/session data in diagnostic output.
- Actual three-iteration worker main loop visits seven failing accounts as
  1..4, 5..7, 1..4. Bounded scan cursor is retained independently; failures never
  authorize donor ingestion, rewrite or publication and do not starve later rows.

## Verification

- 27 new regression variants. Combined health/sync/main-loop/encrypted-factory/
  vertical/source-photo tests: **98 PASS**, session 27187.
- Full backend: **1135 PASS**, 98.42 seconds, session 67016; isolated D: basetemp
  `D:/Codex-Recovery/content-studio-20261008/health-full-1355`.
- Exact CI Ruff, changed-file format, D: bytecode compile and explicit fresh D:
  Alembic upgrade/check/downgrade/upgrade/check: PASS. No schema change.
- Relevant real migrated API/browser configuration and Planner checks: **2 PASS**,
  `D:/Codex-Recovery/content-studio-20261008/health-browser-1358`.
  Unchanged frontend previous full gate is 139 units / 30 browser PASS (57315).
- Prior 58df443d900a5b055a41c8f2751a7310d77c0a2a CI 37765616929: backend/frontend/
  dedicated admission PostgreSQL SUCCESS at inspection; remaining jobs running.
  Exact new checkpoint CI must be inspected after push, not assumed successful.

Windows Docker remains NOT VERIFIED / BLOCKED BY ENVIRONMENT. This is synthetic
local integration, not live authorization or current Windows packaging proof.
No operational DB/session/key/model qualification/worker flags changed. PHASE 1
is not complete. Next independent check: isolated PostgreSQL execution of the
combined vertical scenario in GitHub CI, then a separate create-only combined
Compose restart acceptance; do not reset old fixtures or operational volumes.
