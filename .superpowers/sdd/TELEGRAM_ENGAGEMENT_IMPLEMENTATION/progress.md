# SDD ledger — plan: docs/TELEGRAM_ENGAGEMENT_IMPLEMENTATION.md

Spec: docs/TELEGRAM_ENGAGEMENT_DESIGN_20261013.md; human-approved original
Hype/view-velocity/planning scope, not a new product or architecture replacement.
Root read current state/implementation, provider/current factory/ingestion/models/
strict PG helper/migration patterns and original Hype sections. Skills: NewsFlow
product-discovery, architecture-evolution, data-migrations-recovery, runtime-qa;
brainstorming, writing-plans and SDD. Existing codex/dark-navy-ui/origin checked,
Docker29.8/Linux healthy, Python3.12.10/Ruff0.17 actual. No restart needed.

## Preflight shared-interface and self-consistency scan

| Tasks | Producer/consumer or internal contract | Finding |
| --- | --- | --- |
| 1 / 2 | frozen observation identity/time/counters consumed by persisted record/history | Same fields/types/UTC/unknown semantics; Task2 consumes accepted Task1 only |
| 1 / 2 | Task1 provider and pure math files; Task2 two models/service/migration/CI | No shared edited source files; sequential writer/review gates |
| 1 | helper uses existing bounded _run/peer/session; separate counters vs TelegramMessage | Delegation only; no original content equality/authorization semantics changes |
| 1 | nullable resets and midpoint acceleration tests vs rate specification | Unequal intervals explicit, zero/missing/decrease not conflated |
| 2 | composite snapshot PK/source FK/append-only triggers vs replay/rollback | Exact replay does not UPDATE; caller transaction owns atomic source+snapshot |
| 2 | fresh strict PG helper and one CI file append vs environment/migrations | Explicit URL only/no SQLite fallback/no production schemas/no prior check removal |
| 2 | downgrade requirements vs retained append-only history | Refuse nonempty; empty additive-only removal, no destructive history fallback |

Ruling: proceed without new intermediate approval ceremony — original Hype/
view snapshots and latest explicit autonomous no-question authorization bind;
cost if wrong: bounded synthetic-only feature can be revised, no operational
activation/data loss/paid calls or UI change.
Ruling: separate observation contracts/history rather than adding mutable
counters to TelegramMessage — preserve existing source/media equality fences;
cost if wrong: additional model/seam maintenance, not rewrite identity churn.
Ruling: this increment ends at durable history, not unsupported Hype/event/live
claims — subsequent consumers use this tested foundation; cost if wrong: extra
increment boundary, no fabricated source metrics.
Ruling: Task1 uses focused+covering tests; ONE combined full backend after Task2 —
no repeated unchanged whole suite; cost if wrong: late unrelated failures are
diagnosed before acceptance, not promoted as passed.

Spec/plan self-review: every bounded scope requirement mapped to Task1 or Task2;
full HypeScore/baselines/event matching/opt-in collector explicitly subsequent,
not fake completed. Interfaces consistent; no undefined consumed functions or
placeholder steps. New source not dispatched until root docs checkpoint commit.
Generated brief ended with an extra blank line: initial staged diffcheck native2
was followed by documentation commit e05560f because controller shell sequence
did not stop. Corrected only trailing generated blank before source dispatch;
retain this controller bookkeeping failure, not a product test failure.
Corrective docs0bc8ebd staged diffcheck native0/commitnative0/clean tree.
Task1 solewriter /root/telegram_engagement_provider,gpt-6.1-sol/high/forknone/
nohelpers dispatched at BASE0bc8ebd77ec985d43e5e3a349697d6ea7fe8c21b.
Exact six source/test files + own report only; root owns docs/CI. Do not
redispatch until report/review; Task2 waits clean spec+quality review.
Root prepares actualPG helper only (no execution before reviewed Task2):
D:/Codex-Recovery/content-studio-20261008/telegram-engagement-acceptance-20261013a/verify-postgres.ps1,
parsernative0/SHA B2A26B89759731E6ED9BBD2BF26B2472694C3BBEA1BE0CF112E875301A19E384.
Existing exact owned PG container/manifest/solevolume/loopback plus input hashes,
2032baseline namespace retention/public unchanged/JUnit0SKIP guards; supports
fresh new namespaces only. No real credentials or unchanged gates replayed.
Ruling: Task1 brief pre-client "identity/time/counter checks" means request
identity/observed_at before IO, raw counters/publication date after bounded read
and before return — response counters do not exist before RPC; cost if wrong:
invalid provider responses fail without persisted history, no pretend preflight.
Clarification delivered to solewriter; exact spec response checks unchanged.
Task1 writerDONE8308f15; complete106line report read, all six owned SHA256+report
B461DC726602DB217D076CBF07D3D98C8E3D3250D717DB0D7869F7341779ADED matched.
Actual88focusedPASS0.52s/453coveringPASS38.58s/native0/Telethon1.45/static0;
causal missingreader RED, fixture collection signature error not productRED,
type-contract negatives and lint corrections retained. No full suite requested.
Fresh scoped /root/telegram_engagement_provider_review,gpt-6.1-sol/high/forknone/
nohelpers active; complete BASE0bc8ebd..8308f15 onecommit42030byte package.
Do not launch Task2 until review resolves. Root earlier missingreport read was
before writer finished, no mutation/rerun/loss; report now complete/hashverified.

