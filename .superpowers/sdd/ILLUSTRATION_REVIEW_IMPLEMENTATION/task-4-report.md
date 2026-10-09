# Task 4 implementation report — 2026-10-09

## CURRENT_STATE

Status: DONE_WITH_CONCERNS, round1 review fixes verified. Round1 retained Windows
restart/crash/verify PASS; covering regressions: 152 PASS. Fresh independent
review/new CI pending.
Prior corrected retained Windows acceptance PASS and baseline full backend
1871 PASS/1 SKIP remain historical, not rerun evidence for round1. Primary alias
refusal and parent Tee wrapper failure remain FAIL history. No live acceptance
or PHASE completion is claimed.
Baseline `dae0e3057b6c3b6b5d6b174b944e2b0babb01c15`, existing
branch `codex/dark-navy-ui`, origin `borovojarkadij-png/content-studio`.
No production source, schema, operational credentials or worker settings changed.
No helpers/subagents/reviewers dispatched, no push or merge performed.

## Implemented

Dedicated `verify-illustration.ps1` launcher and test-only
`illustration_restart_controller.py` own only the
`newsflow-verification-illustration-*` family. The controller uses existing base
Compose and API-only reviewer override, with a separate read-only worker mount
for `docker_illustration_probe.py`. Packaged API and worker use migrated
PostgreSQL and persisted PostgreSQL/media/Redis volumes. PostgreSQL stays on its
private Compose network and never binds the parent's retained 5432 fixture.

The launcher refuses unsafe inherited environment/Compose overrides and changes
to the pinned normalized source graphs before any file or Docker command.
It then checks absent artifact path, distinct free loopback ports, labeled and
unlabeled exact containers/networks/volumes. Files use create-only writes. Public
deterministic master and reviewer values occupy different persistent files, and
reviewer is mounted API-only. Every network worker flag is explicitly 0. The
operator environment is validated and preserved, never cleared or overwritten.

Before operations the controller verifies ownership/version, strict duplicate-
rejecting JSON, original files, full synthetic PostgreSQL URL/role/password/host,
resolved service graph, worker command, API-only secret targets, media/probe
mounts, loopback ports and original labeled volumes. Immutable runtime image
IDs/mounts/environment are captured once and compared before further operations.
The PostgreSQL crash reuses the existing unchanged exact-ID exit-barrier helper.
Successful bounded scoped Docker stderr/warnings are emitted to the transcript.

The standalone packaged probe imports production seams only. It does not import
`backend.tests` or initialize a real Telethon client. Real authenticated HTTP
presentation, validator/photo, review, latest-review and revoke endpoints create
canonical server-reviewed evidence. Exact original review/audit, binding/row IDs,
photo and encrypted snapshot hashes are recorded in create-only manifests.
There are four distinct cases: approved, revoked, stale draft and abandoned
SENDING. Review revocation is actual HTTP. A separate rejected synthetic
ingestion proves REJECT -> rewrite_allowed=false -> no new RewriteJob, with
original four succeeded synthetic jobs unchanged and zero rewrite usage/calls.

Fresh probe processes reopen the original database/media after down/up, actual
PostgreSQL crash and a second down/up. The configured photo publisher receives
an explicitly injected synthetic Telethon client, preserving real TL request,
upload, paid-send refusal, exact nonce and direct response receipt validation.
Approved work has one fake upload/send and exact encrypted durable receipt;
revoked/stale work is BLOCKED before transport and abandoned SENDING is
NEEDS_RECONCILIATION with zero resend. Read-only reopen executes twice with no
admission or transport. SQL/storage verification retains original canonical
photo evidence even when PUBLISHED correctly makes current presentation 409.

Separate CI job `illustration-restart` runs lint, covering refusal/HTTP tests,
packaged PostgreSQL restart/crash acceptance and retained verify. Existing jobs,
checks and global fixture/crash guards are unchanged. The public procedure is
`docs/ILLUSTRATION_RESTART_ACCEPTANCE.md`.

## TDD and scoped verification evidence

- Initial RED: `python -m pytest backend/tests/test_illustration_restart_guards.py
  -q` -> 16 failures: owned controller not implemented.
- Probe RED: `python -m pytest backend/tests/test_illustration_restart_probe.py
  -q` -> 8 failures: standalone probe not implemented.
