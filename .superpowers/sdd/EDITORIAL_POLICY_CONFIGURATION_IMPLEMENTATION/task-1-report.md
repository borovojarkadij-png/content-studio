# Task 1 implementation evidence

Scope: INTERNAL diagnostic singleton configuration only. No API, UI, operator authentication, activation, provider construction, environment/credential access, live calls, model availability/qualification claim, schema migration, flag change, or PHASE completion.

Repository verified before edits: origin `https://github.com/borovojarkadij-png/content-studio.git`, branch `codex/dark-navy-ui`, base/HEAD `56f48999890db57c0b9c0741cad453eb23c35f0a`. Initial working tree was clean. Root owns all subsequent changes outside the four paths listed below. No helper agents, review dispatch, operational database access, secret reads, cleanup, or push performed by this implementer.

Read the exact Task 1 brief, implementer prompt, TDD skill and writing-good-tests reference, NewsFlow data/runtime skills, and verification-before-completion skill. Applied TDD through migrated synthetic fixtures and kept corrupt state visible. All tests use accepted admission/ingestion/runner components and injected synthetic external boundaries.

Implemented:

- Pristine-session refusal before SQL for active transactions and pending objects; independent owned transactions close before returning snapshots.
- Pure missing read, fresh populated identity-map reads, exact diagnostic DTO, detached deep JSON snapshots, strict existing/request validation through accepted admission constraints, and raw SQLite Boolean corruption detection.
- Exact stored-value ETags; sorted content-derived versions; retained legacy no-op and enabled-only body/version semantics; deterministic restored content versions.
- Locked singleton fresh-read and conditional SQL update matching every captured value plus SQL-captured exact JSON text. No JSON equality operator, reconstructed storage whitespace, retry, or overwrite on conflict.
- Singleton PK-only create arbitration after rollback and verification of a valid competing row. Unrelated policy/outbox/commit IntegrityError propagates and rolls back; no false acknowledgement.
- Atomic metadata-only outbox with fresh operation UUIDs, including repeated enable cycles. Configuration creates no diagnostic/rewrite work and changes no existing decisions or diagnostic histories.
- CI change appends only `tests/test_editorial_policy_configuration.py` to the existing strict migrated PostgreSQL command; all previous commands/tests and the 20-minute timeout remain exact.

Owned paths:

1. `backend/src/newsflow/services/editorial_policy_configuration.py`
2. `backend/tests/test_editorial_policy_configuration.py`
3. `.github/workflows/ci.yml`
4. `.superpowers/sdd/EDITORIAL_POLICY_CONFIGURATION_IMPLEMENTATION/task-1-report.md`

## Evidence location and runtime

Unique retained evidence directory (no cleanup): `D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396`.

Python executable: system Python 3.12 at `C:/Users/borov/AppData/Local/Programs/Python/Python312/python.exe`. Every test command explicitly prepended `D:/Codex-Recovery/content-studio-20261008/telethon-145` to `sys.path` before importing Telethon or pytest, then printed actual Telethon version and file. Actual output: `Telethon 1.45.0 D:\Codex-Recovery\content-studio-20261008/telethon-145\telethon\__init__.py`. This avoids the system Telethon 1.44 installation.

All pytest commands ran from the backend cwd:
`C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend`.

Native pytest status was read immediately from `$LASTEXITCODE`, not inferred from the PowerShell pipeline status. Early shells end with `Write-Output`, so their shell exit is zero even when printed native pytest exit is one. The full gate explicitly exits with captured native pytest status and appends that native status to its log.

## Behavioral RED and iteration

Before adding production code, the test file had a deliberately unsafe temporary in-test seam: it loaded the actual migrated singleton, assigned the stale supplied model, and committed while ignoring expected ETag. The test expected a conflict and asserted the original persisted model. This tests missing stale-write protection on real storage, not an absent import. The seam was removed when the real service was added.

Exact RED command:

```powershell
$taskLogs = 'D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-' + [guid]::NewGuid().ToString('N'); New-Item -ItemType Directory -Path $taskLogs | Out-Null; $taskLogs; python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon, pytest; print('Telethon', telethon.__version__, telethon.__file__); raise SystemExit(pytest.main(['tests/test_editorial_policy_configuration.py', '-q', '--basetemp', sys.argv[1]]))" "$taskLogs/tmp-red" 2>&1 | Tee-Object -FilePath "$taskLogs/red.log"; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
```

Actual relevant raw output retained in `red.log`:

```text
E Failed: DID NOT RAISE <class 'test_editorial_policy_configuration.api.<locals>.Conflict'>
FAILED tests/test_editorial_policy_configuration.py::test_stale_configuration_cannot_overwrite_migrated_policy
1 failed in 0.66s
```

