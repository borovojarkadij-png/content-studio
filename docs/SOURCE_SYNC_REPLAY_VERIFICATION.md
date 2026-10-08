# Durable replay of exact retained sync observations

2026-10-08; `codex/dark-navy-ui`, parent
`697fdd11572ce26f4dc1626ff0e5fd677f5aa6c0`; correct origin
`borovojarkadij-png/content-studio`.

## Implementation

Quarantined ingress now records `source.sync_quarantined` with the exact immutable
revision key in the same transaction as the retained source/revision. Exact
replay is idempotent; actual SQL outbox failure rolls back the whole observation.
It still calls no classifier, consumes no fingerprint and creates no rewrite job
during a known gap. No schema migration or inferred historical backfill.

`SourceSyncReplayService` is internal and network-free. Each replay requires a
current bound idle difference cursor, CONNECTED current account/session, no
cooldown/error, exact latest stored revision and current bounded mapping/filter
snapshot. It reconstructs the provider-neutral observation from stored immutable
fields, not guessed text/time matches or a fresh donor fetch. Each mapping goes
through ordinary ingestion in its own guarded transaction. Context is rechecked
before each mapping and completion. Retained obligations survive partial commits,
process exit, SQL reopen and current policy/context changes.

Missing editorial classification on an exact quarantined revision is evaluated
through the normal deterministic filters/exact dedup/EditorialGate path. Unknown
remains MANUAL_REVIEW with rewrite=false; protected REJECT remains authoritative,
with zero new rewrite jobs/usage. Existing decisions are never overwritten by
fabricated neutral metadata. A deleted/superseded revision retires the obligation
without classification or removal of history. The completion outbox entry is
idempotent and does not mean an account connected or a post was published.

`run_batch` scans at most 16 pending obligations, exposes a fair cursor and wraps
after the end; one unresolved donor does not starve other retained records.
Durable work is PostgreSQL-owned; the scan cursor is only scheduling fairness.
There is no new public replay/reset/send endpoint or operational worker flag.

## Verification evidence

- Seven missing durable-obligation failures RED; after marker implementation,
  seven missing-service failures RED; bounded-scan missing method RED, then GREEN.
- 12 dedicated replay tests, combined sync/difference/replay gate **61 PASS**.
- Actual isolated SQL reopen after partial mapping process exit; no duplicate
  revision, fabricated PASS, new AI usage or forgotten obligation.
- Actual SQL insert faults for obligation/completion, pending retry/current-policy
  fence, bound user/session/idle cursor/mappings, deleted and protected-REJECT cases.
- Fresh full backend **918 PASS**, session 41004, unique D: temporary tree;
  exact CI Ruff / changed-file format / compile PASS. Explicit isolated D:
  Alembic upgrade/drift PASS; no operational migration/database writes.
- Frontend unchanged in this increment: preceding actual 65-unit / 26-browser
  gate and inspected sync-gap desktop/mobile screenshots remain historical evidence.

## Limits

The new service is not yet connected to the worker main loop. New obligations
are emitted automatically; historical quarantined revisions from before this
checkpoint are not silently fabricated into completed/recovered work. A bounded
explicit legacy reconciliation policy and opt-in orchestration remain pending.
Unknown-source editorial classification still requires qualified classification
or review; no model release is automatically qualified by synthetic tests.
Windows Docker/current deployment/live Telegram acceptance remains NOT VERIFIED /
BLOCKED BY ENVIRONMENT/AUTHORIZATION. No operational volumes, keys or flags changed.
