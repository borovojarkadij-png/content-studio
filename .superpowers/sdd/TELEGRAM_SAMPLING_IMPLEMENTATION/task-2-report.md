# Task 2 implementation report — 2026-10-13

Status: DONE_WITH_CONCERNS (implementation and synthetic checks complete; actual PostgreSQL execution is explicitly reserved for the controller after source review).

## Scope and implementation

Worked on branch `codex/dark-navy-ui`, verified origin `https://github.com/borovojarkadij-png/content-studio.git`, from dispatch BASE `584f4cbde0c2de68a9abbbafe61c8dbcd3fc758c`. Accepted Task1 is `200b5c9`. Read the complete task brief, complete sampling design, accepted schedule/history/provider/source/model contracts, implementer template, TDD skill/reference, and verification skill. Did not read the whole plan or sibling SDD workspaces. No subagents/reviewers were spawned.

Only these three implementation files plus this report are owned by this task:

- `backend/src/newsflow/services/telegram_engagement_sampling.py`
- `backend/tests/test_telegram_sampling_runner.py`
- `backend/tests/test_telegram_sampling_postgres.py`

The runner has frozen admission/claim contracts, parameter/forged-claim validation before database/provider use, bounded fair admission over actual incoming IDs, same-call wrap after an empty tail, canonical configured donor/mapping/account/session/revision/deletion/sync checks, and idempotent job creation under the incoming lock. Existing jobs still advance the admission cursor; no reset/backfill is performed.

Claim lookup reads at most16 candidate IDs without holding job locks, then locks incoming→job→account with SKIP LOCKED for claim acquisition. It rechecks due ownership, accepts CONNECTED or expired COOLDOWN with a nonempty encrypted session and positive signed64 user, waits without spending attempts for temporary sync/cooldown, blocks permanent source/session failures, and fails attempts3 without a fourth provider call. A canonical token, exact60-second lease, expected user, ciphertext SHA256 and incremented attempt commit before IO.

Execution reconstructs the claim and response, closes the permission transaction before exactly one aggregate fetch, uses the actual acquisition clock, rejects pre-claim/backwards/expired timestamps, and samples the clock again after all final locks. It fences token/lease/step/user/ciphertext/current source/config/health/sync. History source/snapshot and schedule/job advance share one outer transaction. Stale owners store nothing and cannot clobber newer health. SQL interruptions remain outside the private provider-error catch and preserve the earlier committed recovery lease.

Private error outcomes cover current session invalidation, missing/malformed/conflicting observations, three-attempt transient retry, exact nonnegative FloodWait with overflow refusal, and conservative session refresh. FloodWait retains max(current cooldown, fresh final clock+full delay), while synchronization/current source/invalid health fences still apply. No provider construction, credential discovery, login, send, classifier, rewrite, media, publication or worker activation is introduced.

Controller rulings obtained while implementing:

1. Empty `IDs>after_id` with nonzero cursor wraps to the first page in the same call; a nonempty partial tail is not topped up with wrapped IDs.
2. Unknown `Exception` strictly inside provider fetch/response reconstruction becomes current-owner BLOCKED/INVALID_OBSERVATION; BaseException and SQL failures propagate.
3. Only current owned FloodWait may pass a temporary WAIT_COOLDOWN fence to persist the longer required delay; sync/source/config/user/session/token/lease/invalid health still fence it.
4. Candidate lookup is bounded to16. An invocation may return None/IDLE while later jobs exist if the first16 are locked; this is not a statement that the durable queue is empty.

## Behavioral coverage

Migrated synthetic SQLite uses canonical account_id1/user41, encrypted synthetic ciphertext, broadcast donor, mapping, immutable revision and REJECT/rewritefalse. Autouse rewrite-provider tripwires and preservation assertions check original source/revision/editorial state and zero rewrite jobs/usage/outputs, classification jobs, media acquisition jobs, publication candidates/plans/jobs/snapshots/observations and outbox rows.

103 runner cases cover committed admission/claim/success; exact six intervals and discovery; missed windows and source publication versus source edit/ingestion time; bounded admission, duplicate cursor progress and wrap; recent/future bounds; strict parameters/forged claims; actual no-connection callback; pre/post drift of session/user/mapping/deletion/sync/health/cooldown; missing revision/session/user/moved donor; expired takeover, restart/double reopen, committed attempt exhaustion; transient/private/unknown/session/source errors; nullable/zero/reset/maximum counters; malformed responses, identity/time/publication conflicts; schedule/date overflow and early scheduled observations; terminal retention; concurrent cooldown FloodWait; SQL interruption and native SQLite trigger failure rolling back history while preserving the committed lease.

