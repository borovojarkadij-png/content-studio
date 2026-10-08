# Publication intents checkpoint

Branch: codex/dark-navy-ui. Base: aa075af9f15cb346cec184a1e109e26c74bdf658.
Its CI 37707297625 completed SUCCESS in all four jobs; this is NOT the new
publication increment's CI result.

## Implemented, no live sender

- Fresh read-only PublicationPreflight and immutable channel-specific envelope.
- Persistent publication_jobs, nonce/attempt/lease/receipt database constraints,
  migration a6d315c8fa04 and refusal to discard any publication history.
- Injected durable runner: bounded claim recovery, last-boundary revalidation,
  committed SENDING intent, unknown-outcome quarantine, proven-not-sent retry,
  exact acknowledgement and atomic PUBLISHED/delivery outbox.
- Published and sending/unknown-delivery reservations count towards the
  channel/day limit, including cancelled or subsequently revoked reservations.
- Repeatable PublicationGuard Docker procedure and both-provider CI wiring.

## Failure evidence and fixes

Initial seven runner cases failed because the durable runner did not exist.
After implementation, additional regression failures demonstrated:

- Attribution could introduce a forbidden URL after draft filtering: final
  caption, including credit, now passes the same current technical filters.
- Cancelling a slot during media integrity reads escaped a single preflight:
  two fresh snapshots must agree, followed by transport-boundary revalidation.
- An approved altered numeric anchor could be sent: fact guard reruns pre-send.
- ValueError/LookupError/policy-shaped exceptions AFTER sending were incorrectly
  labelled zero-send BLOCKED: only callback-proven pre-RPC failure is a block;
  unknown transport outcomes require reconciliation.
- Late exact acknowledgements were lost after lease expiry: matching immutable
  request can finalize an expired/unknown sending intent, without resending.
- Published slots were replaced and quota reused: published history stays counted.
- Unknown delivery was replaced after editorial revocation/cancellation: the
  separate send intent holds quota until reconciliation. Two local RED cases
  and a real PostgreSQL probe against the old packaged planner reproduced this;
  corrected image passed quota/verify before AND after another down/up.
- Provider acknowledgement without final guard was accepted: now quarantined.

Targeted preflight/runner/planner/migration + scheduler suite: 68 PASS. Final full
backend: 642 PASS. Frontend: 50 unit / 22 browser / format / typecheck / build
PASS, production audit zero vulnerabilities. Exact CI lint, touched-file format
and compile PASS. Isolated SQLite migration
upgrade/check/downgrade-base/re-upgrade/check PASS. Publication schema migration
test validates preserved old outbox and refuses non-empty downgrade.

## Runtime verification (update only from observed results)

Windows Docker fixture newsflow-verification-publication20261008 uses
18022/15195/18102, CrashRecovery + PublicationGuard: PASS. Actual Compose config,
build/startup/migrations/health, encrypted synthetic session/config/media/outbox,
Redis/worker restart, down/up, PostgreSQL crash and Redis-loss recovery passed.
Publication recovery passed: expired CLAIMED reclaims attempt two; old owner has
zero calls; abandoned SENDING becomes NEEDS_RECONCILIATION with zero resend;
exact synthetic receipt/PUBLISHED state persists; rejected queued job blocks
with zero calls. Separate PostgreSQL lock probe sees committed SENDING without
retained locks across the transport. Final corrected packaged worker drift PASS;
quota/verify PASS after another rebuild/down/up. Fixture stopped, all volumes
and history retained. Never reseed, prune or delete volumes.

Operational backend rebuilt/migrated to a6d315c8fa04: packaged PostgreSQL drift,
health and proxied inbox HTTP 200 PASS. All five existing network flags remain
0; env/master key/business data unchanged. Actual authorization, Telegram send permission
checks, live publication, reconciliation and unattended publication worker are
NOT VERIFIED / not implemented by this checkpoint. No actual paid AI calls or
Telegram publications are part of these tests.
