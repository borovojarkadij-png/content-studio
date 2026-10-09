# Task 4 independent review

## Spec Compliance

- **Issues found.** The requested packaged HTTP, persistent original-row verification, synthetic photo transport, REJECT/no-rewrite assertion and independent CI job are implemented. Two operation-target safety gaps prevent approval: redirected build/bind inputs are not refused before writes, and retained startup can execute changed images before the immutable-image guard detects them.
- Reviewed package: `dae0e3057b6c3b6b5d6b174b944e2b0babb01c15..bfba7ede98d775510abd5353f4182c68ceb60b18`. All eight listed changed files are present in the diff. No production source/schema changes or removal of existing CI checks appear in this package.
- **Cannot verify from this diff:** unchanged editorial/source/draft/fact/technical/rights/sync/clean-session enforcement beyond the scenarios explicitly exercised here. These remain cross-task review responsibilities. New CI execution is pending, and live Telegram/AI/publication acceptance is correctly SKIP.

## Strengths

- `scripts/docker_illustration_probe.py:217`, `:374`, `:595`: the packaged flow uses real HTTP bearer authentication, refuses unauthenticated presentation, obtains canonical presentation/photo validators, records server-issued reviewer identity/provenance and revokes through HTTP. It does not supply client reviewer identity or provenance as authentication.
- `scripts/docker_illustration_probe.py:318`, `:356`: configured photo publication receives an injected synthetic Telethon client, checks the actual SendMediaRequest, nonce, paid-send refusal and SENDING state, and returns a direct-response receipt. No real client constructor is used by this probe.
- `scripts/docker_illustration_probe.py:639`: reopened verification checks original review/audit rows, encrypted snapshot and account/peer material, exact photo digest/dimensions, original publication nonce, a single encrypted direct-response observation, blocked revoked/stale intents and NEEDS_RECONCILIATION for abandoned SENDING. REJECT/rewrite_allowed=false and the unchanged original four zero-attempt rewrite jobs plus zero usage are asserted.
- `backend/tests/test_illustration_restart_probe.py:56`: a migrated database and actual loopback Uvicorn server exercise the probe; independent engine reopen, SQL write observation, two read-only verifies, one fake send and no reseed are materially useful behavioral checks.
- `scripts/illustration_restart_controller.py:49`; `backend/tests/test_illustration_restart_guards.py:470`, `:508`: Windows alias normalization preserves original manifest bytes and all mount/image/environment metadata, with foreign-drive/path/traversal and changed permission/type/destination regressions. The regression reaches the actual resource validator.
- `.github/workflows/ci.yml:126`: a separate job adds lint, refusal/HTTP regressions, packaged PostgreSQL restart/crash execution and retained verification; existing jobs are not disabled.

## Issues

### Critical

- None found in the reviewed scope.

### Important

1. **Reject redirected build and bind sources before creating the fixture.** `scripts/illustration_restart_controller.py:328` validates only the two Compose files themselves. It never applies the existing `safe_path` guard to `backend`, `frontend`, or the bound `scripts/docker_illustration_probe.py`. Their lexical paths can remain identical while a Windows junction or symlink points outside the checkout. `create()` then writes the artifact/secret files at `:280`, and initial startup at `:650` uses those redirected inputs. The unchanged Compose graph binds `frontend` read/write and runs `npm ci` there, so a redirected frontend can also mutate foreign storage before the runtime comparison refuses it. Hashing the YAML does not validate the storage to which its relative paths resolve; the existing redirected-parent test covers `.artifacts`, not these sources. Validate the owned input directories/files and relevant Dockerfile paths before any fixture write or Docker mutation, repeat that validation for retained operations, and add covering redirected-input cases asserting zero writes/mutations. This violates the brief's unsafe/redirected target and refusal-before-mutation requirements.

2. **Use the recorded immutable images for retained startup, or refuse changed image resolution before mutation.** `scripts/illustration_restart_controller.py:598` and `:624` call ordinary Compose `up` with the original mutable image references/default build tags. The earlier resource check compares `runtime.json` with the currently existing containers, which says nothing about where those tags resolve now. If a local project build tag or postgres/redis/node tag has changed since initial creation, down/up can start the new image, including the migrations service against retained PostgreSQL. The immutable-image mismatch is detected only at `:602` or subsequent health validation, after those processes have run. Pin retained startup to the captured IDs with no build/pull fallback and refuse missing/mismatched required images before down, crash or up. Add a regression in which the running containers still match the baseline while tag resolution changes; no mutation may occur. This is a guard-ordering defect, not a claim that the recorded Windows run actually used changed images.

### Minor

- None additionally raised.

## Named checks and evidence boundaries

- **Controller prewrite/operation safety:** read the complete controller and covering guard tests in the diff. One focused outside-diff check read `compose.yaml` and `compose.illustration-review.yaml` to verify the actual relative build/bind inputs, read/write frontend mount, mutable image references and migrations startup dependencies. This establishes the two findings above.
- **Exact PostgreSQL crash targeting:** one focused outside-diff read of `scripts/verification-postgres-crash.ps1` confirmed exact 64-character container ID selection, repeated project/service/running-state verification, SIGKILL of that exact ID and exit-137 barrier. This helper is unchanged in the reviewed package.
- **Strict manifests/Windows aliases:** inspected ownership/row/auxiliary validation and the duplicate/boolean/foreign-manifest and alias regression cases. The observed alias fix does not broaden accepted drives or paths and does not rewrite runtime.json. The two safety findings are independent of that normalization fix.
- **Actual retained Windows evidence:** read `docs/ILLUSTRATION_RESTART_PARENT_20261009.md` and all three named native-output logs. `D:/Codex-Recovery/content-studio-20261008/task4-retained-verify-20261009a.log:1` records two successful independent final reopens. `task4-retained-recovery-20261009a.log:65` records two successful reopens after original-graph recovery. `task4-retained-boundaries-20261009a.log:94` records restart success and two final reopens; `:138` records crash success and two final reopens; `:143` records the last two reopens, with no migration drift at `:145`. No warning/error output appears in these supplied successful native logs.
- **Evidence limitations:** the original full creation/build/pending-before-crash stages are described by the parent record but the referenced initial transcript is explicitly metadata-only. The supplied native retained logs independently support corrected retained boundaries; they are not an independently complete transcript of the original build/seed/pending execution. Likewise, the reported full-backend 1871 PASS/1 SKIP and scoped 94 PASS are report assertions tied to sessions, not raw test output present in the reviewed package. No suite was rerun to replace that evidence. Original create failure and parent logging-wrapper failure remain failures, not relabeled successes. Separate Redis/worker restart evidence is after publication execution; pending-state recovery evidence concerns whole-stack and PostgreSQL boundaries.
- **Persistent identity and zero resend:** checked the probe's exact row/hash/nonce/receipt comparisons against what the logs actually run. Final verify is read-only and does not call the runner; initial fake execution additionally checks exactly one upload/send and an extra IDLE run. This establishes synthetic acceptance, not any live provider guarantee.
- **Review discipline:** complete diff read once in bounded chunks, followed only by line-reference indexing; no broader source crawl, source edits, helpers, tests, Git mutations, Docker operations or fixture writes. Only this report was written.

## Assessment

**SpecCompliance: Issues found. Quality: Needs fixes.**

The functional verification is substantial and the retained Windows evidence supports the corrected synthetic persistence scenario. The controller must close the two pre-mutation target-validation gaps before this task's isolation and immutable-runtime claims can be trusted.
