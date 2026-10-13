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
