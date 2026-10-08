# Synthetic unattended Telegram vertical slice

2026-10-08, `codex/dark-navy-ui`, origin
`https://github.com/borovojarkadij-png/content-studio.git`.

## Scope and actual path

`test_unattended_vertical_slice.py` uses Alembic-migrated isolated SQLite and the
actual durable ingestion, rewrite, semantic verification, media acquisition,
timer planning and publication services. Every stage disposes its engine and
reopens the original database. External rewrite/verifier/photo/sender boundaries
are synthetic; no Telegram login, download, upload, send or paid AI call occurs.
Stable encrypted session/peer markers and persistent exact decoded PNG bytes are
retained. A qualified release exists only in the isolated test fixture, never in
operational configuration. Trusted test editorial annotations are not a live
classifier qualification.

Two configured mappings produce two independently rewritten PENDING drafts.
Pinned synthetic evidence permits guarded approval; explicit source rights permit
exact original-photo acquisition. Automatic daily quota 1 per channel and future
slots/delay yield one reservation per channel. Repeated ticks, including after
SQL reopen, yield exactly two distinct acknowledged publication intents, one
attempt each, and no duplicate transport call. Captions use each channel's own
draft and retained attribution.

Five scenarios verify success, reject before verification, reject before media,
reject before publication, and account-wide FloodWait/recovery. The originally
protected reject always has `rewrite_allowed=false`, no RewriteJob/candidate,
zero rewrite calls and no RewriteUsage. Later rejection preserves historical
neutral rewrites instead of deleting them to manufacture a zero-history count.

## Reproduced failures and fixes

- FloodWait from the first source-photo job put its account in COOLDOWN. A second
  queued job on the same account was immediately claimed, charged an attempt and
  permanently BLOCKED by current source/health validation. Actual integration
  regression failed with `BLOCKED != IDLE` before the fix.
- Source-photo claim query now excludes known paused source owners before claiming
  any attempt. Source ownership resolves from the immutable SQL revision identity,
  not a split string or output account. Future cooldown is respected even if the
  recorded health label is CONNECTED (separate regression RED -> GREEN). Under
  persisted synchronization enforcement, expired COOLDOWN remains paused until
  verified health recovery. Legacy execution guards remain unchanged.
- Waiting mutates no job, token, history or committed attempt. Expired RUNNING
  leases retain their previous budget; an expired owner cannot acquire/register
  media. Missing/invalid identities still reach unchanged fail-closed guards.
- Sync mode selected only CONNECTED accounts and bypassed legacy polling; no
  automatic reconnect existed for an expired COOLDOWN. Actual tick regression
  returned no donor processing instead of POLL_COMPLETE; RED -> GREEN.
- Opt-in sync now performs at most four expired, provisioned cooldown account
  probes before deletion-first donor processing, with a separate fair cursor in
  the real main loop. Health service commits before RPC. Timeout/connection failures
  remain paused and cannot starve later accounts; future cooldown, invalid or empty
  sessions are never automatically probed. No login or operational flag added.
- The full vertical FloodWait scenario uses the actual sync worker tick to verify
  the session and resume the original two jobs after SQL reopen, not a manual
  health mutation. First job retains attempt 1, second retains attempt 0 while
  paused. Three total synthetic download attempts yield two exact photo results.

## Fresh verification

- Combined vertical/photo/sync/main-loop/account-health/media-admission regressions:
  **94 PASS**, session 60590, isolated D: basetemp.
- Full backend: **1108 PASS**, 102.82 seconds, session 62523,
  `D:/Codex-Recovery/content-studio-20261008/unattended-full-1410`.
- Exact CI Ruff command, changed-file Ruff format, D: bytecode compile and fresh
  explicit D: Alembic upgrade/check/downgrade/upgrade/check: PASS.
- Unchanged frontend regression gate: **139 units / 30 browser PASS** (57315),
  format/typecheck/build PASS, production audit 0 vulnerabilities. Actual isolated
  API fixture and eight-section accessibility/responsive checks included. Browser
  output: `D:/Codex-Recovery/content-studio-20261008/unattended-browser-1415`.
- Previous approval policy 06813663a799d2811affdd0bd7e5e91023c969d1 CI
  37763228825 and semantic status 157ed68e07cac857eab37159accdf785fca3342f CI
  37761899546 completed SUCCESS overall, all six jobs (actual gh inspection).
  New checkpoint's exact CI remains pending until push and inspection.

## Limits / next independent work

This is synthetic offline SQLite service integration, not current Windows Docker,
real PostgreSQL acceptance of this new combined scenario, live model accuracy or
live publication proof. Licensed-library publication still fails closed pending
visual-semantic relevance approval; it is not falsely counted as supported here.
Full albums/video, operational authorization and real qualified semantic release
remain pending. Current Windows Docker stays **NOT VERIFIED / BLOCKED BY
ENVIRONMENT**: C: about 0.47 GiB free and no confirmed repaired writable storage.
No Docker retry, reset/prune, data/key/volume removal or operational flags changed.
PHASE 1 IS NOT COMPLETE. `/docs` remains source of truth; Obsidian pending.

Next: adversarial automatic-health interleavings (invalidation/session replacement
during RPC, eligibility change after bounded scan) and exact main-loop cursor
recovery, followed by a separate create-only PostgreSQL restart acceptance for
this combined vertical scenario when safely available. Preserve all hard gates.
