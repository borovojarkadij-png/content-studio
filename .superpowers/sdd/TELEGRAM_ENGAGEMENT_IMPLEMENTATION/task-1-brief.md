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

