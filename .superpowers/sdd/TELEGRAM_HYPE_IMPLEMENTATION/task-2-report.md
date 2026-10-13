# Task 2 — bounded read-only Telegram Hype projection

Status: DONE within delegated scope; source frozen and sole full-backend verification complete. Actual PostgreSQL and packaged/CI gates remain root-owned.

## Implementation and scope

Added `TelegramHypeService(session).inspect(incoming_post_id, *, as_of, weights=None, minimum_coverage=0.5)` and frozen `TelegramHypeProjection`. The service validates signed64 ID, aware timestamps and policy before cold-start returns. It uses fresh scalar SQL column reads, including canonical incoming labels, under one `session.no_autoflush` scope. Cached ORM values and pending caller edits cannot replace database evidence or cause incidental flushes.

Target history reads at most two snapshots at/before `as_of`. Missing data, one observation, exact five-minute freshness, stale observations and explicit-clock freshness remain visible. Fresh paired observations use the accepted pure donor baseline. Baseline SQL filters exact account/donor, earlier publications within inclusive 30 days (clamped at aware datetime.min), other incoming identity, and observations at/before target end. It orders publication DESC, incoming ID DESC, observation DESC, reads at most 2001 rows, processes only the first 2000, forms chronological adjacent per-message windows and reports truncation. Only freshness and the three observed relative velocity components are populated. SQLite alone repairs naive storage datetimes.

Added migrated synthetic SQL tests and four explicit create-only PostgreSQL contracts. The PG fixture uses only `NEWSFLOW_UNATTENDED_POSTGRES_URL` and the existing strict `create_postgres_namespace`; no URL discovery/fallback, schema deletion, runtime credentials or operational data. Missing URL is SKIP. CI changes are exactly one appended test path in the existing PostgreSQL invocation, preserving all previous gate text.

No model, migration, pure domain, API, worker, UI or existing test edits. No network, Telegram, AI, queue or publication execution. All test fixtures retain original source/revision, REJECT and rewrite_allowed=false, zero RewriteJob and RewriteUsage; autouse forbidden rewrite-provider hooks retain zero rewrite calls. SQL-only read receipts and database read-only transactions additionally cover transaction ownership.

## TDD evidence and retained failures

Evidence root: `D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a` (new, retained; no cleanup).

`red.log`: initial execution command had one extra closing parenthesis and Python returned SyntaxError/native_exit=1. This is retained as a command failure and is not counted as causal RED.

`red-corrected.log`: migrated synthetic fixture seeded target 20 views/min, five ordinary donor messages at 10 views/min, original source/revision and REJECT. The test function ran and failed at its deferred service import: `ModuleNotFoundError: No module named 'newsflow.services.telegram_hype'`; `1 failed in 0.76s`, native_exit=1. The service file did not exist at this point. This is the causal function-level RED, before implementation.

`green1.log`: first implementation run produced `40 passed, 1 failed in 11.45s`, native_exit=1. The failed clock fixture mistakenly put its supposed future snapshot exactly at its as_of, correctly selecting that snapshot and changing the interval. Fixed the fixture to place it one minute later and corrected the earlier one-observation baseline expectation; production source behavior was unchanged.

`focused.log`: `45 passed, 4 skipped in 12.44s`, native_exit=0. PG skips explicitly say an isolated synthetic URL is required. One additional all-NULL target counter case was then added and verified in the final covering/full runs.

`covering.log`: `625 passed, 35 skipped in 121.75s`, native_exit=0. Includes final 46 SQL projection cases plus accepted pure Hype, interval rates, Telegram provider/history, planner review and relevant editorial gate/admission/worker/durable runner/history. Skips are 4 Hype PG + 26 engagement PG + 5 root-owned durable editorial PG lock cases; no PG success is claimed.

`full.log`: the ONE combined backend run completed `3496 passed, 56 skipped in 586.72s (0:09:46)`, native_exit=0; no warnings/errors. Source remained frozen throughout. Four new PG cases explicitly skipped for missing URL, alongside retained pre-existing opt-in/platform/conditional skips. All 46 new SQL cases and accepted pure tests ran. Root independently inspected the same terminal full log. No unchanged full repetition was run.

## Executed commands

Working directory for all pytest and compile commands: `C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend`. All pytest commands set `$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/pycache'` and insert the execution-only Telethon 1.45 directory at sys.path[0] **before** importing pytest. No environment-specific SDK path was added to source/tests.

