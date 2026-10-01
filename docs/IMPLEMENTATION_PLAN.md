# Implementation plan

- [x] Repository, backend test harness, frontend build foundation
- [x] Editorial/Rewrite/Publication domain hard-gate prototype with tests
- [x] Compose persistence design and Windows command scripts
- [x] Architecture, state, data-flow, requirements and research docs
- [~] SQLAlchemy schema constraints; Alembic migrations and transactional outbox foundation
- [~] Telegram domain model, source revisions, state transitions and donor bulk parsing
- [~] Telegram provider contract and deterministic FakeTelegramProvider
- [~] Telegram persistence entities/constraints and donor bulk-import API
- [~] Offline ingestion idempotency, immutable revisions and technical/editorial prefilters
- [~] Durable ingestion transaction: filters, exact source delivery dedup, editorial decision and guarded rewrite outbox
- [~] Telethon adapter boundary and offline message/album normalization; encrypted-session boundary and live account management pending
- [~] Account health/reconnect policy with persisted FloodWait cooldown and offline tests
- [ ] Filters, semantic dedup, events, hype, media, routing and scheduler
- [ ] OpenAI adapter, fact guard, queues and operational workers
- [ ] Dashboard onboarding, inbox, calendar, audit/history and realtime UI
- [ ] Docker persistence E2E and full PHASE 1 quality gate
