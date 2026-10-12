# Task 1 — canonical durable diagnostic admission

Implementation is admission-only. The accepted offline request/entity contract is
the authority; accepted classifier adapters remain unwired. No synthetic result
qualifies a real model or grants rewrite/publication permission.

## Repository and ownership

- Verified before writing: origin `https://github.com/borovojarkadij-png/content-studio.git`,
  branch `codex/dark-navy-ui`, HEAD `1d00655e7722ea615f23a35f860800b01d1d1bff`,
  clean `git status --short`. Alembic actual parent head `c5e81b29a704`.
- Read the exact task brief, only Global Constraints from the implementation
  document, and complete TDD (including writing-good-tests), NewsFlow data
  migration/recovery and AI eval skills. No subagents/helpers/reviewer dispatch.
- Root-owned progress/state/plan/CI recovery/live-acceptance documents became
  modified concurrently; none are owned, edited, staged or committed by this task.
- All synthetic SQLite files, pytest caches, Python bytecode and test artifacts
  use unique `D:/Codex-Recovery/content-studio-20261008/editorial-admission-*` paths.
  No real data, credentials, sessions, keys, queues or retained namespaces touched.

## Scoped changes

1. `backend/src/newsflow/persistence/models.py`: singleton explicit disabled-by-default
   policy; diagnostic job with bounded states/provider/attempts/leases/digests,
   immutable binding identity and RESTRICT references; nullable fingerprint owner.
   No policy/model/protected entity defaults or historical owner backfill.
2. `backend/alembic/versions/d7b340a92e16_add_editorial_diagnostic_admission.py`:
   one additive migration from the actual parent. SQL Boolean false default,
   no inserted policy row, SQLite/PostgreSQL binding-update refusal triggers,
   and populated downgrade refusal before any DDL.
3. `backend/src/newsflow/services/editorial_admission.py`: frozen canonical binding,
   sanitized blocked reason codes, fresh SQL reads, exact SQL source-key resolution,
   donor and output ownership resolved separately (explicit cross-account mappings
   supported), current manual decision/no rewrite work, latest/deletion/sync guards,
   reconstructed Telegram observation and current intake filter, strict existing
   fingerprint ownership, accepted policy/source validation, internally derived
   canonical hashes, atomic QUEUED job plus diagnostic event. Caller owns transaction;
   storage/integrity failures propagate. Exact terminal history is returned unchanged.
4. `backend/src/newsflow/domain/durable_ingestion.py`: both existing exact-dedup
   reservations write the exact revision owner using the existing targeted conflict
   insert. Only the new configured positive-int mapping MANUAL_REVIEW branch calls
   canonical enqueue after source persistence/state update. Existing statuses,
   passing fan-out and cheap rejection/dedup/stale/sync paths remain intact.
5. `backend/tests/test_editorial_admission.py`: 88 migrated SQL behavior cases.
   Strict opt-in fresh UUID PostgreSQL namespace via existing unattended helper;
   otherwise isolated newly migrated SQLite. Source reopen retains terminal job
   identity/state/event. Real insert fault injection at diagnostic job and diagnostic
   outbox insertion proves whole ingress rollback and fresh retry. Provider constructors
   fail the test if called. Explicit current/foreign/cross-account bindings, all
   deterministic holds, policy/input bounds, retained-session refresh, mapping/filter
   digest behavior and source edit/stale handling are exercised.
6. `backend/tests/test_editorial_admission_migration.py`: 31 isolated SQLite cases
   preserve source/editorial/rewrite/fingerprint sentinels, check upgrade metadata,
   empty downgrade/re-upgrade, populated policy/job refusal, bounded row constraints,
   immutable/unique binding and RESTRICT history. SQLite foreign keys enabled on
   the test engine. Synthetic raw SQL timestamps use ISO strings, avoiding deprecated
   Python sqlite datetime adaptation.
7. `.github/workflows/ci.yml`: exactly one existing command-line addition:
   `tests/test_editorial_admission.py` appended to the existing migrated PostgreSQL
   vertical-slice pytest list. No permission, timeout, service or other workflow edit.

Missing-owner read tests inject only a specific `Session.get` miss while the rest
of canonical SQL resolution remains real. PostgreSQL FKs prohibit manufacturing
committed orphan rows; these tests do not claim orphan corruption was committed on PG.

## Actual TDD and verification evidence

Runtime: native Windows Python 3.12.10; SQLAlchemy 2.0.52; Alembic 1.20.0;
pytest 8.4.2; explicit Telethon 1.45.0 insertion; native Ruff 0.17.0 executable:
`D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe`.

