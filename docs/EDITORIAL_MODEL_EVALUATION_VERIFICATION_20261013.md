# Bounded editorial model evaluation verification — 2026-10-13

Status: IMPLEMENTATION ACCEPTED LOCALLY; EXACT NEW CI PENDING. NOT MODEL QUALIFICATION.
Repository borovojarkadij-png/content-studio, branch codex/dark-navy-ui.
BASE34ad476550f4a33ddbe2de71f0ad6ce4a743462a.
Requirements: EDITORIAL_MODEL_EVALUATION_IMPLEMENTATION.md and own SDD brief.
Sole source writer /root/editorial_model_evaluation; root owns this report,
CURRENT_STATE/IMPLEMENTATION_PLAN, independent native checks and remote CI.

## Scope

Separate labeled synthetic fixture, bounded diagnostic evaluator and explicit
opt-in CLI. Reassess actual source-bound evidence rather than trusting a returned
verdict. Default no provider calls; one fixed accepted classifier, no retry,
repair, rewrite or fallback. Reports stay UNATTESTED/unqualified with false
execution/rewrite permission. No SQL/schema/worker/settings/UI changes.
Implementation tests use injected HTTP and synthetic credentials, not live keys.

## Original behavioral TDD evidence

Root read the actual original logs, without repeating the RED cycle:
D:/Codex-Recovery/content-studio-20261008/
editorial-model-eval-05c41d0c5be74af099ae3c5be2836a38/.

red.log:1FAIL/0.18s, accepted classifier counted one injected HTTP request.
A misleading returned PASS replaced source-bound evidence requiring REJECT;
the assertion compared actual_diagnostic_status PASS against REJECT. This was
a behavioral failure, not absent-import or route setup evidence. Raw log SHA256
087CB5BC5AD4DBF496038F4D0861CFA08B244806428C99B11CFBC551937E4330.
The raw RED log has no native exit marker; actual native provenance remains
writer-owned until its final report/tool result, not reconstructed by root.

green-initial.log:1PASS/0.05s with explicit NATIVE_EXIT=0 marker; SHA256
6F3ED330B18E1639D6BCF707A9936E213B468F4FBDA1F6740FA4559404EE8325.
This is initial narrow evidence only; subsequent frozen checks follow below.
No implementation or benchmark acceptance is inferred before scoped review.

## Frozen local checks

Root read actual focused-final.log:361 PASS/18.65s/native0. Ruff0.17 full
backend CI lint command, three changed Python files format, compile and exact
single CI script suffix/retained strictPG20-minute job/24-case fixture checks
all recorded native0. diff-final.log native0 retains Git's LF-to-CRLF warning;
no test warning or failure is hidden and no Git configuration changed.

Root independently hashed the five frozen files:

- service: CCAAD2B3535A91A774987098353C2128DDADD471AF982467B240A4622ED16769
- fixture: 02E2C54AA9F907A64EA2B697F8A34529D2C4EA0384DE2225516EEF944264BC10
- tests: FDEC20E8F24EDF5252752FE3CB0CE5B2A6862D2105FC94073280B671166AC092
- CLI: 5E583F934169377F5AC3A3814C8D94D4CBE78C943E1486923D2684477A6E9B1E
- CI: E38CF4204E093961B8F9BCF3D8E240E1F9073F9F78126116AC92F443BD2A187D

Independent root command python scripts/evaluate_editorial_model.py returned
expected native2/PROVIDER_CALLS_DISABLED, attempted_count0/rewrite_calls0,
all permission/qualification flags false and transport UNATTESTED. Wrapper
assertions PASS/native0. No credential was read or transport constructed.
Evidence directory D:/Codex-Recovery/content-studio-20261008/
editorial-model-root-cli-e5f5abcd24a44fc48b30ecf3d5bdee8b/;
native.log SHA2564EF310307A2F55159637E80F2076A0BDE402295B3FF0AA21439C12F9E3ACA7C3,
exit.log records2. Expected refusal is not a failed implementation check.

Original full invocation session26469 used repository root cwd, whereas existing
tests resolve alembic/alembic.ini relative to backend cwd (as CI does). Early
failures exposed this invocation error; it is not passing evidence. Writer will
stop only its own invalid-cwd process and preserve its interrupted native/log
result, then run the one valid complete backend gate from backend cwd with
Python3.12/explicit Telethon1.45 and fresh isolated D: temporary storage.
Root ruled this necessary correction explicitly; no source edits or test
weakening. All five source hashes remain frozen. Final raw/native/hash inspection
and review pending; no PostgreSQL/UI/recovery test rerun needed for this pure seam.

Actual correction: session26469 interrupted with tool native1, no pytest terminal
summary or invented native marker. Original full-once.log SHA256
833FD6985EA149D86EB64988BA477CCD28828FF2A0317B97463144BE582FE22D,
independently hashed by root. No matching Python descendant remained.
Corrected sole valid backend-cwd gate is session84779/full-corrected.log;
source hashes unchanged, terminal pending. Initial own report read through EOF;
final terminal append/commit/scoped independent review still required.

Corrected full gate terminal:2744PASS/11inheritedPG-onlySKIP/415.63s,
NATIVE_EXIT0/no warnings in full-corrected.log. Root read actual terminal log,
SHA25655C4D62A780FF964A8BD88633D5DD5C9170A509FF581A1B1EC11CEB1604DE23C,
and independently rehashed all five frozen files unchanged after completion.
Skipped tests are not local PASS; accepted predecessor actualPG/CI evidence
remains separate. Writer native session result/final report/owned commit and
fresh scoped spec+quality review still pending; no second valid full run.

## Separate exact history-source CI

