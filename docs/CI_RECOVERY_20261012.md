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

Terminal run38296489059/head21c08a7 completed SUCCESS, all9 jobs SUCCESS.
Root read both provider terminal logs: original-state synthetic persistence
checks passed, publication pending/final/reopen checks passed, actual Telegram/
AI network calls0. This accepts classifier contract candidate67afc09, not later
adapter source6dd3517. Reviewed adapter/docs pushed1d00655, exact new
run38297928080 is in_progress and must execute/upload the new benchmark artifact.

## Classifier adapter exact CI accepted

Terminal run38297928080/head1d00655e7722ea615f23a35f860800b01d1d1bff is
completed SUCCESS, all9 jobs SUCCESS. Native completed backend114973443738:
2182 PASS/6 explicit PostgreSQL-only SKIP/772.41s, native lint/compile,
isolated migration cycle and no-drift PASS. Separate PostgreSQL114973443849:
332 PASS/330.84s plus5 controlled concurrency PASS/6.64s. Full-stack114973443746:
1 PASS/4 deliberately deselected/337.48s and packaged no-drift PASS. Both provider
families retained-state persistence/publication reopen PASS, real network calls0.

The newly required offline benchmark actually executed and uploaded artifact
editorial-classification-contract, ID11770351819. Root downloaded that exact
run's artifact to D:/Codex-Recovery/content-studio-20261008/editorial-contract-ci-38297928080/.
Report SHA256318DE43F3C8C0DE9501B324A31B14C3390E6AFE6470A6913571393A0B9896E45:
24 cases/24 matched/0 mismatched, SYNTHETIC_CONTRACT, provider_calls0,
rewrite_calls0, real_model_qualified=false. Not real model accuracy or authority.

Native runner warns that existing checkout/setup-python/upload-artifact action
versions target deprecated Node20 and are forced to Node24. This did not fail
the run; no workflow check was disabled. Future action-version maintenance is
separate from this narrow source increment, not silently hidden or auto-upgraded.
New durable admission source is not part of this SHA and needs its own exact CI.

## Canonical durable admission candidate

Independently reviewed source88ce234, report provenance0d142f1 and root evidence
pushed at e8b761728c6630473620adb04b518b8262c2283b to authorized origin/branch.
Exact run38300513652 is in_progress; no prior candidate substitutes for its
expanded PG/admission migration gate. Diagnostic executor is a later independent
task and is not included in this SHA. No checks/permissions/timeouts disabled.

Completed native backend114982032345 is SUCCESS:2301 PASS/6 explicit
PostgreSQL-only SKIP/347.20s; lint/compile/migration/no-drift PASS. Actual
PostgreSQL114982032560 is SUCCESS:420 PASS/255.64s plus5 controlled concurrency
PASS/4.79s. Frontend, channel-sync, illustration and guarded admission jobs also
completed SUCCESS. Both provider persistence families and full-stack were still
running at this inspection; whole-run acceptance remains pending.

Root downloaded this exact run's editorial-classification-contract artifact
ID11770269469 to
D:/Codex-Recovery/content-studio-20261008/editorial-contract-ci-38300513652/.
Actual report SHA256318DE43F3C8C0DE9501B324A31B14C3390E6AFE6470A6913571393A0B9896E45:
24 cases/24 matched/0 mismatched, SYNTHETIC_CONTRACT, provider_calls0,
rewrite_calls0, real_model_qualified=false. Its equality to the prior report
does not replace executing/downloading the new candidate's actual artifact.

Terminal run38300513652/head e8b761728c6630473620adb04b518b8262c2283b is
completed SUCCESS, all9 jobs SUCCESS. Root read native full-stack114982032513:
1 PASS/4 deliberately deselected/346.48s and packaged no-drift PASS.
Both provider jobs114982032270/114982032326 end with original-state synthetic
persistence PASS, publication pending/final/double-reopen PASS and explicit
zero Telegram/AI network calls. This accepts admission candidate88ce234 and
its associated root docs, not the later uncommitted execution task.

## Corrected diagnostic execution candidate

