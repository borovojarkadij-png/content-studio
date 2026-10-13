# Task 3 — default-disabled Telegram engagement worker seam

Base: `810a0debc2ae9087b6bec522b0879919929fd75e`.
Branch: `codex/dark-navy-ui`.
Origin: `https://github.com/borovojarkadij-png/content-studio.git`.
Evidence: `D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task3-20261013a/`.

## Implementation and boundaries

Created the separate sampling tick service and frozen, slotted
`EngagementSamplingTickResult(outcome, cursor, queued_ids)`. Exact bool validation
precedes every other check. Disabled returns the supplied transient cursor and
empty admissions without inspecting time, cipher, provider, credentials or SQL.
Enabled requires the existing non-None stable-cipher prerequisite, normalizes
aware time with accepted `utc_timestamp`, and validates exact signed64 cursor
before credential or SQL IO. Injected providers require no credentials; the
noninjected path requires an explicit path and uses only the existing loader and
configured encrypted provider. One accepted runner admits at most16 sources and
executes one `run_next(now=clock())`; actual provider acquisition remains owned
by the runner clock. SQL jobs remain restart truth. IDLE means no acquired claim
in the bounded window, never an assertion that the queue is empty.

Worker main parses exact string0/1 `NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED`, default0;
includes sampling in its existing stable-key/cipher prerequisite; initializes a
separate transient cursor0; invokes the seam after sync/ingestion and before
editorial/rewrite when enabled and not stopped. It retains the cursor after a
successful seam return only, uses the exact existing credentials environment
name/default, and records private outcome/count or
`telegram_engagement.execution_interrupted`/`recovery=persisted_lease` without
exception text, sessions, digest, traceback or source content. Sync errors still
wait/continue, and sampling interruption still permits independent later work.

CI changes only the existing unattended PostgreSQL pytest invocation: append
`tests/test_telegram_sampling_postgres.py` once before its existing `-q`. No
previous test, order, job, environment, dependency or check changed. No Compose,
UI, API, settings, activation, session, real key or authorization changes.

## Tests and TDD evidence

All native pytest commands ran from `backend`, with this exact bootstrap:

```python
import sys
sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145')
import telethon
assert telethon.__version__ == '1.45.0'
import pytest
raise SystemExit(pytest.main(ARGS))
```

Each pytest command set both TEMP and TMP to the fresh evidence directory and
passed `-q -o junit_family=legacy`, its own numbered JUnit path and its own
`--basetemp` directory under D:. Output was retained through Tee-Object; the
immediate native LASTEXITCODE was separately saved before `exit` with that code.
No older RED/FAIL artifact was overwritten or removed.

- `01-red`: ARGS starts with `tests/test_telegram_sampling_tick.py
  tests/test_scheduler_worker.py`; JUnit `01-red.xml`, basetemp `01-temp`. Before any
  production implementation:44 failed,6 passed in3.95s, native1.
  Actual old-main behavioral RED: `test_main_invalid_engagement_flag_fails_before_cipher_or_tick`
  executed main and failed `DID NOT RAISE ValueError` (raw log line725);
  `test_main_engagement_requires_existing_stable_key` executed main and failed
  `DID NOT RAISE RuntimeError` (line743);
  `test_main_stopped_before_engagement_skips_tick` executed main and failed
  `assert [] == ['key']` (line795). These are causal absent opt-in/cipher behavior.
  Separately, new seam/parser imports failed because the implementation did not
  yet exist; those are prerequisite failures, not seam function-body causal RED.
  The initial CI assertion failed because the sampling invocation was absent.
- `02-green`: same two pytest files, JUnit `02-green.xml`, basetemp `02-temp`:
  50 passed in3.93s, native0 after implementation.
- `03-focused`: same two files, JUnit `03-focused.xml`, basetemp `03-temp`:
  54 passed in4.52s, native0 after extra integration coverage.
- `04-covering`:19 complete relevant modules, JUnit `04-covering.xml`, basetemp `04-temp`:
  909 passed,25 skipped in197.56s, native0. Exactly20 skips require the explicit
  synthetic PostgreSQL URL;4 finalizer-lock proofs and1 row-lock proof explicitly
  defer actual PostgreSQL to root. These are not accepted execution or suppressed
  failures. No warnings.
  Modules: `test_telegram_sampling_tick.py`, `test_scheduler_worker.py`,
  `test_engagement_sampling.py`, `test_telegram_sampling_migration.py`,
  `test_telegram_sampling_runner.py`, `test_telegram_sampling_postgres.py`,
  `test_telegram_engagement.py`, `test_telegram_engagement_history.py`,
  `test_telegram_hype.py`, `test_editorial_worker.py`,
  `test_durable_editorial_runner.py`, `test_editorial_history.py`,
  `test_editorial_admission.py`, `test_channel_sync_main_loop.py`,
  `test_channel_sync_tick.py`, `test_publication_main_loop.py`,
  `test_rewrite_worker_policy.py`, `test_semantic_admission_fairness.py`,
  `test_media_admission_fairness.py` (all under backend/tests).
- `09-final-focused`: same two own test modules after formatting and removing
  the brittle whole-workflow assertion per root ruling; JUnit `09-final-focused.xml`,
  basetemp `09-temp`:53 passed in4.44s, native0, pristine output.