- Real migrated SQLite + loopback Uvicorn authenticated HTTP test initially
  failed on validator header case; subsequent actual fixture failures exposed
  synthetic review clock, unique schedule, SENDING lease and TL photo argument
  problems. These fixture issues were fixed with production behavior preserved.
- Resolved-config refusal RED: secret-target mutation crossed the config gate;
  the guard was tightened. Actual read-only Docker Compose rendering then
  exposed absolute default secret targets and the policy was normalized.
- Pre-fix focused GREEN: 43 passed in 12.98s. This is historical evidence.
- Self-review identified inherited override and changed build/source graph
  refusal needed before files. Targeted RED command:
  `python -m pytest backend/tests/test_illustration_restart_guards.py -q -k
  'inherited or changed_compose' --tb=short` -> 19 failures, all DID NOT RAISE.
  Those tests assert zero file/Docker/DB mutations and unchanged operator env.
- Pre-alias scoped GREEN command:
  `python -m pytest backend/tests/test_illustration_restart_guards.py
  backend/tests/test_illustration_restart_probe.py
  backend/tests/test_postgres_crash_barrier.py -q --tb=short`
  -> 78 passed in 21.93s. This includes 62 new tests and 16 existing crash tests.
- Final new probe/controller/test lint, compileall and `git diff --check`: PASS.
- Fresh actual Windows no-write candidate preflight: PASS, project
  `newsflow-verification-illustration-win-20261009a`, ports 18237/15394/18337.
- Pre-fix full suite was stopped at 39% without test failures after revalidating
  and stopping only exact owned Python PID7496, parent shell28372. Incomplete;
  explicitly not PASS.
- The broad pre-alias-fix full suite completed: 1855 passed, 1 skipped in
  380.70s (6:20). The later Windows-only comparison correction has its own
  post-fix full frozen gate is recorded below; the earlier broad result is
  historical, not a substitute for the post-fix result.
- Actual primary Windows create failed only during final reopening after the
  second successful down/up: `Retained immutable image/mount/environment
  changed`. Parent read-only diagnosis found only web bind-source spelling
  changed from its exact Windows path to `/run/desktop/mnt/host/c/...`.
  Original files, snapshots, receipt, media and all Docker resources remained.
- Mount correction RED: 15 parametrized normalization tests failed because the
  helper was absent. More significantly, the actual `Fixture.validate_resources`
  covering test reproduced `Retained immutable ... changed` with the exact
  alias/order input before implementation. GREEN normalizes only known owned
  Windows drive sources and their Docker Desktop alias, preserves all metadata,
  sorts mount order, and compares transformed original/current inventories.
  Foreign drive/path, traversal, near misses, RW, destination, type, image and
  environment changes remain refused. The original runtime manifest is not
  rewritten; SHA-256 remains
  `239FE7796C246CE1A5763F10E1897658C89868569A69D2AD5698623D0407CE34`.
- Post-fix scoped command (same three test files above): 94 passed in 21.40s.
  New controller/probe/test lint and compile: PASS. Controller frozen SHA-256:
  `5175A05685D6E10A1BEFBAED5E860EF5C94F5D0007289BF73DB283E626AAD813`.
  Probe unchanged SHA-256:
  `D917CEF2D8E7156D5DF7CE00EF006F637B8A1BD00C85E2F4D581EB4BB9483039`.
- Final frozen full backend command `python -m pytest -q` from `backend`:
  1871 passed, 1 skipped in 326.78s (5:26), session69652 exit0. This is the
  covering post-alias gate, run once while parent executed retained boundaries.
  Final lint and `git diff --check`: PASS. Controller/probe SHA-256 and original
  runtime manifest SHA-256 were rechecked unchanged after Windows recovery.

## Windows/CI/live acceptance

Parent owns actual Windows execution after final scoped freeze. Primary create
command ran; post-fix retained verification, recovery, additional owned
restart/crash boundaries and final no-drift check PASS:

```powershell
pwsh -NoProfile -File scripts/verify-illustration.ps1 -Project newsflow-verification-illustration-win-20261009a -ApiPort 18237 -WebPort 15394 -ProductionPort 18337
pwsh -NoProfile -File scripts/verify-illustration.ps1 -Mode verify -Project newsflow-verification-illustration-win-20261009a
pwsh -NoProfile -File scripts/verify-illustration.ps1 -Mode restart -Project newsflow-verification-illustration-win-20261009a
pwsh -NoProfile -File scripts/verify-illustration.ps1 -Mode verify -Project newsflow-verification-illustration-win-20261009a
```

