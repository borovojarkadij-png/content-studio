# Durable Telegram Engagement Sampling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task-by-task. Steps use checkbox syntax.

**Goal:** Collect honest, time-stamped donor aggregates with durable restart recovery, without changing content authority.
**Architecture:** Add a separate PostgreSQL job and pure interval schedule, a bounded leased read-only provider runner, then a default-disabled worker seam. Reuse accepted immutable engagement history/provider contracts.
**Tech Stack:** Python3.12, SQLAlchemy, Alembic, pytest, SQLite/PostgreSQL; no dependencies added.
**Spec:** docs/TELEGRAM_SAMPLING_DESIGN_20261013.md

## Global Constraints

- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch codex/dark-navy-ui; no main merge/force-push/PR.
- Telegram-only; accepted UI unchanged. Synthetic data only; no real credentials/login/sends/operational queues/volumes/data.
- REJECT → rewrite_allowed=false → no new RewriteJob → rewrite calls=0. Aggregate evidence is never editorial/review/fact/media/rights/publication permission.
- PostgreSQL is durable truth; no Redis timers/authority, missed historical samples or source text/edit-time relabeling.
- One source writer at a time; no helpers/reviewer spawning. Root owns docs/evidence/actualPG; each writer owns listed files plus own report.
- All provider IO outside SQL transactions; commit attempt/lease before IO, fence response/errors against fresh token/lease/session/user/config/source.
- Stable external master key only. No key discovery/creation/authorization or enabled Compose flag; no running worker replacement.
- Inputs exact finite bounded values/aware UTC; no bool-as-int. Revalidate frozen claims. SQLite naive time restoration only internally.
- Root performs exact-generation PostgreSQL/package/CI and final integration review; environment SKIP never PASS or PHASE/live completion.

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

### Task 2: Bounded durable sampling runner and real PostgreSQL contracts

**Files:** Create backend/src/newsflow/services/telegram_engagement_sampling.py, backend/tests/test_telegram_sampling_runner.py, backend/tests/test_telegram_sampling_postgres.py. No worker/API/frontend changes.
**Consumes:** Accepted Task1 job model/SamplingAdvance/advance_sampling; TelegramProvider.fetch_engagement(account_id,donor_identifier,message_id,*,observed_at); TelegramEngagementHistory(session).record(observation); source_identity_deleted/source_identity_sync_blocked; existing configured account/mapping and strict create_postgres_namespace.
**Produces:** TelegramEngagementSamplingRunner(session_factory,*,provider,clock); enqueue_window(*,now,after_id=0,limit=16)->EngagementSamplingAdmission(cursor,queued_ids); claim_next(*,now)->EngagementSamplingClaim|None; execute(claim)->str; run_next(*,now)->str. Frozen admission/claim fields and outcomes exactly as spec. No hidden provider factory/credential IO in this file.

- [ ] Seed migrated synthetic account_id1/user41/canonical donor/source/revision/mapping and REJECT/rewritefalse. Causal RED asserts a committed claim and one observation advances schedule without any rewrite/job/usage mutation:
```python
admitted = runner.enqueue_window(now=NOW)
assert admitted.queued_ids == (post_id,)
claim = runner.claim_next(now=NOW)
assert claim is not None and claim.step == 0
assert runner.execute(claim) == "SAMPLED"
assert history_after[0].observed_at == NOW
assert rewrite_jobs == 0 and rewrite_calls == 0
```
- [ ] Implement bounded fair scan at most16actualincoming IDs, cursor wrap, created_at admission within60minutes/future exclusion, canonical account/donor/mapping/revision/current source/health checks and idempotent creation under incoming lock. Do not filter existing jobs before advancing cursor; every scanned ID can advance fairness. No reset/backfill. Parameter validation before DB.
- [ ] Implement fresh short-transaction claim with candidate lookup outside locks, incoming→job→account order/SKIPLOCKED, due QUEUED/expiredRUNNING, attempts3 terminal without fourth IO. Account CONNECTED or expired COOLDOWN accepted only with encrypted session/expected user. Temporary current cooldown/known sync retains queued/no new attempt, available_at=max(now+30seconds,cooldown_until if future); invalid/deleted/moved/missing source/session BLOCKED. Commit canonical UUID token/60second lease/user/ciphertext SHA256/attempt before IO. Fresh claim reconstruction rejects bool/out-of-range/naive/invalid identity/token/digest before IO.
- [ ] Pre-call ownership/current checks close SQL transaction, then actual clock timestamp used for exactly one aggregate fetch. Clock must lie in [lease_expires_at-60seconds,lease_expires_at), pre-claim/backwards/expired time is STALE_CLAIM/no fetch. Fully reconstruct response and require exact identity/requestedtime; no source-body rewrite/media/send/login/join. Reopen locks same order, resample clock after final locks, check expiry/token/user/digest/current health/config/sync/source; history.record and schedule+job advance one atomic commit. Stale owner returns STALE_CLAIM/no new rows. Current provider errors follow spec private bounded outcomes; stale errors never mutate newer health. FloodWait persists full nonnegative exact required delay/current longer cooldown; overflow fails privately/no early retry. SQL interruption preserves committed recovery lease.
- [ ] Migrated SQLite tests cover success/discovery/six intervals/missed, source originaldate rather than edit/created, duplicate admission, expired claim/reopen/committed3attempt exhaustion, pre/postcall drift/sessionrefresh/user/mapping/deletion/sync/current health, read-only/no-transaction callback, invalid/unknown/reset counters, mismatched timestamp/pub/source conflict, retry/FloodWait/overflow/private errors, failed atomic history+job commit and retained terminal rows. Fake/provider count tripwires prove maxonecall and REJECT0rewritejobs/calls throughout. Real SQL, not mocked persistence.
- [ ] Explicit create-only PG tests cover migration raw constraints/retained downgrade, independent-concurrent admission and SKIPLOCKED claims, expired takeover/stale finalizer, lease expiry while waiting for row lock, real nullable counters+history/job atomic rollback and restart/double reopen. Explicit NEWSFLOW_UNATTENDED_POSTGRES_URL only; no fallback/drop/public mutation. Root actual ownedWindowsPG after source review; this task does not append CI yet.
- [ ] Focused and relevant history/account-health/ingestion/recovery/EditorialGate regressions, Ruff0.17/format/compile. No full backend yet. Missing explicit PG URL is reasoned SKIP only. Self-review/freeze three source hashes/report, commit only three files+report. Root scoped source review before Task3; root may actualPG while preparing worker brief, no simultaneous source modifications during hash-fenced gate.