- `14-combined-full`: the single combined full backend invocation for all three
  tasks; ARGS has no file filter, JUnit `14-combined-full.xml`, basetemp `14-temp`.
  3801 passed,76 skipped in649.92s (10:49), native0; pristine output.
  Independent JUnit parse16 confirms3877 cases/0 failures/0 errors/76 skips.
  Skip breakdown:61 explicit missing synthetic PostgreSQL URL;5 concurrency
  opt-in absent;4 root-owned PG finalizer locks;2 PG singleton locking;1 root-owned
  PG lock;1 PG row lock;1 strict PG TRUNCATE;1 policy INSERT/create-only case.
  No suppressed assertion or warning. There was exactly one full invocation,
  no source edits during it and no full retry.

Exact full-suite ARGS for the bootstrap above:

```python
ARGS = [
    '-q', '-o', 'junit_family=legacy',
    '--junitxml=D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task3-20261013a/14-combined-full.xml',
    '--basetemp=D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task3-20261013a/14-temp',
]
```

Own tests use migrated SQLite fixtures with actual admission/runner/history,
fresh tick instances, duplicate idempotence, due/future/terminal schedule,
FloodWait restart/no early fetch, stale clock/no fetch, bounded16/oneRPC with no
checked-out connection during provider callback, SQL-finalization interruption
and expired-lease recovery, and current deletion/sync/mapping/health/cooldown
quarantine. Main-loop tests cover strict flags/default off, stable-key
prerequisite, stop fencing, default/explicit credentials path, shared cipher,
cursor success/failure retention, private exception logs, ordering and continued
independent work, sync error/continue preservation, and an actual SQL-backed
sample with every other opt-in disabled. The migrated fixtures automatically
assert REJECT/rewritefalse, unchanged source/revision and zero downstream jobs;
rewrite-provider tripwires remain active. Public deterministic synthetic key,
fake provider and synthetic api_id123/hash'a'*32 only; no real credentials read.

## Static verification

Ruff executable throughout:
`D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe`.

- `05-ruff-initial`: check own four Python files:All checks passed/native0.
- `06-ci-static`: first evidence-only YAML traversal failed KeyError'name' on an
  unnamed uses step, native1; retained. Product/config files unchanged by command.
- `07-ci-static-corrected`: safe YAML parse plus exact BASE comparison using
  `step.get('name')`, native0. Assert current workflow equals BASE with exactly
  the single expected line replacement; sampling test occurrence1; parsed
  unattended-postgres selected step ends with prior Hype PG, appended sampling
  PG, then-q. All prior checks/order preserved. Whole-workflow baseline assertion
  was removed from permanent runtime tests per root ruling, so later unrelated
  legitimate CI edits will not break these tests.
- `08-format`: format own four Python files:3 reformatted,1 unchanged/native0.
- `10-final-ruff`: `ruff check src tests alembic --cache-dir <evidence>/ruff-cache`:
  All checks passed/native0.
- `11-final-format`: `ruff format --check` own four Python files:
  4 files already formatted/native0.
- `12-compile`: `python -m compileall -q src tests` with PYTHONPYCACHEPREFIX under
  `<evidence>/compile-cache`:native0.
- `git diff --check` own modified tracked files:0; only Git CRLF notices.

## Frozen source and self-review

`13-frozen-source-hashes.json` retained before the full invocation. HEAD810a0de,
no source or HEAD mutation during full; post-completion15-freeze-verified.log
confirms5/5 hash match and unchanged HEAD.16-full-junit-summary.log/native0
records the independent complete JUnit parse and explicit skip reasons.

| Source | SHA256 |
| --- | --- |
| backend/src/newsflow/services/telegram_engagement_tick.py | 9AF05F32E812664546F4E8734B29B0E35B4E4A72C2F39DE4BADDEE55AF3EB0EE |
| backend/src/newsflow/worker.py | 2E6C53FEAF804477C80E3F25F947E9F410BFCA927A8B6BBAF4B66A14BEF16FA0 |
| backend/tests/test_telegram_sampling_tick.py | B48084F9C0C0C3EED0D856EF23A3AB5A5F98789265C1D47F83A600AA8536D1FD |
| backend/tests/test_scheduler_worker.py | 0C567384DA41785D0A4A0E8C08335C2A834A4BE30D9EFAD547FE971ACF1F4D88 |
| .github/workflows/ci.yml | 9346EB70EDC8CFF414BAC516D8F7DEC5C5B12C33351E2D3AB60C1DF41FF364D8 |

Read own final source/diff against brief and current accepted interfaces.
Changes are exactly the five owned source files plus this report. Existing
worker is large; edits remain a localized parser/import/prerequisite/cursor/
bounded private tick block, without restructuring other work. Self-review found
the initial whole-workflow runtime test brittle; root confirmed moving its exact
validation into retained static evidence. No unresolved implementation issue.
Root-owned dirty progress/current-state/verification documents are preserved
and excluded from this commit. No subagents, push, PR, merge, reset, prune,
production data, real Telegram IO, paid AI or publication action.

Actual PostgreSQL Task1/2 acceptance was already completed independently by
root (20 passed/0 skipped/native0) and was not repeated here; root explicitly
confirmed no repeat PostgreSQL gate. Independent source review, packaged
synthetic restart/three actual synthetic container starts, exact-generation CI
and cross-task integration remain root-owned subsequent gates.
No live/PHASE completion claim.
