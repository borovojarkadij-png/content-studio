# Editorial operator API implementation report

Status: DONE. Implementation, local verification and root-owned strict PostgreSQL
verification are complete. The implementation commit SHA is returned in the
handoff rather than embedded self-referentially in its own report.

## Scope and implementation

Starting HEAD `a24c2265335982dc9ea0bfd86344f853d2adb945`, branch
`codex/dark-navy-ui`, origin
`https://github.com/borovojarkadij-png/content-studio.git` were confirmed before
changes. No push, merge, real provider, Docker, PostgreSQL connection, operational
SQL, host credential read, dependency upgrade or cleanup was performed by this
implementer. Root owns PostgreSQL verification and all other documents.

Implemented dedicated default-disabled editorial operator authentication, a
strict GET/PUT `/api/settings/editorial-policy` API, and route-exact private
validation/no-store responses. Actor identity comes only from the configured
operator principal. The existing configuration service is called directly with
pristine request sessions and was not modified. Its DTO and commit boundary are
preserved. Configuration creates only its existing metadata outbox audit;
diagnostic-only remains true and qualification/execution/rewrite authority remain
false.

Extracted the existing reviewer's bounded file and constant-time bearer header
mechanics into a shared environment-free helper. Reviewer environment, public
principal/errors and HTTP semantics are retained. Operator credential files
exclude effective stripped master and actual reviewer paths, resolved aliases
and hardlinks without reading those credentials. Separate files do not establish
different token bytes, explicitly exercised by tests.

API errors classify stale ETags as 409, strict/service/persisted JSON corruption as
private 422, and missing migration/storage/SQL failures as private 503. Only
`JSONDecodeError` is additionally caught for malformed SQLite JSON hydration;
unrelated storage exceptions are not converted to conflict or success. No input,
SQL, path, alias, token or exception detail is returned by these handlers.

Owned implementation files:

- `backend/src/newsflow/security/bounded_bearer.py`
- `backend/src/newsflow/security/illustration_reviewer.py`
- `backend/src/newsflow/security/editorial_operator.py`
- `backend/src/newsflow/api/editorial_policy.py`
- `backend/src/newsflow/app.py`
- `backend/tests/test_editorial_policy_api.py`
- `.github/workflows/ci.yml`
- This report only under `.superpowers/sdd/EDITORIAL_OPERATOR_API_IMPLEMENTATION/`.

CI change is exactly one appended `tests/test_editorial_policy_api.py` in the
existing strict migrated PostgreSQL command. The existing reviewer API test was
already present and is retained once. All other commands and the 20-minute
timeout remain identical to starting HEAD.

## Runtime and evidence conventions

Workspace: `C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2`.
Every pytest invocation ran from its `backend` directory using system Python
`3.12.10` and explicitly prepended
`D:/Codex-Recovery/content-studio-20261008/telethon-145` before importing Telethon,
printed `TELETHON 1.45.0`, and asserted that exact version. No tests used the
system Telethon 1.44 installation.

Unique retained evidence root (abbreviated `E` below):
`D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f`.
Every pytest run has a fresh named temp/cache directory beneath E. No temp/log
directories were cleaned or reused. Logs are redirected directly, followed
immediately by `$taskExit = $LASTEXITCODE`; the shell prints its native marker
after reading the log and exits with that same value. Native markers are terminal
evidence, not claimed as bytes inside raw log files.

## TDD and failed iterations (preserved)

Initial behavioral RED command, backend cwd:

```powershell
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_editorial_policy_api.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/red-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/red-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/red.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/red.log; Write-Output "NATIVE_EXIT=$taskExit"; exit $taskExit
```

Observed real TestClient behavior: GET returned 404, assertion required 503.
`1 failed in 0.42s`, native exit 1. This is behavioral RED before implementation,
not an absent import. Log SHA256:
`9F66392B1D1E51D5C5AAD89A29B46D3D930AF1710FC254071BE034E48A980668`.

First implementation iteration command, backend cwd:

```powershell
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_editorial_policy_api.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/iteration1-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/iteration1-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/iteration1.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/iteration1.log; Write-Output "NATIVE_EXIT=$taskExit"; exit $taskExit
```

