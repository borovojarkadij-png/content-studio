# Task 1 — retained Telegram intake comparison schema

Status: DONE. Four product/test paths changed, plus this report. No caller,
repository, ingress, provider, publication, CI or operational storage activation.
Root's independent review and single native PostgreSQL gate remain separate.

## Starting state and scope

- Repository: `C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2`.
- Branch: `codex/dark-navy-ui`.
- Starting HEAD: `8fc3c9def7d3b2f09e6b8f40c362fa0daf4e91f7`; initial status clean.
- Single initial Alembic head: `b8c34d26e190`; final single head: `c9d45e37f201`.
- Read the complete task brief, complete design (including transactional/later
  boundary constraints), implementer instructions, TDD/writing-good-tests,
  NewsFlow migrations/recovery, and verification-before-completion guidance.
- Models change is strictly an append of two classes (175 lines), with no
  unrelated existing model edits. New migration is standalone and imports no
  mutable application model definitions.
- Root approved signed64 physical types: BigInteger with SQLite Integer variant
  for ledger IDs and sequences; existing Integer mapping FK retained.
- Root owns all other documentation/CI/evidence edits visible in the shared
  working tree; none is included in this commit.

## Implemented behavior

Added `TelegramIntakeSelectionStreamModel` and
`TelegramIntakeSelectionWindowModel`, their exact unique identities, RESTRICT
FKs, bounded integer/digest/payload/time storage checks, SQLite type/ASCII/NUL
checks, and PostgreSQL payload byte checks. Matching metadata constraints use
`ddl_if` for dialect-specific SQL. The digest check portably removes every
allowed lowercase hex character and requires an empty remainder plus length64.

Migration `c9d45e37f201` installs initial carry0/sequence1 admission, missing
mapping/stream and duplicate/replacement guards, stream identity/policy/time
immutability, exact window/carry/sequence-linked advancement, unconditional
window update/no-op/delete refusal, and stream delete refusal. PostgreSQL
admission locks the mapping or stream before checking state. PostgreSQL
BEFORE TRUNCATE checks both ledger tables, including CASCADE from parents.

Downgrade acquires the specified PostgreSQL mapping→streams→windows lock, or
SQLite zero-row write lock, then checks both counts before any owned DDL.
Retained stream-only and stream/window history refuse downgrade with exact
rows, tables and head intact. Empty downgrade removes only owned tables and
PostgreSQL functions; empty re-upgrade and Alembic checks pass.

Synthetic fixtures create account/donor/output/mapping and a pre-upgrade source
revision plus REJECT/false editorial decision. Each fixture asserts unchanged
source text and REJECT/false decision, zero rewrite_jobs/rewrite_usage/
outbox_events, and forbids OpenAI/OpenRouter rewrite methods. No real URL
fallback, user data, provider credentials, paid call or operational namespace
was used. Native PostgreSQL tests use the existing create-only UUID namespace
helper and retain those namespaces for the later root gate.

Schema tests deliberately permit bounded ASCII text without proving JSON
semantics; canonical JSON, hash/result consistency and kernel recomputation
are Task 2 repository responsibilities.

## Retained TDD and compatibility evidence

All pytest commands below ran from the repository's `backend` directory.
Each set TEMP/TMP to the D recovery location, inserted the Telethon1.45 overlay
at sys.path0 before importing pytest, and asserted the actual `1.45.0` version.
Distinct D basetemp directories preserve failure stores separately.

### Discovery RED, before any declaration or migration

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger_migration.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task1-discovery']))"
```

Native exit1: `1 failed in 0.70s`. The test collected and migrated successfully;
`assert inspect(engine).has_table(STREAMS)` failed with False. This is discovery
evidence only, not the behavioral guard RED.

### Actual raw SQL guard RED, after declarations/checks but before guards

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger_migration.py','-q','-k','migration_exposes or window_raw_update or cannot_advance_without','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task1-guards-red']))"
```

Native exit1: `2 failed, 1 passed, 103 deselected in 1.33s`.

