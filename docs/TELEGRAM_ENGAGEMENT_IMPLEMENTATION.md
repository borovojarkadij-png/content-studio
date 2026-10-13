# Telegram Engagement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task-by-task. Steps use checkbox syntax.

**Goal:** Preserve honest Telegram aggregate observations independently of content identity, enabling subsequent donor-relative ranking.
**Architecture:** Separate observation dataclasses/helper and caller-owned append-only PostgreSQL history; reuse existing authenticated read-only adapter, no content/rewrite changes.
**Tech Stack:** Python3.12, Telethon1.45, SQLAlchemy, Alembic, pytest, SQLite/PostgreSQL.
**Spec:** docs/TELEGRAM_ENGAGEMENT_DESIGN_20261013.md

## Global Constraints

- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch codex/dark-navy-ui; no main merge/force-push/PR.
- Telegram-only; accepted dark-navy frontend unchanged. Never real credentials/login/sends/operational queues, volumes or data; synthetic tests only.
- REJECT → rewrite_allowed=false → no new RewriteJob → rewrite calls=0. Observation/scoring never changes editorial or approval authority.
- PostgreSQL is the source of truth; Redis is not durable history. No auto-generated master key or plaintext session storage.
- TelegramMessage and source revision/media equality semantics remain unchanged; counters are separate observations, not new content.
- Unknown counters remain None/SQL NULL; known exact zero remains zero. No fabricated baseline, HypeScore or semantic-proof claim.
- Existing active Docker29.8/Linux engine is healthy; no restart/reset/delete/prune/down-v. No new operational opt-in enabled.
- All new timestamps aware/UTC-normalized at public boundary; signed64 exact integers, no bool acceptance. Existing storage read UTC repair is internal only.
- One source writer at a time. Root owns state/plan/requirements/evidence; implementer owns listed source/test files and its report only; no helpers/reviewer spawning.

### Task 1: Validated read-only engagement provider and honest rate math

**Files:** Create backend/src/newsflow/providers/telegram_engagement.py, backend/src/newsflow/domain/engagement.py, backend/tests/test_telegram_engagement.py, backend/tests/test_engagement_rates.py. Modify backend/src/newsflow/providers/telegram.py (one delegating method only), backend/src/newsflow/services/telegram_provider_factory.py (one delegation only).
**Consumes:** Existing TelethonTelegramProvider._run(account_id,async_callback), _channel_id, _input_channel and ConfiguredTelegramProvider._adapter; actual SDK MessageReactions/ReactionCount. Existing session checks/deadlines/FloodWait/finally cleanup unchanged.
**Produces:** frozen TelegramEngagementObservation and TelegramEngagementProvider/FakeTelegramEngagementProvider; fetch_engagement(account_id,donor_identifier,message_id,*,observed_at). engagement_velocity(previous,current) and engagement_acceleration(first,second,third) immutable result objects with views_per_minute/forwards_per_minute/reactions_per_minute and matching per_minute_squared acceleration fields; velocity reset_metrics tuple of metric names.

- [ ] Write causal missing provider behavior test, run RED before implementation (not collection/import/setup failure).
```python
def test_fetch_is_separate_from_content_identity():
    before = provider.fetch_message("1", "-1001234567890", 1)
    measured = provider.fetch_engagement("1", "-1001234567890", 1, observed_at=NOW)
    assert measured.views == 100
    client.raw.views = 200
    assert provider.fetch_message("1", "-1001234567890", 1) == before
```
- [ ] Implement exact spec contracts, bounded SDK reader, deterministic separate fake and pure interval/midpoint math. Canonical identity/time/counter checks before client construction; raw identity/date/counters before return. Tests use existing Client extension with real SDK reaction shapes, no network. A missing/partial aggregate is None, complete empty results zero; malformed/overflow raises, no silent zero repair.
- [ ] Add validation boundary tests (bool/float/negative/overflow, noncanonical/foreign IDs, invalid/naive/future time, missing/partial/malformed reactions, no credentials, auth/FloodWait/timeout cleanup), math missing/reset/zero/unequal interval cases, frozen mutation, source equality and no unexpected calls. Example: 0→100 views over2minutes gives50/min; next+200 over4minutes also50/min, acceleration0. 0→100 over2 then+400 over4 gives100/min, midpointdistance3minutes, acceleration50/3/min².
- [ ] Run focused then covering provider/factory/media/revision tests once; actual Telethon1.45 first on sys.path; Ruff0.17, format, compile. No full backend yet (combined Task2 once). Record commands/native exits/raw log paths/counts and any corrected fixture failures separately. Self-review/freeze all owned hashes, commit owned files plus report; root reviews full BASE..HEAD diff.

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