Every pytest invocation below ran in `backend` with this actual wrapper, substituting
the listed case arguments and artifact label (not an implicit environment/PYTHONPATH):

```powershell
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/editorial-admission-<label>-cache'
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main([<case arguments>,'--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-admission-<label>-temp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-admission-<label>-pytest']))"
```

Actual native results, including unsuccessful intermediate runs:

| Label | Case arguments / purpose | Native exit and result |
| --- | --- | --- |
| red01 | admission file, `-q --maxfail=1` | 1; assertion placed in fixture produced 1 setup error; corrected before using RED evidence |
| red02 | admission file, `-q --maxfail=1` | 1; **1 failed**, absent migrated diagnostic job table assertion; no collection/import error/skip/xfail |
| green01 | admission file, `-q` | 1; 31 failed, 39 passed; test expectations incorrectly counted the existing incoming-source event and missing-read fault setup needed correction |
| green02 | admission file, `-q --tb=short` | 0; 70 passed |
| migration01 | migration file, `-q --tb=short` | 1; 1 failed, 18 passed, 38 sqlite datetime-adapter deprecations; exposed quoted false server default as SQLite text. Fixed SQL Boolean default and synthetic timestamp adaptation |
| time-red | admission file, `-q -k invalid_caller --tb=short` | 1; 1 failed, 8 passed, 70 deselected; aware year-1 offset overflow escaped validation. Fixed only time-validation overflow handling |
| green03 | admission + migration files, `-q --tb=short` | 0; 98 passed, no warnings |
| cover01 | covering files listed below, `-q --tb=short` | 0; 398 passed in 47.31s, no warnings |
| final-target | final expanded admission + migration files, `-q --tb=short` | 0; 118 passed in 32.57s, no warnings |
| full01 | full backend, `-q --tb=short` | Intentionally stopped owned PID 15104 at approximately 15% before fixing the self-review Unicode edge; process exit 1, no completed-suite claim |
| unicode-red | admission file, `-q -k invalid_unicode --tb=short` | 1; 1 failed, 87 deselected; stored surrogate ad marker caused UnicodeEncodeError hashing the mapping. Fixed only canonical hash validation to sanitized blocking |
| final02-target | final frozen admission + migration files, `-q --tb=short` | 0; **119 passed (88 + 31)** in 34.44s, no warnings |
| full02 | sole completed frozen full backend gate | **0; 2301 passed, 6 skipped** in 396.76s (0:06:36), no warnings |
| pgfix-target | amended admission file after root PG exception-class finding, `-q --tb=short` | 0; **88 passed** in 27.86s, no warnings; production/source hashes unchanged |

Root-reported actual Windows PostgreSQL final02 execution on strict fresh UUID
synthetic schemas returned **1 failed / 87 passed**, native exit 1, 60.67s. Its only
failure was the overlength OPENAI model test expecting SQLite's IntegrityError:
PostgreSQL's VARCHAR(255) rejects it earlier with DataError/StringDataRightTruncation.
The amended test explicitly expects DataError only for PostgreSQL overlength;
blank models and SQLite continue to require IntegrityError. No production code or
constraint was changed. Root owns this execution, retained log
`D:/Codex-Recovery/content-studio-20261008/editorial-admission-root-pg-20261012b.log`,
and the amended strict-PG follow-up. The full02 run continues on its already loaded
test hash E7A658A1652C0F833FD321F1394BA07DD2F57CB238A5E49A13BBDD24573F077C;
root explicitly directed targeted amended tests instead of a duplicate full gate.

Root subsequently reported the amended A17D test hash passed **88 actual Windows
PostgreSQL cases**, native exit 0, 62.03s, retained log
`D:/Codex-Recovery/content-studio-20261008/editorial-admission-root-pg-20261012c.log`.
This is root-owned execution evidence, not a PostgreSQL run by this worker.
Production hashes remained unchanged. Root separately owns retained synthetic PG
restart/double verification and exact remote CI; neither is inferred from this suite.
Root later reported the owned synthetic PG restart and two independent original-SQL
reopens passed, preserving the prior snapshot including 118 diagnostic jobs
(116 QUEUED, 2 terminal REJECT), with rewrite usage zero. The complete independent
evidence is root-owned `docs/EDITORIAL_DURABLE_ADMISSION_VERIFICATION_20261012.md`.
This worker performed no PostgreSQL restart or namespace mutation.

Covering file arguments, exactly as executed in cover01:

