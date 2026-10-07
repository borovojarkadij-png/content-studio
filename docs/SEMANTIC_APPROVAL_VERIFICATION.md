# Semantic evidence / guarded automatic approval

## Implemented boundary

- Per-channel MANUAL (default) / VERIFIED approval policy, persisted in PostgreSQL.
  GET/PUT `/api/telegram/output-channels/{id}/approval-policy` use actual API state.
  A client cannot post verdicts, qualify a model or invoke an auto-approve endpoint.
- Strict bounded semantic assessment: exact source/draft quotations, support,
  contradiction, unsupported/omitted claims, uncertainty and coverage. Cheap fact
  anchors run first. Unknown/malformed/incomplete results cannot approve anything.
- Evidence binds the immutable revision, exact source/draft digests and a digest
  of the qualified provider/model/prompt/benchmark/report release. Editorial,
  source, job, policy and release gates run before and after injected verification,
  and inside automatic approval. The service stores evidence, not a new rewrite.
- Approval method preserves historic human approvals as MANUAL. Guarded automatic
  approval activates only its channel's candidate. Scheduling/activation recheck
  current approval; revoked evidence/release/policy blocks reservations as
  BLOCKED_REVIEW without deleting history.
- Independent structured OpenAI/free-only OpenRouter verification adapters share
  the already bounded JSON transports. No repair call. The verifier is pinned to
  one qualified model; a rewrite fallback is not a qualified verification fallback.
  Returned model identity must match. Dynamic `openrouter/free` cannot qualify.
- Additive migration `b7d2e904a613`; downgrade refuses evidence/release/automatic
  state loss. Existing drafts and explicit manual review are preserved.
- Additive migration `d82f6a190bc4` persists verification jobs and known usage.
  Two attempts maximum, committed before provider calls; 60-second recoverable
  leases fence stale owners at evidence write and approval. Successful completion
  and automatic approval/candidate activation commit in one transaction.
- Encrypted verifier factory reuses the selected provider credential, not its
  rewrite model selection: it pins the qualified release model. Worker opt-in
  `NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED=1` defaults to 0 and never enables send.
  REVIEW/BLOCKED/FAILED are terminal manual outcomes, not infinite paid retries.

## Regression evidence

Test-first checks reproduced the missing API/contract, then exercised synthetic
negation, opposite action, subject, certainty, attribution, new/omitted claims,
ambiguity and injection cases. `semantic-facts-v1.json` is versioned.

Additional failing adversarial regressions exposed and fixed:

1. A cached ORM release could conceal an external revocation: fresh locked policy
   and release queries are now required at automatic approval.
2. Replacing model metadata under an existing release ID could reuse evidence:
   release identity/report digests are now part of the evidence binding.
3. Duplicate JSON keys could conceal negative values: strict duplicate rejection.
4. An approved draft could conceal a now-failed rewrite job: current approval
   checks job scope/state, editorial constraints and latest source too.
5. Cached draft/editorial/source values could hide external changes: critical
   ORM queries now explicitly refresh identity-map values at their point of use.
6. Old manual drafts could starve qualified channels: enqueue selects only current
   VERIFIED policies and excludes already-created jobs before applying its limit.

Local contract/provider/database tests are synthetic and make no live AI calls.
They establish guard behavior, NOT the classification accuracy of any live model.
Latest full local gate: 314 backend tests, lint and compile PASS; frontend 26 units,
19 Chromium E2E, format, TypeScript/Vite build PASS. Isolated migration
upgrade/check/downgrade-to-base/re-upgrade/check PASS; downgrade refuses data loss.

## Actual Windows Docker verification

Executed on Docker Desktop in isolated project
`newsflow-verification-semantic20261008`, ports 18008 / 15181 / 18088:

```powershell
./scripts/verify-persistence.ps1 -Project newsflow-verification-semantic20261008 -ApiPort 18008 -WebPort 15181 -ProductionPort 18088 -CrashRecovery -RewriteRecovery -SourceGuard -SemanticGuard -RewriteProvider OPENROUTER
```

PASS: Compose config/build/startup/migrations/health, forced API-IP change without
proxy restart, Redis and worker restart, down/up, PostgreSQL SIGKILL, Redis FLUSHDB,
synthetic encrypted session/config/media/outbox/job recovery, expired rewrite
lease fencing, structured synthetic OpenRouter completion and old-source rejection.

PASS: synthetic semantic evidence/automatic approval survived another down/up.
The synthetic release was then revoked; approval became ineligible and the prior
reservation became BLOCKED_REVIEW. No external provider requests or Telegram sends.
Probe requires both the explicit verification flag and `newsflow_verification` DB.
The terminal fixture retains revoked-release history; use a fresh project to rerun.

The later leased-runtime probe passed on Windows Docker Desktop in isolated
`newsflow-verification-semantic-lease20261008` (18009 / 15182 / 18089), with
the same switches and `-RewriteProvider OPENAI`. It seeds an unfinished verification
claim, actually downs/ups the stack, waits for the persisted 60-second lease,
recovers attempt 2 and fences attempt 1 before any synthetic provider call.
Exactly one injected verification completes; approved draft/job/evidence/known
token usage survive worker restart. Revocation then blocks its scheduled slot.
No external AI or Telegram calls occurred; volumes/history retained, stack stopped.
Post-probe cached-ORM fixes passed targeted/full local tests and were packaged on
the healthy operational stack; actual PostgreSQL schema drift check passed there.

CI now runs the semantic probe after both synthetic provider recovery variants.
Actual PostgreSQL drift check also passed using
`command.check(runtime_migration_config())`. A plain `alembic check` invocation
initially inspected the container's default local SQLite URL and reported
not-up-to-date; that read-only diagnostic was not a PostgreSQL migration failure.
The corrected command explicitly uses DATABASE_URL. No database reset occurred.

## Remaining operational qualification

Runtime jobs/factory/worker are implemented and verified with synthetic providers.
This does not establish a live model's semantic accuracy. Known provider usage is
persisted per attempt; unavailable tariff is NULL. A crash between a provider
response and usage persistence can leave unknown usage, never a claimed zero cost
or exactly-once external charge. Attempt limits bound repeat calls after crashes.

No operational model is qualified. A real, fixed-model adversarial benchmark and
reviewed evaluation report are required before activating a real release. Current
authorized key-file presence check found no usable credential; live tests remain
blocked by credentials. No key was printed, changed, persisted or committed.

Live Telegram authorization/transport and operational unattended publication remain
pending. PHASE 1 is NOT complete. This increment does not enable real publication.