Both failures were `DID NOT RAISE sqlalchemy.exc.DBAPIError`, after valid rows
had actually been inserted into migrated tables:

```sql
UPDATE telegram_intake_selection_windows SET carry_out=99;
UPDATE telegram_intake_selection_streams SET carry=30,next_sequence=2;
```

The first illegally changed an otherwise row-valid window; the second advanced
without any corresponding window. Table discovery passed independently.

Full pre-guard behavior run:

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger_migration.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task1-all-red']))"
```

Native exit1: `34 failed, 67 passed, 5 skipped in 29.02s`. Expected failing
families: missing parents, noninitial stream state, mismatched window state,
stream immutable identity/policy/time changes, invalid advancement, all window
updates/no-ops/deletes, stream delete, primary/unique replacement erasure,
populated downgrade, and missing empty-downgrade serialization. Five explicit
PostgreSQL skips required NEWSFLOW_UNATTENDED_POSTGRES_URL; none counted as PASS.

### First guard GREEN

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger_migration.py','-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task1-green']))"
```

Native exit0: `101 passed, 5 skipped in 29.78s`. The same five native PostgreSQL
cases skipped honestly because no explicit synthetic URL was supplied.

### Actual SQLite sampling version behavior and controller ruling

Original, unmodified SQLite sampling assertion:

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_telegram_sampling_migration.py::test_populated_downgrade_refuses_before_ddl_and_preserves_exact_rows_version','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task1-existing-head-red']))"
```

Native exit0: `1 passed in 0.53s`. Despite the historical directory suffix,
this was PASS, not RED. No old-head failure was observed for the unmodified
SQLite test.

Temporarily replacing its old-head literal with exact before/after capture:

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_telegram_sampling_migration.py::test_populated_downgrade_refuses_before_ddl_and_preserves_exact_rows_version','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task1-retained-version-red']))"
```

Native exit1: `1 failed in 0.79s`; exact failure:

```text
AssertionError: assert 'b8c34d26e190' == 'c9d45e37f201'
```

Local Alembic begin_transaction/run_migrations source inspection confirmed
nontransactional-DDL SQLite begins/commits per migration. Empty ledger downgrade
therefore succeeds and commits b8 before sampling refuses its own populated
downgrade. This is different from transactional PostgreSQL. Root explicitly
ruled to restore the SQLite file unchanged, keep PostgreSQL before-version
capture, and add no downstream sampling preflight or env.py change. Root
updated the brief/design to state that arbitrary multi-revision SQLite chain
atomicity is not promised. `git diff --exit-code --
backend/tests/test_telegram_sampling_migration.py` returned native exit0.
Existing source/job/state safety assertions are preserved.

## Final covering run

Added NULL digest cases, pending-window primary/unique replacement cases,
new-versus-missing-parent REPLACE behavior, and additional optional native
PostgreSQL checks before this final covering run.

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger_migration.py','tests/test_telegram_sampling_migration.py','tests/test_telegram_sampling_postgres.py','tests/test_configuration_migration.py','tests/test_runtime_migrations.py','-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task1-final']))"
```

Native exit0: `219 passed, 27 skipped in 63.40s (0:01:03)`. No failures or
warnings. All 27 skips explicitly require the synthetic PostgreSQL URL:
7 new ledger PostgreSQL cases and 20 existing sampling PostgreSQL cases.
No native PostgreSQL service, container, volume, Windows packaging/resource
probe or giant backend suite was started/repeated by this writer.

The run includes actual SQLite upgrade/reopen/empty downgrade/re-upgrade,
`command.check(config)` before and after the roundtrip, existing runtime
metadata drift checks, populated downgrade retention and the concurrent
zero-timeout SQLite writer blocked between count and DDL.

## Static validation and native exit status

Commands below ran from the repository root unless noted.

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' --version
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check backend/src/newsflow/persistence/models.py backend/alembic/versions/c9d45e37f201_add_telegram_intake_selection_ledger.py backend/tests/test_intake_selection_ledger_migration.py backend/tests/test_telegram_sampling_postgres.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check backend/src/newsflow/persistence/models.py backend/alembic/versions/c9d45e37f201_add_telegram_intake_selection_ledger.py backend/tests/test_intake_selection_ledger_migration.py backend/tests/test_telegram_sampling_postgres.py
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/intake-task1-pycache'; python -m py_compile backend/src/newsflow/persistence/models.py backend/alembic/versions/c9d45e37f201_add_telegram_intake_selection_ledger.py backend/tests/test_intake_selection_ledger_migration.py backend/tests/test_telegram_sampling_postgres.py
git diff --check
git diff --exit-code -- backend/tests/test_telegram_sampling_migration.py
```

