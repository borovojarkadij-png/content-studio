# Task 2 implementer report — 2026-10-13

Status: DONE_WITH_CONCERNS (implementation complete; actual PostgreSQL and corrected full CI qualification remain controller-owned).

## Implemented and scope

Added the two focused engagement models, additive migration `a7e239bc5180` after verified actual predecessor `f6a42c91b805`, and caller-transaction-owned `TelegramEngagementHistory.record/history`. The service revalidates Task 1's frozen domain contract, locks and refreshes the canonical incoming source before writing, checks its real configured account/donor, preserves first publication time, treats exact replay as False, refuses conflicting replay, retains out-of-order snapshots, and returns bounded latest observations chronologically. Nullable counters stay unknown; SQLite naive internal timestamps are restored to UTC only at the storage boundary. There are no service commits, rollbacks, RPC/provider calls, jobs, outbox effects, activation flags, API, worker or frontend changes.

The migration has named signed64/date checks, RESTRICT FKs, exact microsecond ordering, SQLite canonical timestamp/type checks and parent/no-replace/update/delete guards (including incoming source identity retention with FK enforcement OFF), and PostgreSQL update/delete/TRUNCATE refusal. Empty downgrade locks before checking/removing tables; populated source-only or snapshot history refuses downgrade. PostgreSQL downgrade locks incoming first, matching writer order before removing its new retention trigger. No existing migration or trigger was weakened or rewritten, and no existing identity/data was changed or backfilled.

Controller clarification: history is an audit reader. It requires a canonical existing incoming source, but remains readable after current donor configuration is removed; record still requires configured account/donor. A causal RED/GREEN regression verifies this distinction without authority effects.

Initial ownership was exactly six source/test/migration/CI paths plus this report. After the single full run exposed historical fixture assumptions, the controller explicitly extended ownership to only the additive/empty-roundtrip test in `backend/tests/test_editorial_attempt_migration.py` and the downgrade-refusal test in `backend/tests/test_media_runner.py`. The former keeps historical PARENT/HEAD constants and all sentinels/refusal assertions, checking current metadata only after upgrading to actual head. The latter stamps the exact media migration under test rather than claiming `create_all` installed later migration triggers, retaining refusal and adding exact retained job/state/attempt and Alembic-version assertions.

Modified/created paths (workspace root `C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2`):

- `.github/workflows/ci.yml`: append the PostgreSQL test file exactly once to the existing PG command; every preceding command/check unchanged.
- `backend/src/newsflow/persistence/models.py`: only two focused additive models.
- `backend/src/newsflow/services/telegram_engagement_history.py`.
- `backend/alembic/versions/a7e239bc5180_add_telegram_engagement_history.py`.
- `backend/tests/test_telegram_engagement_history.py`.
- `backend/tests/test_telegram_engagement_postgres.py`.
- `backend/tests/test_editorial_attempt_migration.py`: narrowly authorized historical test correction.
- `backend/tests/test_media_runner.py`: narrowly authorized fixture correction.
- This report.

Preflight: branch `codex/dark-navy-ui`, initial HEAD `86ba3d2f4efb7491da884a70567152d5a37cd8af`; origin is `borovojarkadij-png/content-studio`. No push/PR/merge/force-push operation. Controller-owned dirty state/docs were preserved and excluded from staging. No subagents/helpers/reviewers dispatched. No real credentials, Telegram login/RPC/send, operational database, queue or volume used.

Staging note: the initial `git add -- <owned paths and report>` exited 1 because the report directory is ignored, while staging only the eight authorized source paths. The explicit report-commit instruction is satisfied with `git add -f -- .superpowers/sdd/TELEGRAM_ENGAGEMENT_IMPLEMENTATION/task-2-report.md` for that one report; no ignore rules or other ignored paths were changed.

## Runtime and evidence commands

