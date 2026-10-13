# Task 2 — bounded transactional intake comparison ledger

Status: DONE. Final focused and covering checkpoints pass; native PostgreSQL,
installed-package reopen and full backend verification remain root-owned gates.

## Scope and implementation

Started at `c4bd05c32b08c9bde57b21395d801ca3eb7eaefe` on
`codex/dark-navy-ui`, in
`C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2`.
The root's documentation edits were already present in the shared worktree;
they are not this writer's changes and are excluded from this commit. The
correct origin is `https://github.com/borovojarkadij-png/content-studio.git`;
the other named remote was observed but not used. No push by this writer.

Read the complete Task 2 brief, binding design, actual Task 1 models/migration,
Task 1 report and Approved/no-findings review, implementer prompt,
test-driven-development with writing-good-tests, NewsFlow data migrations and
recovery, and verification-before-completion instructions. No helper agent,
subagent or reviewer was dispatched.

The four owned product/test/workflow paths are:

- `backend/src/newsflow/services/intake_selection_ledger.py`
- `backend/tests/test_intake_selection_ledger.py`
- `backend/tests/test_intake_selection_ledger_postgres.py`
- `.github/workflows/ci.yml`

The only additional owned path is this report. Task 1 source is unchanged.

Implemented the exact frozen `RecordedIntakeWindow`, conflict/corrupt exception
types and repository API. The repository requires an explicit active clean
caller transaction; an autobegun SELECT transaction is rejected by checking
`SessionTransaction.origin`, as are pending, dirty, deleted and inactive states.
It never begins, commits or rolls back the caller's transaction. A caller may
flush its own work and reuse that clean explicit transaction.

Arguments and tampered frozen dataclasses are validated through the accepted
public kernel before SQL. Canonical ASCII policy/input/result evidence is
bounded before parsing or storage; JSON decoding rejects duplicate keys,
nonfinite values, wrong/missing/excess keys, invalid exact types, noncanonical
numbers/order/serialization and excessive or duplicate candidate identities.
Every loaded result is recomputed with its original carry; canonical output,
all counters, selected IDs, per-candidate reasons, version, digest, policy and
carry must match. Stored output is never a trusted result constructor.

Recording locks mapping then stream with `populate_existing`, verifies initial
state or exactly the preceding sequence window, and rejects corrupted evidence
without repair/default/reset. Initial streams must have no retained windows;
this is a bounded indexed existence query, not a history traversal. New windows
flush before the single stream carry/sequence advancement; caller rollback or
failure before advancement leaves neither partial history nor carry changes.
SQLite contention and unrelated native IntegrityError propagate unchanged for
the caller to handle. Exhausted signed64 sequence refuses before insertion.

Replay uses the original carry even after later commits, preserves the original
IDs/sequence/result, and writes nothing. Reordering and int/float equivalents
replay; changed inputs or settings under the retained binding conflict. A
distinct binding may create a distinct stream.

Load uses one outer-join SELECT for a coherent stream/window snapshot under
SQLite legacy transaction control and PostgreSQL READ COMMITTED. This prevents
mixing the stream before a competing commit with the window after it. It reads
at most one stream and one window and never writes. Recording query counts are
tested against the required <=12 first-creation and <=10 existing-stream limits
at 1000 candidates; load is tested against <=2 and all-SELECT statements. There
is no per-candidate SQL, history scan, external IO, Hype/provider computation or
ingestion activation.

CI changes exactly one `run` scalar: appends the migration and native PG test
modules to the existing unattended-postgres pytest command. Parsed YAML
comparison to the starting commit proves all existing modules and every other
workflow setting are retained.

## TDD and intermediate commands

All pytest commands below ran from `backend` using Python 3.12.10. Every command
sets TEMP/TMP to D recovery storage, prepends the Telethon overlay before pytest
import, and asserts actual Telethon version `1.45.0`. Distinct basetemp roots
retain separate synthetic stores. No native PostgreSQL URL was supplied.

