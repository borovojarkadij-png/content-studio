### Task 2: Immutable durable observation history and migration contracts

**Files:** Modify backend/src/newsflow/persistence/models.py (add two focused models only), .github/workflows/ci.yml (append new PG file to existing PG invocation only). Create backend/src/newsflow/services/telegram_engagement_history.py, backend/alembic/versions/a7e239bc5180_add_telegram_engagement_history.py, backend/tests/test_telegram_engagement_history.py, backend/tests/test_telegram_engagement_postgres.py. No worker/API/UI/config changes.
**Consumes:** Task1 TelegramEngagementObservation; existing IncomingPostModel/DonorChannel/TelegramAccount and Base.metadata; strict create_postgres_namespace and NEWSFLOW_UNATTENDED_POSTGRES_URL.
**Produces:** TelegramEngagementSourceModel(incoming_post_id PK/FK, published_at); TelegramEngagementSnapshotModel(incoming_post_id+observed_at composite PK/FK, views/forwards/reactions nullable BigInteger); TelegramEngagementHistory(session).record(observation)->bool and history(incoming_post_id,*,limit=60)->tuple[TelegramEngagementObservation,...].

- [ ] Write causal record/replay test with actual migrated fixture and call expected service, run RED. Seed only own synthetic account/donor/source/revision and editorial REJECT tripwire. Unknown identities fail; no counter update changes source text/revisions/decision/jobs/usage.
```python
with factory() as session, session.begin():
    history = TelegramEngagementHistory(session)
    assert history.record(observation) is True
    assert history.record(observation) is False
with factory() as session:
    assert TelegramEngagementHistory(session).history(post_id) == (observation,)
```
- [ ] Implement new additive models and current-head migration with named nonnegative64/time SQL constraints, RESTRICT FKs and append-only UPDATE/DELETE triggers matching existing dialect conventions. Check actual head, not assumed ancestry. Downgrade refuses any history; empty drop works. No backfill/old triggers/source identity edits.
- [ ] Implement caller-owned transaction service: revalidate contract, bind existing canonical source to configured account/donor, lock incoming row before first source insert/read, immutable publication timestamp, exact replay no-op/conflict refusal, out-of-order snapshot append. No hidden commit/rollback/provider/job/outbox effects. Bound history limit/identity; round-trip UTC only at storage boundary.
- [ ] Add real SQL insert/read/reopen/rollback/append-only/update/delete/foreign/time/overflow/NULL/replay/conflict/chronological limit and preserved original data regressions; SQLite up/check/down-refusal/empty downgrade. Explicit PG tests create-only fresh schemas (no missing URL fallback); cover actual uniqueness, independent committed writer replay/conflict, FK/append-only and rollback; no destructive schema cleanup. Append new file once to existing PG CI list, all prior commands/checks untouched.
- [ ] Run focused/covering and ONE combined full backend; Ruff0.17/format/compile, migration validation and YAML append check. Missing explicit PG URL is recorded SKIP, never PASS; root supplies actual owned Windows PG after clean review. Self-review/freeze owned hashes and report, commit own paths. Root then scoped review/actualPG/exactCI/evidence, continue durable scheduling/Hype consumers.