### Task 3: Default-disabled worker tick, strict opt-in and CI integration

**Files:** Create backend/src/newsflow/services/telegram_engagement_tick.py, backend/tests/test_telegram_sampling_tick.py. Modify backend/src/newsflow/worker.py (new bounded seam invocation/flag/cipher/cursor/private logging only), backend/tests/test_scheduler_worker.py (new main-loop contracts only), .github/workflows/ci.yml (append tests/test_telegram_sampling_postgres.py once to current PG invocation). No Compose/dependency/frontend/API/settings changes.
**Consumes:** Accepted TelegramEngagementSamplingRunner/admission/outcomes; existing stable SessionCipher, load_telegram_credentials, ConfiguredTelegramProvider; main worker current opt-ins.
**Produces:** Frozen EngagementSamplingTickResult(outcome,cursor,queued_ids); run_telegram_engagement_tick(session_factory,*,now,enabled=False,cipher=None,provider=None,credentials_path=None,cursor=0,clock=...) -> result in separate service. worker.telegram_engagement_enabled(value:str)->bool, strict exact0/1 NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED default0. Worker uses own transient engagement_cursor (SQL remains truth).

- [ ] Causal RED disabled-provider/DB/credential tripwires and enabled injected actual SQL tick/main-loop capture:
```python
result = run_telegram_engagement_tick(forbidden_factory, now=NOW, enabled=False)
assert result == EngagementSamplingTickResult("DISABLED", 0, ())
with pytest.raises(ValueError):
    telegram_engagement_enabled("true")
```
- [ ] Implement exactbool enabled check before IO, disabled immediate return; enabled validates stablecipher/time/cursor, injected Fake needs no credentials. Noninjected requires explicit credentials_path and existing loader/factory only. Admission followed by one run_next(actualclock), persisted state retained across new tick instances. Pass source identity/current-policy only via accepted runner, no authorization/rewrite trigger.
- [ ] Main imports separate tick; parse strict flag/default0, add stablecipher prerequisite and cursor initialization, execute after ingestion/sync and before editorial/rewrite when flag1/notstopped. Exact NEWSFLOW_TELEGRAM_CREDENTIALS_FILE defaultexistingpath, private execution_interrupted/recoverypersisted_lease logging, retain cursor only after success; no raw exceptions/session/digest. Current channel-sync error/continue behavior and every other opt-in unchanged.
- [ ] Tests main opt-in/cipher/missingflag/invalidflag/privateexception/continuedindependentwork/disablednoIO/sourcequarantine; actual SQLite tick restart/duplicate/due/future/FloodWait/stale and REJECT0calls. Append PG test once without weakening/reordering prior checks. YAML/static exactappend validation.
- [ ] Run focused tick/main and relevant full runner/history/Hype/editorial/worker regressions, Ruff0.17/format/compile. Freeze five source hashes then ONE combined full backend for all three tasks; no source edits during full. If failure, diagnose/fix scoped with targeted+covering/re-freeze, preserve originalFAIL and require exactcorrectedCI rather than duplicate unchanged full runs. Self-review/report/commit five files+report.
- [ ] Root completes scoped review, final actualWindowsPG/packaged synthetic restart, final cross-task integration review and guarded exactbranchpush/CI. No PHASE/live/operational completion inferred; accepted UI and real data untouched.
