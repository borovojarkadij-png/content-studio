# Exact-candidate CI recovery — 2026-10-12

Origin: borovojarkadij-png/content-studio. Branch: codex/dark-navy-ui.
No merge/force-push/disabled assertion or live provider activation.

## Original failed candidate

Run38294424666, head24e515eb4e62b2a04e38d23651f621870f1a11ae:
Backend quality gate/job114961980698 failed before tests at lint. Log confirms
fresh dependency resolution installed Ruff0.17.0; the existing scheduler negative
test had unused `# noqa: DTZ001` at tests/test_scheduler_worker.py:153. Local
Ruff0.16.6 had passed the same command. No runtime/planner behavior failed here.

Root installed only isolated test-tool Ruff0.17.0 under
D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012, no global upgrade.
`python -m ruff` still selected installed0.16.6 despite PYTHONPATH; using the
explicit native target executable reproduced the exact RUF100/exit1. Removed
only unused suppression, retained intentional naive-time input and explanatory
comment. Native0.17 full exact workflow lint command PASS; scheduler4 PASS/1.03s.
Verified correction commit81dd4f00a71061cbc3727bb8ba76b4b02da4a9d4 pushed only
authorized origin/branch using process-local existing owner identity.

Completed supporting jobs of the original failed candidate, read from native
GitHub logs (not a claim of whole-workflow success):

- PostgreSQL job114961980610: migrated332 PASS/373.90s; real controlled
  planner/media concurrency5 PASS/7.26s, including the three residual I4 cases.
  Expected constraint/deadlock-control ERROR lines occur in passing negatives;
  they are not omitted or misrepresented as unexpected failures.
- Illustration job114961980711: focused136 PASS/27.69s; actual Linux packaged
  health/pending down-up/PostgreSQL crash/fake execution/final down-up/double
  reopen PASS. Real Telegram/AI calls0; live acceptance SKIP explicitly.
- Frontend, guarded admission and channel-sync jobs completed SUCCESS at this
  checkpoint. Remaining jobs were running; original workflow is not accepted.

## Corrective candidate

Exact run38294917279/head81dd4f00a71061cbc3727bb8ba76b4b02da4a9d4 is currently
in_progress. Terminal verdict/log counts must be recorded before acceptance;
neither the original partial successes nor local lint predicts that verdict.
New classifier contract work is independent/unwired and is not included in this
SHA. Its source gate/review/new exact CI are separate requirements.

Subsequent exact corrective job logs inspected:

- PostgreSQL114963572876 SUCCESS: migrated332 PASS/324.08s and real controlled
  planner/media concurrency5 PASS/6.17s.
- Frontend114963572723 SUCCESS:243 unit tests, production build PASS,33 existing
  browser tests plus1 protected illustration browser PASS/11.0s.
- Authenticated illustration, channel sync and guarded admission SUCCESS.
- Backend/full-stack/two provider recovery jobs still running at this checkpoint.
  Whole workflow is not yet accepted.

Later exact corrective logs establish backend114963572824 SUCCESS:
1989 PASS/6 explicit PostgreSQL-only SKIP/457.23s, lint/fixture lint/compile and
isolated migration cycle/no-drift PASS. The six skips are covered separately
by actual PostgreSQL332+5 above. Full-stack114963572447 SUCCESS:
1 PASS/4 deliberately deselected/356.64s and packaged no-drift PASS; synthetic
combined fixture/storage retained. Both provider recovery jobs still running;
the complete workflow is not accepted until terminal.

Terminal corrective run38294917279 is now completed/SUCCESS, all9 jobs
SUCCESS including both OPENAI/OPENROUTER synthetic persistence families.
Original run38294424666 completed/FAILURE: backend lint failed, all other8 jobs
SUCCESS. Both provider original logs end with retained persistence PASS and
zero-network synthetic publication verification; no live acceptance inferred.
This terminal acceptance is exact81dd4f0 only, not classifier source67afc09.

## Offline classifier candidate

Exact run38296489059/head21c08a716d4af0316a5f941af69d27dbe34dd57a includes
the independently accepted classifier contract67afc09. Root read native completed
job logs rather than attributing prior-candidate counts to this source:

- PostgreSQL114968694154 SUCCESS:332 PASS/240.84s plus5 controlled concurrency
  PASS/4.67s.
- Frontend114968694138 SUCCESS:243 unit tests, production build PASS,33 browser
  plus1 protected illustration browser PASS/11.0s.
- Illustration114968694009 SUCCESS:136 regressions/38.33s, packaged synthetic
  create/restarts and original-state double reopen PASS; live acceptance SKIP.
- Guarded admission SUCCESS. Backend/full-stack/channel-sync/two provider
  persistence jobs are still running at this checkpoint. No terminal whole-run
  acceptance yet; the new adapter work is not included in this candidate.

Later completed logs establish backend114968694152 SUCCESS:2084 PASS/6 explicit
PostgreSQL-only SKIP/353.17s, lint/compile/migration cycle/no-drift PASS.
Full-stack114968693727 SUCCESS:1 PASS/4 deliberately deselected/341.10s plus
packaged no-drift. Channel sync also SUCCESS. Both provider persistence jobs
still running; whole exact candidate is not accepted until terminal verdict.

## Windows runtime boundary

Fresh root check: real Linux Engine29.8.0 responds; retained20261009c API,
PostgreSQL, Redis and production web healthy, other worker/dev-web running.
Actual HTTP18239/healthz and18339/healthz return newsflow-api/statusok.
No reseed/rebuild/secret regeneration, operational queues or real sends.
Full retained original-state reopening proof is in
DOCKER_STARTUP_RECOVERY_20261012.md. This does not complete PHASE1/live acceptance.
