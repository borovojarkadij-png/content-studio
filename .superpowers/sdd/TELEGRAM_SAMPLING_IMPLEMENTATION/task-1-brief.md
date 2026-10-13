### Task 1: Retained sampling job, migration and pure threshold schedule

**Files:** Modify backend/src/newsflow/persistence/models.py only for new TelegramEngagementSamplingJobModel. Create backend/alembic/versions/b8c34d26e190_add_telegram_engagement_sampling.py, backend/src/newsflow/domain/engagement_sampling.py, backend/tests/test_engagement_sampling.py, backend/tests/test_telegram_sampling_migration.py. No existing model behavior changed.
**Consumes:** Accepted migration head a7e239bc5180; existing IncomingPostModel canonical identity and engagement utc_timestamp validation.
**Produces:** TelegramEngagementSamplingJobModel/table telegram_engagement_sampling_jobs and migration revision b8c34d26e190/down_revision a7e239bc5180. Frozen SamplingAdvance(step:int,available_at:datetime,missed_windows:int); advance_sampling(published_at,observed_at,*,step:int,missed_windows:int)->SamplingAdvance. Step7 result available_at equals observed_at. Existing step0..6 and missed0..6 exact int; aware publication<=observation, output counters bounded. No hidden clock/SQL/provider dependency in domain.

- [ ] Write hand-derived schedule and actual migrated DB causal RED before implementation. A failing function body/assertion must execute, not collection/import failure. Examples:
```python
result = advance_sampling(PUBLISHED, PUBLISHED + timedelta(seconds=60), step=0, missed_windows=0)
assert result.step == 2 and result.missed_windows == 1
assert result.available_at == PUBLISHED + timedelta(seconds=300)
late = advance_sampling(PUBLISHED, PUBLISHED + timedelta(seconds=601), step=1, missed_windows=0)
assert late.step == 4 and late.missed_windows == 2
```
- [ ] Implement exact fields/state coherence/private codes/initial INSERT/transition/retention rules from spec. Use named CHECKs for state/step/attempt/missed/time/claim validity; SQLite exact integer/date/UUID/digest guards and PG equivalent supported types. Fresh queued rows do not contain session digests. Due index on state/available_at/lease_expires_at. Incoming identity/created_at cannot be rebound or replaced while retained job exists. Reject UPDATE/DELETE/REPLACE terminal jobs and DELETE/TRUNCATE retained jobs; initial INSERT only step0/attempt0/missed0. No source/history guards weakened.
- [ ] Implement schedule with exact seconds tuple(60,300,600,1200,1800,3600), first future index and bounded missed-window counting from spec. No future-published/naive/bool/negative/forged/bounds/overflow acceptance. Tests cover every threshold just before/equal/after, delayed discovery/step, repeated missed counts, completion, UTC offsets, datetime min/max and immutable result.
- [ ] Migrated SQLite tests execute raw invalid state/coherence/counter/claim/date/association/creation/terminal revival/DELETE/REPLACE SQL, including FK-disabled retention; populated downgrade refuses before DDL and keeps exact rows/version, empty downgrade/upgrade+alembic.check preserve old sentinels. Where a historical fixture operates at its own revision, keep its original boundary rather than weaken guards; report any unavoidable unrelated fixture change to root before editing.
- [ ] Focused domain/migration then existing engagement history and runtime migration regressions using Telethon1.45. Ruff0.17/format/compile/Alembic roundtrip. No full backend yet. Retain raw RED/failure/correction logs/native exits, self-review/freeze five owned hashes, commit five files plus report. Root fresh scoped review and actual PG after runner task.