### Importability RED

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-discovery']))"
```

Native exit1: `1 error in 0.48s`, expected ModuleNotFoundError for the missing
repository module. This is importability evidence, not behavioral evidence.

### Literal migrated behavior RED against minimal declarations

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-behavior-red']))"
```

Native exit1: `1 failed in 0.74s`. The synthetic migrated account/donor/output/
mapping and retained REJECT fixture collected successfully. The literal
`selected_ids == (10,9,8,7,3)`, sequence1/nonreplay recording invocation failed
at the minimal declaration's NotImplementedError, before any implementation.
The declarations did not fabricate a result or fake successful persistence.

### Complete preimplementation contract RED

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','tests/test_intake_selection_ledger_postgres.py','-q','-rs','--tb=line','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-contracts-red']))"
```

Native exit1: `53 failed, 9 skipped, 58 errors in 19.22s`. Recording cases failed
at NotImplementedError; load cases had the missing method; corruption setup
could not record its initial evidence. Nine explicit native PG skips were not
passes. Oversized default parameter IDs caused extremely large diagnostic
output, which the tool truncated; short explicit IDs now keep diagnostics and
Windows fixture paths bounded. This batch is supplementary missing-feature
evidence, not a claim that all corruption cases reached their assertions.

### Initial implementation and fixture correction

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','-q','-x','--tb=short','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-first-green']))"
```

Native exit1: `58 passed, 2 errors in 15.64s`. This was not GREEN: oversized
parameter identifiers produced fixture errors and output truncation before the
oversized-payload cases completed. Short explicit IDs were added; production
logic was unchanged for this fixture correction.

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','tests/test_intake_selection_ledger_postgres.py','-q','-rs','--tb=short','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-second-green']))"
```

Native exit0: `107 passed, 9 skipped in 19.68s`, no warnings. The nine PG skips
still required the explicit synthetic URL.

### Coherent load regression RED/GREEN

Self-review found that the first implementation's separate stream/window reads
could mix two commits. A real second SQLite connection appends the requested
window between those reads; this produced a false corruption exception.

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','-q','-k','different_commits or literal_bytes or writer_contention or integrity_error','--tb=short','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-coherent-load-red']))"
```

Native exit1: `1 failed, 3 passed, 107 deselected in 1.74s`. Exact failing
reason: `Window sequence linkage mismatch`, wrapped as IntakeLedgerCorrupt.
The other three checks proved literal canonical bytes, actual SQLite lock
contention propagation, and preservation of an unrelated native IntegrityError.

Replaced load's two SELECTs with the coherent outer join:

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','-q','-k','different_commits or literal_bytes or writer_contention or integrity_error','--tb=short','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-coherent-load-green']))"
```

Native exit0: `4 passed, 107 deselected in 1.54s`.

### Initial-history corruption regression RED/GREEN

An isolated corrupt store with next_sequence1/carry0 but only a sequence2
retained window must fail closed. Checking only sequence1 missed this state.

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','-q','-k','noninitial_retained or time_boundaries or conversion_overflow or unsupported_dialect or each_decision','--tb=short','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-initial-history-red']))"
```

Native exit1: `1 failed, 9 passed, 111 deselected in 2.62s`; exact expected
failure was `DID NOT RAISE IntakeLedgerCorrupt`. Replaced the initial check with
a bounded indexed existence query for any window of that stream.

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','-q','-k','noninitial_retained or time_boundaries or conversion_overflow or unsupported_dialect or each_decision','--tb=short','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-initial-history-green']))"
```

Native exit0: `10 passed, 111 deselected in 2.36s`.

## Final focused and covering checkpoints

Source was frozen before these final runs. No product/test/workflow change was
made after them. No writer full backend run was released or executed.

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_intake_selection_ledger.py','tests/test_intake_selection_ledger_postgres.py','tests/test_intake_selection.py','tests/test_intake_selection_ledger_migration.py','-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-final-focused']))"
```

