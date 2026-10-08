# Requirements matrix

| ID | Requirement | Phase | Status | Evidence |
| --- | --- | --- | --- |
| R-001 | Editorial hard gate | 1 | PARTIAL | domain/editorial.py; durable ingestion workflow tests |
| R-002 | Zero rewrite calls after reject | 1 | PARTIAL | rewrite/pipeline and durable retry tests |
| R-003 | Safe publication revalidation | 1 | PARTIAL | publication tests |
| R-004 | Durable PostgreSQL/outbox | 1 | PARTIAL | SQL workflow, migrations, transactional outbox tests |
| R-005 | Telegram accounts and sessions | 1 | PARTIAL | stable key/cipher, encrypted account-scoped peers, current-user/CAS checks, actual synthetic peer/health/import-resolution PostgreSQL restart acceptance; live authorization pending |
| R-009 | Mapping deterministic filters | 1 | PARTIAL | persisted GET/PUT policies, Unicode/domain/media/ad ingress, fresh worker/review/calendar guards, stale-task zero-call Docker down/up, real API and working UI reload/failure regression acceptance; publication-execution wiring pending |
| R-010 | Exact dedup before editorial | 1 | PARTIAL | mapping-scoped durable fingerprint and retry regression tests |
| R-011 | Moderation inbox API read model | 1 | PARTIAL | DATABASE_URL session wiring; latest revision/editorial integration tests |
| R-006 | Compose persistence | 1 | PARTIAL | actual Windows Docker build/migration/down-up/crash/DNS/synthetic lease acceptance; DOCKER_VERIFICATION.md; live authorization/provider recovery pending |
| R-012 | Automatic channel planning | 1 | PARTIAL | timer ticks, timezone/slots/quota/idempotency/stale-reject tests; publication/automatic approval pending |
| R-013 | Rewrite factual preservation | 1 | PARTIAL | 25 synthetic anchor/hard-policy regressions; semantic equivalence deliberately not claimed |
| R-014 | Durable rewrite recovery | 1 | PARTIAL | committed attempt budget, leases/fencing, delayed retry, PENDING draft/outbox, guarded migration and injected Docker recovery; network daemon pending |
| R-007 | Russian dashboard | 1 | PARTIAL | eight dark-navy compositions, DEMO forms, actual inbox GET, 18 frontend/18 browser regressions; durable live mutations pending |
| UI-001 | Reference-based eight-section UI increment | UI | VERIFIED LOCALLY | 40 screenshots; manual PNG comparison; UI_DARK_NAVY_VERIFICATION.md |
| UI-002 | Preserve source/manual drafts | UI | VERIFIED LOCALLY | navigation/overwrite-confirm/reject read-only regressions |
| UI-003 | Honest DEMO/API boundaries | UI | VERIFIED LOCALLY | actual isolated API, HTTP retry, malformed response and no DEMO API traffic tests |
| UI-004 | Accessible/responsive default sections | UI | VERIFIED LOCALLY | axe A/AA checks; five viewport sizes; modal focus regressions |
| R-008 | YouTube contracts | Future | NOT IMPLEMENTED | architecture only |
| R-015 | Exact source-photo reuse with explicit rights | 1 | PARTIAL | immutable media identity/protection, bounded adapter, fenced durable source jobs, versioned explicit mapping rights, queue/status API and Connections rights UI, 581 backend/42 frontend/21 browser gate and actual synthetic Windows Docker recovery; SOURCE_PHOTO_JOBS_VERIFICATION.md; candidate media UI and live authorization pending |
