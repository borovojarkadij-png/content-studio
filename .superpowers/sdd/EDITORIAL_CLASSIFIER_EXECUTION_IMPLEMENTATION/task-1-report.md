# Task 1: durable diagnostic classifier execution

Status: DONE. The frozen full backend suite and independently executed root-owned actual PostgreSQL runner/restart checks passed. No push was performed.

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

## Frozen full-suite and final provenance

Exactly one full suite started `2026-10-12T20:07:17.9092986Z`, exec session31926, directory `editorial-execution-full-6d5a38802c234c85baab8f2db0d707e7`, arguments `-q,-ra,--basetemp,$run/temp,-o,cache_dir=$run/cache`. Native exit **0**, **2462 passed, 7 skipped in 444.14s (0:07:24)**; no warnings/errors. Raw native.log SHA256 `084A9BF09531B413BE6BEE5DF7E77F75BE3D000D1CA28B1AAB34E1B12E00AC36`. Root was notified before independent PG testing; no source/test/migration/CI edits after this freeze.

The seven local skips are explicit PostgreSQL-only controls: one new runner competing-claimants proof (independently executed and passed in root's actual PG120 gate), one existing real TRUNCATE check in illustration storage, and five existing planner/media PostgreSQL concurrency opt-ins. Skips are not represented as passes. No browser or Docker suite was repeated.

Raw SHA256 of the full-tested and final owned files (paths relative to repository), rechecked unchanged during the run and at finalization. The full-tested production/test/migration/CI bytes are exactly the final committed source/test/migration/CI bytes; only this report was completed after the freeze:

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