Native exit0: `360 passed, 17 skipped in 55.61s`. No failures or warnings.
Seventeen explicit skips comprise ten new native PG repository cases and
seven existing Task 1 native PG migration cases. Missing URL is SKIP, not PASS.

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'; $env:TMP=$env:TEMP; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; sys.exit(pytest.main(['tests/test_durable_ingestion.py','tests/test_durable_ingestion_workflow.py','tests/test_durable_editorial.py','tests/test_durable_editorial_runner.py','tests/test_editorial_admission.py','tests/test_editorial_admission_migration.py','tests/test_editorial_history.py','tests/test_editorial_policy_configuration.py','tests/test_editorial_policy_api.py','tests/test_persisted_mapping_filters.py','tests/test_mapping_technical_filters.py','tests/test_mapping_filter_migration.py','tests/test_mapping_fanout_dedup.py','tests/test_hidden_donor_links.py','tests/test_inbox_technical_holds.py','tests/test_engagement_sampling.py','tests/test_telegram_sampling_runner.py','tests/test_telegram_sampling_tick.py','tests/test_telegram_sampling_migration.py','tests/test_telegram_sampling_postgres.py','tests/test_hype.py','tests/test_telegram_hype.py','tests/test_telegram_hype_postgres.py','-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/intake-task2-final-covering']))"
```

Native exit0: `1014 passed, 33 skipped in 242.31s (0:04:02)`. No failures or
warnings. The explicit skips are five root-owned strict native PG editorial
runner cases, three strict opt-in native PG editorial policy cases, twenty
native PG sampling cases, four native PG Hype cases, and one existing policy
INSERT/create-only applicability case. None is claimed as PASS.

The writer turn was interrupted after the run had reached96 percent. On resume,
the original execution session `83515` returned its retained completion and
native exit0 through `write_stdin`; no covering rerun was needed or executed.
HEAD remained `c4bd05c`, and all four source hashes still matched the frozen
values. Root's documentation edits remained separate and unstaged.

## Static checks and source freeze

Commands from repository root; each native exit was checked independently.

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' --version
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check backend/src/newsflow/services/intake_selection_ledger.py backend/tests/test_intake_selection_ledger.py backend/tests/test_intake_selection_ledger_postgres.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check backend/src/newsflow/services/intake_selection_ledger.py backend/tests/test_intake_selection_ledger.py backend/tests/test_intake_selection_ledger_postgres.py
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/intake-task2-pycache'; python -m py_compile backend/src/newsflow/services/intake_selection_ledger.py backend/tests/test_intake_selection_ledger.py backend/tests/test_intake_selection_ledger_postgres.py
git diff --check
git diff --exit-code -- backend/src/newsflow/persistence/models.py backend/alembic/versions/c9d45e37f201_add_telegram_intake_selection_ledger.py backend/tests/test_intake_selection_ledger_migration.py backend/tests/test_telegram_sampling_postgres.py
```

Ruff `0.17.0` confirmed, native exit0. Final lint native exit0 (`All checks
passed!`), format-check native exit0 (`3 files already formatted`), compile
native exit0, standalone diff-check native exit0, Task 1 unchanged native exit0.
Only expected Git CRLF normalization notices occurred. Earlier first lint
returned native exit1 for a single I001 alias-import layout finding, corrected
with apply_patch; all subsequent lint invocations returned0. Ruff format ran
three times with the same three paths: native exit0 with `3 files reformatted`,
then `2 files reformatted, 1 file left unchanged`, then `1 file reformatted,
2 files left unchanged`. These were before the frozen final tests.

YAML semantic preservation command, native exit0:

