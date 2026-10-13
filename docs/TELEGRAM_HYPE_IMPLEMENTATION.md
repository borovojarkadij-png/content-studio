# Telegram HypeScore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task-by-task. Steps use checkbox syntax.

**Goal:** Explain donor-relative performance and weighted HypeScore without fabricated metrics or authority changes.
**Architecture:** Pure frozen scoring/baseline contracts consumed by a bounded read-only PostgreSQL/SQLite projection over accepted engagement history.
**Tech Stack:** Python3.12, SQLAlchemy, Alembic, pytest, SQLite/PostgreSQL; no new dependencies.
**Spec:** docs/TELEGRAM_HYPE_DESIGN_20261013.md

## Global Constraints

- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch codex/dark-navy-ui; no main merge/force-push/PR.
- Telegram-only; accepted dark-navy frontend unchanged. Synthetic data only, no real credentials/login/sends/operational queues/volumes/data.
- REJECT → rewrite_allowed=false → no new RewriteJob → rewrite calls=0. Ranking evidence is not editorial/review/fact/media/rights/publication permission.
- PostgreSQL is durable truth; consume accepted append-only engagement history. No schema migration, Redis authority, candidate ordering or provider/worker activation in this increment.
- Unknown components/rates are None, not invented zero/fifty. Exact zero is known. No absolute views ranking, hidden clock, network or paid call.
- One source writer at a time, no helpers/reviewer spawning. Root owns docs/evidence/actualPG; implementer owns listed files plus own report.
- Pure inputs aware UTC/exact finite bounded values, no bool-as-int. Revalidate forged frozen values at boundaries. SQLite naive time repair at internal DB boundary only.

### Task 1: Pure transparent weighted score and comparable donor baseline

**Files:** Create backend/src/newsflow/domain/hype.py, backend/src/newsflow/domain/donor_performance.py, backend/tests/test_hype.py, backend/tests/test_donor_performance.py. No existing source modifications.
**Consumes:** TelegramEngagementObservation, utc_timestamp and engagement_velocity from accepted newsflow.domain.engagement.
**Produces:** Frozen HypeComponents/HypeWeights/HypeAssessment; score_hype(components, weights=None, *, minimum_coverage=0.5); freshness_score(published_at,as_of,*,half_life_minutes=30); relative_velocity_score(ratio). Frozen EngagementWindow(previous,current), DonorRelativePerformance with expected_views_per_minute/relative_views_velocity/views_samples and analogous forwards/reactions fields; donor_relative_performance(target,samples,*,minimum_samples=5).

- [ ] Write and run meaningful function-level RED before implementation. Hand-derived examples:
```python
from newsflow.domain.hype import HypeComponents, HypeWeights, score_hype
weights = HypeWeights(freshness=1, view_velocity=3, forward_velocity=0,
    reaction_velocity=0, cross_source_trend=0, source_authority=0,
    breaking_signals=0, ai_importance=0, channel_relevance=0,
    topic_priority=0, historical_performance=0)
result = score_hype(HypeComponents(freshness=100,view_velocity=0), weights)
assert result.score == 25 and result.coverage == 1
assert score_hype(HypeComponents()).score is None
```
- [ ] Implement the exact eleven fields/default weights, unknown/coverage rules and validated finite formulas from the spec. Hype code imports no SQLAlchemy/Telethon/service code. Freshness at publication=100, half-life30minutes=50, sixtyminutes=25. Baseline compares actual adjacent interval rates, not lifetime count/age. Tuple samples at most2000; minimum exact int1..200. Revalidate every window before exclusions. Exclude foreign/current/future/noncomparable; one selected window per message, deterministic age/duration/latest-end/latest-start ordering; reject conflicting canonical source/observation time and publication timestamps across target/all samples, exact duplicates add no sample. Per-metric median baseline from at least minimum valid independent windows; reset/missing excluded, insufficient samples unknown, known median0 preserved as expected0/relativeNone. Relative score min(100,50*ratio), None preserved.
- [ ] Add literal arithmetic/donor-size fairness, independent messages versus repeats, boundary25% inclusivity, unequal windows, foreign/future/nonprior/current exclusion, reset/missing/zero median, tie input-order independence, disabled weights, min-coverage boundary/insufficient evidence, NaN/Infinity/bool/negative/overflow/forged frozen/input tuple bounds and aware time tests. Returned dataclasses immutable; no invented seven unavailable components.
- [ ] Run focused new tests and existing engagement math/provider regression once with actual Telethon1.45. Ruff0.17 lint/format/compile; no full backend yet. Retain actual raw logs/native exits/TDD failures and corrections. Self-review/freeze four hashes, commit only four files plus task report. Root reviews complete BASE..HEAD before Task2.

