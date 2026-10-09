# Combined correction wave — I-1 through I-4

Base: `7af4324cac284b8bd3085eecb80e14c166149ccc`, branch `codex/dark-navy-ui`.
Implemented and verified; ready for root's scoped independent re-review. No operational
migration, live provider/network invocation, push or merge is part of this wave.

## I-1 — populated historical migration

The historical migration now freezes its own editorial hard-gate predicate
(no imports from future application policy) and dispatches only explicitly
passing decisions and AWAITING_REWRITE candidates. Original job/event rows
remain as SUPERSEDED history for fan-out; no audit rows are deleted. The positive
fixture now supplies real valid neutral PASS evidence. Reject, manual, missing,
hostile PASS, unknown classification PASS, rewrite-disabled PASS and ineligible
candidate states receive no new output work.

Already-applied databases: changing this historical revision does not rerun it.
Existing scoped jobs/events remain retained. Current worker guards continue to
fence ineligible execution; no cleanup, repair DML or operational migration was
performed or is implied by these fresh synthetic upgrade tests.

## I-2 — semantic technical eligibility

Common binding now calls the fresh shared output technical filter, covering
admission, pre-factory execution and post-call evidence persistence. Tests use
real durable jobs, reopen with a separate engine, and change current route
policy or retained legacy source metadata. Mandatory video/hidden YouTube and
custom-domain/media policy exclusions are covered at all three boundaries.
Mid-call exclusions preserve the claimed attempt and pending output, retain
terminal BLOCKED history and produce no semantic evidence or approval.

## I-3 — destination identity

Mandatory and custom-domain policy share one bounded strict host extractor for
visible and hidden links. It decodes host escapes once; invalid escapes,
recursive escapes, encoded host separators, backslashes, controls, malformed ports,
unknown schemes and invalid host labels fail closed. Encoded letters/dots,
scheme-relative hosts and subdomains match the same destination. Filtering does
not alter the message or retained source observation. Full ingress regressions
assert classification never starts, no job/request event exists, and runner
provider construction remains zero.

## Behavioral RED/GREEN command output excerpts

All commands run from `backend` with local Python 3.12; these are synthetic tests.
No failed check is counted as a pass. Raw terminal summary/excerpts follow.

```
python -m pytest tests/test_configuration_migration.py -k requeues -q
AssertionError: Left contains 2 more items, first extra item: (1, 'DISPATCHED')
7 failed, 1 passed, 3 deselected in 2.78s

python -m pytest tests/test_configuration_migration.py -q
11 passed in 4.89s

python -m pytest tests/test_strict_link_hosts.py -q --tb=short
Failed: Excluded link reached classification
24 failed, 9 passed in 3.74s

python -m pytest tests/test_strict_link_hosts.py tests/test_hidden_donor_links.py tests/test_persisted_mapping_filters.py tests/test_mapping_technical_filters.py -q --tb=short
77 passed in 8.58s

python -m pytest tests/test_semantic_technical_guards.py -q --tb=short
admission: assert 2 == 0
queued-reopen: assert 1 == 0 (provider factories)
during-call: assert <SemanticEvidenceModel ...> is None
12 failed in 2.14s

python -m pytest tests/test_semantic_technical_guards.py tests/test_semantic_runner.py tests/test_semantic_approval.py -q --tb=short
67 passed in 9.19s

python -m pytest tests/test_planner_media_postgres.py -q --tb=short
2 skipped in 0.47s
```

The two PG skips are absence of the explicit isolated concurrency opt-in, not
concurrency evidence. Parent separately performed the actual controlled execution.

Initial scoped Ruff check found three import-block findings and an import alias
finding in new tests. Explicit fixture alias plus scoped import/format correction
resolved those; the final independent static check is recorded below.

## I-4 — shared lock order and actual PostgreSQL proof

Reconciliation locks the planned row alone, retaining the delivery-receipt
planned-before-candidate ordering. It then takes job → editorial → draft →
automatic policy/release → candidate, matching media acquisition and approval.
Candidate identity/state and reservation identity/state/date are reloaded and
all existing eligibility gates are revalidated. New scheduling uses the same
ordered candidate boundary and rechecks READY after the lock. No retry loop or
removed gate is used.

