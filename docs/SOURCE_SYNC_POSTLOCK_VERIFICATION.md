# Replay post-lock source snapshot

2026-10-08; branch `codex/dark-navy-ui`, parent
`ab134033d15f5be0d9e24918d4cc1813a97044f6`; correct origin
`borovojarkadij-png/content-studio`.

## Reproduced boundary and fix

The replay inspector read latest revision/deletion before acquiring current donor,
cursor, account and mapping locks. An independent writer committing at that boundary
made the initial READY snapshot obsolete. Existing later guards prevented processing:
actual regression outcome was WAIT_SYNC, not an observed forbidden AI call. However,
the obsolete obligation unnecessarily survived until another scan.

After the binding locks, replay now locks the exact post in ordinary ingestion's
mapping → post order, reloads latest revision/deletion and canonical account/channel
binding, then constructs the event. Concurrently superseded/deleted obligations are
retired immediately without editorial classification. Historical revisions remain;
there is no fabricated REJECT/PASS, cursor reset or source identity guess.

## Actual offline evidence

- Two test-first independent-writer interleavings (new revision / tombstone) RED:
  WAIT_SYNC instead of SUPERSEDED. Both GREEN after post-lock freshness reload.
- Retired obligation is idempotently ALREADY_COMPLETED; no editorial decision,
  RewriteJob or usage is created for the obsolete exact key.
- Added a create-only terminal `concurrency` synthetic probe with a separate new
  account/donor; real bootstrap/claim/quarantine/final difference services precede
  the replay race. Independent edit writer and real SourceDeletionService writer
  commit at the max-read/binding-lock boundary; PostgreSQL writers use a bounded
  two-second lock timeout. No async sleeps, real providers or history deletion.
- Dedicated probe contract RED → GREEN, repeat seed refused; retained three
  revisions and zero jobs/usage verified. New terminal probe added to separate CI
  ChannelSyncGuard family, not mixed into legacy suites.
- **59 combined targeted tests PASS**; fresh complete backend **965 PASS**,
  session **97075**, 74.15 seconds. Exact CI Ruff/changed-file format/compile,
  PowerShell parser and explicit fresh D: migration round-trip/drift PASS.

## Runtime evidence boundaries

Earlier enforcement 72685a3 CI **37747730266** completed SUCCESS (actual gh list).
Previous probe ab13403 CI **37748969125** dedicated **Synthetic channel sync
PostgreSQL restart** completed SUCCESS (actual gh view). That proves its baseline/
deletion/quarantine/replay down-up/worker-Redis/PG-crash and RPC lock checks on
Linux Docker/PostgreSQL, NOT this newly added concurrency case or Windows runtime.
Other jobs in that run were still in progress at inspection; no overall PASS yet.

New concurrency PostgreSQL execution remains pending its exact new CI checkpoint.
SQLite unit interleavings are not PostgreSQL row-lock proof. Current Windows Docker
stays **NOT VERIFIED / BLOCKED BY ENVIRONMENT**. No real flags, sessions, keys,
operational DB or volumes modified; PHASE 1 remains incomplete.

## NEXT_STEP

Push this checkpoint and inspect its dedicated PostgreSQL concurrency job; fix any
failure without weakening assertions. Then add bounded nonterminal rewrite waiting
for a temporary active/error synchronization cursor, preserving the durable job and
attempt budget with zero provider calls. Permanent deletion/stale revision/editorial
REJECT must remain terminal. Do not reactivate any historical SUPERSEDED job or
waive missing/foreign/legacy continuity; test restart, expiry and fresh PASS before
any permitted provider execution. Keep operational network flags 0.
