# Telegram automation: observed selection gaps

Scope: approved Telegram-only Content Studio, existing architecture and accepted
dark-navy UI. This is a discovery record, not a replacement implementation plan
or a claim that unfinished functions work. NewsFlow Product Discovery and
Architecture Evolution were used to trace actual handoffs before defining the
next bounded increment. Current sampling implementation must finish its own
review/runtime/exact-CI gates before another source writer starts.

## User outcome

The operator configures donors, output channels, daily limits, timing, filters,
rewrite provider/style and media policy. The software subsequently chooses
suitable posts and recovers after restart without repeated manual scheduling.
Manual review remains mandatory where editorial, facts, media rights or current
authorization require it. Unknown evidence is not permission.

## Observed current behavior

| Boundary | Evidence in existing source | Remaining obligation |
| --- | --- | --- |
| Mapping intake | `domain/technical_filters.py`, `MappingTechnicalFilter.evaluate`: stable SHA256 bucket versus intake_percent | This is observable deterministic sampling, not the best-scoring proportion of a comparison window |
| Durable ingress | `domain/durable_ingestion.py`, configured mapping and cheap checks before editorial; passing decision produces per-output rewrite work | A ranked pre-rewrite hold/selection boundary must preserve exact dedup, current policy/source fencing and REJECT0calls; changing planner ordering alone cannot recover content already filtered from intake |
| Editorial admission | `services/editorial_admission.py`: current mapping technical policy and owned fingerprint are bound to the request | A new intake policy must participate in that binding; it cannot silently reuse a stale PASS or diagnostic qualification |
| Hype evidence | `services/telegram_hype.py`: bounded read-only donor-relative projection with unknown/stale/coverage reasons | No current publication selection consumer; no score can authorize content |
| Metrics acquisition | Sampling schema/runner independently reviewed; actual owned Windows PostgreSQL20PASS/0SKIP; default-disabled worker under implementation | Finish Task3, combinedfull, packaged/container restart and exact-generation CI; live Telegram authorization is separate |
| Publication planning | `services/publication_planning.py`, `plan_day`: READY candidates ordered by static priority then ID, fresh guards and serialized daily quota | Hype-aware comparison, target mix and auditable selection policy are not yet implemented here |
| Target mix | Channel mapping stores target_mix_percent and binds configuration | Storing the value does not implement a proportional donor allocation algorithm |
| Automatic approval | Independent synthetic contract/runtime checks exist | Actual real-provider benchmark and qualification remain external/live acceptance; never convert synthetic verdicts to automatic approval |

The original approved specification explicitly names RANDOM, TOP_SCORE and
HYBRID (default HYBRID), observable sampling decisions and preference for the
best30 of100 suitable posts at intake30%. Existing daily slots/limits and
immediate/delayed mapping eligibility are not evidence of those ranking modes.

Confirmed against the actual original attachment, sections8/9/104: intake is
the proportion of suitable donor messages admitted further; target mix is the
desired donor share within an output, not a second intake filter. Section104
requires observable persisted sampling decisions, modes RANDOM/TOP_SCORE/HYBRID
and defaultHYBRID. Section39 makes daily maximum a hard limit and minimum only
a soft target: unsuitable material must not be used to fill a quota. These are
the retained requirements, not new behavior invented from a stored field name.

Further concrete integration evidence: publication_planning._lock_planning_batch
already freezes at most1000candidate hints and locks reservations→rewritejobs→
editorialdecisions→drafts before downstream policy checks. A ranking consumer
must not acquire a new upstream lock after these downstream locks. Calling the
current HypeService.inspect separately for every candidate could multiply up to
1000×2001baseline rows; a future consumer needs a total bounded evidence budget,
not an assertion that each individual inspect is bounded. Current default Hype
weights assign50of100 to freshness+three velocities, minimumcoverage0.5; missing
velocity evidence can therefore honestly keep the score unknown. Unknown is
not a zero score or automatic permission to fill daily minimums.

The existing DurableIngestionWorkflow reserves a mapping fingerprint and may
create editorial/rewrite work in the same transaction. Its existing-source
fan-out path returns duplicate when no decision exists. A pre-AI ranking hold
must therefore be integrated for both initial and fan-out sources, retain the
exact owned fingerprint, and add current-selection checks to diagnostic/admission
and rewrite boundaries. A post-rewrite planner-only change does not satisfy
the original intake cost-saving/best-percentage requirement.

Additional verified seam: services/mapping_filters.mapping_filter already has
keyword intake=False, constructing the same persisted technical policy with
intake_percent100. candidate_technical_allowed uses it for current downstream
suitability. Future durable ranked intake can reuse this explicit seam only
after validating opt-in policy/owned selection; no new ad/link/media filter
fork is needed and merely setting intake=False is not authorization.

Current next bounded increment is specified in
TELEGRAM_INTAKE_SELECTION_DESIGN_20261013.md and its singleTask plan: pure
deterministic bounded kernel first, no caller activation or durable claim.
This deliberately does not close the observed ingestion/planning obligations.

Downstream integration trace, inspected after kernel review: the common
candidate_technical_allowed boundary is consumed by rewrite runner both before
and after execution, illustration binding, publication preflight, planning and
calendar checks; output_technical_allowed reaches review outputs, semantic
verification and automatic approval. A durable selection binding should be
revalidated at these established boundaries, not added as a planner-only flag.
resolve_editorial_admission separately binds current source/mapping/fingerprint
before diagnostic classification. DurableEditorialService.create_rewrite_job
currently has only editorial/source availability and output-scoped idempotency;
its two ingestion/fanout callers must establish current owned selection before
creating work. No API exists to treat the pure kernel result as authority.
No integration implementation or permission change is claimed by this trace.

## Constraints on the next implementation

- Preserve the current core and accepted UI; add a bounded seam, not a new app.
- Rank only technically suitable, deduplicated, current sources. Editorial
  HARD REJECT always dominates score and selection. Selection grants neither
  rewrite nor publication authority.
- Define a finite comparison window and explicit cold-start/insufficient-score
  behavior. Do not label missing counts zero or fabricate past observations.
- Persist policy/version, candidate-window membership, selected/skipped reasons
  and idempotency/recovery state in PostgreSQL. No hidden random decision.
- Revalidate current source, mapping, session/account health and policy at every
  transition; stale task/retry/manual scheduling must not bypass gates.
- Preserve per-output rewrite identity and provider cost accounting; a shared
  source is not one shared rewritten text across channels.
- Bound total SQL/provider work, not merely per-candidate query size. Avoid an
  accidental candidates×historical-baseline query explosion.
- Do not silently activate a new selection policy or replace running workers
  while testing. Use isolated synthetic fixtures and explicit opt-in migration.
- Video/manual holds and YouTube-link exclusion remain before rewrite; this
  project does not implement YouTube ingestion or publication.

## Acceptance signal

A synthetic mixed donor window has hand-derived expected selected IDs, explicit
reasons for skipped/unknown/rejected rows and repeatable daily allocation.
Restart/retry/concurrent workers preserve the same durable decision without
duplicate rewrite work. All rejected cases retain rewrite_allowed=false,
no new RewriteJob and zero provider rewrite calls. Only after actual source,
SQL, runtime and exact-CI evidence may the corresponding requirement advance.

No source changes, provider calls, policy activation or progress-percentage
claim were made by this discovery record.
