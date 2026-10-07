# Immutable source freshness before approval/planning — 2026-10-08

## Reproduced failure and fix

A successfully rewritten revision retained its historical PASS decision after a
donor edited the source. Manual approval only checked that old decision and job,
so an old PENDING draft could be approved. An already approved draft could also
be activated later; a READY or PLANNED old candidate could obtain/retain a slot.
Regression tests reproduced these paths before their fixes.

The shared source resolver joins immutable account/donor/message/revision identity,
rejects absent/ambiguous matches and checks the latest persisted revision. It is
used by the rewrite runner, draft recording/review/projection, candidate activation
and publication planner. No permissive missing-source legacy fallback is added.

An old/missing draft cannot be re-recorded or approved, even when its old job is
SUCCEEDED and stored editorial decision remains PASS. Review API returns 409 and
projects `approve_allowed=false`; it never calls an AI provider. Historical draft,
approval and job are retained. Rejection remains available for pending stale drafts.

The planner refuses missing-source candidate registration, skips non-current READY
candidates and reconciles old PLANNED slots to `BLOCKED_SOURCE`, freeing active
quota/slot uniqueness without deleting history. GET adds `source_current` as a
read-only projection; it does not silently mutate a reservation. Actual Telegram
send still needs final source/editorial/fact revalidation in the future transport.

## Verification

- Source edit after rewrite, source edit after approval, old READY selection and
  old PLANNED reconciliation tests failed before implementation, then passed.
- Missing revision blocks draft re-record/approval and actual HTTP approval.
- Former synthetic fixture shortcuts were replaced with actual IncomingPost and
  ContentRevision identities; tests keep exercising real persistence contracts.
- Full backend: 233 passed; lint and compile passed. Browser integration: 19 passed
  against a migrated isolated actual API; existing style persistence still works.
- PostgreSQL Docker probe and latest CI evidence are recorded in CURRENT_STATE.md.
  `-SourceGuard` adds an explicit synthetic approval, edit and reservation-blocking
  step after rewrite recovery. It is confined to newsflow_verification with an
  explicit probe flag, never operational data or real Telegram/provider calls.
- Actual PostgreSQL probe passed in rebuilt `newsflow-verification-openrouter20261008`:
  explicit synthetic approval, immutable source edit, old re-approval blocked and
  prior slot transitioned to BLOCKED_SOURCE. Actual API projected false and returned
  HTTP 409 too. Stack stopped, volumes/history retained; no provider/network/send.

## Boundaries

This validates source freshness at each covered transition, not full semantic
truth or proof against all concurrent ingestion interleavings. No automatic
approval is enabled. Future live ingestion/publication must serialize identity
changes appropriately and recheck latest source immediately before sending.
Manual overrides do not bypass EditorialGate. PHASE 1 remains incomplete.