The explicit PostgreSQL harness reuses the unmodified strict local synthetic
fixture validator and creates fresh UUID schemas with no reset/drop. Two events
deliberately hold media's editorial row while the old planner owns candidate,
or the corrected planner waits for the already-owned job. Backend PIDs come
from the connections actually acquiring locks. All those connections have
15-second lock / 20-second statement timeouts. A frozen legacy-order control
must produce 40P01; the production order must finish with NO_MATCH, one provider
search, one committed attempt and cleared lease, with reservation retained.

Parent-owned Windows PG evidence (the child did not run Docker or mutate any
existing namespace):

```
python -m pytest tests/test_planner_media_postgres.py -q --tb=short
RED on unchanged production planner: errors=['40P01']
1 failed, 1 passed in 4.91s
GREEN on corrected production planner, strengthened exact-PID/timeouts harness:
2 passed in 3.00s
```

Raw native logs: `D:/Codex-Recovery/content-studio-20261008/planner-media-red-20261009a.log`
and `D:/Codex-Recovery/content-studio-20261008/planner-media-green-20261009a.log`.
Parent owns fixture identity and execution evidence. CI now explicitly runs
this target with the already-existing public synthetic PG service identity;
no runner, dependency, secret or operational configuration was changed.

Parent additionally completed the existing dedicated PostgreSQL target set:
`332 passed in 377.96s`, exit 0, native log
`D:/Codex-Recovery/content-studio-20261008/cross-task-postgres-20261009a.log`.
It started before the URL compatibility correction and is intermediate evidence
for unchanged planner/media/storage paths, not final-parser identity evidence.

## Combined checks and corrections during verification

```
python -m pytest tests/test_publication_planning.py tests/test_internet_media.py tests/test_media_acquisition_api.py tests/test_planner_media_postgres.py -q --tb=short
24 passed, 2 skipped in 3.20s
```

One preceding invocation used repository-root cwd with backend-relative test
paths: `ERROR: file or directory not found`, `no tests ran`. It was corrected
to backend cwd and is not application evidence.

Three supplementary retained-source-observation tests initially opened a read
transaction before invoking the ingestion transaction. Combined output was
`3 failed, 179 passed, 2 skipped in 37.27s` with SQLAlchemy's
`A transaction is already begun on this Session.` Test setup was corrected to
use separate read/ingestion sessions, without a production change:

```
python -m pytest tests/test_strict_link_hosts.py -k excluded_edit -q --tb=short
3 passed, 33 deselected in 1.04s

python -m pytest tests/test_configuration_migration.py tests/test_strict_link_hosts.py tests/test_hidden_donor_links.py tests/test_persisted_mapping_filters.py tests/test_mapping_technical_filters.py tests/test_semantic_technical_guards.py tests/test_semantic_runner.py tests/test_semantic_approval.py tests/test_publication_planning.py tests/test_internet_media.py tests/test_media_acquisition_api.py tests/test_planner_media_postgres.py -q --tb=short
182 passed, 2 skipped in 30.32s

python -m ruff check src tests alembic
All checks passed!
python -m ruff format --check src/newsflow/domain/technical_filters.py src/newsflow/services/semantic_verification.py src/newsflow/services/publication_planning.py alembic/versions/e7d3a4f810bc_scope_rewrite_jobs_to_output_channels.py tests/test_configuration_migration.py tests/test_strict_link_hosts.py tests/test_semantic_technical_guards.py tests/test_planner_media_postgres.py
8 files already formatted
python -m compileall -q src tests alembic
[exit 0, no output]

python -m alembic upgrade head
python -m alembic downgrade base
python -m alembic upgrade head
python -m alembic check
No new upgrade operations detected.
Fresh migration namespace: C:\Users\borov\AppData\Local\Temp\newsflow-final-fix-migration-4dd410d8e62f4e5c96e64c376de379e4
```

The migration command used a new UUID temporary directory and explicitly scoped
DATABASE_URL, checking every exit code. It did not open backend/newsflow.db.

## Full-gate compatibility correction

The first full gate revealed the pre-existing compatibility contract that
`https://youtube.com@example.org/news` identifies host `example.org`, not
YouTube. A blanket userinfo refusal was overly restrictive. Focused RED:

```
python -m pytest tests/test_donor_automation_exclusions.py -q --tb=short
test_non_youtube_hosts_paths_and_plain_mentions_are_not_falsely_rejected[Read https://youtube.com@example.org/news]
AssertionError: assert False (TechnicalFilterDecision: INVALID_LINK)
1 failed, 43 passed in 6.05s
```

