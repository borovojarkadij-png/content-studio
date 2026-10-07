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

Local contract/provider/database tests are synthetic and make no live AI calls.
They establish guard behavior, NOT the classification accuracy of any live model.
Latest full local gate: 298 backend tests, lint and compile PASS; frontend 26 units,
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

CI now runs the semantic probe after both synthetic provider recovery variants.
Actual PostgreSQL drift check also passed using
`command.check(runtime_migration_config())`. A plain `alembic check` invocation
initially inspected the container's default local SQLite URL and reported
not-up-to-date; that read-only diagnostic was not a PostgreSQL migration failure.
The corrected command explicitly uses DATABASE_URL. No database reset occurred.

## Not yet complete / next increment

The evidence service is a guarded transaction seam, not a durable verification
daemon. Add leased verification jobs, bounded committed attempts, fencing,
per-attempt usage and restart recovery before enabling runtime model calls.
Connect an encrypted verifier factory and explicit opt-in worker flag afterwards.

No operational model is qualified. A real, fixed-model adversarial benchmark and
reviewed evaluation report are required before activating a real release. Current
authorized key-file presence check found no usable credential; live tests remain
blocked by credentials. No key was printed, changed, persisted or committed.

Live Telegram authorization/transport and operational unattended publication remain
pending. PHASE 1 is NOT complete. This increment does not enable real publication.