20 create-only PostgreSQL contracts require explicit `NEWSFLOW_UNATTENDED_POSTGRES_URL` and reuse strict `create_postgres_namespace` without fallback. They cover migrated raw constraints, retained downgrade/version/identity/delete/TRUNCATE refusal, independent concurrent admission and simultaneous claim ownership, incoming/job/account SKIP LOCKED, bounded16 locked candidates without17th acquisition and recovery, expired takeover/stale finalizer/reopen, lease expiry while waiting for final account lock, nullable history/job atomicity, and actual PostgreSQL trigger failure. Every namespace is retained; connections have bounded lock/statement timeouts. No actual PostgreSQL URL was supplied to this task, so all20 are honestly SKIPPED. Actual owned Windows PostgreSQL remains the controller's gate after source review.

## Native commands and retained evidence

Evidence directory (fresh, no overwritten logs):
`D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task2-20261013a/`.

All commands below ran from `C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend` unless stated. Every numbered run has raw `.log` and `-exit.txt`; pytest runs also have native JUnit `.xml`. The initial `01-red-command.txt` is a human label; the exact bootstrap/arguments below are the authoritative native command.

Exact Python bootstrap used for EVERY pytest run (global Telethon1.44 was never used):

```powershell
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(ARGS))"
```

`ARGS` was the exact Python list specified below. Every call redirected native output using `*> EVIDENCE/STEM.log`, captured `$taskExit = $LASTEXITCODE`, wrote `$taskExit | Out-File EVIDENCE/STEM-exit.txt`, displayed the raw log, and `exit $taskExit`. `EVIDENCE` is the absolute directory above; `--junitxml=EVIDENCE/STEM.xml` below denotes that exact absolute path, not an environment fallback.

| Stem | Exact pytest arguments preceding JUnit argument | Native exit/result |
|---|---|---|
|01-red|`['tests/test_telegram_sampling_runner.py','-q']`|1; causal test fails in enqueue_window function body at NotImplementedError; 1 failed|
|02-green|`['tests/test_telegram_sampling_runner.py','-q']`|0; 1 passed|
|03-boundaries-red|`['tests/test_telegram_sampling_runner.py','-q']`|1; 3 failed,1 passed: private RuntimeError escaped, backwards final clock stored history, SQLite savepoint leaked history after failed job update|
|04-boundaries-green|`['tests/test_telegram_sampling_runner.py','-q']`|0; 4 passed after all3 corrections|
|05-expanded|`['tests/test_telegram_sampling_runner.py','-q']`|1;81 passed,1 teardown error: old history helper assumed exactly1 revision globally while fair-window test intentionally seeded20 sources; corrected checker to retain original source/REJECT plus zero authority side effects|
|08-flood-clock-red|`['tests/test_telegram_sampling_runner.py','-q','-k','concurrent_cooldown or between_precheck']`|1;4 failed:2 concurrent cooldown outcomes, sync precedence, backwards prefetch test exhausted its initial2-value fake clock|
|09-clock-causal-red|`['tests/test_telegram_sampling_runner.py','-q','-k','between_precheck']`|1;1 failed,84 deselected after supplying3 clock values: SAMPLED instead of STALE_CLAIM (causal assertion)|
|10-focused-green|`['tests/test_telegram_sampling_runner.py','tests/test_telegram_sampling_postgres.py','-q']`|0;85 passed,17 skipped;17 record_property/xunit2 warnings retained|
|14-focused-final|`['tests/test_telegram_sampling_runner.py','tests/test_telegram_sampling_postgres.py','tests/test_engagement_sampling.py','tests/test_telegram_sampling_migration.py','-q','-o','junit_family=legacy']`|0;255 passed,19 skipped in60.19s; pristine|
|18-regression|`['tests/test_telegram_engagement.py','tests/test_telegram_engagement_history.py','tests/test_account_health.py','tests/test_telegram_provider_factory.py','tests/test_donor_ingestion_runner.py','tests/test_durable_ingestion_workflow.py','tests/test_publication_observation_recovery.py','tests/test_editorial_gate.py','-q','-o','junit_family=legacy']`|0;215 passed in32.16s; pristine|
|21-runner-final|`['tests/test_telegram_sampling_runner.py','tests/test_telegram_sampling_postgres.py','-q','-o','junit_family=legacy']`|0;103 passed,20 skipped in30.81s; pristine, final source/test generation|

