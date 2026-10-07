# Fact anchors and durable rewrite recovery — 2026-10-07

## Implemented boundary

`RewriteService` rejects non-PASS/disabled editorial decisions before validating
source text or constructing a rewrite call. Valid source text is bounded; the
returned text must preserve deterministic anchors (number/sign/date/time/count,
link, mention and quotation multisets). Explicit named literals can be checked
against source evidence, with word boundaries. Invalid results are rejected once,
not repaired by asking AI to change facts or make protected-entity content positive.

The versioned synthetic benchmark in `test_fact_guard.py` covers changed, removed,
added/repeated numeric facts, dates, signs, links, mentions, quotes, invalid/oversized
responses, Unicode digit formatting and named facts. **Anchor preservation is not
semantic factual proof**: “closed 3 lines” versus “opened 3 lines” demonstrates
this explicitly. Successful anchor checks still require review, never auto-approve.

## Durable runner component

`DurableRewriteRunner` accepts a server-side provider factory keyed by output
channel. PostgreSQL selects jobs with `FOR UPDATE SKIP LOCKED`; a 60-second lease
and unique attempt token fence old owners. The attempt budget is committed when
claiming, before any potential provider side effect. A crash cannot reset it.

Execution locks job → current editorial decision → candidate, checks the exact
immutable source revision and current latest revision, then invokes `RewriteService`.
Editorial lock remains held for the bounded provider operation. Current editorial,
source freshness and lease are checked again before result persistence. Provider
unavailability retries durably after a delay, at most the configured attempt budget;
fact changes terminate without a draft. Error storage contains category codes,
not provider exception text, credentials or prompts. Late successes AND late
provider errors cannot transition an expired claim.

Success atomically stores SUCCEEDED + one output-scoped PENDING draft + one
`rewrite.completed` outbox event. It does not approve, activate, schedule or publish.
An unknown provider/process/database exception leaves its committed claim available
for lease-based recovery; external provider calls can be repeated after an unknown
outcome, within the persisted budget. This is not exactly-once provider billing.

Migration `f6b20d8a9143` adds attempts/availability/token/lease/error fields and a
nonnegative attempts constraint without resetting existing jobs. Downgrade refuses
to discard nonzero attempt or active claim history; use a forward fix for real state.

## Verification

- TDD: missing implementation and changed-fact/empty-source failures were observed;
  lease-budget, expired success and expired error tests failed before their fixes.
- Backend full gate: **179 passed**, lint (including Alembic and both Docker
  probes) and compile passed. Frontend gate remains **24 unit / 19 browser** passed.
- Regression cases exercise independent per-channel rewrites, PENDING approval,
  stale Editorial REJECT with no provider construction, persisted delayed/bounded
  retry, expired owner fencing, source edits, fact rejection and guarded migration.
- Explicit isolated migration upgrade/check/downgrade/re-upgrade/check passed.
  Drift checking found two pre-existing ORM index declaration differences; the
  models now match the existing migrated schema without altering persisted data.
  A regression and CI drift gate prevent their return.
- Actual PostgreSQL migration drift check in the operational container also passed.
- Shared current-policy revalidation additionally rejects an inconsistent PASS
  flag if its protected entities/sentiment/framing still violate hard constraints.
  Regression covers provider construction, rewrite, approval/read eligibility,
  planning, new dispatch and publication; a stored flag alone cannot bypass policy.
- Actual PostgreSQL/Docker synthetic acceptance invoked the runner component:
  claim persisted → worker container restart → actual lease expiry → a new owner
  recovered it → old token refused → one synthetic rewrite → pending draft and
  completion outbox persisted → worker restart → result verified. No network AI,
  real Telegram session or send was used. See DOCKER_VERIFICATION.md for scope.
- Final combined Windows acceptance `newsflow-verification-final20261007` passed
  with `-CrashRecovery -RewriteRecovery`, including forced API address change,
  down/up, PostgreSQL crash, Redis loss and expired-owner fencing.
- GitHub Actions **37680562785** passed backend, frontend and synthetic Docker
  storage jobs for foundation commit `4b093c5`; this predates the runner increment.

Repeat the extended isolated acceptance on a **fresh** project:

```powershell
./scripts/verify-persistence.ps1 -Project newsflow-verification-new-run -CrashRecovery -RewriteRecovery
```

This terminal fixture procedure intentionally consumes its one pending job. Do
not rerun the initial DISPATCHED-fixture seed assertions against that completed
project. Use another verification project/ports; old volumes remain inspectable.
Without `-RewriteRecovery`, the original storage procedure leaves the job pending.

## Remaining scope

The default daemon still performs timer planning ONLY. Network provider factories,
OpenAI structured rewrite, usage/cost persistence, semantic fact verification,
configurable guarded automatic approval and publication delivery are not enabled.
The runner has been exercised through injected synthetic providers, not a live
OpenAI/OpenRouter worker. Human review remains mandatory. PHASE 1 is not complete.