The exact corrected RED, first GREEN, focused, covering and full Python commands were:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_hype.py::test_twice_ordinary_donor_interval_is_100_without_rewrite_authority','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/red-temp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/red-cache']))"
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_hype.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/green-temp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/green-cache']))"
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_hype.py','tests/test_telegram_hype_postgres.py','-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/focused-temp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/focused-cache']))"
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_hype.py','tests/test_engagement_rates.py','tests/test_telegram_hype.py','tests/test_telegram_hype_postgres.py','tests/test_telegram_engagement.py','tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','tests/test_planner_review_api.py','tests/test_editorial_gate.py','tests/test_editorial_admission.py','tests/test_editorial_worker.py','tests/test_durable_editorial.py','tests/test_durable_editorial_runner.py','tests/test_editorial_history.py','-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/covering-temp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/covering-cache']))"
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/full-temp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/full-cache']))"
```

Each command was followed by `2>&1 | Tee-Object <evidence-root>/<respective-log>; $taskExit=$LASTEXITCODE; Write-Output "native_exit=$taskExit" | Tee-Object -Append <same-log>; exit $taskExit`, so pipeline logging never masked the native result. Initial malformed command matches corrected RED except for the extra final ` )` and `red.log` output path.

Static commands (root working directory except Ruff backend/compile):

```powershell
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format backend/src/newsflow/services/telegram_hype.py backend/tests/test_telegram_hype.py backend/tests/test_telegram_hype_postgres.py
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check backend/src/newsflow/services/telegram_hype.py backend/tests/test_telegram_hype.py backend/tests/test_telegram_hype_postgres.py
# Working directory backend:
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check src tests alembic
# Working directory repository root:
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check backend/src/newsflow/services/telegram_hype.py backend/tests/test_telegram_hype.py backend/tests/test_telegram_hype_postgres.py
# Working directory backend:
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/telegram-hype-task2-20261013a/compile-pycache'
python -m compileall -q src tests
# Working directory repository root:
python -c 'from pathlib import Path; import subprocess,yaml; original=subprocess.check_output(["git","show","cd0d85847f2fae7e2a17f8ad6970fc9512c7ac38:.github/workflows/ci.yml"],text=True); current=Path(".github/workflows/ci.yml").read_text(); old="tests/test_telegram_engagement_postgres.py -q"; new="tests/test_telegram_engagement_postgres.py tests/test_telegram_hype_postgres.py -q"; assert original.count(old)==1; assert current==original.replace(old,new); data=yaml.safe_load(current); step=next(s for s in data["jobs"]["unattended-postgres"]["steps"] if s.get("name", "").startswith("Migrated PostgreSQL")); assert step["run"].count("tests/test_telegram_hype_postgres.py")==1; assert "NEWSFLOW_UNATTENDED_POSTGRES_URL" in step["env"]; print("YAML parsed; exact one-path append; all prior gate text retained")'
```

Native results: format exit0 (`3 files reformatted`), focused Ruff exit0 (`All checks passed!`), backend Ruff exit0 (`All checks passed!`), format check exit0 (`3 files already formatted`), compile exit0 (quiet), YAML exit0 (`YAML parsed; exact one-path append; all prior gate text retained`). Raw logs: format.log, ruff.log, ruff-backend.log, format-check.log, compile.log, yaml.log.

`versions.log` retains Python 3.12.10 [MSC v.1943 64 bit AMD64], Telethon 1.45.0 from the required execution-only directory, pytest 8.4.2, SQLAlchemy 2.0.52, Alembic 1.20.0, PyYAML 6.0.3, Ruff 0.17.0; Python and Ruff native exits0.

## Frozen owned source hashes (SHA256)

- backend/src/newsflow/services/telegram_hype.py: `854618692B497B6EEFA12858D3980ECEDAC10D25EB1071DD7E605C14F2F2E0EF`
- backend/tests/test_telegram_hype.py: `25CFBD1CDAE6FB5AE3CDB5DB73D3D42D291ADEC894A830ECC1831C7054F0DA02`
- backend/tests/test_telegram_hype_postgres.py: `3B55B2A947359A366FB9328D11DEEDF3CCA6974F2F5FE595C9C9C56799CBBC50`
- .github/workflows/ci.yml: `7E85411EB715C8F7B139391D412FB198459007E79CD495D8A070CA34D91EFE95`

Raw `frozen-hashes.log` retained. Root notified before sole full run; no source edits during full execution. Own fifth file is this report. Root-owned dirty documents/progress/index remain untouched and will not be staged by this implementation.

## Self-review and limits

Read all four owned files and CI diff against exact approved design. Checked zero/unknown/reset semantics, no target self-baseline, canonical exact account/donor identity, stale cache, inclusive time boundaries, row truncation before adjacency grouping, one message independence, donor-size fairness, early-year UTC clamp, untouched seven evidence components, malformed frozen weights, and SELECT-only pending caller transactions. No implementation findings remain. Corrected one clock test fixture, as recorded above. The production module remains one focused read-only service; no unrelated restructuring.

Actual Windows PostgreSQL execution and exact source CI are root-owned after clean source review. The four local PG skips are not PostgreSQL proof. No live/operational/PHASE success claim. No implementation concerns remain.

## Scoped commit receipts

Only the four listed owned source/CI files and this report are staged. Commit subject: `feat: add bounded read-only Telegram hype projection`. No push. Root-owned dirty docs and progress remain untouched. Initial exact five-file `git add` returned native_exit=1 because the new report directory is ignored; retained in staged.log. Corrected with `git add -f -- .superpowers/sdd/TELEGRAM_HYPE_IMPLEMENTATION/task-2-report.md` only. Before commit, exact staged-name verification, `git diff --cached --check` and final four SHA256 verification are run and retained under this evidence root; staged whitespace gate native_exit=0 is required. Final SHA is returned separately to root (a report cannot contain its own immutable commit SHA).

`staged.log` actual receipts: report_force_add_native_exit=0, staged_diff_check_native_exit=0, exactly five owned paths listed (907 insertions, one CI line deletion). Final report receipt restaged before a final check; no root-owned document is staged. Four source hashes above remain unchanged after full.
