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
