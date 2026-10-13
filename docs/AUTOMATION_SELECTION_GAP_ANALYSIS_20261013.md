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
