# Task 2 implementer report — explicit Telegram login CLI

Scope: Task 2 brief and binding onboarding design; base supplied by controller
`bb30b9642ad156689b72bbf98860c3be024aa53f`. Only the five specified implementation,
test, operator-doc and workflow paths plus this report are owned. Task 1 provider/
service interfaces are consumed unchanged. Root dirty documentation was preserved.

## Implementation

- Added `python -m newsflow.telegram_login`, `main(argv=None)` and module guard.
  Default returns LOGIN_DISABLED/2. Help returns 0. Private argparse errors never
  echo unknown options, supplied secrets or invalid values. Enabled arguments
  validate name and signed64 identities before configured runtime construction.
- Requires stdin/stderr TTY before runtime. Validates explicit PostgreSQL+psycopg
  URL/database/role, existing shared-loaded credentials/master key, and equality
  of the packaged single Alembic head and read-only MigrationContext heads.
  Uses configured_session_factory only after URL validation; closes its sessions
  without disposing the shared cached engine or clearing other runtime caches.
- Calls real service preflight before masked phone, then provisions once. All
  secret fields use getpass; GetPassWarning is promoted to an error before echoed
  fallback input can run. Fixed success/internal ID, failure and abort statuses
  suppress native configuration/SQL/SDK exceptions and tracebacks.
- Added CLI tests around actual parser/module/service/cipher/migrated SQL with
  only terminal/RPC/configured database boundary fakes. Default/help/nonTTY real
  subprocesses block socket connections and verify unchanged secret/database
  sentinels and no extra session files. Includes Unicode names, secret-bearing
  invalid argv, prerequisites, head mismatch, one-code/2FA, repeat refusal,
  EOF/Ctrl-C/cancellation, warning refusal and actual getpass fallback refusal.
- Added 11 explicit PostgreSQL-only cases using strict create_postgres_namespace:
  migrated insert+outbox and independent encrypted consumer reopen; six exact
  snapshot CAS races against an independent committed engine; two creation/user
  conflicts; two audit rollbacks (insert/CAS). Each records its new UUID schema,
  retains it, seeds immutable REJECT/rewrite_allowed=false, asserts all unrelated
  job/usage/media/publication tables empty and guards rewrite provider calls.
- Appended only the new PG file to the existing unattended-postgres migrated
  command. Parsed YAML structural comparison verifies every other field, job,
  step, env and timeout remains unchanged, including Windows native contracts.
- Added operator procedure with backend and interactive Compose commands,
  explicit credential mounts, existing migrations/TTY, separate key custody,
  one attempt, no replacement, audit/health semantics, remote-login/SQL rollback
  limit, human code/2FA and separate encrypted restart/test-channel gates.

## TDD and retained failures

Before implementation, CLI tests were written. The first real CLI fixture run
failed with `ModuleNotFoundError: No module named 'newsflow.telegram_login'`
(1 setup error, native 1); that is recorded as a missing implementation setup
failure, not claimed as an assertion RED. The dedicated entrypoint availability
assertion then produced causal RED against the absent module:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_login_cli.py::test_explicit_cli_entrypoint_is_available','-q']))"
```

Output: `assert importlib.util.find_spec('newsflow.telegram_login') is not None`
failed because the result was None: **1 failed in 0.63s**, native **1**. The CLI
module was then added. The prewritten parser/service/abort cases initially
reported **13 failed, 37 passed** (native 1), with zero RPCs in the failing paths.
Diagnosis: instance-level isatty patches were restored as instance bound methods
on pytest's reused capture streams, shadowing later class-level patches. Moving
the simulated terminal to a module-local sys facade fixed the test boundary;
no runtime exception text was exposed to make tests pass. Temporary direct
diagnostic preflight assertions were removed.

GREEN:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_login_cli.py','-q','--basetemp=D:/Codex-Recovery/telegram-login-task2-green3']))"
```

Output: **50 passed in 8.60s**, native **0**. Subsequent coverage added two forbidden
argument cases and actual getpass fallback refusal. The initial red/setup and
first diagnostic runs used pytest's default temporary directory; subsequent
named covering/full runs use D: exclusively. No operational fixtures were used.

## Verification commands and results