```text
tests/test_editorial_admission.py tests/test_editorial_admission_migration.py
tests/test_durable_ingestion_workflow.py tests/test_durable_ingestion.py
tests/test_durable_editorial.py tests/test_mapping_technical_filters.py
tests/test_hidden_donor_links.py tests/test_source_deletion_guards.py
tests/test_source_sync_guards.py tests/test_source_sync_replay.py
tests/test_mapping_fanout_dedup.py tests/test_editorial_classification.py
tests/test_editorial_classifier_adapters.py -q --tb=short
```

Completed static/native checks:

```text
ruff.exe check src tests alembic                                  exit 0
ruff.exe format --check <six changed Python paths>                exit 0
python -m compileall -q backend/src backend/tests backend/alembic  exit 0
git diff --check                                                 exit 0
```

Ruff initially reported 3 import ordering issues (corrected, then PASS). YAML was
parsed with `yaml.safe_load`; inspected the migrated PostgreSQL step's `run` command
and confirmed only the appended file. Actual parse/command inspection exit 0.
The parent Alembic heads check first invoked from repository root used an incorrect
relative script path and exited 1; rerun in backend resolved actual sole parent
`c5e81b29a704` successfully. All final migrations run inside tests passed including
`command.check`, not inferred from source inspection.

`git diff`/staging may print normal Windows LF-to-CRLF conversion notices. They are
not test warnings. No tests skipped/xfail used as evidence. No UI, Compose/recovery,
whole-PG, actual provider or publication gate was run by this worker.
The six full02 skips are existing opt-in PG checks: five planner/media concurrency
cases without NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL, and one real TRUNCATE case
requiring the strict isolated PG CI namespace. No new admission/migration test
skipped. Root separately executed all 88 new admission cases on actual PG.

Full02 exact invocation is the wrapper above with label `full02` and arguments
`'-q','--tb=short'`, piped through `Tee-Object` to
`D:/Codex-Recovery/content-studio-20261008/editorial-admission-full02.log`, followed
by `exit $LASTEXITCODE` to preserve the native pytest status.
Retained full02 log SHA256:
`DB2792CD7E0A25F6EB87104A3FC850C968A4AB596E281FB6E7795718C2337B72`.

## Final frozen content hashes (SHA256, raw file bytes)

| File | SHA256 |
| --- | --- |
| backend/src/newsflow/persistence/models.py | AD5C353133FD325997D32860D0C211816CEBA91B0E6202C88E0B3A7BB4B4724F |
| backend/src/newsflow/services/editorial_admission.py | 8328ECC822EB9DD528F28D35C7CDED4266FE12145E0D77C7856E9496BE18E58F |
| backend/src/newsflow/domain/durable_ingestion.py | 3DE4A65AE1E70BC950D24D668923782B56FA8AD08D2AA0EBB4588E894D7141A5 |
| backend/alembic/versions/d7b340a92e16_add_editorial_diagnostic_admission.py | E71E33060DEF299D644D7C1FE10C85184FC9FDC7DFF192640E49828CEC7E59F7 |
| backend/tests/test_editorial_admission.py (final PG exception-class amendment) | A17DDB1B079F4E766EEAB81226FA48A7283658DD83EE3B7BCC10254DD37D9E99 |
| backend/tests/test_editorial_admission_migration.py | 2AFEF8C0D42BDC8733A0B7EA959B806F96935F039733BA2F10E3B680CF66A5E5 |
| .github/workflows/ci.yml | 998B2FCDFF8CC24735FD13B8FE9143FE24E6E62384C7B62E1C15D41AE2715744 |

Freeze01 was invalidated before commit by the self-review Unicode RED. Root was
notified before changing source and received the final freeze02 hashes; only the
admission service and admission test hash changed. The later explicit PostgreSQL
exception-class amendment changes only the admission test, with final hash above.
Root independently owns actual
Windows PostgreSQL verification and CI tracking. This worker does not claim those
external/native PG gates as its own PASS.

## Rollback and remaining limits

- Additive upgrade leaves old rows and defaults intact; old fingerprint ownership
  stays NULL. No legacy row is adopted or backfilled, including prototype keys.
- Downgrade is explicitly refused if either new table contains even one row,
  including disabled policies and terminal jobs. Refusal happens before DDL and
  preserves version/new/old data. Prefer forward repair for populated deployments.
- Empty-table downgrade removes the fingerprint owner column and loses any owner
  evidence in that column. Only use that downgrade on an isolated copy; it is not
  a safe operational rollback for retained ingestion evidence.
