# Task 1 — retained sampling schema and pure schedule

Status: DONE. Base checkpoint f0ff9336b718cdee1b22594d77233316bf5bd712.
Only the five task-owned source/test files and this report are committed.
No push, operational database, credentials, provider, network sampling, worker,
queue, volume, UI, or external authorization was changed.

## Implemented

- Added TelegramEngagementSamplingJobModel and additive revision b8c34d26e190,
  down_revision a7e239bc5180, table telegram_engagement_sampling_jobs.
- Named checks enforce exact SQLite integer types, bounded counters/positive
  identities, private error codes, complete state/claim coherence, canonical UUID
  and lowercase64hex digest text, valid fixed26-character UTC SQLite timestamps,
  supported PostgreSQL timestamp/integer types and regex equivalents.
- available_at>=created_at and lease_expires_at>available_at follow the root's
  explicit clarification. Fixed26-character ASCII UTC SQLite dates preserve actual
  timestamp ordering; PostgreSQL compares timestamptz values. Exact lease duration
  remains runner-owned. created_at is explicitly required; SQLite CURRENT_TIMESTAMP
  would produce a19-character value incompatible with strict restoration.
- Initial INSERT requires fresh QUEUED/step0/attempts0/missed0 and an existing
  incoming source. Transition triggers retain association/creation time, monotonic
  step/missed counters, nondecreasing attempts unless advancing, allowed state
  transitions, and immutable terminal rows. DELETE/REPLACE are refused. Incoming
  identity/creation time/DELETE/REPLACE are retained even without SQLite FKs.
- PostgreSQL admission locks incoming before insertion, serializing creation-time
  mutation as well as FK identity; retained jobs and incoming parents refuse
  TRUNCATE. Empty downgrade locks before count/drop; populated downgrade refuses
  before DDL and preserves exact rows/version. No old source/history trigger changed.
- Frozen SamplingAdvance and clock-free advance_sampling implement exact
  60/300/600/1200/1800/3600-second thresholds, current scheduled-step fulfillment,
  later-window skip accumulation, completion step7/available_at=observed_at,
  aware UTC normalization and bounded validation. Per root ruling, an acquisition
  before its own scheduled threshold fails, accumulated missed>6 fails without
  clamping, and step7 is output-only. Datetime/schedule overflow fails closed.

## Commands, TDD and raw evidence

Fresh evidence directory:
`D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task1-20261013a`.
All logs below remain there, including native failing output; none was overwritten.

All runtime pytest commands used backend working directory and this exact bootstrap
before pytest import (no machine paths were added to product or tests):

```powershell
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task1-20261013a/pycache'
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(ARGS))" *> LOG
$native=$LASTEXITCODE
Get-Content LOG -Tail 45
Write-Output "Native exit: $native"
exit $native
```

The original red bootstrap additionally included `telethon.__version__` as the
assertion diagnostic. ARGS/LOG below describe each exact invocation; temporary
and cache paths were explicit fresh directories under the evidence directory,
named `<run>-temp` and `<run>-cache` respectively. Common options:
`--basetemp=<evidence>/<run>-temp -o cache_dir=<evidence>/<run>-cache`.

| Run / log | pytest arguments before common options | Native exit / result |
| --- | --- | --- |
| red / red.log | -q tests/test_engagement_sampling.py tests/test_telegram_sampling_migration.py | 1;2 failed |
| expanded-red / expanded-red.log | same files | 1;139 failed,2 passed |
| green1 / green1.log | same files | 0;141 passed |
| blob-red / blob-red.log | -q tests/test_telegram_sampling_migration.py -k BLOB | 1;1 failed,2 passed,83 deselected |
| time-red / time-red.log | -q tests/test_telegram_sampling_migration.py -k '2029 or lease_expires_at' | 1;3 failed,4 passed,82 deselected |
| cover1 / cover1.log | -q tests/test_engagement_sampling.py tests/test_telegram_sampling_migration.py tests/test_telegram_engagement_history.py tests/test_runtime_migrations.py tests/test_telegram_engagement.py tests/test_engagement_rates.py | 0;317 passed |
| nul-red / nul-red.log | -q tests/test_telegram_sampling_migration.py -k hidden | 1;3 failed,89 deselected |
| final / final.log | covering arguments plus tests/test_source_deletion_migration.py tests/test_source_observation_migration.py | 0;322 passed,0 skipped |

Final also included
`--junitxml=D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task1-20261013a/final-junit.xml`.
JUnit confirms322tests,0failures,0errors,0skips. New tests:61 pure schedule,
92 migrated SQLite. Existing coverage:75history,56provider contract,32rates,
4runtime migration and2source migration. No full backend suite was run.

