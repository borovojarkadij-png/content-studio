# Residual I-4 — transaction-wide planner ordering

Base `e1604efe99db1332702d0eed6ee2f2e861950dc0`, source baseline `f8aa00b`,
branch `codex/dark-navy-ui`. I-1–I-3 remain accepted and unchanged. This focused
continuation follows the parent's recorded human-autonomy ruling in
`residual-i4-brief.md`; it does not expand operational authority. Implementation
and the final frozen full gate are complete; ready for scoped independent review.

## Residual and correction

The original correction ordered one candidate correctly but held shared policy
P while advancing to another job J_B. A media transaction could own J_B and
wait for P, producing SQLSTATE 40P01. Both loops and the transition between
reconciliation and READY selection had this transaction-wide cycle.

The planner now fixes one candidate identity snapshot spanning both loops.
It locks reservations alone, then all referenced jobs in ID order, all existing
editorial rows in content-key order, and all referenced drafts in ID order.
Only afterward can per-candidate checks acquire shared policy/release and
candidate locks. A media operation holding J_B can finish its policy check
before the planner acquires shared policy; once the planner holds policy, every
upstream job/editorial/draft it may need is already owned. Shared editorial
ordering also applies across output channels. Policy is not pre-acquired ahead
of jobs.

The snapshot includes source/candidate/output/job identities. Changed bindings
fail closed; newly READY candidates wait for the next tick. Re-read plan,
candidate/job/draft and reservation identity/state accompany existing fresh
source, editorial, technical and review checks. Missing editorial rows remain
missing for this batch instead of permitting a new late editorial lock. Local
batch state is cleared in `finally`, including rollback and service reuse.
No network I/O, retries, budget resets or migrations were added.

Work is explicitly capped at 1,000 candidate/reservation hints. Over-capacity
raises `PlanValidationError` and rolls back without silently truncating or
committing a partial plan. This is an intentional fail-closed capacity limit;
larger backlogs need a separately designed bounded planner strategy rather
than an unbounded lock set. Daily limits/slots, uncertain-delivery quota,
eligibility and existing approval/source/technical/history gates remain in place.

## Controlled PostgreSQL evidence

The existing strict `create_postgres_namespace` helper is unchanged. Each case
uses a fresh migrated UUID namespace and known local synthetic fixture opt-in
`NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL`; none are dropped/reset. Two distinct
source keys/drafts on one output receive genuine AUTOMATIC approval through
the real semantic binding/evidence and approval services, using explicitly
synthetic verifier/release data. Daily limit is two.

The media connection holds B's job/editorial/draft before its policy request.
Events force the original planner to acquire A's policy or the corrected
planner to reach the upstream batch boundary. The exact lock-owning PostgreSQL
backend PIDs differ. Connections use 15-second lock and 20-second statement
deadlines; thread/event waits are bounded, with no timing sleeps.

The original joined-lock legacy control and manual one-candidate success case
remain. The legacy control explicitly bypasses the new batch hook because its
purpose is to retain the historical pre-batch inversion, not inherit the fix.
Successful pair cases require two planned candidates, one NO_MATCH acquisition,
one committed attempt, cleared claim and one synthetic provider search.

Parent-owned actual Windows commands/results:

```
python -m pytest tests/test_planner_media_postgres.py -q --tb=short
PRE-FIX: reconciliation, ready, mixed each errors=['40P01']
3 failed, 2 passed in 13.23s
[exit 1]

python -m pytest tests/test_planner_media_postgres.py -q --tb=short
5 passed in 6.50s
[exit 0]
```

Native logs:
`D:/Codex-Recovery/content-studio-20261008/planner-pair-red-20261009a.log`
and `D:/Codex-Recovery/content-studio-20261008/planner-pair-green-20261009a.log`.
Parent verified the retained synthetic container/project and loopback endpoint.
The child performed no Docker/runtime/operational DB actions. The already-wired
CI target names the whole test file, so the three new cases run there without
workflow/runner changes or waivers.

## Local verification and every intermediate failure

Commands below run from `backend`. Following the parent's low-C-drive warning,
new TEMP/TMP and PYTHONPYCACHEPREFIX are under the owned directory
`D:/Codex-Recovery/content-studio-20261008/residual-i4-tests-c1db93c277904e00b29b05ef9e699456`.
No retained fixture, manifest or runtime artifacts were cleaned up.

```
python -m pytest tests/test_planner_media_postgres.py -q
5 skipped in 0.91s
```