Do not attribute the parent's unrelated retained PostgreSQL acceptance or
baseline CI to this new fixture. Windows primary process 79669 ended with exit1
after actual seed/invalidation/pending/first restart/PostgreSQL crash/fake
execution PASS. The metadata-only native PowerShell transcript
`D:/Codex-Recovery/content-studio-20261008/task4-windows-20261009-1104.log` is
retained but is not full native-output proof; parent is retaining native outputs
through Tee. Retained `Mode verify` ran twice with zero transport calls: PASS,
captured in `task4-retained-verify-20261009a.log` under the same recovery directory.

A parent wrapper error (`Tee-Object -LiteralPath -Append`, unsupported parameter
combination) canceled the next pipeline after the owned restart had completed
down. This is separate from the controller alias fix. Exact project containers
and network were absent, original volumes/manifests remained, and no controller
was running. Parent validated original ownership/config/secrets, original retained
volume IDs and absent labeled containers/network, then performed only original
Compose up (no build/reseed), health and verify-final twice: PASS, process32247
exit0, captured in `task4-retained-recovery-20261009a.log`. The corrected parent
wrapper uses `Tee-Object -FilePath`. Final process36991 exit0 performed the owned
full down/up then verify-final twice, exact PostgreSQL crash then verify-final
twice, separate Redis/worker restart then health and verify-final twice, and
`alembic check`: `No new upgrade operations detected.` Actual combined corrected
retained Windows gate: PASS, captured in
`D:/Codex-Recovery/content-studio-20261008/task4-retained-boundaries-20261009a.log`.
The original runtime manifest SHA above is unchanged. Approved fake receipt is
still exactly one; revoked/stale remain blocked and abandoned SENDING remains
quarantined without resend. Every final verification reports real Telegram/AI
calls=0 and new rewrite jobs/calls=0. Primary alias refusal and parent wrapper
failure remain historical FAIL evidence, not silently relabeled successful.

Exact immutable images independently read from the original `runtime.json`:

| Service | Immutable image ID |
|---|---|
| api | sha256:40a8904aaa5bf6d8600319cb2ad2efcce39d7ddf225c1a183160eaff12126fed |
| migrations | sha256:57a2a648d6f21361dd18a4f9db6edc75fde6959424ae41476e4520dcb4833c18 |
| postgres | sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea |
| redis | sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499 |
| web | sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 |
| web-production | sha256:6dad9afd03b97857cf2f706b0098307be640619aa9e7bd84de8fe11ef6a6c8ab |
| worker | sha256:1e6ef273b11eecfef105b5a3670a1f6f9f78e10b0d09fd67a34e7180daf5ec74 |

New CI execution: pending, not PASS. Credential-dependent live Telegram/AI/
publication acceptance: SKIP by design; no real calls or credentials activated.

## Files, self-review and recovery

Owned changed files: `.github/workflows/ci.yml`, two new backend test files,
three new scripts, the dedicated procedure and this report. Parent-owned
`docs/ILLUSTRATION_PRESENTATION_PARENT_20261009.md`, `docs/REQUIREMENTS_MATRIX.md`,
`docs/ILLUSTRATION_RESTART_PARENT_20261009.md` and progress ledger are excluded
from staging.

Self-review fixed pre-write inherited/source-graph safety gaps before any owned
runtime was created. The dedicated probe/controller are comparatively long
verification infrastructure; no production classes or old family policies were
extended. Future intentional Compose changes require reviewed source digest
updates and covering refusal tests. All failed/partial fixtures must remain
recoverable; no down -v, prune, truncate, destructive volume removal, reseed,
secret regeneration or recovery-by-overwrite is implemented.

## Independent-review fix round1

Baseline: `bfba7ede98d775510abd5353f4182c68ceb60b18`. Read Important1 and
Important2 in `task-4-review.md` and confirmed both controller guard-order gaps.
No helpers/reviewers or runtime mutations performed by the implementer.

