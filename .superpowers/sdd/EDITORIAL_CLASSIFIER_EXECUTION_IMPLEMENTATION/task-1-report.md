# Task 1: durable diagnostic classifier execution

Original implementation status at `c9c16d122ba6b3cee5bd6a3a157d72ca41268166`: DONE. Its frozen full backend suite and independently executed root-owned actual PostgreSQL runner/restart checks passed. Review correction round 1 is documented below, with separate amended-byte provenance. No push was performed.

## Scope and implementation

Repository verified before edits: origin `https://github.com/borovojarkadij-png/content-studio.git`, branch `codex/dark-navy-ui`, base `e8b761728c6630473620adb04b518b8262c2283b`. The owned tree was initially clean. Root-owned documentation changed concurrently and is excluded from this commit.

Read the task brief, only Global Constraints from the accumulated plan, the implementer prompt, TDD and writing-good-tests reference, NewsFlow migration/recovery guidance and AI-evaluation guidance. No helpers/subagents were dispatched. No Docker, operational SQL, real credentials, live provider calls, secret lookup, credential decryption, settings/API/UI/worker activation, publication, push or PR operation was performed.

Implemented:

- Read-only `last_evidence_json`, reset at entry before rejected request/payload paths, populated only after returned-model validation and canonical bounded actual transport JSON serialization. `classify` retains its return contract.
- Additive `f6a42c91b805` migration from actual head `d7b340a92e16`, with immutable claim provenance and one append-only receipt per claim. Claim uniqueness, canonical UUID shape, attempt bounds, outcome/diagnostic bounds, UTF-8 evidence byte bound, JSON reason-list shape, observed/unobserved usage, count and finite nonnegative known cost constraints are enforced in storage. SQLite guards references and replacement as well as UPDATE/DELETE; PostgreSQL guards UPDATE/DELETE and TRUNCATE. Downgrade acquires write protection, counts both tables before DDL, and refuses either populated table. No seeds/backfill/settings/policy/job resubmission.
- `DurableEditorialRunner` validates inputs, scans a bounded due-ID list, locks/rechecks jobs with SKIP LOCKED, resolves fresh canonical admission and exact job binding before reserving an attempt. RUNNING state, UUID token, 60-second lease and immutable claim commit atomically. Legacy RUNNING tokens without matching immutable history fail closed.
- All SQL sessions close before injected factory and classifier IO. Factory provider/model/prompt identity is checked, admission is re-resolved after construction and after IO. Only bounded actual receipt evidence is assessed by the accepted pure contract. Protected negative evidence becomes diagnostic REJECT; every other valid/uncertain report becomes REVIEW. Original editorial decisions remain MANUAL_REVIEW/false and no RewriteJob is created.
- Only ProviderUnavailable retries once through the same QUEUED job after 60 seconds. Other provider/configuration/response failures use stable codes. Invalid/missing/oversized evidence terminally fails, while bounded schema/binding/uncertain evidence becomes manual REVIEW without repair calls. Usage is validated without converting unknown/invalid counts to zero. Late receipts require exact immutable history and cannot overwrite reclaimed/new/terminal owners.
- Receipt, owned job transition/release and exact attempted outbox event commit atomically. Existing exact receipts replay unchanged. Storage faults propagate and roll back the whole boundary.
- Strict migrated PostgreSQL CI list receives only `tests/test_durable_editorial_runner.py`.

Root explicitly authorized a narrow historical migration-test compatibility adjustment: the original pinned d7 upgrade/downgrade assertions remain; metadata `command.check` now follows an explicit upgrade to actual head so intentional new-table metadata is checked at the correct version. No drift check was weakened.

## Test evidence and native command contract

All pytest commands ran in `backend` using installed Python 3.12.10 and explicit Telethon 1.45.0 insertion:

```powershell
python -c "import sys;sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145');import pytest;raise SystemExit(pytest.main([<arguments below>]))" *> "$run/native.log"
$code = $LASTEXITCODE
Get-Content "$run/native.log"
Write-Output "NATIVE_EXIT=$code LOG=$run/native.log"
Get-FileHash "$run/native.log" -Algorithm SHA256
```

Each `$run` is the exact unique directory below under `D:/Codex-Recovery/content-studio-20261008/`. Every invocation supplied `--basetemp,$run/temp,-o,cache_dir=$run/cache`; logs were preserved without rewriting. SQLAlchemy 2.0.52, Alembic 1.20.0 and pytest 8.4.2 were verified. No actual PostgreSQL target was set or operated by this implementer; the fixture otherwise migrates fresh SQLite. Strict PG uses the accepted fresh-UUID create-only namespace helper and is run by root.

### Behavioral RED before production implementation

Arguments: `tests/test_durable_editorial_runner.py,-q`.
Directory `editorial-execution-red-92ffd96b31de41528dad529f907be667`.
Native pytest exit **1**, summary **1 failed in 0.57s**.

```text
assert (job.state, job.attempts) == ("REVIEW", 1)
AssertionError: assert ('QUEUED', 0) == ('REVIEW', 1)
```

This exercised real migrated synthetic ingress and persisted SQL state. A temporary test-only discovery guard allowed missing runner implementation to reach that behavioral assertion; it was removed as soon as the runner API existed. There was no import/collection error, skip, xfail or comparison of mocked verdict values in this RED.
Log SHA256 `E58980C363BF17FC82642C58673EF0821B3388BB7A4CE898169E586E3CB8FE97`.

### Core and migration GREEN

Initial core covering arguments: `tests/test_durable_editorial_runner.py,tests/test_editorial_classifier_adapters.py,tests/test_editorial_admission_migration.py,-q`.
Directory `editorial-execution-green1-57f019e56cc74fe0a2f304475cfe8f6b`.
Summary **142 passed in 16.64s**. The call accidentally printed only command output and discarded its running session identifier, so its native exit field was not retrieved; it is not claimed as an independently captured native exit0. Log SHA256 `9C20722BD5F838B5995D8D44299260D6ABF413AA8AAFD581065B5DA2F1518C47`.

Migration covering arguments: `tests/test_durable_editorial_runner.py,tests/test_editorial_attempt_migration.py,tests/test_editorial_admission_migration.py,-q`.
Directory `editorial-execution-migration1-2ad9cacbe49c41179e7faf645fdea721`.
Native exit **0**, **78 passed in 24.61s**; includes all **31 original admission migration cases** plus new migration and core runner cases.
Log SHA256 `14758789D68B140514F0D1F5C168B68CC4021317F795172A1DCDF0854B410A06`.

### Iteration failures retained honestly

Runner arguments `tests/test_durable_editorial_runner.py,-q`, directory `editorial-execution-runner2-81210104f74943538117d2201f562ebd`: native exit **1**, **111 passed, 1 skipped, 2 setup errors in 36.58s**. Pytest's automatic parameter ID for the 262146-byte Unicode input overflowed Windows' `PYTEST_CURRENT_TEST` environment-variable limit (`ValueError: the environment variable is longer than 32767 characters`). Explicit short IDs fixed test infrastructure without changing the evidence-size expectations. This log is large and is preserved intact; do not print it unbounded.
Log SHA256 `B90B2E5AB25AD20347FEF67B442795CB186D942F394476A9D40B17AF09B0B6F7`.

Corrected runner3: same arguments, directory `editorial-execution-runner3-f8ca3d7758034d208f1bd7e90266bd66`: native exit **0**, **112 passed, 1 skipped in 34.11s**. The skip is the deterministic actual-PG lock proof when using SQLite.
Log SHA256 `CADFF8CE8420126E7A2EBE159FFF50522BA74A79CA52669214E13834CECF6265`.

