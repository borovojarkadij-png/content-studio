# Task 1 implementation evidence

Base: `388cb3cc92490ad8f8a9cd8106308863b1b5100e`. Branch: `codex/dark-navy-ui`.
The sole configured origin was verified as the requested Content Studio repository.

## Implementation

Added `ConfiguredEditorialClassifierFactory`: exact immutable admission-binding type,
fresh canonical admission and full snapshot comparison before credential access,
matching encrypted rewrite-provider credential only, explicit injected cipher,
sanitized missing/unavailable-secret errors, and SQL closure before adapter construction.
Diagnostic provider/model are pinned by the canonical binding; rewrite primary and
fallback settings cannot retarget classification. Unexpected storage errors propagate.

Added the exact `0`/`1` flag parser and exact-bool bounded worker tick. Disabled execution
returns before any dependency construction. Enabled execution requires the existing
stable cipher and invokes one accepted runner operation. `worker.main` reads the default
disabled flag, includes it in the stable-key guard, honors stop state and logs only stable
outcomes/recovery markers. `.env.example` documents diagnostic-only/no-approval semantics.

Tests reuse migrated isolated admission fixtures. The transport is injected and counted;
rewrites are forbidden in worker tests. A neutral diagnostic commits REVIEW, claim history,
immutable attempt evidence/usage and attempted outbox while preserving MANUAL_REVIEW/false,
zero RewriteJobs and zero rewrite calls. Two queued jobs yield one processed job. Both
adapters retain strict JSON/model contracts, and OpenRouter retains zero-price/no-fallback
guards. Independent commits during decrypt or construction are blocked by the accepted
runner's post-factory admission check before IO. Factory construction and transport entry
observe no open factory/runner session.

No schema, runner, adapter, dependency, UI, Compose, policy activation, real credential,
provider call, Telegram session, publication, model qualification or operational SQL change.

## Native test commands and chronology

All test commands ran from repository `backend` under Python 3.12 using this exact launch
form (the explicit insertion is necessary because PYTHONPATH is ignored here):

All logs, cache and temporary paths use the unique directory
`D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/` (called `RUN` below).
The actual native commands, in chronological order (native exit captured immediately
after each invocation with `$taskExit=$LASTEXITCODE`), were:

```powershell
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_editorial_worker.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/red-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/red-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/red.log
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_editorial_worker.py','tests/test_editorial_classifier_factory.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/green1-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/green1-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/green1.log
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_editorial_worker.py','tests/test_editorial_classifier_factory.py','tests/test_durable_editorial_runner.py','tests/test_editorial_admission.py','tests/test_editorial_classifier_adapters.py','tests/test_scheduler_worker.py','tests/test_rewrite_worker_policy.py','tests/test_semantic_runner.py','-q','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/green2-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/green2-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/green2.log
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['-q','-rs','--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/full-tmp','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/full-cache']))" *> D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/full.log
```

1. Original RED: `['tests/test_editorial_worker.py','-q','--basetemp=RUN/red-tmp','-o','cache_dir=RUN/red-cache']`.
   Native exit **1**, **1 failed**. The real migrated enabled-policy/queued-job fixture
   reached the behavioral assertion `IDLE == REVIEW`; this was not an import or collection
   error. An explicitly temporary test-only missing-feature fallback returned IDLE and
   was removed before implementation verification. The original native log is retained.
2. First focused iteration: `['tests/test_editorial_worker.py','tests/test_editorial_classifier_factory.py','-q','--basetemp=RUN/green1-tmp','-o','cache_dir=RUN/green1-cache']`.
   Native exit **1**, **89 passed, 1 failed** in 21.56s. The assertion incorrectly expected
   the request's system role verbatim; the accepted OpenAI transport uses developer role.
   Corrected the test to check the existing role, exact instruction content and decoded
   source payload; no accepted transport change.
3. Expanded GREEN: `['tests/test_editorial_worker.py','tests/test_editorial_classifier_factory.py','tests/test_durable_editorial_runner.py','tests/test_editorial_admission.py','tests/test_editorial_classifier_adapters.py','tests/test_scheduler_worker.py','tests/test_rewrite_worker_policy.py','tests/test_semantic_runner.py','-q','--basetemp=RUN/green2-tmp','-o','cache_dir=RUN/green2-cache']`.
   Native exit **0**, **439 passed, 5 skipped** in 101.83s. The skips are existing
   PostgreSQL-only checks in this SQLite execution; independent actual PostgreSQL
   acceptance is controller-owned. Native session 47117 completed successfully.