Important1: prewrite policy now checks physical backend/frontend directories,
both Dockerfiles and the standalone bound probe. Every path and ancestor passes
the existing symlink/reparse guard, must resolve to its exact lexical checkout
path and have the required existing directory/file type. Retained validation,
restart, crash and retained up repeat this gate before Docker operations.

Important2: before down/crash/up, read-only image inspection requires every
original recorded SHA-256 image to exist and each original Compose explicit
image/default project build tag to resolve to the same ID. Retained up supplies
an in-memory stdin Compose override with all seven original image IDs, including
migrations, plus `--no-build --pull never`. No new fixture file, seed, secret or
manifest is written, and no mutable-tag build/pull fallback is permitted.

Actual local checks:

- RED: `python -m pytest backend/tests/test_illustration_restart_guards.py -q
  -k redirected_build_inputs --tb=short` -> 20 failed in 4.32s. Creation did not
  refuse; retained paths reached Docker config rather than the input gate.
  Tests use real Windows junctions at build directories/ancestors and Dockerfile
  paths, with untouched foreign sentinel, original file bytes and zero commands.
- Initial GREEN for that change: 20 passed in 3.85s. Final covering matrix adds
  the probe path and direct retained-up boundary, totaling 30 junction cases.
- RED: same test file with `-k 'image_tags or required_immutable or
  retained_startup' --tb=short` -> 19 failed in 1.64s. Running containers still
  validated against baseline while changed tag resolution was not refused;
  retained up also lacked no-build/pull-never and original-ID arguments.
- Initial GREEN: 19 passed in 1.24s. Final image matrix covers all seven tags at
  down/crash/up, missing or mismatched immutable images, original-byte retention
  and exact image-ID startup arguments. No Docker daemon mutation is simulated
  through to a real Docker call.
- First combined run: 151 passed/1 failed in 27.97s; the existing read-only
  Compose test's incomplete sample lacked the now-required Dockerfiles/probe.
  Its setup now copies valid physical inputs; no guard or assertion was weakened.
- Frozen final covering command:
  `python -m pytest backend/tests/test_illustration_restart_guards.py
  backend/tests/test_illustration_restart_probe.py
  backend/tests/test_postgres_crash_barrier.py -q --tb=short`
  -> 152 passed in 27.79s, session97753 exit0.
- `python -m ruff check` for both Task4 scripts/tests: PASS;
  `python -m ruff format --check` for changed controller/guard tests: PASS;
  `python -m compileall -q` for both scripts/tests and `git diff --check`: PASS.
- Controller frozen SHA-256:
  `0AF2EED48878A5007071956EB049D512703BA15DD24BD1654F4BF1BA1EF4E12D`.
  Standalone probe unchanged:
  `D917CEF2D8E7156D5DF7CE00EF006F637B8A1BD00C85E2F4D581EB4BB9483039`.
  Original runtime manifest still:
  `239FE7796C246CE1A5763F10E1897658C89868569A69D2AD5698623D0407CE34`.

Round1 actual Windows process10576 exit0: original runtime/input validation and
all seven original ID/current-tag resolutions PASS, then pinned no-build/pull-
never full restart -> verify-final twice -> exact PostgreSQL crash -> verify-final
twice PASS. Real Telegram/AI calls=0; original approved receipt remains exactly
one and abandoned SENDING has no resend. No build/reseed/new fixture files or
rewritten manifest; original runtime SHA-256 above remains unchanged. Native
evidence:
`D:/Codex-Recovery/content-studio-20261008/task4-fix1-immutable-boundaries-20261009a.log`.
The implementer independently read its health/crash/final verify PASS tail and
rechecked frozen source/probe/runtime hashes. Root owns these runtime operations.
No additional whole backend rerun: small controller-only fix uses covering tests;
the 1871 PASS/1 SKIP baseline remains historical. New exact remote CI and fresh
independent review remain pending. Probe, production source and original crash
helper are untouched. Parent CURRENT_STATE/IMPLEMENTATION_PLAN and all previously
listed parent-owned reports/ledger remain excluded from this fix commit.

NEXT_STEP: fresh Task4 scoped independent review of round1, then exact new CI.
After parent acceptance, cross-task
whole-branch commercial QA/review precedes the next remaining Telegram increment.
No user confirmation is required for these already authorized scoped gates.