Result: `1 failed, 95 passed, 16 warnings in 12.33s`, native exit
1. The failure was test setup: Windows rejects an embedded NUL in an environment
variable before product authentication executes. This is not claimed as product
RED. Corrected it to exercise the bounded reader directly with the malformed
path. The 16 real warnings were TestClient per-request cookies deprecations;
corrected by configuring cookies on the client itself, without suppression.
Raw `iteration1.log` SHA256:
`F56B3D6246F65A05FEE765AA5A1F2418960AF7F12CB3296E74A4F6913C92128A`.

Additional product RED command, backend cwd:

```powershell
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_editorial_policy_api.py','-k','malformed_stored_json','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/corrupt-red-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/corrupt-red-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/corrupt-red.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/corrupt-red.log -Tail 35; Write-Output "NATIVE_EXIT=$taskExit"; exit $taskExit
```

Observed SQLAlchemy decoding malformed persisted SQLite JSON raised
`json.decoder.JSONDecodeError` out of TestClient. Expected private 422.
`1 failed, 97 deselected in 1.13s`, native exit 1. Corrected only the HTTP
boundary; existing accepted configuration service untouched. Log SHA256:
`09EB9D858828C3190D2CD689E9547E320E535F497EFE2030D64AC21121818621`.

First full CI lint iteration failed with exactly one `I001` import-order error in
the new test file, native exit 1. Fixed the import ordering. Retained `lint.log`
SHA256 `4954FB9A58A990014C20A6E6369041EE7081C0F38D747DD4ADB3EB3DC1B4844A`.

## Verification results

Focused seven-file GREEN command, backend cwd:

```powershell
python -c "import os,sys; [os.environ.pop(k,None) for k in ('NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE','NEWSFLOW_EDITORIAL_OPERATOR_ID','NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE','NEWSFLOW_ILLUSTRATION_REVIEWER_ID','NEWSFLOW_MASTER_KEY_FILE','NEWSFLOW_UNATTENDED_POSTGRES_URL','NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL')]; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_editorial_policy_api.py','tests/test_editorial_policy_configuration.py','tests/test_illustration_review_api.py','tests/test_illustration_review_storage.py','tests/test_editorial_admission.py','tests/test_editorial_classifier_factory.py','tests/test_durable_editorial_runner.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/focused-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/focused-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/focused.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/focused.log -Tail 60; Write-Output "NATIVE_EXIT=$taskExit"; exit $taskExit
```

Result: `600 passed, 10 skipped in 158.57s (0:02:38)`, native exit 0, no warnings.
This run did not use `-rs`. The ten skips are attributed from the executed
SQLite fixture and existing test contracts/parameterization, not a fabricated
raw pytest skip-reason transcript:

| Existing test contract | Cases | Literal skip reason |
| --- | ---: | --- |
| `test_storage_failures_roll_back_policy_and_event_without_acknowledgement`, create=False / operation=policy_insert | 1 | policy INSERT applies only to create |
| `test_postgres_two_connection_create_and_stale_update_arbitration`, create=True/False | 2 | strict opt-in PostgreSQL: actual singleton locking/unique arbitration |
| `test_postgres_existing_singleton_lock_blocks_other_connection_until_release` | 1 | strict opt-in PostgreSQL: actual row lock |
| `test_postgresql_truncate_cannot_clear_owned_review_history` | 1 | Real TRUNCATE requires the strict isolated PostgreSQL CI namespace |
| `test_two_postgres_claimants_cannot_own_the_same_attempt` | 1 | Actual strict migrated PostgreSQL lock proof is root-owned |
| `test_postgres_finalizer_waiting_on_row_lock_refreshes_lease_clock`, completion=review/reject/retry/blocked | 4 | Actual strict migrated PostgreSQL finalizer row-lock proof is root-owned |

These skips are not passes and establish no PostgreSQL lock/immutability proof.
Both synthetic symlink cases actually passed on this Windows host. The new
API's raw malformed JSON case also passed on SQLite; PostgreSQL rejects that
corruption before persistence, so it has a separately declared PostgreSQL-only
skip when root runs the strict gate.

Final API-only run after self-review added explicit reopened zero-work
assertions used this exact command, backend cwd:

```powershell
python -c "import os,sys; [os.environ.pop(k,None) for k in ('NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE','NEWSFLOW_EDITORIAL_OPERATOR_ID','NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE','NEWSFLOW_ILLUSTRATION_REVIEWER_ID','NEWSFLOW_MASTER_KEY_FILE','NEWSFLOW_UNATTENDED_POSTGRES_URL','NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL')]; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_editorial_policy_api.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/api-final-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/api-final-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/api-final.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/api-final.log; Write-Output "NATIVE_EXIT=$taskExit"; exit $taskExit
```

That command redirected to `E/api-final.log`, read the whole log rather than
`-Tail 60`, captured immediate native exit 0, and reported `98 passed in 12.68s`
without warnings or skips.

Focused log SHA256:
`B8D17557D9DBEE20761DB70F1BD33530B75C80E7140BEFA6783EF7E9F9462B90`.
Final API-only log SHA256:
`B9D170BE81D068A63618C0A075299514994CB704963D2585BC2BAE98BBE230BB`.

Full CI lint, backend cwd (both `lint-green` and final `lint-freeze` executions):

```powershell
D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check src tests alembic ../scripts/ui_fixture_api.py ../scripts/docker_persistence_probe.py ../scripts/docker_rewrite_recovery_probe.py ../scripts/docker_source_guard_probe.py ../scripts/docker_semantic_probe.py ../scripts/docker_media_probe.py ../scripts/docker_ingestion_probe.py ../scripts/docker_telegram_health_probe.py ../scripts/docker_telegram_peer_probe.py ../scripts/docker_mapping_filter_probe.py ../scripts/docker_donor_resolution_probe.py ../scripts/docker_source_photo_probe.py ../scripts/docker_publication_probe.py ../scripts/docker_channel_sync_probe.py ../scripts/docker_rewrite_sync_wait_probe.py ../scripts/docker_admission_probe.py ../scripts/evaluate_editorial_contract.py ../scripts/evaluate_editorial_model.py ../scripts/ui_illustration_fixture_api.py --cache-dir D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/ruff-freeze-cache *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/lint-freeze.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/lint-freeze.log; Write-Output "LINT_NATIVE_EXIT=$taskExit"; exit $taskExit
```

`ruff --version` confirmed `ruff 0.17.0`. Both GREEN lint executions reported
`All checks passed!`, native 0. The additional final lint was justified by the
new explicit zero-work assertions before FREEZE. Initial successful lint log
SHA256 `A4443AFDCFB6D7363ADB285762515CCF7CF50473B1A05C20C1A50F6BED4D26B0`.
Final pre-FREEZE lint log has the same SHA256 and contents.

Changed formatting, workspace cwd:

```powershell
D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check backend/src/newsflow/security/bounded_bearer.py backend/src/newsflow/security/editorial_operator.py backend/src/newsflow/security/illustration_reviewer.py backend/src/newsflow/api/editorial_policy.py backend/src/newsflow/app.py backend/tests/test_editorial_policy_api.py; $taskExit = $LASTEXITCODE; Write-Output "FORMAT_NATIVE_EXIT=$taskExit"; exit $taskExit
```

`6 files already formatted`, native 0. Earlier formatting mutations were only
the same command without `--check`, before FREEZE (3 files formatted initially,
then 1 test file formatted after a further test addition; remaining unchanged).

Compile/exact CI/YAML/timeout/unchanged-service check, workspace cwd:

```powershell
python -c "import pathlib,py_compile,subprocess,yaml; root=pathlib.Path('.'); changed=['backend/src/newsflow/security/bounded_bearer.py','backend/src/newsflow/security/editorial_operator.py','backend/src/newsflow/security/illustration_reviewer.py','backend/src/newsflow/api/editorial_policy.py','backend/src/newsflow/app.py','backend/tests/test_editorial_policy_api.py']; output=pathlib.Path('D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/compile-freeze'); output.mkdir(); [py_compile.compile(str(root/p),cfile=str(output/(str(i)+'.pyc')),doraise=True) for i,p in enumerate(changed)]; current=(root/'.github/workflows/ci.yml').read_text(); original=subprocess.check_output(['git','show','a24c2265335982dc9ea0bfd86344f853d2adb945:.github/workflows/ci.yml'],text=True); assert current==original.replace('tests/test_editorial_policy_configuration.py -q','tests/test_editorial_policy_configuration.py tests/test_editorial_policy_api.py -q'); job=yaml.safe_load(current)['jobs']['unattended-postgres']; assert job['timeout-minutes']==20; command=next(s['run'] for s in job['steps'] if s.get('name')=='Migrated PostgreSQL vertical slice with original SQL reopen at every stage'); assert command.split().count('tests/test_editorial_policy_api.py')==1; assert command.split().count('tests/test_illustration_review_api.py')==1; subprocess.run(['git','diff','--exit-code','a24c2265335982dc9ea0bfd86344f853d2adb945','--','backend/src/newsflow/services/editorial_policy_configuration.py'],check=True); print('COMPILE 6 files PASS; CI exact append/YAML/timeout PASS; accepted service unchanged')"; $taskExit = $LASTEXITCODE; Write-Output "STATIC_NATIVE_EXIT=$taskExit"; exit $taskExit
```