- Admission uses fresh reads without taking a new lock order, but does not provide
  completed runtime TOCTOU fencing across later IO. A future executor needs
  source/policy/mapping CAS before/after real provider calls, claim/lease execution,
  usage and evidence retention, and independent real model qualification.
- No protected-entity configuration UI/API, automatic editorial PASS propagation,
  per-output rewrite activation, provider factory/transport wiring or worker changes
  are included. The queued request and synthetic tests confer none of these powers.
- Source commit is local only, restricted to the seven owned implementation/test/CI
  files plus this report. Root-owned documents are excluded; no push/merge/PR by worker.

## Original RED output provenance clarification

The excerpts below are transcribed now from the original native tool results still
present in this agent's conversation history. They are **reconstructed transcriptions,
not original standalone log files**, and were not produced by rerunning tests. The
original RED commands were executed through `functions.exec` calling
`tools.exec_command`; their results include the native `exit_code` and `chunk_id`
shown below. These synchronous commands completed without an ongoing execution
session ID. The original standalone RED logs were **not retained**: those original
outputs remain in agent tool history only. Existing report artifact labels identify
the original temporary fixture/cache paths, not retained stdout log files.

Original `red01` result: `exec_command` chunk `566bb2`, native exit 1, no session ID.
The assertion was initially inside fixture setup; this result was not used as the
required behavioral RED:

```text
E       AssertionError: Migrated storage must retain diagnostic classification requests
tests\test_editorial_admission.py:43: AssertionError
ERROR tests/test_editorial_admission.py::test_mapped_unknown_queues_one_durable_diagnostic_and_reopens_terminal_history
1 error in 0.77s
```

Original corrected `red02` result: `exec_command` chunk `11205b`, native exit 1,
no session ID. The assertion was moved into the test body before this execution:

```text
>       assert "editorial_classification_jobs" in inspect(store[0]).get_table_names(), (
            "Migrated storage must retain diagnostic classification requests"
        )
E       AssertionError: Migrated storage must retain diagnostic classification requests
tests\test_editorial_admission.py:79: AssertionError
FAILED tests/test_editorial_admission.py::test_mapped_unknown_queues_one_durable_diagnostic_and_reopens_terminal_history
1 failed in 0.79s
```

Original `migration01` result: `exec_command` chunk `97701a`, native exit 1,
no session ID. This exposed the quoted Boolean default before the correction:

```text
tests\test_editorial_admission_migration.py:104: in test_populated_downgrade_refuses_before_ddl_and_preserves_history
    assert connection.scalar(text("SELECT enabled FROM editorial_classifier_policy")) == 0
E   AssertionError: assert 'false' == 0
FAILED tests/test_editorial_admission_migration.py::test_populated_downgrade_refuses_before_ddl_and_preserves_history[policy]
1 failed, 18 passed, 38 warnings in 5.88s
```

Original `time-red` result: `exec_command` chunk `fb3ba7`, native exit 1,
no session ID:

```text
tests\test_editorial_admission.py:301: in test_invalid_caller_inputs_never_write
    assert api().enqueue_editorial_classification(session, content_key=key,
src\newsflow\services\editorial_admission.py:172: in enqueue_editorial_classification
    observed_at = now.astimezone(UTC)
E   OverflowError: date value out of range
1 failed, 8 passed, 70 deselected in 2.86s
```

Original `unicode-red` result: `exec_command` chunk `e06805`, native exit 1,
no session ID:

```text
_____ test_invalid_unicode_in_stored_filter_blocks_with_sanitized_reason ______
tests\test_editorial_admission.py:728: in test_invalid_unicode_in_stored_filter_blocks_with_sanitized_reason
    assert api().enqueue_editorial_classification(session, content_key=KEY,
src\newsflow\services\editorial_admission.py:260: in enqueue_editorial_classification
    binding = resolve_editorial_admission(
src\newsflow\services\editorial_admission.py:239: in resolve_editorial_admission
    sha256(_canonical(identity)).hexdigest(),
src\newsflow\services\editorial_admission.py:57: in _canonical
    ).encode("utf-8")
E   UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' in position 381: surrogates not allowed
FAILED tests/test_editorial_admission.py::test_invalid_unicode_in_stored_filter_blocks_with_sanitized_reason
1 failed, 87 deselected in 0.80s
```

The excerpts intentionally omit surrounding pytest decoration and intermediate
traceback lines. Line numbers are historical, as printed by those original runs;
they do not claim to identify the final formatted source. The native exit and chunk
identifiers come from the original tool-result metadata, not from pytest text.
This provenance clarification changes only this report; no source/test rerun or
source/test edit accompanies it.