### Task 2: Bounded read-only SQL Hype projection and strict PostgreSQL contracts

**Files:** Create backend/src/newsflow/services/telegram_hype.py, backend/tests/test_telegram_hype.py, backend/tests/test_telegram_hype_postgres.py. Modify .github/workflows/ci.yml (append new PG file once to existing PG invocation only). No models/migrations/API/worker/frontend edits.
**Consumes:** Accepted engagement source/snapshot models and canonical incoming identities; Task1 HypeComponents/HypeWeights/HypeAssessment/EngagementWindow/DonorRelativePerformance/score_hype/freshness_score/relative_velocity_score/donor_relative_performance; strict create_postgres_namespace and NEWSFLOW_UNATTENDED_POSTGRES_URL.
**Produces:** TelegramHypeService(session).inspect(incoming_post_id,*,as_of,weights=None,minimum_coverage=0.5)->TelegramHypeProjection. Frozen projection contains assessment, nullable performance, nullable observed_at, baseline_truncated bool and reason string.

- [ ] Write migrated synthetic SQL behavior test and run RED before service. Seed only own canonical incoming/engagement history plus retained REJECT decision; known donor ordinary interval10/min and target20/min must produce relative2/view component100, not absolute-size ranking.
```python
projection = TelegramHypeService(session).inspect(post_id, as_of=NOW)
assert projection.assessment.components.view_velocity == 100
assert projection.performance.relative_views_velocity == 2
assert session.scalar(select(func.count()).select_from(RewriteJobModel)) == 0
```
- [ ] Implement exact spec bounded SQL reads: source plus latest two snapshots<=as_of, fresh canonical labeling, missing/one/stale cases; freshness uses as_of and maximum snapshot age five minutes. Same account/donor, other earlier publications within30days/clamped datetime.min, observed<=target end. Fetch at most2001 rows ordered publication desc/incoming ID desc/observed desc, process2000 and expose truncation. Group chronological adjacent windows, pure independent baseline; populate only freshness and three measured relative velocity components. Read cached rows freshly, repair naive dates only for SQLite. Use session.no_autoflush, validate policy even on empty result. No write/flush/commit/rollback/RPC/job/usage/outbox effects.
- [ ] Add migrated SQL/reopen/rollback/readonly/no-write, unknown/one/stale/as_of/foreign/current/older-than30days/reset/zero/cold-start, deterministic bounds/truncation and stale identity-cache tests. Assert original source/revision/REJECT/rewritefalse/jobs/usage unchanged even for a high score. Unknown post/noncanonical identity/invalid parameter fail. No current donor configuration required for historical reading. Explicit create-only PostgreSQL tests cover real time/nullable rates/isolation/bounded projection/read-only behavior, no URL fallback or schema deletion. Append test path exactly once to existing PG CI command, no weakened prior gate.
- [ ] Run focused then relevant engagement/planner/editorial regression, Ruff0.17/format/compile and YAML append validation. Run ONE combined full backend after both tasks. Missing explicit PG URL is SKIP only. Freeze four owned hashes/report, self-review and commit only owned files/report. Root performs scoped source review, fresh owned Windows PG, exact source CI and final cross-task integration review; no PHASE/live/operational success claim.