The parser now ignores unambiguous userinfo for host comparison; its parsed
hostname retains all strict decoded separator/control/label checks. This is
compatibility preservation, not a policy bypass or an expected-test change.

```
python -m pytest tests/test_donor_automation_exclusions.py tests/test_strict_link_hosts.py tests/test_hidden_donor_links.py tests/test_persisted_mapping_filters.py tests/test_mapping_technical_filters.py -q --tb=short
124 passed in 16.81s
```

The initial full process had imported the pre-correction parser. After the
focused regression proved its failure and the fix passed, that known-failed
process was deliberately terminated at approximately 47% (exit 1, no completed
suite count). Its exact PID/command was checked before termination; the parent's
independent PG process was untouched. This is ABORTED intermediate evidence,
not a completed full-suite result. The final fresh full process on corrected
frozen source is the only complete final full gate.

## Frozen source identity

Final implementation/test/CI bytes before the final full gate (SHA-256; report
edits only are permitted while the gate runs):

```
backend/src/newsflow/domain/technical_filters.py
3EDECEB940A0702066CEB10295471474731BB86616305138242BA712314CC69E
backend/src/newsflow/services/semantic_verification.py
6BC90E6AEA337E69D99590AE07B1988FB9B0E1E308A033FE49A70DFD83793332
backend/src/newsflow/services/publication_planning.py
DB7D1F036829B5E4AEE00EC6570486506E1E79B7D67060C1F30404DDF064AE4C
backend/alembic/versions/e7d3a4f810bc_scope_rewrite_jobs_to_output_channels.py
759186D38F86B7091F93FAE67F0991AF567A019B06C913E87A87B1D5DAF566F4
backend/tests/test_configuration_migration.py
69BF457CD8E55D1088372A9E1600B6DB7BF29143842315139C6A95DE786CEE19
backend/tests/test_strict_link_hosts.py
E9DD7C7CFDCAF65E8CC7C8FBF6496481ACB952AA70D5570FCA3F5B34DE407FCC
backend/tests/test_semantic_technical_guards.py
2CDAA0CF9445D16587F06E68E77E3082645376C2F3F8B6538CEE16E1C192A425
backend/tests/test_planner_media_postgres.py
BAF92D16868DC1F2F6C5A5EDE94F63627141145EC8C20451F55BFAEFCE053FA3
.github/workflows/ci.yml
1EAC60CEBC23302EF314DF097B925B17C4511378BE78207F0E3052B485397690
```

Final-source Ruff (all backend source/tests/migrations), format (eight changed
Python files) and compileall were repeated after the compatibility correction:
`All checks passed!`, `8 files already formatted`, compile exit 0. The migration
source and PostgreSQL planner/harness did not change after their successful gates.

## Remaining boundaries

All evidence is synthetic. No model qualification, live Telegram/publication,
operational migration or PHASE 1 completion is claimed. Historical databases
already beyond the revised migration are not rewritten. Existing parent-owned
status/evidence docs remain outside this scoped commit. Root owns exact remote
CI and the one subsequent scoped independent re-review. Baseline CI37924345507
belongs to 7af4324, not these changes; its success is not new-source CI evidence.
Prior formatting debt, color-output and Actions runner/runtime warnings remain
separate; this wave does not silently resolve or waive them.

## Final frozen full backend gate

```
python -m pytest -q
1984 passed, 3 skipped in 397.90s (0:06:37)
[exit 0]
```

This was the sole completed final full gate, started on the final source above.
There were no source/test/CI edits during it. Earlier interrupted full execution
and every setup/compatibility failure remain disclosed above.

The three default-SQLite skips are:

- `test_postgresql_truncate_cannot_clear_owned_review_history`: requires strict
  PostgreSQL namespace, exercised separately in parent's 332-pass PG set.
- `test_planner_media_two_connection_lock_order[old-order-detects-deadlock]`.
- `test_planner_media_two_connection_lock_order[current-order-completes]`.

Both new concurrency cases passed separately on actual parent-owned PostgreSQL
with the same final planner/harness bytes. The full default suite does not
claim SQLite proves PostgreSQL locks or TRUNCATE semantics. Final remote CI and
independent scoped review remain root-owned next steps; no push was performed.