Executor c9c16d1 plus independently accepted lease-clock correction e29779b and
root evidence/review reports pushed at388cb3cc92490ad8f8a9cd8106308863b1b5100e.
Remote exact branch ref independently read/verified; correct owner/origin/branch,
no persistent authentication switch. Native git push succeeded0; outer wrapper
returned1 from optional suppressed missing-variable cleanup after success. No
push retry or force was performed, independent remote verification native0.
Exact CI38304194927 started all9 jobs; terminal result remains pending.
Original full2462/7 identifies c9, not amended bytes. Corrected covering326/5
PG-only skips and root actual WindowsPG10/noSKIP/native0 plus clean scoped
re-review are accepted; exact amended remote complete suite remains required.
New PG list includes the executor/actual-held-row cases, not only old admission.
Later encrypted-factory/worker implementation is independent/not in this SHA.

Exact backend114994133321 completed SUCCESS:2468 PASS/11 explicit PG-only SKIP/
545.67s, lint/compile/migration/no-drift PASS. Root read native terminal summary.
This is the amended executor's actual remote full suite, distinct from original
c9 local2462 gate. No automatic approval or later worker source is covered.
Downloaded exact-run benchmark artifact11772106662 to
D:/Codex-Recovery/content-studio-20261008/editorial-contract-ci-38304194927/:
raw report SHA256318DE43F3C8C0DE9501B324A31B14C3390E6AFE6470A6913571393A0B9896E45,
24/24/0mismatch, provider/rewrite calls0 and real_model_qualified=false. Root
validated all case flags; repeated content hash does not substitute for this
new run's actual execution/download.

Strict PG114994133488 completed CANCELLED at the configured ten-minute deadline;
no terminal test PASS exists. Original native log retained:
D:/Codex-Recovery/content-studio-20261008/editorial-execution-ci-38304194927/postgres-job.log,
SHA2560B7D845B228999FAF037142DEBBBCD89F362A01D60BA34EAC9FD88D98CC88707.
Actual progress13/26/39/52/65/78/91% at20:27:24..20:36:14 with no assertionFAIL,
then operation-canceled20:36:25. Concurrency step deliberately not run because
job was canceled; it remains SKIPPED, not PASS. Expected negative PostgreSQL
constraint ERROR lines in container teardown are test evidence, not the cause.
Fresh migrated workload grew420->550 cases; measured progress outran old job
deadline, not a demonstrated deadlock. Checkpoint log confirms large schema-file
write activity. Same task writer authorized to change only this finite job
budget10->20 after its frozen suite; all checks/commands/isolation retained.
Correction and exact new-source CI required; current whole-run not accepted.

Terminal exact run38304194927 is completed CANCELLED,8 jobs SUCCESS/1 PG CANCELLED.
Root inspected both provider native tails: synthetic publication pending/final/
double-reopen/persistence PASS, explicit zero Telegram/AI network calls. Actual
full-stack114994133467:1 PASS/4 deliberately deselected/354.61s, packaged drift
PASS. Frontend/channel-sync/guarded admission/illustration jobs SUCCESS. No
rerun overwrites this canceled original; new finite-budget candidate must pass.

## Diagnostic factory/worker and finite PG budget candidate