Task 1: complete (commits 0bc8ebd..8308f15, review clean).
Fresh independent speccompliant/qualityApproved/no findings; verbatim review
retained. Cannotverify PG/history belongs Task2/controller; broader source/
media/editorial authority covered by actual453regression and unchanged paths,
not presumed live proof. No repeated suites or review changes. Task2 ready.
Root checkpoint86ba3d2 native0/stageddiff0/clean tree. Task2 solewriter
/root/telegram_engagement_history,gpt-6.1-sol/high/forknone/nohelpers dispatched
at BASE86ba3d2f4efb7491da884a70567152d5a37cd8af; exact19linebrief, six listed
source/test/migration/CI files plus own report. Existing append-only SQLite
parent/no_replace and PG noTRUNCATE conventions explicitly carried. Root owns
docs and actualPG, no second writer. Batch authorized push after Task2 review/
runtime rather than duplicate same-block CI. Do not redispatch Task2.
Ruling: history() binds and validates retained canonical incoming identity, but
does not require a still-configured account/donor; record() retains strict current
configuration validation — audit history must survive donor configuration removal;
cost if wrong: read-only retained aggregate visibility, never provider or editorial
authority. Solewriter adds removal/read-versus-record regression before freeze.
Task2 causal SQLite temporal microsecond regression exposed julianday precision
loss; strict timestamp comparison/checks corrected. Stale ORM identity reads
exposed by behavioral regression and corrected with populate_existing. Focused/
covering/full evidence remains writer-owned until final report, not presumed PASS.
Root read-only lookups used an unsupported Windows filename glob and guessed
planning/worker/channel_sync paths; corrected using rg --files discovery to
publication_planning.py, worker.py and channel_sync_tick.py. No source/runtime
mutation or failed gate was promoted. Actual Docker29.8/Linux/API1.56 responds;
authorized branch/origin unchanged, no restart/reset needed. Initial root ledger
patch context missed the preceding sentence; corrected exact context, no lost edit.
Ruling: extend Task2 ownership narrowly to
backend/tests/test_editorial_attempt_migration.py, only the historical additive/
empty-roundtrip test, after full terminal confirms latest-head drift failure —
new migration makes command.check at historical f6a head invalid; keep historical
PARENT/HEAD/sentinels/populated downgrade, check metadata only at actual head;
cost if wrong: reviewed test-only adjustment, no product guard weakening.
One combined full continues unchanged after collection; writer changed only
already-SKIPped PG assertion SQLSTATE specificity during that run before root's
freeze message arrived. Full generation cannot prove changed PG tests; final
collection/static plus root actual Windows PG will prove those exact assertions.
No second unchanged local full: if the confirmed sole failure is this old test,
retain FAIL and use targeted historical/engagement tests, then exact pushed CI
full gate for final generation. Any other failure must be diagnosed separately.
Combined full terminal: native1,2FAIL/3347PASS/52explicitSKIP/557.10s; raw
D:/Codex-Recovery/telegram-engagement-task2-20261013a/full.log retained. Root read
actual two tracebacks: historical f6a command.check not latest, and metadata-only
media fixture stamp(head) falsely claiming new migration triggers installed.
Ruling: extend eighth path backend/tests/test_media_runner.py only
test_media_migration_refuses_durable_history_loss — stamp actual media migration
e93b0a4217d6, retain refusal and strengthen job identity/state/version retention;
cost if wrong: reviewed historical-fixture correction, no product DROP/TRIGGER
weakening. Original writer owns both fixes, then targeted modules/engagement,
static/freeze. Full FAIL remains FAIL until exact final-generation CI executes.
Root existing owner GitHub credential used only in temporary restored process
environment; authenticated login borovojarkadij-png and exact remote6bc5adc
verified native0. No global auth switch, new key or remote write yet.
Task2 writerDONE_WITH_CONCERNS344a28a15424d2219177ed4e6a5b5c844d67f08f;
root read full124line report, matched all8owned working-byte hashes and report
EEE62DC71A5477CF890A3D73B1D9856F492934191BFF2859089E7457B0CF10E9.
Complete86ba3d2..344a28a review package1commit74132bytes generated. Fresh scoped
/root/telegram_engagement_history_review,gpt-6.1-sol/high/forknone/nohelpers
active; no actualPG/package execution before clean source review. Report concerns
are explicit pending controller gates, not unexplained implementation escalation.
Root verified actual final119PASS/26PG-onlySKIP raw output/static7/native exits
recorded in report; full FAIL retained. No repeated old suites or source edits.

Task 2: complete (commits86ba3d2..344a28a, review clean).
Fresh scoped independent speccompliant/qualityApproved/no findings; cannotverify
actualPG/package resolved by actual root gates, corrected whole-suite CI remains
pending. Actual exact344a28a Windows Docker PostgreSQL26PASS/0SKIP/native0/18.93s,
2032existing+26new=2058namespaces/public unchanged/all12inputs unchanged.
Actual packaged image5993419c7290... buildnative0/network-none/read-only/noVolumes
SQLite smoke native0:2snapshots/reopen/replay/NULL/rate/appendonly/REJECT0jobs;
Python3.12.15/Telethon1.45/allinputs unchanged. Evidence hashes in own verification
report. No actual source/provider/operational authority activated.
Fresh final cross-task /root/telegram_engagement_integration_review,
gpt-6-astra/high/forknone/nohelpers active, complete0bc8ebd..344a28a148302byte
package. Hype Task1 waits its acceptance; no secondsourcewriter.
Root read-only mixed-log JSON extraction and guessed skill-reference diagnostics
corrected without rerunning gates; missing docs patch context applied no changes.
No result relabeled. Scope remains increment integration, not whole PHASE review.

Final cross-task integration review Approved/speccompliant/noCritical/Important/
Minor; verbatim integration-review.md retained. No fixwave required. Corrected
exact CI remains the complete full-gate obligation; original localFAIL retained.
Root updates precise checkpoint and commits reviewed source acceptance/Hype
design only before guarded push; no PHASE/live/merge claim or old gate replay.