```powershell
python -c "import pathlib, subprocess, yaml; p=pathlib.Path('.github/workflows/ci.yml'); old=subprocess.check_output(['git','show','c4bd05c:.github/workflows/ci.yml'],text=True); new=p.read_text(); a=yaml.safe_load(old); b=yaml.safe_load(new); prior=a['jobs']['unattended-postgres']['steps'][3]['run']; current=b['jobs']['unattended-postgres']['steps'][3]['run']; added=' tests/test_intake_selection_ledger_migration.py tests/test_intake_selection_ledger_postgres.py'; assert current==prior.removesuffix(' -q')+added+' -q'; b['jobs']['unattended-postgres']['steps'][3]['run']=prior; assert a==b; print('YAML parsed; only two required modules appended; all previous modules and workflow settings retained')"
```

Output: `YAML parsed; only two required modules appended; all previous modules
and workflow settings retained`.

Frozen SHA256 from Get-FileHash, before final covering results/report/commit:

| Owned source | SHA256 |
| --- | --- |
| backend/src/newsflow/services/intake_selection_ledger.py | C86AD8A671941B0D2C93B2684D73E1B93E8A851DCEFD7342CE1020E635F2E9FE |
| backend/tests/test_intake_selection_ledger.py | 1FCD54E7A7B453A5C4CE86BE144A2DCF56FE8AC0638C6E712C871777C1325062 |
| backend/tests/test_intake_selection_ledger_postgres.py | E2DF0680F095E2A71F4E2F07D6A05C9E27A8C9FF5150762B2D31DE0090AEE57B |
| .github/workflows/ci.yml | E41DDCEF78C5F9AA47B0A6F9A55F32F81AAD1679FEDD43448BA9A64C7F3028C8 |

The report is excluded from recursive self-hashing. Root owns later evidence,
documentation/index checkpoints, actual PG execution and installed-package
reopen verification.

## Retained safety state, self-review and limits

Normal fixtures run actual migrations and seed only synthetic account/donor/
output/mapping plus unchanged source text and REJECT/rewrite_allowed=false.
All repository fixtures assert retained source text, exact REJECT/false state,
zero rewrite_jobs, zero rewrite_usage, zero outbox_events. Both rewrite provider
methods are forbidden and a zero-call list is asserted after each case. No
approved source permissions are fabricated. No real credentials, Telegram
login/session, network AI, publication, UI, operational volumes or business data
were used. The ledger grants no editorial/rewrite/publication authority.

Corruption fixtures deliberately use separate metadata-created SQLite stores
without Alembic immutability triggers, with check constraints relaxed only
within those isolated synthetic fixtures for otherwise unrepresentable invalid
payloads. They test decoder honesty; they do not claim that public migrated API
or immutable SQL guards can be bypassed. Failures preserve exact before/after
ledger rows; no repair, catch-and-default or hidden rollback is present.

Self-review read all owned source/test/workflow changes through EOF, checked
exact signatures, scalar/time validation, clean explicit session origin,
mapping-to-stream lock order, previous-window bounded linkage, original-carry
replay, insert-before-advance order, query budgets, zero-call safety, coherent
read snapshot and exhaustion handling. Two real self-review defects were
fixed with recorded RED/GREEN regressions above. No Task 1 correction needed.

The ten PostgreSQL repository tests collect but remain explicitly unexecuted by
this writer. They use the existing create-only UUID namespace helper, retain
all schemas and require the explicit allowlisted synthetic URL. Separate backend
PIDs and barrier events prove same-window one-decision/replay and four different
serialized 30-percent windows (quotas0,0,0,1; carry30,60,90,20). Rollback contention
uses events and real `pg_blocking_pids` evidence without sleeps/global monkeypatch
barriers; a native injected SQL failure after insertion must roll back window
and carry. Raw SQL immutable/delete/advance/truncate and reopened replay cases
are defined. Root must execute the combined native Windows PG gate after review.

Installed package/Docker reopen, full backend checkpoint, final increment
review and exact CI are root gates, not writer passes. No service/container,
provider, package installation or broad full backend run was started here.
