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
