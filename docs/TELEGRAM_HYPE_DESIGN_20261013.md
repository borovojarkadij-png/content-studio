# Telegram donor-relative HypeScore — approved-scope increment

## Outcome and boundaries

Implement the approved non-random news ranking foundation: a transparent numeric
score using a donor's own observed performance, not absolute channel size. Reuse
the separately validated, immutable engagement history. This increment provides
pure scoring and a bounded read-only SQL projection; it does not collect new
observations, change candidate ordering, admit rewrites, or publish. Persistent
settings/API controls and an opt-in collector/consumer follow separately. Missing
data is visible and cannot produce a fabricated complete score.

This is a new bounded subsystem within the original approved Hype/velocity scope,
not a replacement architecture. The human's autonomous implementation instruction
overrides additional intermediate approval ceremonies. Accepted UI stays unchanged.

## Options and decision

Absolute views would unfairly favor large donors; arbitrary/random ranking would
violate the requirement. A learned/LLM score would hide uncertainty and add costs.
Choose deterministic, explainable donor-relative intervals and weighted evidence.
The consequence is an honest cold start until enough comparable observations exist.
Rollback is to stop using this read-only projection; no migrations or authority
changes are required for this increment.

## Pure scoring contract

New SDK/SQL-independent `newsflow.domain.hype` contains frozen dataclasses:

- `HypeComponents`: optional `freshness`, `view_velocity`, `forward_velocity`,
  `reaction_velocity`, `cross_source_trend`, `source_authority`, `breaking_signals`,
  `ai_importance`, `channel_relevance`, `topic_priority`, `historical_performance`.
  Known values are finite exact int/float values in 0..100, excluding bool;
  missing is None, not a default zero or fifty.
- `HypeWeights`: the same fields as exact int weights 0..1000, positive total.
  Defaults respectively 10,20,10,10,10,5,5,5,10,10,5 (total100). These are engine
  inputs, not a claim that persistent settings/UI are implemented.
- `HypeAssessment(score, coverage, components, weights, reason)`: score optional
  float0..100; coverage known positive-weight / all weight. `score_hype(components,
  weights=None, *, minimum_coverage=0.5)` computes the weighted mean over known
  enabled components only. No known enabled weight or insufficient coverage means
  score=None/reason=INSUFFICIENT_EVIDENCE; otherwise reason=READY. Minimum coverage
  finite exact int/float in0..1, excluding bool. Known zero counts as evidence;
  zero-weight unknown does not reduce coverage. Revalidate frozen inputs at trust
  boundaries. No rounding hides coverage or changes ordering.

`freshness_score(published_at, as_of, *, half_life_minutes=30)` validates aware UTC
times/publication<=as_of and finite exact int/float half-life in1..10080. Return
100*2**(-age_minutes/half_life_minutes), bounded0..100; no hidden clock.

## Comparable donor baseline contract

Frozen `EngagementWindow(previous,current)` contains revalidated engagement
observations for the same complete identity/publication and strictly advancing
times. It reuses actual interval math, not lifetime views/age labeled as velocity.

`donor_relative_performance(target, samples, *, minimum_samples=5)` consumes an
explicit tuple of at most2000 windows and minimum exact int in1..200. Every sample
is validated, including samples later excluded. Exclude foreign accounts/donors,
the target message, publications not strictly before the target publication,
observations after target.current.observed_at, and noncomparable windows.
Comparable means end age and interval duration each within25% of the target's
positive age/duration, inclusive. One independent message contributes at most one
window: choose closest end age, then closest duration, then latest end time,
then latest start time. Input order cannot change the result. Conflicting values
for the same canonical source/observation time are invalid; each canonical source
must have one publication time across target and all samples, including excluded
ones. Exact replay is not additional evidence. Counter decreases/missing counters
are excluded per metric.

Frozen `DonorRelativePerformance` exposes for views/forwards/reactions:
`expected_*_per_minute`, `relative_*_velocity`, and `*_samples` counts. Expected
rate is the median of valid independently selected windows for that metric.
Fewer than minimum samples means expected/relative=None. A measured median0
remains expected=0 with relative=None (zero baseline is not infinity). A known
target rate0 with positive baseline gives0.
Reset/unknown target rate cannot become a known relative rate. Ratio overflow
is rejected, never NaN/Infinity. `relative_velocity_score(ratio)` maps a validated
nonnegative finite ratio to min(100,50*ratio), and None to None. Ordinary donor
performance is50, twice ordinary performance100, independent of donor size.

## Read-only SQL projection

`newsflow.services.telegram_hype.TelegramHypeService(session).inspect(
incoming_post_id, *, as_of, weights=None, minimum_coverage=0.5)` returns frozen
`TelegramHypeProjection(assessment: HypeAssessment, performance:
DonorRelativePerformance|None, observed_at: datetime|None, baseline_truncated:
bool, reason: str)`. Validate exact positive signed64 post ID and aware UTC as_of. Require an
existing canonical incoming identity; retained historical reads do not require
current donor configuration, matching the accepted audit-reader rule.

Read publication time from TelegramEngagementSourceModel and at most latest two
snapshots at/before as_of, ordered by observed_at. Missing source/history returns
explicit NO_ENGAGEMENT with unknown components/no score; a source with exactly
one snapshot still supplies known freshness. A latest snapshot older than
five minutes relative to as_of yields STALE_ENGAGEMENT and no performance values.
Freshness always uses as_of, not the snapshot time. No observation after as_of
may influence any result.

For a fresh target window, read at most2001 historical snapshot/source/incoming
rows: same exact account/donor, other messages published strictly before target,
within preceding30 days, observed<=target end. Order publication descending,
incoming ID descending, observation descending; process at most first2000 and
set baseline_truncated if an extra row exists. Clamp the lower time bound at
aware datetime.min rather than overflowing. Group into chronological per-message
adjacent windows, pass to the pure baseline function. Truncation is reported,
not claimed to represent the donor's entire archive. Current observations are
never included as their own baseline. SQLite naive DB dates repaired to UTC only
at storage boundary; PostgreSQL requires actual aware datetimes. Fresh reads
avoid SQLAlchemy identity-map stale labeling. No unbounded scan, RPC, commits,
rollback, locks, updates, jobs, usage, outbox, approval or publication.
Use session.no_autoflush for all reads: a projection must not flush unrelated
pending caller changes as a side effect. Validate weights/coverage even for an
empty projection; malformed policy must not hide behind a cold-start result.

Only freshness and the three actual donor-relative velocities are populated.
All seven other components remain None, honestly pending their own evidence.
Projection reason is READY or INSUFFICIENT_EVIDENCE for a fresh target, and the
specific NO_ENGAGEMENT/STALE_ENGAGEMENT otherwise. Even READY is ranking evidence,
never editorial/review/fact/media/rights/publication permission.

## Verification

TDD hand-derived formulas (50 ordinary,100 twice ordinary, weighted zero/unknown,
unequal interval/donor-size fairness), cold start, malformed/frozen/finite input,
same-message independence, foreign/future/stale/out-of-order/reset/duplicate
exclusion and deterministic tie cases. SQL tests use migrated synthetic history,
reopen and rollback/no-write receipts, bounded/truncated baseline, as_of isolation,
fresh canonical identity, and unchanged REJECT/rewritefalse/no RewriteJob/usage.
Explicit new PostgreSQL cases use fresh create-only namespaces with the existing
strict helper; missing URL is SKIP, not proof. Root actual Windows PG follows
clean source review. No credentials, AI calls, real Telegram/publication or UI
change. One combined backend gate after both tasks, no unchanged full repetition.
