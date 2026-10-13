# SDD ledger — plan: docs/TELEGRAM_SAMPLING_IMPLEMENTATION.md

Spec: docs/TELEGRAM_SAMPLING_DESIGN_20261013.md. Prepared only; no sampling
source writer dispatched before current Hype source/runtime/integration gates.
Architectural subproject of the already approved Telegram automated planning
scope; NewsFlow product-discovery/architecture-evolution/runtime-qa plus
brainstorming/writing-plans applied. Stable existing sessions only, no activation.

## Preflight shared-interface and self-consistency scan

| Tasks | Produced/consumed contract or internal agreement | Finding |
| --- | --- | --- |
| 1 / 2 | SamplingJob model + pure SamplingAdvance/advance_sampling | Exact table, fields, states, schedule and names shared; Task2 only after review |
| 1 / 3 | Additive b8c migration vs current main-loop/startup | Startup already migrates head; no runtime startup alteration needed |
| 2 / 3 | Runner constructor/admission/claim/execute/run_next + private outcomes | Tick consumes one bounded admission and one runner, no duplicated selection |
| 1 / 2 | Raw state/lease/attempt/terminal guards vs runner mutation | Successful advance resets attempts; retry does not; terminal never revives |
| 1 / 2 | Immutable incoming creation time vs recent-source admission | Locks/retention protect identity; created_at only admission bound, not publication date |
| 1 / 2 | 1/5/10/20/30/60 schedule vs delayed actual observations | Discovery fulfills no thresholds, late scheduled sample fulfills its own index, skipped only later elapsed indices |
| 2 / 3 | Provider/network vs transaction and credentials ownership | Runner injected provider only, tick explicit stable cipher/factory, no auth |
| 2 / 3 | Strict PG tests vs single CI append | Task2 creates PG file; Task3 appends once, no prior check weakening |
| 1 | Own five files vs schedule/migration validation | Pure and migrated tests independently reviewable, no full backend yet |
| 2 | Own three files vs realistic concurrent/recovery semantics | Fresh migration/SQL isolation and independent claims tested, actualPG root-owned |
| 3 | Five files vs one combined full and exact-generation CI | Main loop default0, no Compose activation; source frozen through full |

Ruling: continue approved automated Telegram scope without intermediate human
approval/execution-choice questions — explicit latest overnight autonomy and
prior approved plan bind; cost if wrong: isolated default-disabled collector can
be revised, no new external authority or operational writes.
Ruling: sample independently of editorial status but never authorize content —
aggregate reads of REJECT fixtures are safe ranking data, no rewrite calls;
cost if wrong: unnecessary bounded read-only metrics, never editorial bypass.
Ruling: split schema/schedule, runner, worker into three independently reviewed
tasks — concurrent SQL/state/network boundaries differ; cost if wrong: review
latency, not mixed authority or duplicate full suites.
Ruling: retain SDD workspaces/evidence during ongoing PHASE rather than delete
them at subproject completion — human requires resumable CURRENT_STATE and
reports; cost: small scratch/docs storage, no data or volume removal.

Spec self-review: explicit claim fields, private outcomes, state coherence,
threshold counting examples, attempt reset, terminal/identity/delete retention,
overflow, clock and source/health validation all mapped to tasks. No missing
placeholder/interface; no policy/API/UI/candidate consumer folded into collector.
Plan self-review read in full; search TODO/TBD/fill/appropriate/similar found none.
Task2 seed account_id1/user41 (not account41) is the canonical fixture convention.
Two root documentation patch attempts contained unnecessary stale trailing
context, both failed atomically/no change and were corrected. Read-only context
lookups accidentally used guessed migration/runtime-migration filenames;
actual migration was discovered/read as a7e239bc5180_add_telegram_engagement_history.py.
No source edit or test result inferred from those diagnostics.

Ruling: bound execute/finalization clock to the committed60second claim window,
including pre-claim/backwards-time refusal and fresh clock after final row locks —
otherwise a held lock or clock rewind could extend authority; cost if wrong:
conservative stale sampling retry, never content/authorization mutation.
Spec/Task2 updated before dispatch; no implementation or actual acceptance yet.
Task1 own19line brief generated/read and trailing generator blank removed only.

NEXT: finish current Hype report/review/actualPG/integration, then commit reviewed
root sampling design/plan/brief/checkpoint and dispatch only Task1. No sampling
source or success yet; current Docker29.8/Linux/API1.56 healthy, no reset.

Hype653e113 actualWindowsPG4/0SKIP and package315inputs/reopen/REJECT0calls
accepted, fresh final integration Approved/no findings. Rootcheckpoint/push
then soleTask1 dispatch allowed while exactHypeCI runs; source development is
not release/runtime acceptance. Own actualPG helper prepared only/notexecuted:
D:/Codex-Recovery/content-studio-20261008/telegram-sampling-acceptance-20261013a/verify-postgres.ps1,
parsernative0/SHA D5BA82E89F83048B4A06E4892CD43DDCE189077AE3B7F1D3AAFA77FCF64A7D1F.
Exactoriginalmanifest/container/solevolume/loopback/2062retainednamespaces/
freshUUID/public/source/JUnit0SKIP guards. Execute only after runner/source
review; preparation is not sampling runtime proof.
