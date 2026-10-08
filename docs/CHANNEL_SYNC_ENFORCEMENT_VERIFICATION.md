# Durable synchronization enforcement and opt-in worker

2026-10-08; branch `codex/dark-navy-ui`, parent
`bb0ebf46f042bef987f184adc9d712c2044b3468`; correct origin
`borovojarkadij-png/content-studio`.

## Behavior

`NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED` is strict `0`/`1`, default `0`.
Opt-in requires ingestion enabled, a provisioned persistent master key and
validated existing Telegram credentials. It records one immutable SQL outbox
fact before any downstream action. Turning the runtime flag off cannot remove
this fact or waive source synchronization. There is no disable/reset endpoint.

Shared freshness now fences every missing, foreign, ambiguous, active, incomplete,
errored or unhealthy baseline under enforcement, including legacy donors outside
the current bounded scan. Historical PASS/source text are retained, but effective
rewrite permission is false. Cached/retried/stale jobs and real approval API cannot
bypass the guard; no fabricated editorial rejection is written.

Enabled main-loop order: donor resolution → new-only baseline/deletion-first
difference → history only after final completion → exact replay → scheduler and
downstream workers. Legacy ingestion fallback is disabled in this mode. A failed
sync tick skips downstream processing and logs no provider exception/secrets.
Non-final chunks retain exact observations without classification/jobs and persist
`DIFFERENCE_INCOMPLETE`; only a validated final chunk permits ordinary replay.

Operational `.env`, keys, sessions and enablement flags were not changed. Compose
already passes its configured env file; no business-logic production fork added.

## Actual verification

- Test-first contract failures for enforcement/main-loop behavior were reproduced
  in the preceding execution and fixed. Final combined targeted gate: **81 PASS**.
- Fresh full backend: **953 PASS**, session **21080**, 72.84 seconds; temporary
  databases/files on a new isolated D: test tree, not user databases.
- Exact GitHub backend Ruff scope, changed-file format (9 files) and compile PASS.
- Explicit fresh D: Alembic upgrade/check/downgrade/base/re-upgrade/check PASS;
  no schema drift, no operational migration.
- SQL reopen/runtime flag-off preserves enforcement; missing/error/non-final/
  active/invalid-session baselines deny processing. Healthy idle bound cursor
  remains eligible. Prototype keys without durable source are denied.
- DISPATCHED/RETRY/expired RUNNING legacy jobs become SUPERSEDED with zero provider,
  output and usage; actual Inbox reports SOURCE_SYNC_REQUIRED and approval is 409.
- Actual main loop with real services/synthetic provider verifies ordering,
  default-off behavior and sync failure skipping downstream. Real two-chunk replay
  retains unknown MANUAL_REVIEW, no RewriteJob or OpenAI rewrite call.
- Previous bb0ebf4 CI **37746062697** and replay 7215570 CI **37745127358** completed
  SUCCESS (actual gh run list), as did baseline/gap checkpoints.

Frontend unchanged; prior 65-unit/26-browser verification remains historical,
not a new browser run. Current Windows Docker is **NOT VERIFIED / BLOCKED BY
ENVIRONMENT** (host low storage/read-only containerd); Linux CI is not Windows
proof. Live Telegram authorization and legacy resynchronization remain pending.
PHASE 1 is not complete.

## Next

Add a separate create-only synthetic channel-sync restart probe and Linux
PostgreSQL CI acceptance. Keep it separate from old fixture suites: enforcement
is global and must not be silently disabled to make legacy fixtures pass.
Verify encrypted session, retained baseline/pts/tombstones/replay obligations,
crash recovery and zero AI/send effects across independent SQL reopen/down-up.