All pytest commands insert the supplied Telethon 1.45 path before importing
pytest; full output confirms `Telethon=1.45.0`. Commands run from backend unless
specified otherwise.

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_login_cli.py','tests/test_telegram_login.py','tests/test_telegram_login_postgres.py','-q','-rs','--basetemp=D:/Codex-Recovery/telegram-login-task2-cover1']))"
```

**153 passed, 11 skipped in 16.35s**, native **0**. All eleven skips explicitly
say `PostgreSQL-only: explicit synthetic NEWSFLOW_UNATTENDED_POSTGRES_URL required`.
They are collection/no-URL refusal evidence, **not PostgreSQL verification**.
Actual migrated PostgreSQL execution/namespaces remain the root's post-review
gate. CLI success uses actual migrated isolated SQLite only behind the configured
test boundary; production SQLite URLs are refused before factory/input/RPC.

Repository-root static commands:

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check backend/src/newsflow/telegram_login.py backend/tests/test_telegram_login_cli.py backend/tests/test_telegram_login_postgres.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check backend/src/newsflow/telegram_login.py backend/tests/test_telegram_login_cli.py backend/tests/test_telegram_login_postgres.py
python -m compileall -q backend/src/newsflow/telegram_login.py backend/tests/test_telegram_login_cli.py backend/tests/test_telegram_login_postgres.py
```

Final output: `All checks passed!`, `3 files already formatted`, compile silent;
native lint=**0**, format=**0**, compile=**0**. Initial static run reported a
redundant imported-fixture alias, unused unpacked variable, missing explicit
subprocess check argument and formatting/import ordering; these were fixed,
no checks disabled (only the intentional imported pytest autouse fixture F401
annotation documents its registration role).

Parsed workflow validation command (repository root):

```powershell
python -c "import pathlib, subprocess, yaml; p='.github/workflows/ci.yml'; before=yaml.safe_load(subprocess.check_output(['git','show','HEAD:'+p], text=True)); after=yaml.safe_load(pathlib.Path(p).read_text()); key='jobs'; steps=after[key]['unattended-postgres']['steps']; oldsteps=before[key]['unattended-postgres']['steps']; changed=[(a,b) for a,b in zip(oldsteps,steps) if a!=b]; assert len(changed)==1; old,new=changed[0]; assert new['run']==old['run'].replace(' -q',' tests/test_telegram_login_postgres.py -q'); new['run']=old['run']; assert after==before; print('Parsed YAML: only migrated PostgreSQL command appended; all other fields unchanged')"
```

Output confirms exact lone append/all other fields unchanged; native **0**.

Single full backend run after combined implementation and static fixes:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon, pytest; print('Telethon=' + telethon.__version__); raise SystemExit(pytest.main(['-q','--basetemp=D:/Codex-Recovery/telegram-login-task2-full-20261013']))" 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/telegram-login-task2-full-20261013.log
$taskTestExit = $LASTEXITCODE
Write-Output "native pytest exit=$taskTestExit"
exit $taskTestExit
```

Full backend result: **3186 passed, 26 skipped in 514.98s (0:08:34)**,
native **0**, no reported warnings or failures. The 26 skips include all 11 new
no-URL PostgreSQL cases; they do not satisfy the actual migrated PG gate. Complete
stdout is retained at `D:/Codex-Recovery/telegram-login-task2-full-20261013.log`.
No frontend suite was run because this task changes no UI.

## Self-review and remaining gates

Read the entire CLI, CLI tests, PG cases, operator procedure and scoped workflow
diff against the brief. All writes are confined to permitted paths. Checked
no secret parameters, no migrations in CLI, no engine/cache destruction, no
saved-session replacement, private warning/error handling and retained immutable
REJECT/zero unrelated execution invariants. No Task 1 source changes or unresolved
implementation defects identified. Synthetic subprocess fixtures create no
Telethon session artifacts. Controller-owned actual PG, packaged network-none
smoke, fresh review, authorized push and exact hosted CI remain pending. Human
live login and independent encrypted restart remain pending manual gates.

## Frozen owned content SHA256 (working-tree bytes)

| Path | SHA256 |
| --- | --- |
| backend/src/newsflow/telegram_login.py | 1C29C832D68C93515A50DCDF7FD37EB1061BA6DD2E08D464DAB0799EFA39FEEA |
| backend/tests/test_telegram_login_cli.py | 8B1487A442537B8A161AFA05E5484537CF469C278D6D24D717A15BF22919BFD7 |
| backend/tests/test_telegram_login_postgres.py | 3C771ED1FDE6094628212CD68296170369A64585F40DD78D57AA2378441F859F |
| docs/TELEGRAM_LOGIN.md | FB9529CE27B29CCD444B59DA0D6E754BAEFC56978EC9D821FCB2FDDEC024018E |
| .github/workflows/ci.yml | B96B6E4DA70FE7970E574C23510E2BCC670D1393E8380EF009A45A669A97DBE7 |

This report's own final hash is provided separately after finalization to avoid
a self-referential hash. The owned commit contains only these five paths and this
report. Status: **DONE** for implementation/implementer verification; the explicitly
assigned controller and manual acceptance gates above remain pending.

Commit preparation: the first scoped `git add` returned native 1 because the SDD
directory is ignored. Added only this explicitly owned report with `git add -f`;
the ignore rules and all controller-owned dirty files remain unchanged.