All assertions passed, native 0. Initial compile used a fresh `compile` directory;
final compile used fresh `compile-freeze`. Compiled bytes live only under E.

Diff check (workspace cwd):

```powershell
git diff --check -- .github/workflows/ci.yml backend/src/newsflow/app.py backend/src/newsflow/security/illustration_reviewer.py; $taskExit = $LASTEXITCODE; Write-Output "DIFF_NATIVE_EXIT=$taskExit"; exit $taskExit
```

Native 0. Git warned existing auto-CRLF policy may normalize the CI/reviewer
files next time Git touches them; no whitespace errors were reported.

## FREEZE

One focused GREEN/static/FREEZE milestone was sent to root after the preceding
native results. Frozen working-file SHA256 values:

| File | SHA256 |
| --- | --- |
| `.github/workflows/ci.yml` | `143E01182E7F09639B160B91C5DE7B105E80A360F5DACE4402636E0C88C4AEB5` |
| `backend/src/newsflow/app.py` | `36D9B4BE70F95EC17A222DE649DDF5864789B3148EC8E277F7618B909B611042` |
| `backend/src/newsflow/security/illustration_reviewer.py` | `FA5875FC4E294E45B919B69925CE8F0DA1E9B5BCEC148FF016024E8C390B9AC2` |
| `backend/src/newsflow/security/bounded_bearer.py` | `40A5CF2340567476995121C8CE58EFEE637F092B96FB71A5F170B4E0DE99398C` |
| `backend/src/newsflow/security/editorial_operator.py` | `D4FB5D8C3B394E7C75741C4D6FC865BD90DB2A37D27D154A7D46B3A3B7B274B2` |
| `backend/src/newsflow/api/editorial_policy.py` | `E6C061BBD04F006059C348453556EADD63CF570AB9A14F5E3949DD3998343372` |
| `backend/tests/test_editorial_policy_api.py` | `852C390343FE2B28E4B3CC7C6B39CA74FBAD6C31AA27DAFD9B5289C0FA91F774` |

The report may be updated; source/test/CI bytes are frozen. Root was explicitly
notified it may run strict Windows PostgreSQL on these bytes, independently of
the implementer's full SQLite backend gate.

Full backend gate command, backend cwd:

```powershell
python -c "import os,sys; [os.environ.pop(k,None) for k in ('NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE','NEWSFLOW_EDITORIAL_OPERATOR_ID','NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE','NEWSFLOW_ILLUSTRATION_REVIEWER_ID','NEWSFLOW_MASTER_KEY_FILE','NEWSFLOW_UNATTENDED_POSTGRES_URL','NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL')]; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/full-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/full-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/full.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/full.log -Tail 80; Write-Output "NATIVE_EXIT=$taskExit"; exit $taskExit
```

Full result: `2933 passed, 15 skipped in 456.00s (0:07:36)`, native exit 0,
without warnings. Actual completion was unified-exec chunk `fc8b17`: the original
shell immediately captured native `$LASTEXITCODE`, printed `NATIVE_EXIT=0`
outside the raw log and exited with that same captured value; unified-exec
returned process `exit_code=0`. Root's request for a separate exit receipt arrived
after that process had already completed. A clearly labeled retrospective
receipt of this actual result was therefore written via `Tee-Object` to
`E/full-exit.log`, explicitly identifying its provenance and that it is not an
original in-log marker. It was not inferred from an expected outcome.