Run38310060502/head34ad476 checks the accepted preceding history task, not this
uncommitted evaluator. Five jobs completed SUCCESS at last inspection;
backend/both general persistence families still running. StrictPG completed:
638PASS/562.20s plus5concurrencyPASS/7.64s, native job115013300226 SUCCESS.
Downloaded postgres-job.log SHA256
248E8D9082B7468494C1CD4A720716E4CC95D74A51BB082C1F4AE2991C5BD4F3.
Actual
full-stack job115013300234 native log downloaded:1PASS/4deselected/341.24s,
packaged migration no-drift. Root SHA256
ADA548DDCE5ED6D07D937B99BA0CA893689505DCDF625E4861307A969E9FC98E
at D:/Codex-Recovery/content-studio-20261008/editorial-history-ci-38310060502/
full-stack-job.log. Whole run still in progress. Prior65ed all9 PASS remains
predecessor evidence, not final evaluator proof.

## Independent source acceptance

Writer commitbacdd1854054316c5d99f1420ef915e9b381cc95 contains exactly five
source/fixture/test/CLI/CI files plus own146-line final report. Root read report
through EOF/native terminal/eleven explicit skip reasons and verified inventory.
Complete BASE34ad..bac package77126bytes reviewed by fresh
/root/editorial_model_evaluation_review:speccompliant/taskqualityApproved,
no Critical/Important/Minor. Verbatim task-1-review.md saved.
Root resolves both provenance/cross-task ⚠️: original actual logs/five hashes/
safeCLI/remote identity are inspected above; existing accepted admission/runner/
history tests and actualPG CI preserve REJECT/no-new-RewriteJob/zero calls.
This pure diff adds no SQL/runtime permission integration. Real qualification
and live acceptance stay pending, not waived by source review. Root docs/push
and exact new-source CI are next; predecessor34ad all9 is not bac-source proof.

Root evidence/reviews commita639591f3683da9251f2a5915d667f3f204808cb pushed
native0 to the authorized origin/branch; independent remote-ref check matches
exactly, process-local owner credential restored in finally. Exact new evaluator
CI38312315852 started/all9 in_progress, not PASS. Root tracks alongside the next
independent internal policy-configuration task; no new model/operational authority.

Exact evaluator CI38312315852/heada639591 partial actual evidence (whole run
still in_progress): strict PostgreSQL job115020722860 SUCCESS,638PASS548.37s
plus5concurrencyPASS6.92s; full-stack115020722852 SUCCESS,1PASS/4deselected
336.73s and no new upgrade operations. Actual native logs downloaded by root:
D:/Codex-Recovery/content-studio-20261008/editorial-model-ci-38312315852/:
postgres-job.log SHA256
960FFE0FCB4CBFF56525601AD636FCC08A86C1A9C2794672A536A6694946B594;
full-stack-job.log SHA256
84D7998DE80D2AD04A470967AB8F291A5A4F55EE581A6643E46A29F4986EBAD4.
Backend and both provider persistence families remain in progress at inspection;
this partial success is not whole-CI acceptance or current policy-task proof.

Backend115020723038 subsequently SUCCESS:2744PASS/11explicitPG-onlySKIP/
593.78s, Ruff/compile/migration no-drift PASS. Actual backend-job.log SHA256
DFD839C08B8833DF700BD1B26A6169F740F174C54612AD55B8504839030F5AEC,
same native-log directory. Actual new editorial-classification-contract artifact
11775179022 (zip digest08690f17314939537ba6251207d83083ee940d509f9d488595788583e1e38d09)
downloaded to D:/Codex-Recovery/content-studio-20261008/
editorial-contract-ci-38312315852-224ec8e8265341c295ba155f6616f527/.
Root checked24cases/24matched/0mismatched/provider0/rewrite0/qualificationfalse;
editorial-contract-report.json SHA256
318DE43F3C8C0DE9501B324A31B14C3390E6AFE6470A6913571393A0B9896E45.
Artifact was downloaded from this run, not substituted from identical prior
content. Both provider persistence jobs still running at last inspection.

Terminal acceptance supersedes the partial checkpoint: exact38312315852 at
a639591f3683da9251f2a5915d667f3f204808cb completedSUCCESS/all9SUCCESS.
Actual OpenAI/openrouter native logs independently downloaded/read from the
same editorial-model-ci-38312315852 directory: both source-photo, publication
seed/recovery/quota/pending/final/double-reopen families PASS, explicit zero
Telegram/AI network calls/no publications. openai-job.log SHA256
E2A331066EB3EE9E632F664EF2A1B90B72136629C673538E58A0C4643C9B1285;
openrouter-job.log SHA256
21FFACFE0E4C3365851A184F54841D9C290BABEB9773CC007D7CBAB768C6F85B.
This accepts the exact evaluator candidate's synthetic CI only, not the
subsequent uncommitted internal policy service or any actual model qualification.

## Live boundaries

History CI follow-up:38310060502/head34ad476 now all9SUCCESS, actual native
backend2653/11PG-onlySKIP, strictPG638+5, full-stack and both provider persistence
families PASS. Actual new benchmark artifact11774523569 checked24/24/0/calls0/
qualificationfalse. Full native hashes/paths in CI_RECOVERY_20261012.md. This
resolves the preceding history-CI pending checkpoint only, not this evaluator.

No actual model evaluation, provider catalog request, paid API request, Telegram
authorization or publication performed. Existing credential selection blocker
and manual test Telegram/destination setup are recorded together in
EDITORIAL_LIVE_ACCEPTANCE_20261012.md. The accepted choice is reuse of an existing
key, never automatic key creation/rotation or plaintext from conversation.
Synthetic test fixtures cannot qualify a real model. PHASE1 remains unfinished;
independent implementation continues, disabled heartbeat remains disabled.