Ruff0.17.0 confirmed. Separate final Ruff check native exit0 (`All checks
passed!`), format-check native exit0 (`4 files already formatted`), compile
native exit0, diff-check native exit0, unchanged SQLite file native exit0.
Git emitted only CRLF normalization notices on changed text files.

Earlier formatting commands used the same Ruff binary and `format` over the
three new/extended files, then over all five originally named files; all
returned native exit0. The first combined lint shell printed six findings
(four ISC004 string-parenthesis and two C408 dict literal issues) but its last
git command returned0, so that compound-shell exit was not treated as lint
success. Findings were corrected with apply_patch. Subsequent standalone
checks returned native exit0, including the final command above.

Single-head inspection, from backend, native exit0 before and after:

```powershell
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"
```

Before `['b8c34d26e190']`; after `['c9d45e37f201']`.

## Self-review and frozen source hashes

Read the complete migration, appended model classes, new tests and changed PG
assertion. Confirmed portable constraints match metadata; guards belong only
to the two new tables; no JSON algorithm assertions; no parent IDs altered;
no existing business rows backfilled; insert and advancement ordering valid;
nonempty downgrade checks both tables before DDL; SQLite write serialization
is behavioral; no helper/reviewer/subagent was dispatched.

SHA256 from Get-FileHash after final source edits/static validation:

| Source | SHA256 |
| --- | --- |
| backend/src/newsflow/persistence/models.py | A78C0976DD03AE92E10CA793B4583150DBF89779FEAB821E893324B2FC87C2AF |
| backend/alembic/versions/c9d45e37f201_add_telegram_intake_selection_ledger.py | A9EECE839D3A836976F12C9EDCA3512CEBF6CF2ECC0F07BEF1594CABF6FE3A24 |
| backend/tests/test_intake_selection_ledger_migration.py | A365D278A6F30E87BB34B042D57B8A4F5D98681AC32CB4C53D78F9E16C1D24D3 |
| backend/tests/test_telegram_sampling_postgres.py | 7DE93D833A7CA8C7F2D4B71AA1473DF259463081D36655621186F50BD8225DA9 |

The report itself is excluded from a recursive self-hash. Commit includes
only these four source paths and this exact force-added report path.

## Limits and handoff

- Seven new PostgreSQL cases are collected but not executed by this writer;
  root must perform the single agreed native PostgreSQL gate after both scoped
  reviews. They cover signed64 IDs, empty roundtrip/check, initial/storage
  guards, exact carry advancement, retained downgrade and direct/parent
  CASCADE truncate refusal. Existing PG version capture is also pending that
  native gate; no claim of PG runtime PASS is made here.
- PostgreSQL concurrency/repository semantics and installed Docker reopen
  smoke belong to later tasks/root gates. No substitute mocked PG proof.
- Existing models.py is large; the append avoids restructuring its unrelated
  1382-line prefix. New migration/test files stay within their assigned scope.
- Future repository must enforce canonical bounded JSON, recompute kernel
  results, validate UTC-aware application timestamps, and preserve all later
  source/editorial/publication permission boundaries.
- SQLite multi-revision downgrade limitation is documented above and accepted
  by root; the new migration's own history-retention guarantee is verified.