Python 3.12.10, SQLite 3.49.1, SQLAlchemy 2.0.52, pytest 8.4.2, Telethon 1.45.0; actual Ruff executable version 0.17.0. `runtime.log` confirms explicit PostgreSQL URL variables absent (no values printed). SDK 1.45 was inserted only in invocation `sys.path`, never hardcoded into product or tests.

All raw evidence is under `D:/Codex-Recovery/telegram-engagement-task2-20261013a/`. All pytest commands ran from the workspace's `backend` directory with the exact invocation body:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(ARGS))" *> LOG
$testExit = $LASTEXITCODE
Get-Content LOG -Tail 100
exit $testExit
```

`ARGS` below is the literal Python argument list; `LOG` is the evidence root plus the listed filename. Basetemp paths below are absolute and unique to the invocation. Exit is the propagated native pytest exit, not an inferred success.

| Run | Literal ARGS | Native exit; result | Raw file |
|---|---|---|---|
| Causal RED, before product | `['tests/test_telegram_engagement_history.py::test_record_replay_survives_reopen_without_editorial_side_effects','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/red-temp']` | 1; 1 failed: missing service module at actual migrated record/replay call | `red.log` |
| Initial GREEN | `['tests/test_telegram_engagement_history.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/green-temp']` | 0; 52 passed | `green.log` |
| Microsecond RED | `['tests/test_telegram_engagement_history.py::test_sqlite_temporal_guard_preserves_microsecond_order','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/time-red-temp']` | 1; 1 failed: SQLite julianday comparison accepted earlier microsecond | `time-red.log` |
| Temporal GREEN | `['tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/focused-temp']` | 0; 54 passed, 24 explicit PG skipped | `focused.log` |
| Cached writer identity RED | `['tests/test_telegram_engagement_history.py::test_locked_canonical_source_refreshes_stale_session_identity','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/stale-red-temp']` | 1; 1 failed: cached old identity bypassed new donor configuration check | `stale-red.log` |
| Writer GREEN and expanded bounds | `['tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/focused-final-temp']` | 0; 72 passed, 24 explicit PG skipped | `focused-final.log` |
| Cached audit identity RED | `['tests/test_telegram_engagement_history.py::test_history_refreshes_cached_identity_before_labeling_observations','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/read-red-temp']` | 1; 1 failed: observations labeled with stale donor | `read-red.log` |
| Covering | `['tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','tests/test_telegram_engagement.py','tests/test_editorial_history.py','tests/test_durable_editorial_runner.py','tests/test_illustration_review_storage.py','tests/test_unattended_postgres_target.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/covering-temp']` | 0; 413 passed, 30 skipped; 102.19s | `covering.log` |
| Expanded downgrade/bounds | `['tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/freeze-focused-temp']` | 0; 74 passed, 26 explicit PG skipped | `freeze-focused.log` |
| Audit removal RED, controller ruling | `['tests/test_telegram_engagement_history.py::test_retained_history_remains_readable_after_synthetic_donor_configuration_removal','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/audit-red-temp']` | 1; 1 failed: audit read wrongly required current donor config | `audit-red.log` |
| Final product/SQLite GREEN | `['tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/audit-green-temp']` | 0; 75 passed, 26 explicit PG skipped; 19.19s | `audit-green.log` |
| ONE combined full backend | `['-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/full-temp']` | **1; 2 failed, 3347 passed, 52 skipped; 557.10s** | `full.log` |
| Final PG assertion collection | `['tests/test_telegram_engagement_postgres.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/pg-final-collect-temp']` | 0; 26 skipped, no actual PG execution | `pg-final-collect.log` |
| Historical correction intermediate | `['tests/test_editorial_attempt_migration.py','tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/post-full-historical-temp']` | 0; 109 passed, 26 explicit PG skipped; 28.37s | `post-full-historical.log` |
| Final corrected targeted generation | `['tests/test_editorial_attempt_migration.py','tests/test_media_runner.py','tests/test_telegram_engagement_history.py','tests/test_telegram_engagement_postgres.py','-q','--basetemp=D:/Codex-Recovery/telegram-engagement-task2-20261013a/post-full-final-temp']` | **0; 119 passed, 26 explicit PG skipped; 30.23s** | `post-full-final.log` |

These regressions exercise real migrated SQL storage, reopen and caller rollback; exact replay/conflict/publication immutability; source/config identity and stale session reads; signed64 bounds on all counters; NULL/zero/extreme timestamp roundtrips; chronological/latest bounds; raw SQL FK/time/type/overflow/update/delete/native replace; parent retention with SQLite FK enforcement OFF; drift, empty downgrade and protected count/drop interleaving; populated source-only/snapshot downgrade refusal. Synthetic REJECT/false, unchanged original text/revision and zero RewriteJob/RewriteUsage rows are asserted. An autouse provider tripwire proves zero rewrite calls in engagement cases.

### Full-run failures and generations — no full PASS claim

The single full run executed final product, migration, and SQLite engagement code, with the original historical test generation. It failed only:

1. `test_editorial_attempt_migration.py::test_additive_upgrade_and_empty_roundtrip_preserve_all_old_data_without_drift`: `alembic.util.exc.CommandError: Target database is not up to date.` It checked current metadata at historical `f6a42c91b805` while the new actual head is `a7e239bc5180`.
2. `test_media_runner.py::test_media_migration_refuses_durable_history_loss`: `OperationalError: no such trigger: engagement_incoming_no_delete`. Its `metadata.create_all` fixture stamped current head without installing migration triggers; the new migration correctly refused an inconsistent downgrade path.

Both narrow test-only fixes were made after terminal full exit under explicit controller scope extensions, then both modules and engagement regressions passed together. No product/model/migration change occurred after full launch. PostgreSQL tests collected by the full run were all skipped; their final generation tightens broad DBAPIError assertions to exact expected SQLSTATE so syntax failures cannot masquerade as integrity proof. That skipped-only assertion patch was applied before full terminal receipt (controller informed), then final collection/static and final targeted checks passed. Actual PG remains the controller's gate for that generation. Per controller instruction, no second unchanged local full was run; corrected full-suite proof belongs to exact CI. `full.log` remains an honest **FAIL**, never relabeled PASS.

### Static, migrations and workflow

From workspace root, exact final Ruff commands used this file list:

```text
backend/src/newsflow/persistence/models.py backend/src/newsflow/services/telegram_engagement_history.py backend/alembic/versions/a7e239bc5180_add_telegram_engagement_history.py backend/tests/test_telegram_engagement_history.py backend/tests/test_telegram_engagement_postgres.py backend/tests/test_editorial_attempt_migration.py backend/tests/test_media_runner.py
```

`& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check <list>`: native 0, `All checks passed!`, `frozen-ruff.log`.

`& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check <list>`: native 0, `7 files already formatted`, `frozen-format.log`.

From backend, `python -X pycache_prefix=D:/Codex-Recovery/telegram-engagement-task2-20261013a/frozen-pycache -m compileall -q src tests alembic`: native 0, empty successful output, `frozen-compile.log`.

From workspace root, `git diff --check -- .github/workflows/ci.yml <list>`: native 0; only configured Git LF-to-CRLF notices, no whitespace defects. Initial Ruff TRY004 was corrected to the tested TypeError contract; all final Ruff checks pass.

From backend, exact final migration command (native 0, `final-migration.log`):

```powershell
python -c "from alembic import command; from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config('alembic.ini'); c.set_main_option('sqlalchemy.url','sqlite:///D:/Codex-Recovery/telegram-engagement-task2-20261013a/final-migration-cycle.db'); assert ScriptDirectory.from_config(c).get_heads()==['a7e239bc5180']; command.upgrade(c,'head'); command.check(c); command.downgrade(c,'base'); command.upgrade(c,'head'); command.check(c); print('PASS: single head; fresh SQLite upgrade/check/base downgrade/reupgrade/check')"
```

Actual output: two `No new upgrade operations detected.` and the PASS message. Populated downgrade refusal is separately behavior-tested, never tested by deleting operational data.

From workspace root, exact workflow validation (native 0, `final-yaml.log`):

```powershell
python -c "from pathlib import Path; import subprocess,yaml; p='.github/workflows/ci.yml'; old=subprocess.check_output(['git','show','86ba3d2f4efb7491da884a70567152d5a37cd8af:'+p],text=True); new=Path(p).read_text(); marker='tests/test_telegram_login_postgres.py -q'; assert old.count(marker)==1; assert new==old.replace(marker,'tests/test_telegram_login_postgres.py tests/test_telegram_engagement_postgres.py -q'); assert new.count('tests/test_telegram_engagement_postgres.py')==1; yaml.safe_load(new); print('PASS: valid YAML; exact one-file append; all prior commands and checks unchanged')"
```

Actual output: `PASS: valid YAML; exact one-file append; all prior commands and checks unchanged`.

## Frozen SHA256 and self-review

Hashes are of exact final working-file bytes (Git may normalize configured line endings in committed blobs). Command: `Get-FileHash -Algorithm SHA256 -LiteralPath <eight paths> | Select-Object Path,Hash | ConvertTo-Json`.

| Owned path | SHA256 |
|---|---|
| `.github/workflows/ci.yml` | `53E1BB7C93AA290073537E375137733D356E7045E0509FA55D86B7237F969F0D` |
| `backend/src/newsflow/persistence/models.py` | `67BF15E5A3F5C45BA5B6918B271957E5C70724FDC8CBC3E1A05D7DF17A174211` |
| `backend/src/newsflow/services/telegram_engagement_history.py` | `63119725CACF0DC24560ED8F5E57F27658DBC759682D7401DBEDBAF953B0D6E5` |
| `backend/alembic/versions/a7e239bc5180_add_telegram_engagement_history.py` | `19000D40DAB28C7F42205BB61DE391CA4AA0D59D7FA34BC631184C902D28AA32` |
| `backend/tests/test_telegram_engagement_history.py` | `33F3C43C0C97DA999324ADB1F93F815A5D78FB690799A3EF13B610E4B46AF0C8` |
| `backend/tests/test_telegram_engagement_postgres.py` | `368D8081C0159E56800D4AF537C4900E7C29739E7F0532CBD3AEB74F3994CF80` |
| `backend/tests/test_editorial_attempt_migration.py` | `4D2E340548E4C162EB8694013B78D1BB71FBBD8E4DEF3C24C8951CC4127E9A3A` |
| `backend/tests/test_media_runner.py` | `CEF68FA611126E37722B445AE207A613D5F0D296B12562F2222BDEB387FA1F78` |

Self-review read the final service, migration, tests and exact existing-file diffs. Fixed findings: SQLite microsecond precision, stale ORM writer/reader identity, audit readability after config removal, PostgreSQL downgrade lock order, exact SQLSTATE evidence, and the two scope-authorized historical fixture regressions. Existing large models file was changed only by the two requested classes. No outstanding known implementation defect. The report itself is frozen with the commit; controller can hash its file without a recursive self-hash.

Remaining qualification: **26 PostgreSQL cases are SKIP, not PASS** (explicit URL absent). Tests use strict `create_postgres_namespace`, fresh retained UUID schemas, independent committed connection PIDs, controlled source locking, native uniqueness/upsert/TRUNCATE/FK/time/overflow and rollback checks; they never fall back to SQLite or DROP/reset namespaces. Controller owns actual Windows PostgreSQL, source review, exact CI and package/network-none gates. The local full remains FAIL with both causes fixed in the separately tested final generation. No second full or actual-PG success is claimed here.
