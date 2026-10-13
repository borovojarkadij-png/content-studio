# SDD ledger — plan: docs/TELEGRAM_INTAKE_LEDGER_IMPLEMENTATION.md

Spec: docs/TELEGRAM_INTAKE_LEDGER_DESIGN_20261013.md. Fullselfreview completed;
currentkernel scoped+finalApproved/actualpackage326hashes/native0, root0950b33
guardedpushnative0/exactremote ownerverified. NewCI38340236416 active/all10
running, old38338368307 retainedWindowsFAIL. No caller/worker activation.

| Tasks/interface | Produced/consumed | Preflight finding |
| --- | --- | --- |
|1 /2 models|Two exact retained tables/guards consumed by repository|Shared fields and mapping→stream lock order consistent|
|1 /2 migration|c9d45e37f201 after b8c34d26e190, guarded history downgrade|Task2 migrated fixtures/rootPG consume same schema|
|1 own tests|Raw valid insert/advance versus immutable history|No SQL aggregate algorithm claim; semantic decoder inTask2|
|2 own tests|Literal picks/replay/carry/rollback/query budget/corruption|No approval work or source authenticity implied|
|1 /existing migrationtests|Two tests hardcode priorhead after upgradehead|Use exactbefore/afterversion retention, preserve rest|
|2 /existingkernel|Exact canonical dataclasses and select_intake_window|No kernelchange needed, strict public validation reused|
|2 /futureingress|Comparison evidence only, no current caller|Source/dedup/currentpolicy/reject fences remain next gate|

Ruling: autonomous architectural sub-increment/spec/plan under approvedscope,
no intermediate human approval pause — explicit user asks decide/continue while
asleep; cost if wrong: isolated unused ledger can be revised before activation.
Ruling: two bounded canonical snapshots rather than1000row item table — total
input/output262144ASCIIbytecaps and recomputation keep SQL bounded; cost if wrong:
future analytic queries need projection, snapshots remain truthful audit source.
Ruling: independent retained policy-binding streams each own carry, no implicit
policyreset — futurecaller must supply currentpolicyfingerprint; cost if wrong:
caller binding design may need versioned adjustment before integration.
Ruling: pure comparison IDs are not source foreign-key authority — futurecaller
must freeze/validate realrevision membership; cost if wrong: misuse requires
futureintegrationguards, no current caller/API exists to misuse ledger.
Ruling: preserve SDD workspace during unfinished PHASE — exactstate/evidence
requested; cost small documentationstorage, no deletion.

Speccoverage: two models/strictguards/retention/rollback Task1; boundedstrict
canonical repository/transaction/replay/carry/corruption/concurrency Task2;
rootactualPG/package/finalreview/CI after sourcegates. No missing signatures,
unresolved placeholders, policy/carry/lock contradictions in inlinecheck.
NEXT updateTask1brief after headcompatibility clarification, commitdesign/plan/
ledger, solewriterTask1 then scopedreview. Rootowns docs/evidence/CI only.