Source af45deba6aaf6238a7d4901cca577184911d496d adds the bounded opt-in
diagnostic factory/worker. Its sole full local gate terminated native0:
2565 PASS/11 explicit PG-only SKIP/525.51s, no warnings. Separate root WindowsPG
new-file gate97 PASS/55.81s/noSKIP/native0. Frozen five implementation hashes
unchanged; final report and seven-file commit independently inspected.
After full termination, the authorized CI diff changes only
unattended-postgres.timeout-minutes10->20. All commands, safety flags, service
settings, failure propagation and other budgets remain unchanged. YAML/exact
single-change/static checks passed. This corrects a measured deadline, not a
failed assertion; prior38304194927 remains CANCELLED/8SUCCESS+1PG cancellation.
Independent task review speccompliant/qualityApproved/no findings; root read
complete report and resolved native-provenance item from original logs/hashes.
Corrected exact-new-source CI remains pending.
No local test or earlier artifact substitutes for that CI. No live activation.
Reviewed source and root evidence/review committed/pushed at
65ed7f22e3d8cefc760210bb391c96f9d38a4267. Native git push0 and independent exact
remote ref verified, process-local owner credential restored without persistent
authentication switch. Root tracks this new run while history writer proceeds.
Exact run38306240255/head65ed7f2 completed SUCCESS in all9 jobs. Root downloaded
actual native logs: strictPG115000865985 550PASS/577.47s and concurrency5PASS/8.07s;
backend115000866311 2565PASS/11 explicit PG-only SKIP/615.59s, Ruff/compile and
no-drift PASS. The measured finite20-minute correction passed; original canceled
38304194927 remains canceled, not rewritten as success.
Full-stack115000866038:1PASS/4 deliberate deselections/353.93s and packaged drift
PASS. Both provider persistence families115000866229/115000866239 include pending,
final and double-reopen publication PASS with explicit zero Telegram/AI calls.
Other frontend/channel-sync/guarded-admission/illustration jobs also SUCCESS.
Root separately downloaded artifact11772269923 into
D:/Codex-Recovery/content-studio-20261008/editorial-contract-ci-38306240255/;
report SHA256318DE43F3C8C0DE9501B324A31B14C3390E6AFE6470A6913571393A0B9896E45.
Actual JSON asserts case_count24/matched_count24/mismatched_count0,
provider/rewrite calls0 and qualificationfalse; it remains synthetic-only. No
real-model accuracy or operational acceptance is inferred. Native logs retained
under D:/Codex-Recovery/content-studio-20261008/editorial-worker-ci-38306240255/:
postgres-job.log SHA256198E9BC6905920936D88D996FCF5A2CA6E078EE3C02D3BA14C2EB2566DC39E83;
backend-job.log SHA256DF2815941D6806B275A1C555CFF72C1BB76D423D801175E71D370598C1F7408A;
fullstack-job.log SHA256C0C39A4C754B76828EDE8FF8555576F1691689724E25F2F94328613554CFEC8A;
openai-job.log SHA256DB35F36234B1727428DCB872A3DBFA472A2589AC425F3848320BB530F48515B4;
openrouter-job.log SHA256F7336016ABB663E14904F55B0BB6581C82D623FF61C8FEA52AACD37ED5863B72.
This exact SHA does not include the subsequent uncommitted history-reader task.

## Subsequent retained diagnostic history — accepted locally October13

Source fbb4c6e plus fixfae11e7 independently accepted after one terminal-receipt
coherence finding. Original frozen full2643PASS/11 explicitPG-only skips/native0;
root actualWindowsPG78PASS/noSKIP. Fix original RED4FAIL/6positivePASS, covering
213PASS/5 inheritedPGskips and rootactualPG10PASS/noSKIP/native0; two amended
hashes unchanged. Scoped re-review findingADDRESSED/speccompliant/qualityApproved,
no new findings. Original full is not amended-byte proof; exact new-source CI
must pass separately. Source/reviews/rootdocs are ready to commit/push; remote
new-source run not yet assigned. No live calls, operational changes or UI edits.
See EDITORIAL_DIAGNOSTIC_HISTORY_VERIFICATION_20261013.md.

## Current Windows runtime boundary

Earlier retained20261009c HTTP/health/reopen checks passed as recorded below;
they are not the current post-Desktop-recovery container state. Latest resume
restored actual Linux Engine29.8.0 after the recurring runtime-socket failure.
Only exact owned synthetic unattended PostgreSQL was started, completed normal
interrupted-system fsync/recovery and accepts connections. Retained1697 UUID
namespaces/maxOID1294081 exactly match the pre-stop baseline. No current API
health claim is made. Root strict new-file history PG gate now runs fresh schemas.
No reseed/rebuild/secret regeneration, operational queues or real sends.
Full retained original-state reopening proof is in
DOCKER_STARTUP_RECOVERY_20261012.md. This does not complete PHASE1/live acceptance.
