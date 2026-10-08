# Durable rewrite wait for temporary synchronization

2026-10-08; branch `codex/dark-navy-ui`, parent
`60596f5c461ec27e3dd12b20ab442d7b2cc86ac5`; correct origin
`borovojarkadij-png/content-studio`.

## Behavior

Known temporary synchronization no longer permanently supersedes an otherwise
current pending rewrite. With persistent sync enforcement and an exact healthy
account/donor/user/channel baseline, an active paired claim or allowlisted
transient error yields durable RETRY / SOURCE_SYNC_REQUIRED with a 30-second
available_at. No provider is constructed. Waiting releases the claim and retains
the same job/content/idempotency identity; it never grants rewrite permission.

A pre-provider wait returns only this claim's reserved attempt. Previously spent
attempts and the exhausted-budget sentinel are retained. A sync change after a
real synthetic provider boundary consumes the attempt and does not persist a draft.
After synchronization is current, ordinary fresh editorial/source/technical/fact/
attempt guards run again; any resulting draft still requires PENDING review.

Missing/foreign/legacy baselines, unresolved gaps, invalid sessions, deleted source
and stale immutable revisions remain terminal. Editorial REJECT remains terminal
before the provider. Historical SUPERSEDED jobs are not revived; no public retry,
cursor reset, automatic approval or operational activation was added.

## Actual verification

- Seven test-first RED cases reproduced terminal SUPERSEDED for temporary wait;
  new bounded wait fixes these paths. Exhausted-budget fixture explicitly uses
  max_attempts=2 (runner default is 3), rather than weakening the budget guard.
- **16 dedicated / 75 combined targeted tests PASS**: active/non-final/provider/
  pipeline errors, early-IDLE/repeated-wait zero budget, SQL reopen/fresh resume,
  exhausted budget, rejection, six permanent-source cases, post-provider wait,
  expired RUNNING claim identity/previous budget and account cooldown.
- Fresh complete backend **981 PASS**, session **48068**, 75.57 seconds.
- Exact CI Ruff, changed-file format/compile and explicit fresh D: Alembic
  upgrade/check/downgrade/base/re-upgrade/check PASS; no schema drift.
- Shared source guard remains deny-only. No jobs were created for editorial
  rejection and no OpenAI/OpenRouter network call, real session or send was used.
- Prior post-lock checkpoint 60596f5 CI **37749741849** dedicated **Synthetic
  channel sync PostgreSQL restart** completed SUCCESS (actual gh view), including
  its create-only independent edit/tombstone writer interleavings. Backend/frontend
  also SUCCESS; two old Docker variants still in progress at inspection, not an
  overall CI PASS. ab13403 dedicated restart job also completed SUCCESS.

New rewrite-wait PostgreSQL/restart acceptance is not yet implemented or verified.
Current Windows Docker remains **NOT VERIFIED / BLOCKED BY ENVIRONMENT**;
Linux evidence is not Windows verification. Frontend unchanged. Operational flags,
secrets, data and volumes untouched. PHASE 1 remains incomplete.

## NEXT_STEP

Push this checkpoint and inspect exact CI. Add a separate create-only terminal
rewrite-sync-wait probe to the ChannelSyncGuard family: persist a known temporary
cursor and original pending job/attempt, verify after down/up before recovery,
restore sync only through an actual validated difference chunk, then recover the
same job with a synthetic rewrite provider into PENDING review. Verify rejected,
deleted and exhausted-budget cases remain zero-provider. Do not reuse/reseed old
manifests or activate operational workers.
