# Read-only live Overview and known usage

2026-10-08; branch `codex/dark-navy-ui`, parent
`6d931311d56d702f2516739e7faccdbf210e134e`; correct origin
`borovojarkadij-png/content-studio`.

## Delivered contract

GET `/api/studio/overview` is no-store/read-only and uses SQL aggregates, not
materializing content/session histories. Scope is explicitly ALL_RETAINED_HISTORY,
not today's throughput or current eligibility. Counts include retained deleted
messages/revisions and old jobs. Active jobs mean stored QUEUED/DISPATCHED/RUNNING/
RETRY states, not permission to rewrite. SUCCEEDED delivery intents are counted
separately from NEEDS_RECONCILIATION; no resend/approval action is exposed.

Rewrite and semantic-verification usage remain separate. Known token records,
cached token subset, NULL-price observation count, exact ten-decimal USD estimate
subtotal, durable attempts and attempts without saved usage are reported. Missing
observations are calculated per job, not inferred as measured provider calls.
`billing_complete=false` always: a reserved attempt can precede a provider call,
an interrupted remote request may have unknown charges, and estimates are not a
provider invoice. No price lookup or external provider request occurs.

Working-mode Overview now renders these real aggregates in existing dark-navy
panels/metrics. Every card labels its historical meaning; no DEMO fallback,
fabricated topic distribution/chart, subscribers or live health certificate.
Refresh clears old numbers before failure; abort fencing prevents late unmounted
responses. Strict external DTO rejects malformed/contradictory/unsafe payloads.
DEMO's existing eight reference-based compositions and behavior are unchanged.

## Actual tests and repairs

- Four initial backend contracts RED -> GREEN, plus uncertain/acknowledged history
  regression. **5 dedicated / 30 combined PASS** with wait probe/status API.
- Full backend **1011 PASS**, session **74185**, 86.20 seconds; exact CI Ruff,
  changed-file format, compile and explicit fresh D: migration round-trip/check
  PASS. No schema change; no operational database target.
- 14 component/DTO cases RED -> GREEN; working App integration RED -> GREEN.
  Full frontend **97 unit PASS**, typecheck/build/format PASS; npm audit 0.
- Actual full browser **28 PASS**, session **38350**, 37.5 seconds: real migrated
  isolated FastAPI/Vite, unknown usage/crash budget, refresh/reload, GET-only,
  desktop1440/mobile390, no horizontal overflow and WCAG AA.
- Screenshot inspection found touching summary/metric panels; geometry assertion
  reproduced RED, scoped margin repair now GREEN in the full browser suite.
- Full unit regression exposed old mocks assuming every explicit HTTP method is a
  write and positional response queues consumed by new Overview GET. Fixed only
  test fixtures to address URL and GET/body semantics. Exact mutation assertions,
  protected-source rules and DEMO-zero-network checks retained. Actual TypeScript
  unsupported test selector option/import format also fixed, no check disabled.
- Final screenshots visually inspected:
  `D:/Codex-Recovery/content-studio-20261008/overview-full-browser-1933/studio-real-overview-shows-8f7d5-s-without-fabricated-charts/overview-live-1440.png`
  and sibling `overview-live-390.png`. New evidence/temp remains D: due C: limits.

## PostgreSQL and limits

Create-only dedicated sync/wait probe now checks the real Overview HTTP response
before/after recovery/down-up: exact scope, no-store, unknown billing/usage and
retained history. Its consumer test is RED -> GREEN locally. Exact Overview commit
322603ee85164c624801847217279791e48f332e CI 37755335470 completed FAILURE:
backend/frontend and both legacy Docker variants succeeded, but the dedicated
PostgreSQL sync probe found a JSON counter string at `verify_overview` line 271.
This is an implementation defect, not the independent Windows environment blocker.

Root cause: `SUM(CASE ... job.attempts - COUNT(usage.id) ...)` sums PostgreSQL
BIGINT, whose result is NUMERIC/psycopg Decimal; FastAPI serializes that Decimal
as a JSON string. SQLite returned an integer, so its prior gate did not expose
the mismatch. A real SQL reader + narrowly simulated PG result adapter through
the actual HTTP endpoint reproduced `'1' != 1` RED. Normalize only the integral
`unobserved_attempts` result to Python int; monetary Decimal subtotal remains
exactly ten fractional digits. Same HTTP regression now GREEN; no consumer
validation/probe weakened or skipped. 41 combined overview/wait/media regressions
PASS; new exact PostgreSQL rerun remains pending the corrective commit's CI.

Donor status predecessor 6d93131 CI **37753560333** completed SUCCESS in all five
jobs (actual gh view). Current Windows Docker remains **NOT VERIFIED / BLOCKED BY
ENVIRONMENT**; C: ~0.53 GB free does not prove repaired storage. Operational flags,
secrets, sessions and volumes unchanged. Real authorization/model qualification,
full live update recovery and PHASE 1 completion remain pending.

## Next

Inspect exact new CI and repair any ordinary failures. Continue bounded fair
automatic media admission: existing first-N pending scans can repeatedly visit
rejected/stale candidates and starve later eligible ones. Preserve current gates,
source-rights checks, durable idempotency, exhausted/terminal histories and all
default-disabled operational flags. Regression first, real SQL reopen, then
worker/main-loop integration and full gates; no real download/send test side effects.