`E/full.log` SHA256:
`7E6D99C0FF7D7A9D7ACCE8A4765B2073C12FEAFFB6AFA9B48A111374AD28D433`.
`E/full-exit.log` SHA256:
`94F24E82DF62A6ECD51D8432739BE3193434C6BDB525DC82400B1C3291E8715A`.
After native full completion, all seven raw working-file SHA256 values were
asserted equal to the original FREEZE table above, native exit 0, before any
source amendment. The raw full log was not overwritten or given an invented
original native marker.

Full-suite skip attribution uses the actual final count plus source
contracts, because the command likewise lacks `-rs`. In addition to the focused
ten cases above, `test_planner_media_two_connection_lock_order` has two
legacy=True/False cases and
`test_automatic_pair_shared_policy_has_no_transaction_wide_cycle` has three
loop=reconciliation/ready/mixed cases. All five declare the literal reason
`Explicit isolated PostgreSQL concurrency opt-in not supplied` when this run's
explicitly cleared `NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL` is absent. No
PostgreSQL concurrency proof is inferred from them. These five plus the focused
ten exactly account for the actual fifteen skips; no other skips were observed.

## Post-FREEZE self-review ruling

While preserving frozen source bytes during the full gate, self-review identified
one absolute-response boundary gap: `call_next` could raise unexpectedly, after
which FastAPI's outer ServerErrorMiddleware would construct a generic 500
outside the no-store injection. Defined auth/validation/conflict/storage/framework
responses were already covered; an unexpected 500 also falls under the brief's
"all responses" requirement. Reported this before commit without editing frozen
files. Root ruled this is load-bearing privacy behavior, not a waiver.

Root instructed the implementer to finish and preserve the current full run,
then add a real unexpected-exception RED using
`TestClient(..., raise_server_exceptions=False)`, implement a minimal exact-route
private 500/no-store response, run amended new API plus unchanged reviewer API
and static checks, and send a new FREEZE. Root explicitly ruled not to run the
whole backend suite again solely for this narrow fix. The cost is a small
reversible middleware change for the protected route; unrelated route behavior
must remain unchanged. Final report will distinguish the full-suite source hash
generation from amended bytes and their covering verification. Root PostgreSQL
verification waits for refreeze. No PostgreSQL tests/writes had occurred when
this ruling was sent.

## Unexpected-error amendment: RED, GREEN and final FREEZE

After the full native result and post-full hash match, only the app middleware
and new API tests were thawed. Added real migrated SQL fault injection to GET and
PUT with `raise_server_exceptions=False`: GET fails during the policy query;
PUT fails during metadata outbox insertion after the policy mutation. Both must
return a private 500 with no-store and leave the original policy/ETag and empty
audit after rollback. Added a separate unrelated `/healthz` exception case that
must retain its pre-existing generic framework 500 and no cache header.

Behavioral RED command, backend cwd:

```powershell
python -c "import os,sys; [os.environ.pop(k,None) for k in ('NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE','NEWSFLOW_EDITORIAL_OPERATOR_ID','NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE','NEWSFLOW_ILLUSTRATION_REVIEWER_ID','NEWSFLOW_MASTER_KEY_FILE','NEWSFLOW_UNATTENDED_POSTGRES_URL','NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL')]; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_editorial_policy_api.py','-k','unexpected_policy_failure or unrelated_uncaught','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/unexpected-red-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/unexpected-red-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/unexpected-red.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/unexpected-red.log -Tail 65; Write-Output "NATIVE_EXIT=$taskExit" | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/unexpected-red-exit.log; exit $taskExit
```

Actual: `2 failed, 1 passed, 98 deselected in 1.16s`, native 1. Both protected-route
cases received 500 but failed with `KeyError: 'cache-control'`; the unrelated
framework case passed. This is behavior RED against real auth/dependency/service/
SQL, not an absent import. `unexpected-red.log` SHA256
`C391634B4CEE9FE411C5CC50ED21B9395700C959B0B76583ED10C812532E6E2F`;
direct captured `unexpected-red-exit.log` SHA256
`ED99E2E25075B2E604284BB280498EECF8FCF24193CE73838CF24FC56BE53C97`.