Actual separate tool-terminal output immediately after Tee: `NATIVE_EXIT=1`. The marker is not present inside `red.log`; the native result is retained in the tool-terminal transcript and quoted here.

After all contract tests and the real service were written, focused-1 exposed an unlabeled SQLAlchemy CAST expression result lookup (`NoSuchColumnError`): 90 failed, four skipped in 33.55s, native1. Labeled SQL projections fixed the result mapping. Focused-2: 88 passed, two failed, four skipped in 23.41s, native1. One failure was a hand-written fixture with incorrect Unicode codepoint sort order (`Ё` precedes `Е`); corrected the independent expected literal. The other revealed enabled-only updates serializing existing raw JSON, so a test's later whitespace mutation was no longer a mutation. Enabled-only SQL now writes just enabled and retains exact raw JSON.

Before that fix and the raw-Boolean guard, ran the focused behavior RED:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon, pytest; print('Telethon', telethon.__version__, telethon.__file__); raise SystemExit(pytest.main(['tests/test_editorial_policy_configuration.py', '-q', '-k', 'corrupt_raw_boolean or sql_cas', '--tb=short', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/tmp-red-edges']))" 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/red-edges.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
```

Actual raw result (`red-edges.log`): both raw-Boolean2 validation and same-ETag raw-JSON CAS tests `DID NOT RAISE`; two failed, 93 deselected in 1.01s, native1. The Boolean test first demonstrated that SQLAlchemy returns Python True for actual persisted integer2, then expected the service to reject it. SQL CAST raw Boolean validation fixed this proven issue.

Focused command template (actual earlier focused attempts use this same command with the exact option/path differences below):

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon, pytest; print('Telethon', telethon.__version__, telethon.__file__); raise SystemExit(pytest.main(['tests/test_editorial_policy_configuration.py', '-q', '--tb=short', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/tmp-focused-3']))" 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/focused-3.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
```

Focused-1 used `tmp-focused-1`, `focused-1.log`, and omitted `--tb=short`; focused-2 used `tmp-focused-2`, `focused-2.log`. Actual focused-3 GREEN: `91 passed, 4 skipped in 23.26s`, native0. Three skips are the PostgreSQL-only actual concurrency/lock cases; the fourth is the non-applicable policy-INSERT/update parameter combination. On PostgreSQL, the raw SQLite Boolean corruption test explicitly skips because PostgreSQL rejects non-Boolean storage.

## Targeted regressions

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon, pytest; print('Telethon', telethon.__version__, telethon.__file__); raise SystemExit(pytest.main(['tests/test_editorial_policy_configuration.py', 'tests/test_editorial_admission.py', 'tests/test_editorial_classifier_factory.py', 'tests/test_durable_editorial_runner.py', '-q', '--tb=short', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/tmp-regressions']))" 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/regressions.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
```

Actual raw tail in regressions.log: `368 passed, 9 skipped in 94.83s (0:01:34)`. Separate actual tool-terminal native marker: `NATIVE_EXIT=0` (outside Tee, not in that raw file). Skips are explicit existing PostgreSQL cases plus the new skips described above. No failures or warnings. Synthetic stale disable/model/entity changes blocked fresh factory/runner before decrypt/construction, held original REJECT/manual decisions, left RewriteJob count and rewrite calls zero, and created no work from the configuration operation.

## Static checks before freeze

Ruff executable: `D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe`, actual `ruff 0.17.0`.

Initial focused lint found dict literal/style issues and two deliberate thread exception transfers; resolved before freeze. The worker exception capture explicitly transfers unexpected thread failures into main-thread assertions, rather than losing them in daemon output. Ran safe Ruff fix for nested with statements and formatter on the two owned Python files; no other files formatted.

Exact final lint/format commands from backend cwd:

```powershell
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe --version
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check src tests alembic ../scripts/ui_fixture_api.py ../scripts/docker_persistence_probe.py ../scripts/docker_rewrite_recovery_probe.py ../scripts/docker_source_guard_probe.py ../scripts/docker_semantic_probe.py ../scripts/docker_media_probe.py ../scripts/docker_ingestion_probe.py ../scripts/docker_telegram_health_probe.py ../scripts/docker_telegram_peer_probe.py ../scripts/docker_mapping_filter_probe.py ../scripts/docker_donor_resolution_probe.py ../scripts/docker_source_photo_probe.py ../scripts/docker_publication_probe.py ../scripts/docker_channel_sync_probe.py ../scripts/docker_rewrite_sync_wait_probe.py ../scripts/docker_admission_probe.py ../scripts/evaluate_editorial_contract.py ../scripts/evaluate_editorial_model.py 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/lint.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check ../scripts/ui_illustration_fixture_api.py 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/lint-illustration.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check src/newsflow/services/editorial_policy_configuration.py tests/test_editorial_policy_configuration.py 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/format.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
python -m compileall -q src tests 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/compile.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
python -c "import pathlib, subprocess, yaml; path='../.github/workflows/ci.yml'; content=pathlib.Path(path).read_text(); baseline=subprocess.check_output(['git','show','56f48999890db57c0b9c0741cad453eb23c35f0a:.github/workflows/ci.yml'], text=True); assert content == baseline.replace('tests/test_editorial_history.py -q', 'tests/test_editorial_history.py tests/test_editorial_policy_configuration.py -q'); doc=yaml.safe_load(content); assert doc['jobs']['unattended-postgres']['timeout-minutes']==20; print('YAML parsed; CI baseline differs only by appended new strict PostgreSQL test path; 20-minute limit preserved')" 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/yaml.log; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
git diff --check -- ../.github/workflows/ci.yml src/newsflow/services/editorial_policy_configuration.py tests/test_editorial_policy_configuration.py; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
```

Raw results: full lint `All checks passed!`, separate illustration lint `All checks passed!`, format `2 files already formatted`, compile silent, YAML `YAML parsed; CI baseline differs only by appended new strict PostgreSQL test path; 20-minute limit preserved`, diff check no whitespace error. Every native exit0. Git prints its existing LF-to-CRLF warning for CI; no unrelated normalization performed.

## Freeze and terminal gates

Frozen after targeted and static checks, before the single full suite and root-owned actual Windows PostgreSQL gate. Exact command from repository root:

```powershell
Get-FileHash -Algorithm SHA256 backend/src/newsflow/services/editorial_policy_configuration.py, backend/tests/test_editorial_policy_configuration.py, .github/workflows/ci.yml | Format-List Path,Hash | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/frozen-hashes.log
```

SHA256:

```text
backend/src/newsflow/services/editorial_policy_configuration.py FDB4C4CC50920D43E1A22E322CDEB66D0165AA518B3383F9250439DCEA8D0303
backend/tests/test_editorial_policy_configuration.py 23AA4060E9F52FAFC6369040E5E1C743A0D3BE79D84D489F6D22C78A6B575115
.github/workflows/ci.yml 0874A52835D234315BF8BC8D1A829C8F63BB9D3E206A9DD6F95D51ED2244C68D
```

Sent all three hashes and explicit freeze to root before starting full. Only this report may change while gates live.

Exact ONE full backend command:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon, pytest; print('Telethon', telethon.__version__, telethon.__file__); raise SystemExit(pytest.main(['-q', '--tb=short', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/tmp-full']))" 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/full.log; $taskNative = $LASTEXITCODE; Write-Output "NATIVE_EXIT=$taskNative" | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/full.log -Append; exit $taskNative
```

Full result, post-gate hash validation, root-owned PostgreSQL outcome, final self-review, and commit evidence are appended at EOF when actually known. No terminal gate result is inferred from partial progress.

## Root-owned actual Windows PostgreSQL evidence

Root performed the actual strict migrated new-file PostgreSQL gate after freeze and separate ownership validation; this implementer did not connect to that database. Reported root session1460: native0, `93 passed, 2 skipped in 53.41s`. Both skips are explicit and non-applicable on this target: SQLite raw-Boolean corruption (PostgreSQL refuses that storage value), and policy-INSERT/update parameter combination. All three PostgreSQL locking/concurrency cases ran and passed.

Root verified exact synthetic container/sole-volume/loopback ownership before the gate, created only 95 fresh UUID schemas, retained all fixture evidence, and restored the prior database URL in finally. Root-reported baseline `1785 schemas|maxOID1372163` became `1880 schemas|maxOID1451681`; all three frozen source/test/CI hashes were unchanged before/after. No old Docker/UI/recovery gate repeated.

Read and independently hashed the retained result files:

```powershell
Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-policy-root-pg-286c57f6fe874862903deff524648e6c/native.log -Tail 12
Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-policy-root-pg-286c57f6fe874862903deff524648e6c/exit.log
Get-FileHash -Algorithm SHA256 D:/Codex-Recovery/content-studio-20261008/editorial-policy-root-pg-286c57f6fe874862903deff524648e6c/native.log
```

Actual raw evidence:

```text
Telethon 1.45.0 D:\Codex-Recovery\content-studio-20261008/telethon-145\telethon\__init__.py
SKIPPED [1] tests\test_editorial_policy_configuration.py:429: SQLite raw Boolean corruption; PostgreSQL rejects non-Boolean storage
SKIPPED [1] tests\test_editorial_policy_configuration.py:468: policy INSERT applies only to create
93 passed, 2 skipped in 53.41s
PYTEST_NATIVE_EXIT=0
native.log SHA256 036CC27F404481137EE6425C859D8895576D1F011D58CA64ADF0C75BBEFE5200
```

The full root-owned PG invocation, ownership details, schema inventory, and evaluator-CI tracking belong to the controller's verification report; this report makes no claim that the implementer ran or repeated them.

## Final full result, freeze verification, and self-review

The ONE full backend run completed from backend cwd using the exact full command above. Actual raw tail inside `full.log` (this command appends the captured native marker):

```text
..........................................                               [100%]
2835 passed, 15 skipped in 452.29s (0:07:32)
NATIVE_EXIT=0
```

The command's final shell exit was also0. No failures or warnings. Fifteen skips are explicit conditional cases; the new file contributes three local PostgreSQL lock/concurrency skips and one non-applicable policy-INSERT parameter combination. They are not counted as passes. Actual root PostgreSQL verification above exercised the skipped new lock/concurrency cases successfully.

After full completion, ran from repository root:

```powershell
Get-FileHash -Algorithm SHA256 backend/src/newsflow/services/editorial_policy_configuration.py, backend/tests/test_editorial_policy_configuration.py, .github/workflows/ci.yml | Format-List Path,Hash | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/post-full-hashes.log
git diff --check -- .github/workflows/ci.yml backend/src/newsflow/services/editorial_policy_configuration.py backend/tests/test_editorial_policy_configuration.py .superpowers/sdd/EDITORIAL_POLICY_CONFIGURATION_IMPLEMENTATION/task-1-report.md; Write-Output "NATIVE_EXIT=$LASTEXITCODE"
git diff --cached --name-only
```

Actual hashes match all three frozen values exactly. Diff native0; index empty before staging. Root independently verified the same frozen hashes around actual PostgreSQL. Only this report changed during the terminal gates.

Read the complete new service, the concurrency and pipeline tests, and the exact CI diff for self-review. Confirmed no missing configuration reset, stale overwrite, provider construction, secret access, activation or diagnostic work creation; no-op/legacy identity and metadata-only outbox behavior remain bounded to the brief. Rechecked error catch scope: only the singleton policy primary-key INSERT can enter verified create arbitration; unrelated storage errors escape and roll back. Confirmed disabled/content-changed bindings block through real resolver/factory/runner boundaries and original REJECT/manual decisions remain held. Confirmed original CI file differs only by the appended path. No known correctness concerns remain from self-review. Independent review belongs to the controller; no implementer reviewer dispatch performed.

Retained raw evidence SHA256, read after completion:

```text
red.log 0D9C6566660EDDDFCD88C89DCAA8850A7384041937A0D6C5240ECFD3889E6789
red-edges.log D65957AA77B7A7AECB25E81884D29540D4436FAA7C6486839C602456DDC15FDB
regressions.log A8CD131DA06B54CBB796AE6A79FF1FD84344419C2F9D2C941B86ED2121498FBD
full.log F2919AF3DDE4EAC0A0E8DE2B926394018365C94938C6E51F6FE6E22A89D5EF68
```

Commit only the four owned paths using the commands below; root owns unrelated docs and evaluator-CI tracking. The final commit identity is returned in the implementer completion message, avoiding a self-referential commit hash inside its own report. No push.

```powershell
git add -- backend/src/newsflow/services/editorial_policy_configuration.py backend/tests/test_editorial_policy_configuration.py .github/workflows/ci.yml
git add --force -- .superpowers/sdd/EDITORIAL_POLICY_CONFIGURATION_IMPLEMENTATION/task-1-report.md
git diff --cached --name-only
git diff --cached --check
git commit -m "feat: persist internal diagnostic editorial policy configuration" -- backend/src/newsflow/services/editorial_policy_configuration.py backend/tests/test_editorial_policy_configuration.py .github/workflows/ci.yml .superpowers/sdd/EDITORIAL_POLICY_CONFIGURATION_IMPLEMENTATION/task-1-report.md
git show --stat --oneline HEAD
git status --short
```

Limits: no dedicated operator auth/API/UI, live model availability benchmark/qualification, guarded PASS propagation, automatic activation, or PHASE1 completion is claimed. Those are deferred by the brief. All synthetic evidence is retained; no operational user data or credentials were inspected or changed.