Additional malformed-usage RED: arguments `tests/test_durable_editorial_runner.py,-q,-k,observed_usage`, directory `editorial-execution-usage-red-fdcccde1051e466e803e7cfed978f38e`: native exit **1**, **1 failed, 14 passed, 99 deselected in 4.56s**. A real classifier result with RewriteUsage(provider=[]) raised `TypeError: unhashable type: 'list'` instead of persisting unobserved invalid usage. The production fix checks exact string type before supported-provider membership.
Log SHA256 `C90A3A923F56E6A2A59E9D68DA1870DF2A34DE95663C8D89F500EE9A7E981232`.

Usage GREEN: same selected arguments, directory `editorial-execution-usage-green-80c67089d8364e63b9500de1c78be7b7`: native exit **0**, **15 passed, 99 deselected in 4.72s**.
Log SHA256 `226581FCA4AD4741BAD4F116D6CC264B16A35BC878E8C52D0C1272ED53D322F3`.

First broad covering invocation used nonexistent `tests/test_source_revision_guards.py`: native exit **4**, **no tests ran in 0.00s**, directory `editorial-execution-covering-ebf831e4d05a4f62a98f1cc482761935`. Corrected to actual source sync/deletion guard files. Log SHA256 `B0B9614B55ECB21B70AE9F85EF4726C12859026551ACD7D2D78F724101997D44`.

Initial Ruff diagnostics identified imported-fixture F811/F401, two deliberate unknown-provider exception boundaries needing justified BLE001 annotations, and one unused mapping variable. All were corrected; no blanket lint suppression. One tooling command also mistyped the Ruff executable path as `D:/Codex-Recovery/content-studio-20261012/bin/ruff.exe` and failed command lookup after its preceding lint step. The verified actual native executable is `D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe`. A read-only discovery command requested nonexistent root `ruff.toml`; actual repository rules and backend configuration were used by Ruff. These incidental tool failures are not counted as passing verification.

### Final covering GREEN before source freeze

Arguments:

```text
tests/test_durable_editorial_runner.py
tests/test_editorial_attempt_migration.py
tests/test_editorial_admission_migration.py
tests/test_editorial_classifier_adapters.py
tests/test_editorial_admission.py
tests/test_editorial_classification.py
tests/test_durable_ingestion.py
tests/test_durable_ingestion_workflow.py
tests/test_source_sync_guards.py
tests/test_source_sync_replay.py
tests/test_source_deletion_guards.py
-q
```

Directory `editorial-execution-covering2-122bf4cd561848f7bb9a6530bcadc145`.
Native exit **0**, **534 passed, 1 skipped in 85.53s**; no warnings/errors. Sole skip is actual-PG deterministic concurrency proof on SQLite.
Log SHA256 `1D4D9046438BD84A8DDD6532A294AC3F83E3DEB36E723CA00A92D43511554BCC`.

Coverage includes migrated ingress→RUNNING claim→REVIEW receipt; read-only transport receipt reset; forged return and evidence binding/schema/type/encoding/byte bounds; protected-negative REJECT; canonical source/policy/mapping/editorial/ownership/fingerprint/technical/video/YT/ads/album/deletion/sync holds; factory identity and raw exception sanitization; independent committed changes after claim, during factory, during classify; session closure over factory/classifier; known/unknown/malformed usage; late expired/reclaimed receipt provenance; forged/legacy claims; active/future/terminal/due ordering and bounded scan; retry/exhaustion; receipt replay/outbox idempotency; SQL reopen; and claim/job-update/receipt/outbox fault rollback with subsequent retry. Real rewrite provider methods are forbidden by an autouse fixture.

PostgreSQL-only concurrency test synchronizes an actual held first-row lock with threading Events and completes the second claimant while the first holds it. No sleeps/probabilistic scheduling. Fresh namespace helper enforces the exact synthetic local target; nothing is dropped, reset or cleaned up.

### Static verification

Directory `editorial-execution-static-0c93755210c94ef8ad2c0172baecb8ce`:

- Native Ruff **0.17.0** `check src tests alembic`: exit0, `All checks passed!`; ruff.log SHA256 `A4443AFDCFB6D7363ADB285762515CCF7CF50473B1A05C20C1A50F6BED4D26B0`.
- Ruff `format --check` on all eight changed Python files: exit0, `8 files already formatted`; format.log SHA256 `3FA62C94B1301255F0C64C429C668A4FABC4CB9D3848EDB2790B607266D16092`.
- `python -m compileall -q src tests alembic`, with `PYTHONPYCACHEPREFIX=$run/pycache`: exit0; empty compile.log SHA256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.
- `python -c "from pathlib import Path;import yaml;yaml.safe_load(Path('../.github/workflows/ci.yml').read_text());print('YAML parse passed')"`: exit0; yaml.log SHA256 `C50F9677DE3402DDADE0E4E429DDA580EBA79D3B59E23C310912850B48A22F8C`.
- `git diff --check -- src tests alembic ../.github/workflows/ci.yml`: exit0; only Git's existing LF→CRLF working-copy notices, diff.log SHA256 `839F9108E3AB900586F73C20E9FC523BB381C9A9D00290A7E4B73EC4C5F6FB53`.

## Original c9 frozen full-suite and provenance

Exactly one full suite started `2026-10-12T20:07:17.9092986Z`, exec session31926, directory `editorial-execution-full-6d5a38802c234c85baab8f2db0d707e7`, arguments `-q,-ra,--basetemp,$run/temp,-o,cache_dir=$run/cache`. Native exit **0**, **2462 passed, 7 skipped in 444.14s (0:07:24)**; no warnings/errors. Raw native.log SHA256 `084A9BF09531B413BE6BEE5DF7E77F75BE3D000D1CA28B1AAB34E1B12E00AC36`. Root was notified before independent PG testing; no source/test/migration/CI edits after this freeze.