For each row the final argument was `--junitxml=D:/Codex-Recovery/content-studio-20261008/telegram-sampling-task2-20261013a/STEM.xml`. Full backend was deliberately not run: one combined full run is reserved after Task3.

Exact scoped static commands, with the same raw output/native exit capture convention:

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check src/newsflow/services/telegram_engagement_sampling.py tests/test_telegram_sampling_runner.py tests/test_telegram_sampling_postgres.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check src/newsflow/services/telegram_engagement_sampling.py tests/test_telegram_sampling_runner.py tests/test_telegram_sampling_postgres.py
python -m compileall -q src/newsflow/services/telegram_engagement_sampling.py tests/test_telegram_sampling_runner.py tests/test_telegram_sampling_postgres.py
```

Static run record: `06-ruff-fix` used check with `--fix`, exit1 (12 findings,3 fixed; corrected unused names and deliberate boundary validation/private catch suppressions). `07-format` exit0. `11-ruff` exit0. `12-ruff-fix`/`13-format` exit0. `15-ruff-final`/`16-format-final`/`17-compile` exit0. After extra native-SQL/authority assertions, `19-ruff-fix`/`20-format` exit0 and final `22-ruff-final`/`23-format-final`/`24-compile-final` all exit0. Final output: `All checks passed!`, `3 files already formatted`, compile quiet. Format runs omitted `--check`; Ruff-fix runs appended `--fix`. All failures and intermediate warnings remain retained.

## Self-review, limitations and freeze

Read the source and scoped tests before handoff. Checked lock ordering, pre-IO committed ownership/no checked-out connection, time-of-lock expiry, late/missed schedule math, immutable publication/replay conflicts before history writes, provider exception privacy versus uncaught SQL interruptions, attempted reset/terminal guard compatibility, third-attempt exhaustion, and stale health/session fencing. No unresolved implementation defect was found.

The initial nested savepoint was removed after causal RED proved SQLite legacy transaction handling could release source/history independently of a later failed job flush. The final implementation uses one outer transaction; both synthetic driver interruption and native SQL trigger failures prove rollback with the committed RUNNING lease retained. No history/migration guard was weakened.

Limitations: actual PostgreSQL execution and cross-task/full-backend/worker integration are intentionally controller-owned subsequent gates. Bounded16 claim lookup can defer jobs behind repeatedly long-held locks in the earliest candidate window, as explicitly ruled by the controller. SQLite tests validate durable behavior and rollback; PostgreSQL-only locking semantics are not claimed proven by SQLite. No worker/Compose setting was activated; no live external credentials, login, AI call, real queue/session/publication mutation, push/merge/force/PR/reset/drop/reseed was performed.

SHA256 of final working-tree implementation bytes, after final format/check/compile and final runner tests (case-insensitive hex):

| File | SHA256 |
|---|---|
|backend/src/newsflow/services/telegram_engagement_sampling.py|`0a3874ade86e3f30b7cec84bbca4d85251c0f890af2603cf1783556de598ef7a`|
|backend/tests/test_telegram_sampling_runner.py|`d894f3a72a06d001bf9f39c881b22ddb9a6970949b2a8ebc781d1b56ce22464f`|
|backend/tests/test_telegram_sampling_postgres.py|`1591e60ec6fa17f5e27de9d785eea6917d09e11617073f280ffcd218ac7fa7b3`|

Source freeze starts at this report. Only the three owned files and this report are staged/committed; controller dirty docs/evidence are preserved and excluded. Commit identity is reported in the handoff; no accepted commit is amended.

Staging note: initial exact-path `git add --` staged the three source files but refused the report because `.superpowers/sdd/TELEGRAM_SAMPLING_IMPLEMENTATION` is ignored. The report is therefore added with `git add -f -- .superpowers/sdd/TELEGRAM_SAMPLING_IMPLEMENTATION/task-2-report.md` only, as explicitly required by the task; no other ignored path is included. `25-staged-check` is native `git diff --cached --check`, exit0, quiet; it ran before the report was force-added. Final four-file staged check is retained separately.
