# Fair guarded semantic admission

2026-10-08; branch `codex/dark-navy-ui`; parent
`e46ee47383c00dc8a3394c7a214f404376f3e58a`; correct origin
`borovojarkadij-png/content-studio`.

## Defect and repair

The semantic admission query excluded manual/unqualified channels but repeatedly
selected the same first 100 PENDING drafts failing their fresh binding. An actual
seven-iteration main-loop regression reproduced a later valid draft remaining
PENDING with no verification, despite a synthetic qualified fixture release.

Add an immutable bounded admission window (scanned/blocked draft IDs, queued job
IDs and last scanned cursor). Default worker scan is 16, explicit bounds 1..100;
empty tail wraps to zero on a later tick. Existing count-returning enqueue API
remains compatible. Main retains independent semantic scan progress, updated
before executing a job. SQL remains the sole truth for jobs, leases, attempt
budgets, source/draft/release bindings, evidence and approval. Restart rescan never
resets task history, calls a rewrite provider or qualifies a release.

Every row still uses the original fresh binding: current EditorialGate permission,
exact current immutable source, PENDING per-output draft, fact anchors, configured
VERIFIED policy and qualified pinned release. Prior jobs for that output/current
release prevent implicit terminal/exhausted re-admission. Errors/uncertainty remain
manual/PENDING rather than fabricated automatic approval or paid repair loops.

## Actual verification

- Core window missing behavior RED -> GREEN. Actual main loop repeated IDLE /
  later PENDING RED -> GREEN. A test fixture DetachedInstanceError was fixed by
  retaining primitive keys, not weakening production guards.
- **17 dedicated / 74 combined** semantic/worker/publication/sync regressions PASS.
- **Full backend 1057 PASS (39884)**, 94.91 seconds, fresh D: basetemp/cache.
- Exact CI Ruff, all three changed files format check, D: redirected compile PASS.
- Explicit fresh D: Alembic upgrade/check/downgrade/base/re-upgrade/check PASS;
  no schema change, operational DB untouched.
- Real SQL 100 neutral historical drafts are later rejected; fresh scanner spends
  zero provider calls/job attempts on those rows. Historical RewriteJob count is
  unchanged (103), not falsified by deleting old history. Only the late current
  draft gets one synthetic verifier call/evidence and APPROVED activation.
- Independent SQL reopen/finite wrap, invalid bounds before DB, disabled inert
  state, post-scan reject/source edit/release revocation, terminal REVIEW/BLOCKED/
  FAILED history after draft change and provider-error committed attempt checked.
  No new RewriteJob/RewriteUsage or publication job created by this increment.
- Corrective Overview 351b137 CI 37757293108 dedicated PostgreSQL sync/wait job
  completed SUCCESS. Media e46ee47 CI 37757580448 backend/frontend/dedicated sync
  completed SUCCESS; legacy Docker variants still running at inspection. Never
  equate a partial CI result to overall success.

All verifiers are synthetic offline fixtures; no operational model qualified,
provider credentials revealed, paid calls, Telegram downloads/login or publishing.
Operational flags unchanged. No new UI; existing frontend behavior remains intact.

## Pending

Exact new semantic commit CI and an isolated create-only admission restart probe
on PostgreSQL still need execution. Add the probe as the next increment without
reseed/reset of old fixtures or erasing global sync quarantine. Current Windows
Docker remains **NOT VERIFIED / BLOCKED BY ENVIRONMENT** independently of Linux CI.

Then continue remaining PHASE 1 tasks from the documented state, not by reopening
approved architecture or enabling live automatic approval without qualification.
