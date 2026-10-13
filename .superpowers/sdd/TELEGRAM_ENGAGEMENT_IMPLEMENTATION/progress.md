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