Minimal fix: bypass the middleware logic immediately for unrelated paths; catch
unexpected `Exception` only around the exact protected path/trailing slash and
return static JSON 500 with no-store. It neither grants success nor converts
unrelated storage errors to conflict. The boundary intentionally does not echo
or log exception details containing secrets. The first amended full lint run
reported `BLE001` at this deliberate catch-all privacy boundary (native 1),
preserved as `lint-amended.log` SHA256
`F3890AA266DC34B06E66DB8BC465E7DF36B2545BB5258DCE34DACD7207DBD560`.
Added a single line-local `noqa: BLE001` with the exact-route privacy rationale;
no global lint setting, assertion, warning or test was disabled. The exception
class remains deliberately broad to satisfy the root's all-response ruling.

Covering GREEN command, backend cwd:

```powershell
python -c "import os,sys; [os.environ.pop(k,None) for k in ('NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE','NEWSFLOW_EDITORIAL_OPERATOR_ID','NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE','NEWSFLOW_ILLUSTRATION_REVIEWER_ID','NEWSFLOW_MASTER_KEY_FILE','NEWSFLOW_UNATTENDED_POSTGRES_URL','NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL')]; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('TELETHON',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_editorial_policy_api.py','tests/test_illustration_review_api.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/amended-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/amended-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/amended.log; $taskExit = $LASTEXITCODE; Get-Content D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/amended.log -Tail 65; Write-Output "NATIVE_EXIT=$taskExit" | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/amended-exit.log; exit $taskExit
```

Actual: `182 passed in 43.66s`, native 0, no warnings/skips: 101 new API plus
81 unchanged reviewer API cases. `amended.log` SHA256
`223AECE1264A8B8B15925C844EF3A2436885EB679AB4263472B9D756EA1ED3E1`;
direct captured `amended-exit.log` SHA256
`50ECF457C4DD72B28211F3B189582BDBD20A9966CA052072D330C6008C9682E0`.

Amended static checks reran the exact full CI lint command above with
`--cache-dir E/ruff-amended-green-cache`, redirected to
`E/lint-amended-green.log`, and captured immediate native exit to
`E/lint-amended-green-exit.log` with Tee-Object before exiting with that same
value. It reported `All checks passed!`, native 0. Log SHA256 remains
`A4443AFDCFB6D7363ADB285762515CCF7CF50473B1A05C20C1A50F6BED4D26B0`.
The preceding amended failing lint used `E/ruff-amended-cache` and
`E/lint-amended.log`; it was not overwritten.

The six-file format check and compile/exact-CI/YAML/20-minute-timeout/unchanged-
service check above reran with fresh `E/compile-amended`, all native 0. After the
line-local lint rationale comment, final app/test formatting was checked again
(2 already formatted, native 0), and final app/test compilation reran:

```powershell
python -c "import pathlib,py_compile; output=pathlib.Path('D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/compile-amended-final'); output.mkdir(); [py_compile.compile(p,cfile=str(output/(str(i)+'.pyc')),doraise=True) for i,p in enumerate(['backend/src/newsflow/app.py','backend/tests/test_editorial_policy_api.py'])]; print('Amended final app/test compile PASS')"; $taskExit=$LASTEXITCODE; Write-Output "COMPILE_NATIVE_EXIT=$taskExit" | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-operator-15803badfe0d440fb8be80a2d3b7204f/compile-amended-final-exit.log; exit $taskExit
```

Native 0. Final changed tracked diff check likewise returned native 0, with
`E/diff-amended-exit.log` capturing its immediate native marker. The tests
execute the final behavior; the line-local comment has no runtime effect.

Final amended FREEZE was sent to root after those native results. Only two
working-file SHA256 values differ from the original FREEZE:

| File | Final SHA256 |
| --- | --- |
| `backend/src/newsflow/app.py` | `9A91DB4FC73C442DE01B70C2EBA948F160BD1730F0CC475379473C29D81486CA` |
| `backend/tests/test_editorial_policy_api.py` | `BCFC6E39395F56653101B62681568C5E8E00B4E733BE4A313D011B5528BBD67E` |

The other five final hashes are exactly their original FREEZE values. Source,
tests and CI remain frozen from this point. No second full backend suite was run,
per the explicit root ruling; the original full suite applies to the original
hash generation and the 182-case covering/static checks apply to the amended
behavior. Root's strict PostgreSQL new API plus existing reviewer API gate is
independent and not inferred from local evidence.