The seven local skips are explicit PostgreSQL-only controls: one new runner competing-claimants proof (independently executed and passed in root's actual PG120 gate), one existing real TRUNCATE check in illustration storage, and five existing planner/media PostgreSQL concurrency opt-ins. Skips are not represented as passes. No browser or Docker suite was repeated.

Raw SHA256 of the original c9 full-tested owned files (paths relative to repository), rechecked unchanged during that run and original finalization. These were exactly the original c9 committed source/test/migration/CI bytes; only this report was completed after that freeze. The runner and its tests were subsequently amended in review round 1 below. Therefore this original 2462/7 full-suite result is not full-tested evidence for the final amended bytes:

| File | SHA256 |
| --- | --- |
| `.github/workflows/ci.yml` | `1EC47A223E6BE4121ABB6E1264E63AAA1CA55A37200E45D3543AB203304C147D` |
| `backend/src/newsflow/providers/editorial_classifier.py` | `2EC23E12137F81D989E3BACDA9DB7914D1CC3012232210127070721E3E389E05` |
| `backend/src/newsflow/persistence/models.py` | `1FFB4033DD4AA336D1D992BC654D11DCB5759A4054F2834D06C5E91BD6F4B351` |
| `backend/alembic/versions/f6a42c91b805_add_editorial_attempt_history.py` | `0DDC9E98FD01208D0FE3B1DB59EE2A26542850613FA1046366FA168F346D602B` |
| `backend/src/newsflow/services/durable_editorial_runner.py` | `FC75A0DCCAF9DDDD04FB682B8A99F4F3206F3C70B131A5CB73FEE516F47F4C72` |
| `backend/tests/test_durable_editorial_runner.py` | `C124814E1F3B098072AF510C2CE117EBE483222B44AC9C508179B6CB0FE092B6` |
| `backend/tests/test_editorial_attempt_migration.py` | `09FD7EA185914DA6B268F3BD73C802E8533FA6431957569D22FDB2865F624B2D` |
| `backend/tests/test_editorial_classifier_adapters.py` | `660ED2DA45F54B03985474A355BA57B209DEAFFE5FAFCF1293DF70DBAAB427F3` |
| `backend/tests/test_editorial_admission_migration.py` | `22248EEEAFDF27D9A316CCE498392A7164A05CC1CA95A7792EB9BE58714CCADC` |

This report is the only additional owned file. Root-owned documentation is neither staged nor edited by this task. Root owns CI/live/runtime verification, state/progress ledger and source review. Native Windows PostgreSQL results belong to root's independent evidence and are not claimed from this implementer's commands.

### Independently executed actual PostgreSQL evidence (root)

Root reported native exit **0**, **120 passed in 86.96s**, no skips/warnings, for all frozen `test_durable_editorial_runner.py` cases using the strict actual Windows local synthetic PostgreSQL target. Root validated baseline 1523 namespaces/maxOID1148480 and exact owned loopback container, created only fresh UUID migrated namespaces, and confirmed all nine frozen hashes match after the run. The root-owned command ran in exec session19635.

Root log: `D:/Codex-Recovery/content-studio-20261008/editorial-execution-root-pg-4b7ffd71be514c50abc3972a470795d7/native.log`, SHA256 `A252A7E6F4A007F762038C0CA9D12D76717F320857EAA7E2F7DD11ED5B58F6BB`.

This is the independent actual-PG proof, including deterministic competing claimants and direct migrated history mutation refusal. Root additionally reported native0 for a task-new-schema snapshot, exact synthetic container restart (StartedAt `2026-10-12T20:10:17Z`) and two read-only reopens: 101 fresh schemas at f6 head retained 78 claims, 73 receipts (four with known usage), and 103 jobs (including three QUEUED and four RUNNING). The manifest SHA256 remained `458DB7405B743D6E0E1F47DC55727B6AA432B30E90499B2BC9813018A77DD3F0`. A deliberately seeded BLOCKED RewriteJob belongs to the negative control, not runner dispatch. Root records exact runtime scope separately in its verification document. This was no test rerun and no additional implementer operation.

## Self-review and limitations

Self-review checked the complete owned diff, transaction rollback/fencing, immutable provenance, canonical resolver use, provider-free negative paths, sanitization and source/session boundaries. Unknown injected provider exceptions are deliberately sanitized; SQLAlchemy storage errors are explicitly re-raised. Response identity is restricted to pinned model and accepted OpenRouter free-name convention. Pre-classify failures do not copy stale adapter diagnostics. No outstanding implementation concern identified. Final self-review and commit do not change the frozen implementation or tests.

All outcomes are diagnostic only. Synthetic conformance is not real-model qualification, PHASE1 completion, automatic editorial approval or rewrite/publication authorization. Actual model qualification/benchmark, encrypted factory, protected-policy settings and opt-in worker orchestration remain deferred. Existing large `models.py` was modified additively without restructuring. The focused runner and its extensive integration test remain single-responsibility files as required.

## Review correction round 1: refresh lease fences after SQL waits

Fix base: `c9c16d122ba6b3cee5bd6a3a157d72ca41268166`. Read the independent task-1 review and receiving-code-review guidance before correction. Reconfirmed the Important finding against the actual runner: `_finish` captured the clock before a blocking row lock, while `_check` captured it before canonical SQL. Both could spend an expired lease. Used behavioral TDD and verification-before-completion guidance; no helpers/reviewers/subagents were dispatched. Only the runner, its tests and this report are amended. Root-owned documents, CI, migrations, models and provider adapters are untouched by this correction.

Minimal correction:

- Refresh the lease clock after acquiring the finalizer's `FOR UPDATE` lock, and again after canonical validation/assessment immediately before authorizing the owned job transition. Expiry wins over REVIEW, REJECT, RETRY and BLOCKED; the immutable LOST_LEASE receipt retains known usage without overwriting the job's ownership, state, attempt, error or lease.
- Refresh ownership after canonical resolution in both pre-IO checks, then compare expiry again at the closed-session boundary immediately before injected factory/classifier IO. SQL and session-close latency cannot authorize IO using an earlier clock instant.
- Preserve exact existing-receipt replay before expiry fencing. Completed REVIEW and LOST_LEASE receipts replay without another factory/classify call or another receipt.

### Actual behavioral RED before the production correction

The newly added SQLite regressions ran against unchanged c9 production source. Arguments, using the native command contract above:

```text
tests/test_durable_editorial_runner.py,-q,-k,expiry_during_canonical or expiry_at_closed or completed_receipt_replays
--basetemp,$run/temp,-o,cache_dir=$run/cache
```

Directory `D:/Codex-Recovery/content-studio-20261008/editorial-execution-fix1-red-23a6c6bfdd284222a9a70b4b3bca0028`, log `native.log`, native exit **1**, **5 failed, 1 passed, 124 deselected in 2.16s**. Failures observed unwanted factory IO, unwanted classify IO, and a persisted REVIEW instead of LOST_LEASE when canonical SQL advanced the injected clock to exact lease expiry. There were no collection/setup errors, skips or xfails. The replay control passed before the correction and remains passing. Original raw log retained, SHA256 `E0DF0FA5CA438E8677736DA1170FA3B98DB1BCA545E794C57D060A54A13B11B5`.

### Amended focused and covering GREEN

Focused arguments exactly match RED. Directory `D:/Codex-Recovery/content-studio-20261008/editorial-execution-fix1-green-3b5600e097ce4f1789d35aeddbbc368d`, log `native.log`, native exit **0**, **6 passed, 124 deselected in 1.97s**. SHA256 `F33915958E2D047AAC6CA18D7256CBB9F1B838AF17EA6F6F615B82343A6EFA03`.

Covering arguments:

```text
tests/test_durable_editorial_runner.py,tests/test_editorial_classifier_adapters.py,tests/test_editorial_classification.py,-q,-ra
--basetemp,$run/temp,-o,cache_dir=$run/cache
```

Directory `D:/Codex-Recovery/content-studio-20261008/editorial-execution-fix1-covering-0cde7959114b46c7996fbb47aeda40c4`, log `native.log`, exec session37358, started `2026-10-12T20:21:48.2917096Z`. Native exit **0**, **326 passed, 5 skipped in 41.65s**, no warnings/errors. SHA256 `7B7BCFA7662E202BF9D2BDABC1EF26FD33A02A604A0B1D355729F639BEC074D1`. All runner lease/late/replay/rollback/retry/evidence cases and unchanged adapter/pure-contract cases were covered. The five SQLite skips are the existing actual-PG competing-claimants case and four new actual-PG finalizer row-lock cases, not claimed as local passes.

Added deterministic regressions:

- `test_expiry_during_canonical_sql_check_fences_io_and_finalization[factory,classify,finish]`: real canonical SQL listener advances the injected clock at first, second or final canonical validation; asserts LOST_LEASE, unchanged ownership and zero classify calls before IO.
- `test_expiry_at_closed_session_boundary_prevents_external_io[factory,classify]`: actual session close advances the injected clock after SQL; asserts zero classify calls and unchanged job ownership.
- `test_postgres_finalizer_waiting_on_row_lock_refreshes_lease_clock[review,reject,retry,blocked]`: independent transaction holds the real job row lock. An Event identifies the waiting finalizer, and a third connection confirms `pg_blocking_pids` names the holder before injected expiry and unchanged-row lock release. No sleeps or probabilistic scheduling. Asserts LOST_LEASE, unchanged job ownership, immutable exact claim/receipt, preserved known usage, no rewrite and no classify replay.
- `test_completed_receipt_replays_unchanged_after_lease_expiry`: exact completed REVIEW replays unchanged after expiry, with one factory, one classify and one receipt total.

### Amended static checks and frozen hashes

Directory `D:/Codex-Recovery/content-studio-20261008/editorial-execution-fix1-static-86221ca314bb47d983e0ca1dbb6b01ae`. Commands ran from `backend`; all native exits **0**:

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check src/newsflow/services/durable_editorial_runner.py tests/test_durable_editorial_runner.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check src/newsflow/services/durable_editorial_runner.py tests/test_durable_editorial_runner.py
$env:PYTHONPYCACHEPREFIX="$run/pycache"
python -m compileall -q src/newsflow/services/durable_editorial_runner.py tests/test_durable_editorial_runner.py
Remove-Item Env:PYTHONPYCACHEPREFIX
git diff --check -- src/newsflow/services/durable_editorial_runner.py tests/test_durable_editorial_runner.py
```

- `ruff.log`: `All checks passed!`, SHA256 `A4443AFDCFB6D7363ADB285762515CCF7CF50473B1A05C20C1A50F6BED4D26B0`.
- `format.log`: `2 files already formatted`, SHA256 `97D85B4B6C185A05396E2D09A3C304FF0F7CC77F8B7B7BB7989EC6CD875B3898`.
- `compile.log`: empty success, SHA256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.
- `diff.log`: only existing LF-to-CRLF working-copy notices, SHA256 `4FAECEC443BAB77D43FF9FEAC88EB079D81D2A4443116761A842ED9AB340FE53`.

Amended raw SHA256, frozen before covering/independent PG execution and rechecked after local covering/static checks:

| File | SHA256 |
| --- | --- |
| `backend/src/newsflow/services/durable_editorial_runner.py` | `A7327B9E5F7251ABF42DAD35760E8FC7F902C0925CE505ADB17DADA1451ACC3E` |
| `backend/tests/test_durable_editorial_runner.py` | `990369208D2D04CC461314A09E904CD98B918A22571BD041EE99E2FB60CBCAC7` |

No other iteration failures occurred in correction round 1. No additional whole backend suite, Docker/browser/live-provider run or actual PostgreSQL operation was performed by this implementer. Original c9 full-suite/PG/restart evidence above remains historical and is not promoted to full-tested final amended bytes. Exact amended full-suite and CI evidence remain parent-owned.

### Independent actual Windows PostgreSQL fix regression gate (root)

Root executed the exact new selection `-k 'expiry_during_canonical or expiry_at_closed or postgres_finalizer_waiting or completed_receipt_replays'` against its strict migrated synthetic PostgreSQL target. Root reported native exit **0**, **10 passed, 120 deselected in 7.58s**, no skips; all four real independent held-row finalizer blocking regressions executed. Frozen runner/test hashes above matched before and after. Native log `D:/Codex-Recovery/content-studio-20261008/editorial-execution-fix1-root-pg-26790f6ce24b4e798dce486945f6f4cc/native.log`, SHA256 `1B06422483B2383334D67413BCA2D277C6896A774AF4774A9A297272F38855C5`.

Root validated its exact existing synthetic container and baseline1624/maxOID1232970; the gate created only ten fresh UUID namespaces, reaching1634/maxOID1241341, and restored its environment in finally. This evidence is explicitly attributed to root, not this implementer's commands. Previous original-source restart manifests remain historical/read-only; this fix gate is not a new restart or full-backend suite claim.

### Correction self-review and limitations

Re-read the full scoped production/test diff after GREEN. Confirmed clock refresh after blocking SQL and canonical resolution, explicit closed-session IO fences, expiry overriding every otherwise-owned completion, unchanged immutable receipt replay, retained known usage and no stale job overwrite. New SQL and session-close tests fail behaviorally against original c9; independent actual-PG row-lock tests passed on root's strict migrated target. No migration/schema/permissions/provider/worker scope expansion. All permissions remain false; diagnostic outcomes cannot approve, rewrite or publish. Source/tests stayed frozen throughout local covering and root's actual-PG gate; only report completion followed those results. Correction round 1 has no outstanding implementation concern; independent re-review remains parent-owned.