4. Frozen sole full backend suite: `['-q','-rs','--basetemp=RUN/full-tmp','-o','cache_dir=RUN/full-cache']`.
   Native session **45430** terminated **0**, **2565 passed, 11 skipped** in **525.51s**,
   no warnings. Log `RUN/full.log`. Existing skips: one actual migrated PG lock proof,
   four actual PG finalizer row-lock proofs, one actual PG TRUNCATE storage test,
   two plus three explicitly opted-in planner/media PG concurrency cases. These are
   unavailable in the SQLite full-suite mode, not claimed as passing here.

The five source/test/template hashes below were sent to the controller before launching
the sole full suite. No source/test/template edits after freeze. The controller owns the
parallel strict Windows/PostgreSQL gate and independent complete BASE..HEAD review.

Controller-owned actual Windows/PostgreSQL verification completed separately: **native
exit 0, 97 passed, zero skips/warnings, 55.81s** for the two new test files. The controller
reported unchanged five frozen hashes before/after, a strict synthetic container and fresh
isolated UUID schemas with restored environment. This worker did not invoke PostgreSQL.
Root evidence log:
`D:/Codex-Recovery/content-studio-20261008/editorial-worker-root-pg-0cd89a78dcd84c6a9b235d0cbd265376/native.log`,
SHA256 `B3FF00760A0010CE27618BF7E7056C41A0E2DB7CB102E05EF3DE5830ED086731`.
This is synthetic database acceptance, not live activation or real-model qualification.

## Native static verification

From repository root, using Ruff 0.17 at
`D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe`:

```powershell
ruff.exe check backend/src backend/tests backend/alembic
ruff.exe format --check backend/src/newsflow/services/editorial_classifier_factory.py backend/src/newsflow/worker.py backend/tests/test_editorial_classifier_factory.py backend/tests/test_editorial_worker.py
python -c "import pathlib,py_compile,yaml; paths=['backend/src/newsflow/services/editorial_classifier_factory.py','backend/src/newsflow/worker.py','backend/tests/test_editorial_classifier_factory.py','backend/tests/test_editorial_worker.py']; [py_compile.compile(p,doraise=True,cfile='D:/Codex-Recovery/content-studio-20261008/editorial-worker-task1-20261012/'+pathlib.Path(p).stem+'.pyc') for p in paths]; print('Compilation: 4 files OK'); ypaths=['compose.yaml','compose.dev.yaml','compose.telegram.yaml','compose.illustration-review.yaml','.github/workflows/ci.yml']; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ypaths]; print('YAML parse: 5 files OK')"
git diff --check -- .env.example backend/src/newsflow/worker.py
```

Every native exit **0**; all Ruff checks passed, four changed Python files already formatted,
four Python files compiled, five YAML files parsed. Git emitted only the existing Windows
LF/CRLF conversion notices. Combined native evidence: `RUN/verification.log`.

## Retained log SHA256

| Log under RUN | SHA256 |
| --- | --- |
| red.log | A756387727C085310CA690D1CB2B91B18317BE0357BA0DBA6138B1CBE06C7DF4 |
| green1.log | 0A2D50C3D35BD4DE713655361B7CFD0A69B81B08EF61F895EE4793F1F0B23D78 |
| green2.log | 74D274849FADE9A99613EC4104536CE1D467200F542497F0F94525F632C3CDBE |
| verification.log | D756EA5D01AC83FD485336CBE8CA3CC1B68502136B51C2AC5FF45075CE929A6C |
| full.log | FE9C79F60474F5AFE77FA71CCD38175E2338EC7C65CAC1E4B97C14DC788A679C |
| ci-budget.log | A9E19151FDF0225B25437C1F260551DEDBD97A79F4473040EDCA23A7F1D68F99 |

## Changed files and frozen raw SHA256