## Final self-review

Read the full owned implementation and diff against every brief requirement.
The accepted internal service is unchanged. Shared credential mechanics were
extracted, not duplicated; reviewer semantics are retained. Authentication
precedes session acquisition. Strict request models reject extra/nested authority
fields and coercion, while policy validation remains in the service. Responses
forward the service DTO and commit-before-success behavior. SQL faults roll back
and explicit retry commits exactly once. Existing protected REJECT decisions are
preserved; no rewrite or diagnostic execution is authorized. Provider creation,
decryption and rewrite are prohibited in new API fixtures. Metadata audits use
authenticated actor/hash only. Scoped expected and unexpected errors are private
and no-store; unrelated validation and exception behavior remains unchanged.

Self-review found and corrected the unexpected-500 gap above. No other
implementation findings remain. Existing files are intentionally changed only
within brief scope. Root-owned document changes and untracked root evidence are
preserved and will not be staged by this implementer. Commit validation and final
post-commit frozen-hash verification are reported to root in the handoff.

Pre-commit validation completed: `git add --` explicitly staged only the seven
owned code/test/CI paths; `git add -f --` force-added only this ignored report.
A Python assertion compared `git diff --cached --name-only` to that exact set of
eight paths and rechecked the authorized branch/origin (native 0).
`git diff --cached --check` returned native 0, covering newly added files as well
as tracked changes. The staged stat has exactly eight files. Root-owned dirty
and untracked documents remain unstaged. HEAD still matched the specified base
at this check. Root's actual corrected strict PostgreSQL native result is
attributed below before the owned implementation commit.

## Root-owned strict PostgreSQL receipt

Root independently performed the real strict migrated Windows PostgreSQL gate
on the final frozen bytes. The implementer did not connect to PostgreSQL or
Docker. Root's actual receipt: **native exit 0; 181 passed, 1 skipped in 108.47s**.
The single actual `-ra` skip is
`tests/test_editorial_policy_api.py:516`: `PostgreSQL JSON storage rejects malformed
JSON before persistence`. This skip is not counted as pass; the same raw JSON
corruption test passed on SQLite. All 101 new API plus 81 existing reviewer API
cases are accounted for as 181 pass and one structurally inapplicable PostgreSQL
case.

Root reports all seven corrected frozen hashes unchanged before/after this gate.
Root validated the exact fixture manifest/ownership/nonce/container/sole volume,
loopback health and baseline before I/O, used backend cwd with explicit Telethon
1.45.0 and process-local cleared/replaced authentication/SQL opt-in settings,
fresh owned UUID namespaces and fresh D: temp/cache directories. Native command
covered `tests/test_editorial_policy_api.py tests/test_illustration_review_api.py
-q -ra`; full guarded root command/provenance is controller-owned evidence.
Root measured 130 fresh UUID namespaces with retained counters
`1880|1451681 → 2010|1560501`, with no drops, namespace reuse or operational SQL.

Root evidence directory:
`D:/Codex-Recovery/content-studio-20261008/editorial-operator-root-pg-76dac080ee19423b9dd466caaaaf74d6`.
`native.log` SHA256:
`4A2CCDEFCB8C03832E9DB06A5E02BC2B772E9F6995685F40ECF2AD968FCA9382`.
Its separate `exit.log` records the immediate captured `PYTEST_NATIVE_EXIT=0`.
`exit.log` SHA256:
`AEA7A78637435AADB0C28B2A5E7D9632B15E49304E7A4F94604D1A025DE26BDB`.
The implementer independently read that receipt and hashed the raw result log,
without inferring native status from the pytest summary. Final independent
spec/quality review and exact implementation-commit CI remain root-owned next
integration gates. Predecessor service CI success is not claimed as new API CI
acceptance.

## Limits

This endpoint remains unprovisioned/default-disabled unless a dedicated operator
file and identity are explicitly configured. This work does not deliver a public
Settings workflow, Compose mount, model qualification, actual fixed-model
benchmark, live authorized Telegram test, or PHASE1 completion. It grants no
publication or rewrite authority. Real PostgreSQL verification and independent
reviews are root-owned and will not be inferred from SQLite tests or skips.