Initial causal RED used behavior-free schedule and migrated table scaffolds:
the hand-derived discovery-age60 assertion reached advance_sampling's body and
raised NotImplementedError; the actual migrated raw UPDATE SET state='INVALID'
executed and failed `DID NOT RAISE DBAPIError`. Expanded RED preceded guard
implementation and exposed absent guards/retention/schedule behavior. Expected
values use literal hand-derived thresholds, never the implementation's constants.

Further causal REDs reproduced a SQLite digest BLOB bypass, backward available/equal
or backward lease times, and NUL suffixes accepted by SQLite length/GLOB semantics.
Corrections added explicit text guards, root-approved ordering, and byte lengths
equal to the canonical ASCII text lengths. The final scoped run covers every RED
without weakening assertions or changing historical fixtures.

Static commands from repository root, with the five owned paths explicitly listed:

```powershell
D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format backend/src/newsflow/persistence/models.py backend/src/newsflow/domain/engagement_sampling.py backend/alembic/versions/b8c34d26e190_add_telegram_engagement_sampling.py backend/tests/test_engagement_sampling.py backend/tests/test_telegram_sampling_migration.py
D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check backend/src/newsflow/persistence/models.py backend/src/newsflow/domain/engagement_sampling.py backend/alembic/versions/b8c34d26e190_add_telegram_engagement_sampling.py backend/tests/test_engagement_sampling.py backend/tests/test_telegram_sampling_migration.py
D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check backend/src/newsflow/persistence/models.py backend/src/newsflow/domain/engagement_sampling.py backend/alembic/versions/b8c34d26e190_add_telegram_engagement_sampling.py backend/tests/test_engagement_sampling.py backend/tests/test_telegram_sampling_migration.py
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task1-20261013a/compile-cache'
python -m compileall -q backend/src/newsflow/persistence/models.py backend/src/newsflow/domain/engagement_sampling.py backend/alembic/versions/b8c34d26e190_add_telegram_engagement_sampling.py backend/tests/test_engagement_sampling.py backend/tests/test_telegram_sampling_migration.py
git diff --check -- backend/src/newsflow/persistence/models.py
```

Native exits0 throughout. format.log:5reformatted; format2.log:5unchanged;
ruff.log/ruff2.log:all checks passed; format-check.log:5already formatted;
compile.log:empty successful output. `ruff --version` confirmed0.17.0. Alembic
upgrade/downgrade/upgrade and `command.check` executed in actual migrated tests;
populated refusal and a second connection blocked between count/drop were exercised.

Read-only diagnostic correction record: one PowerShell diagnostic used an rg
wildcard literal path and Get-Content -Raw with -Tail together, native1; corrected
with `rg --files backend/alembic/versions | rg f6a42` and Get-Content -Tail.
Later final-log inspection combined Get-Process python after pytest had exited;
Get-Process reported no process/native1. The completed pytest session then returned
native0 and322passed. Mixed PowerShell table objects hid grouped JUnit counts;
ConvertTo-Json showed all eight counts above. These diagnostics changed no files
or tests and are not counted as verification failures or success evidence.

## Self-review and boundaries

Read the full five-file implementation/diff and updated root specification.
Verified the old models have no behavioral edit, source/history migrations are
unchanged, no task-owned machine paths or provider IO appeared, every terminal
UPDATE including a no-op refuses, replacement cannot rebind canonical identity,
new QUEUED rows contain no session/claim data, and pure arithmetic has no hidden
clock/SQL/provider dependency. Migration tests retain unchanged synthetic source,
REJECT/rewrite_allowed=false, zero RewriteJob/usage/outbox rows and rewrite-provider
tripwires. No source/history guard or fixture was weakened.

No outstanding implementation concern. Actual PostgreSQL execution and packaged
restart/full backend/CI acceptance belong to the root after later tasks and fresh
review; Task1's SQLite/static evidence does not claim those gates or live readiness.

## Frozen five-file SHA256

| Path | SHA256 |
| --- | --- |
| backend/src/newsflow/persistence/models.py | 68B552292537C0BEFC66DB251F93828E23E5349B10AD06EEB36B3C7D7D46FB32 |
| backend/src/newsflow/domain/engagement_sampling.py | C0561554E64A06AE0E51007AD2CAF100FCFE0F8854622DFD5A5C3E7BC6779E6E |
| backend/alembic/versions/b8c34d26e190_add_telegram_engagement_sampling.py | 9578DBB3C046F90926EF586F4BB5DF2F62A4182C0F1C55D4418E96265F23FEF8 |
| backend/tests/test_engagement_sampling.py | AF18E088DC4CB59884B6DDD0F512B077C0EB0A5D36E5FE158EF9F24396B9E71C |
| backend/tests/test_telegram_sampling_migration.py | 38D6BBA4DAAFD39970470CAC77F297290281D3C301F7B00AC8CD09073D40B977 |
