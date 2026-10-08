# Requirements matrix

| ID | Requirement | Phase | Status | Evidence |
| --- | --- | --- | --- |
| R-001 | Editorial hard gate | 1 | PARTIAL | domain/editorial.py; durable ingestion workflow tests |
| R-002 | Zero rewrite calls after reject | 1 | PARTIAL | rewrite/pipeline and durable retry tests |
| R-003 | Safe publication revalidation | 1 | PARTIAL | durable intents/encrypted exact request/observed acknowledgements, fresh editorial/source/review/filter/media checks and synthetic no-resend recovery; live authorization pending |
| R-004 | Durable PostgreSQL/outbox | 1 | PARTIAL | SQL workflow, migrations, transactional outbox tests |
| R-005 | Telegram accounts and sessions | 1 | PARTIAL | stable key/cipher, encrypted account-scoped peers, current-user/CAS checks, actual synthetic peer/health/import-resolution PostgreSQL restart acceptance; live authorization pending |
| R-009 | Mapping deterministic filters | 1 | PARTIAL | persisted GET/PUT policies, Unicode/domain/media/ad ingress, fresh worker/review/calendar/preflight/pre-send guards, synthetic stale-task zero-call recovery, real API/UI reload/failure checks; live publication pending |
| R-010 | Exact dedup before editorial | 1 | PARTIAL | mapping-scoped durable fingerprint and retry regression tests |
| R-011 | Moderation inbox API read model | 1 | PARTIAL | DATABASE_URL session wiring; latest revision/editorial integration tests |
| R-006 | Compose persistence | 1 | PARTIAL / CURRENT WINDOWS BLOCKED | historical synthetic Windows recovery recorded; latest Windows disk/storage deployment NOT VERIFIED / BLOCKED BY ENVIRONMENT; Linux admission/sync restart CI successful, not Windows proof; live authorization pending |
| R-012 | Automatic channel planning | 1 | PARTIAL | durable timer/slots/quota/delays/priorities, real qualified-release approval form, guarded workers/PostgreSQL queued restart CI; synthetic original-photo vertical SQL-reopen/FloodWait/double-tick integration PASS; library and operational workflow pending |
| R-013 | Rewrite factual preservation | 1 | PARTIAL | 25 synthetic anchor/hard-policy regressions; semantic equivalence deliberately not claimed |
| R-014 | Durable rewrite recovery | 1 | PARTIAL | opt-in encrypted provider worker, committed attempts/leases/fencing, bounded retry and temporary-sync wait, PENDING outbox, stale/reject zero calls and synthetic recovery; operational provider acceptance pending |
| R-007 | Russian dashboard | 1 | PARTIAL | eight dark-navy sections; real configuration/filter/rights/plan/review/approval-policy APIs, Overview and donor/media/publication/semantic diagnostics; 139 frontend unit/30 browser gate; strict DEMO separation; operational runtime pending |
| UI-001 | Reference-based eight-section UI increment | UI | VERIFIED LOCALLY | 40 screenshots; manual PNG comparison; UI_DARK_NAVY_VERIFICATION.md |
| UI-002 | Preserve source/manual drafts | UI | VERIFIED LOCALLY | navigation/overwrite-confirm/reject read-only regressions |
| UI-003 | Honest DEMO/API boundaries | UI | VERIFIED LOCALLY | actual isolated API, HTTP retry, malformed response and no DEMO API traffic tests |
| UI-004 | Accessible/responsive default sections | UI | VERIFIED LOCALLY | axe A/AA checks; five viewport sizes; modal focus regressions |
| R-008 | YouTube contracts (historical requirement) | Excluded | OUT OF SCOPE | User explicitly restricted Content Studio to Telegram on 2026-10-08; no implementation or progress weight |
| R-015 | Exact source-photo reuse with explicit rights | 1 | PARTIAL | immutable protected identity, bounded decoded acquisition and original-photo transport, rights/attribution, durable jobs, Connections rights/Planner queue/exact protected preview; synthetic recovery verified; actual authorized source download/send pending |
