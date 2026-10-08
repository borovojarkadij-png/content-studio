# Durable mapping-scoped exact dedup on fan-out

2026-10-08, existing `codex/dark-navy-ui`, only
`https://github.com/borovojarkadij-png/content-studio.git`.

## Reproduced defects and minimal correction

New-source ingestion reserved a normalized-text fingerprint before EditorialGate,
but `_route_existing_source` reused a retained PASS and queued work without that
reservation. Consequently:

- A source accepted by the first mapping, then fanned out to a second mapping,
  did not consume the second fingerprint; a later identical-text message could
  invoke editorial classification and create a third rewrite job.
- If the second mapping already reserved that text for another source, fan-out
  bypassed it and created additional work anyway.

Four actual migrated SQL behavior regressions failed before the fix (text/photo
duplicates, earlier competing reservation, missing reservation after retry).
One shared `_reserve_exact_content` now gates both branches before new work.
The existing strip/casefold UTF-8 SHA256 policy and mapping scope are unchanged;
this is not semantic/cross-mapping dedup or an image-identity equivalence claim.
Each independently eligible output still receives its own rewrite job and draft.
Historical sources/jobs/candidates/outbox are not deleted or rewritten.

The first savepoint implementation exposed a second actual rollback defect:
SQLite legacy transaction mode released the reservation savepoint before any
outer DML transaction existed. Injecting a later job failure left the fingerprint
committed, poisoning retry. This reproduced as `(2,1,1,1)` instead of the unchanged
`(1,1,1,1)` counts. The documented driver limitation is described in
[SQLAlchemy SQLite transactions](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#legacy-transaction-mode-with-the-sqlite3-driver).

Correction uses one targeted `INSERT ON CONFLICT(mapping_id,fingerprint) DO
NOTHING RETURNING id` in the outer transaction, supported by the existing
[PostgreSQL](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert)
and [isolated SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#insert-on-conflict-upsert)
storage. It updates no existing row. Only the named fingerprint conflict is a
duplicate; other integrity/storage failures propagate, roll back and remain
visible. No driver monkey-patch, migrations, caller commit, retry-budget reset
or global transaction-policy change.

## Verification

`backend/tests/test_mapping_fanout_dedup.py` uses current Alembic migrations,
configured synthetic mappings, independent engine/session reopen between
deliveries and actual worker executions. Cases cover:

- both fan-out duplicate orderings and text/photo observations;
- reject/manual-review replay with no RewriteJob/candidate/rewrite outbox and
  no provider construction;
- atomic classifier/job failure rollback followed by successful retry;
- actual NOT NULL integrity failure is not hidden as a duplicate;
- two independent competing connections, synchronized immediately before the
  fingerprint insert: one reservation/editorial/job/outbox, one cheap duplicate;
- same accepted source routed to two outputs, repeated deliveries and identical
  new-message text: exactly one injected rewrite call per output, distinct
  preserved-fact drafts both PENDING, each original job attempt budget one.

Initial **4 RED / 2 PASS**, shared savepoint correction **1 RED / 5 PASS**
(rollback defect), final targeted **32 PASS / 10.34s** (45068), including five
existing unattended vertical cases. SQLite concurrency passes with real
connections, not mocked SQL. Exact Ruff/format/D: bytecode/YAML and explicit
D: migration upgrade/check/downgrade/upgrade/check PASS. Final full backend
**1230 PASS / 133.53s** (1325), after adding the per-output worker regression;
earlier nine-case snapshot **1229 PASS / 179.39s** (98157).
Frontend source unchanged after the album checkpoint: 184 units/31 browser/
format/typecheck-build/audit0 local PASS; exact 7471132 / CI 37777065559 completed
all-eight jobs SUCCESS (actual gh inspection), including both legacy Docker
variants. Completed PG job 113310490678
has **51 PASS / 22.96s**, including the album/inbox flag regression, not this
uncommitted dedup patch.

Independent `requesting-code-review` source/history-only review found no
actionable findings in this patch and the committed album UI. Reviewer ran no
tests and made no changes; main-agent execution is the verification evidence.
No merge. Dedicated strict create-only PostgreSQL CI now includes these new
tests; actual new PG concurrency/rollback acceptance remains pending exact CI.

No operational secrets/session/DB/channel/configuration/permissions changed.
No real provider call, source download/upload or publication. Windows Docker
remains independently NOT VERIFIED / BLOCKED BY ENVIRONMENT; Linux CI does not
repair the machine. PHASE 1 is not complete. Existing legacy fingerprints are
not erased/backfilled or inferred to be orphaned from missing jobs.