| Owned file | SHA256 |
| --- | --- |
| .env.example | E69A204DAB173A4296D0DC013F59DC26449441846EFE30F0E475C0F9D284434F |
| backend/src/newsflow/services/editorial_classifier_factory.py | FA3EFF0B8EA4FBE0028ABB20105301D0FC6BDBA705459F50FF1E8465088564EB |
| backend/src/newsflow/worker.py | BD1F5570C5C49C90F5E4C20544A64C6F95F32F25994A26F8A1C9C8E09B12EC38 |
| backend/tests/test_editorial_classifier_factory.py | 1AC16D001A7DC08D7F8EE3F0D9C36F1B5F89EF1FBDD1EB8C505AD166480F24E1 |
| backend/tests/test_editorial_worker.py | 3734F47D7F610FC1E985A0F10960F88EB007ABDECAC07BC994824926FD724932 |

The root-authorized post-suite CI amendment also changes `.github/workflows/ci.yml`:
raw SHA256 `7AC1D67C3B8B13F98C8BE7725E3EB50CC2B29EEE41170EBCDDCAE1A922F31681`.
The only remaining owned file is this report. Controller-owned documentation changes
in the shared worktree are intentionally excluded from this worker's seven-file commit.

## Narrow CI amendment after full-suite termination

The controller amended the own task brief during the frozen run. After session 45430
terminated successfully, changed only `jobs.unattended-postgres.timeout-minutes` from
10 to 20. No frozen Python/template edit and no second full-suite run. Self-review of
the actual diff: exactly **1 added / 1 removed line**. A native PowerShell comparison
required the entire current CI file to equal `git show HEAD:.github/workflows/ci.yml`
with only the exact unattended-postgres context's timeout replaced, thereby asserting
unchanged commands, flags, checks, failure propagation, services and all other budgets.
Then executed:

```powershell
python -c "import pathlib,yaml; value=yaml.safe_load(pathlib.Path('.github/workflows/ci.yml').read_text(encoding='utf-8')); budget=value['jobs']['unattended-postgres']['timeout-minutes']; assert type(budget) is int and budget == 20; print('YAML parse OK; finite unattended-postgres budget=20')"
git diff --check -- .github/workflows/ci.yml
git diff --numstat -- .github/workflows/ci.yml
Get-FileHash -LiteralPath .github/workflows/ci.yml -Algorithm SHA256
```

Native exits **0**; `RUN/ci-budget.log` retains the comparison, finite-budget assertion,
diff validation and CI file hash. The existing broad checks already parsed all five
YAML files before the amendment; this post-suite command parsed the changed CI YAML.

The reason is measured deadline exhaustion, attributed to the controller's prior-source
CI evidence: run **38304194927**, PG job **114994133488** advanced 13/26/39/52/65/78/91%
from 20:27:24 through 20:36:14 UTC before cancellation at 20:36:25 UTC. The ten-minute
timeout remains a **failed verification**, with no assertion-failure finding and no
terminal PG PASS; the dependent concurrency step was skipped. Retained root log:
`D:/Codex-Recovery/content-studio-20261008/editorial-execution-ci-38304194927/postgres-job.log`,
SHA256 `0B7D845B228999FAF037142DEBBBCD89F362A01D60BA34EAC9FD88D98CC88707`.
The root owns corrected exact-new-source CI; this deadline change is not itself a CI PASS.

## Self-review and limits

Reviewed the factory and the narrow existing-worker diff against the task brief. Exact
type/flag checks happen before dependencies; credential use follows fresh admission;
model policy stays independent from rewrite settings; there are no retries/fallback
loops in the new tick; accepted runner fences remain authoritative. Typed failures
remain recoverable or terminal according to the existing runner. Static logs contain
no exception/source/credential/binding contents. The existing large worker module was
extended narrowly without refactoring unrelated flows.

Synthetic conformance is not real-model qualification. Protected-policy API/UI, benchmark
qualification, diagnostic-history read model, qualified PASS propagation and its final-gate
serialization remain deferred. This task does not complete PHASE1. No PG/Docker/browser/CI
work was duplicated by this worker. Both local verification gates terminated successfully;
the five frozen implementation files stayed unchanged. No unresolved implementation
concern was found in self-review. The independently reviewed exact commit/new-source CI
remains controller-owned; no worker push, PR or merge was performed.