These local skips reflect missing explicit PostgreSQL opt-in, not lock proof;
the actual parent-owned RED/GREEN results above supply that evidence.

```
python -m pytest tests/test_publication_planning.py tests/test_internet_media.py tests/test_semantic_approval.py tests/test_planner_media_postgres.py -q --tb=short
62 passed, 5 skipped in 7.31s

python -m pytest tests/test_planning_batch_guards.py -q --tb=short
1 failed, 4 passed in 1.49s
sqlite3.IntegrityError: UNIQUE constraint failed: rewrite_outputs.rewrite_job_id
```

The failed supplemental setup tried to rebind to a job that already owned a
different output. It was corrected to create a dedicated synthetic replacement
job, retaining the real uniqueness constraint. No production relaxation or
changed expected result was used. Its purpose is to ensure a changed draft/job
identity cannot become a late lock or planned candidate.

```
python -m pytest tests/test_planning_batch_guards.py tests/test_publication_planning.py tests/test_internet_media.py tests/test_semantic_approval.py tests/test_planner_media_postgres.py -q --tb=short
67 passed, 5 skipped in 8.16s

python -m ruff check src tests alembic
All checks passed!
python -m ruff format --check src/newsflow/services/publication_planning.py tests/test_planner_media_postgres.py tests/test_planning_batch_guards.py
3 files already formatted
python -m compileall -q src tests alembic
[exit 0, no output]
git diff --check
[exit 0; only existing Git LF/CRLF notices]
```

One new test import-block formatting finding was automatically corrected before
the final clean check. Only the three changed Python files were formatted.

Expanded related planner/media/approval/publication regression set:

```
python -m pytest tests/test_planning_batch_guards.py tests/test_publication_planning.py tests/test_internet_media.py tests/test_media_runner.py tests/test_semantic_approval.py tests/test_rewrite_candidate_activation.py tests/test_publication_runner.py tests/test_publication_preflight.py tests/test_publication_observation_recovery.py tests/test_planner_review_api.py tests/test_publication_main_loop.py tests/test_publication_tick.py tests/test_planner_media_postgres.py -q --tb=short
175 passed, 5 skipped in 32.13s
[exit 0]
```

## Frozen source SHA-256

```
backend/src/newsflow/services/publication_planning.py
059FB6758236ED408FF51760C9DB30ACD03351AC16EA9A6A3A77DCFAAF27A991
backend/tests/test_planner_media_postgres.py
D234F7621B2C6DB7CB1451229AB2A7C6F51790FE5F5864921A012BF371D41BBD
backend/tests/test_planning_batch_guards.py
6C46441FD0479E97F78299FBD59E99C2AF382E75C7AD0FB9C67217DE67E50875
```

Only this report changed during the final complete backend gate. After the
intentional conversation interruption, all three source hashes were rechecked
and still matched exactly. The original process handle was recovered without
starting another full suite.

## Final complete backend gate and interruption recovery

```
python -m pytest -q
1989 passed, 6 skipped in 428.88s (0:07:08)
[exit 0]
```

This is the single final full process, session 89870, on the frozen source above.
The six default-SQLite skips are the five explicit PostgreSQL concurrency cases
and the existing `test_postgresql_truncate_cannot_clear_owned_review_history`.
The five concurrency cases passed in the actual PostgreSQL GREEN run above.
Parent separately completed the final corrected-source migrated PostgreSQL set:

```
332 passed in 423.04s
```

Native log: `D:/Codex-Recovery/content-studio-20261008/residual-postgres-20261009a.log`.
That parent process handle was lost across the intentional turn interruption;
the terminal pytest summary was recovered from its native log and no matching
process remained. No unavailable process exit code is invented for that run.

The parent also owns the corrected frozen-source Windows `20261009c` fixture:
its native build/migration/restart/crash/fake-execution log reached terminal
create PASS, followed by a fresh independent read-only double verification
PASS/exit 0. Exact manifests/runtime hashes and all runtime evidence remain in
the parent ledger; the child did not recreate, clean or mutate those fixtures.

## Limits and next boundary

No real model, Telegram authorization/publication or operational activation is
qualified by synthetic tests. Existing e160 CI and f8 Windows runtime evidence
are historical baselines, not final residual-source proof. Root owns new exact
CI and the targeted independent review. Parent status/evidence docs are not
staged by this child. No push, merge, credential, schema or operational change.
