# Separate create-only channel synchronization recovery probe

2026-10-08; branch `codex/dark-navy-ui`, parent
`72685a33c528aa084f465a21f5711376d7fee2f4`; correct origin
`borovojarkadij-png/content-studio`.

## Procedure implemented (Docker execution pending)

`scripts/verify-persistence.ps1 -Project newsflow-verification-channel-sync-ci
-CrashRecovery -ChannelSyncGuard` uses a separate fresh synthetic stack. Combining
ChannelSyncGuard with legacy guard suites is rejected before Docker/filesystem
setup: persistent enforcement cannot be undone for test convenience.

After ordinary foundational persistence verification, the terminal sync family:

1. Creates a unique synthetic account, encrypted session, two output mappings,
   new donor and a legacy donor with one previously eligible durable rewrite job.
   Exclusive versioned manifest/account detection forbids reseeding.
2. Persists global enforcement, authentic-contract synthetic checkpoint pts=10,
   non-final chunk pts=11, deleted-103 tombstone and exact retained observations
   101/102 with no editorial/jobs. Commits a 60-second continuation claim, then
   leaves it unfinished (simulated process exit, not a fabricated reset).
3. Performs down/up and independent pending verification, waits for the real
   persisted lease, resumes from pts=11 without checkpoint/history fallback.
   Final pts=12 deletes 101 before history, retains 104 and replays exact sources.
   Deleted originals stay deleted; unknown 102/104 stay MANUAL_REVIEW.
4. Exercises actual legacy rewrite guard with a forbidden provider; no AI calls
   or usage. A prior synthetic base job is processed through its actual guard
   rather than skipped. Bounded scan regression proves coexistence.
5. Verifies real read-only Inbox HTTP truth, Redis/worker restart, another down/up,
   PostgreSQL SIGKILL recovery, encrypted session/pts/identity/tombstones/immutable
   revisions/obligations/completion retention and repeated zero-side-effect reads.

The provider is synthetic and read-only. A second PostgreSQL transaction takes
the exact donor/account/cursor locks during injected RPC with a two-second lock
timeout. SQLite tests do not prove PostgreSQL lock behavior. CLI requires the
explicit isolated PostgreSQL verification database, all seven network flags 0
and the separately mounted stable public fixture key; no generation/rotation.

GitHub Actions now has a dedicated **Synthetic channel sync PostgreSQL restart**
job; existing provider suites remain separate. The new actual Docker job has
not yet been observed passing. Do not promote it to VERIFIED WORKING prematurely.

## Actual offline evidence

- Initial absent probe contract RED; fixed synthetic message timestamps after
  strict difference contract correctly rejected incomplete Fake payloads.
- Continuation-claim semantics verified: non-final error is retained before
  claim; active token itself fences freshness after claim clears non-gap errors.
- Coexisting earlier synthetic job RED reproduced, real bounded guard scan GREEN.
- Missing stable-key and real Inbox verification contracts RED → GREEN.
- **9 dedicated / 44 combined targeted tests PASS**; actual FastAPI read before
  and after recovery, no HTTP fixture interception.
- Fresh final full backend **962 PASS**, session **24877**, 74.56 seconds.
- Exact CI Ruff (including new probe), changed-file format and compile PASS.
- Explicit fresh D: Alembic round-trip/drift PASS; no operational DB touched.
- PowerShell parser PASS; actual invalid-suite invocation refuses before Docker.
- Frontend unchanged. Previous enforcement CI **37747730266** backend/frontend
  SUCCESS; Docker variants still in progress at inspection, not overall PASS.

Current Windows Docker **NOT VERIFIED / BLOCKED BY ENVIRONMENT**; C: ~0.16 GB
free and previously read-only containerd storage. No reset/prune/key regeneration,
real authorization, real source download, paid provider call or publication.
PHASE 1 remains incomplete.

## NEXT_STEP

Push this verified offline increment and inspect exact new GitHub run/job.
Then harden replay's source snapshot after acquiring current donor/cursor/account/
mapping locks: a concurrently committed source edit must not be classified from
an earlier max-revision read. Add test-first interleaving regression, fresh gates
and PostgreSQL concurrency evidence; keep operational flags 0. Explicit legacy
resynchronization/TooLong recovery remains separate, not an implicit latest reset.
