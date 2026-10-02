# Requirements matrix

| ID | Requirement | Phase | Status | Evidence |
| --- | --- | --- | --- |
| R-001 | Editorial hard gate | 1 | PARTIAL | domain/editorial.py; durable ingestion workflow tests |
| R-002 | Zero rewrite calls after reject | 1 | PARTIAL | rewrite/pipeline and durable retry tests |
| R-003 | Safe publication revalidation | 1 | PARTIAL | publication tests |
| R-004 | Durable PostgreSQL/outbox | 1 | PARTIAL | SQL workflow, migrations, transactional outbox tests |
| R-005 | Telegram accounts and sessions | 1 | PARTIAL | schema, stable key loader, SessionCipher, reconnect/cooldown and Telethon normalization tests |
| R-009 | Mapping deterministic filters | 1 | PARTIAL | mapping technical filter and durable ingress tests |
| R-010 | Exact dedup before editorial | 1 | PARTIAL | mapping-scoped durable fingerprint and retry regression tests |
| R-011 | Moderation inbox API read model | 1 | PARTIAL | DATABASE_URL session wiring; latest revision/editorial integration tests |
| R-006 | Compose persistence | 1 | PARTIAL | compose.yaml; Docker unavailable |
| R-007 | Russian dashboard | 1 | PARTIAL | eight dark-navy compositions, DEMO forms, actual inbox GET, 18 frontend/18 browser regressions; durable live mutations pending |
| UI-001 | Reference-based eight-section UI increment | UI | VERIFIED LOCALLY | 40 screenshots; manual PNG comparison; UI_DARK_NAVY_VERIFICATION.md |
| UI-002 | Preserve source/manual drafts | UI | VERIFIED LOCALLY | navigation/overwrite-confirm/reject read-only regressions |
| UI-003 | Honest DEMO/API boundaries | UI | VERIFIED LOCALLY | actual isolated API, HTTP retry, malformed response and no DEMO API traffic tests |
| UI-004 | Accessible/responsive default sections | UI | VERIFIED LOCALLY | axe A/AA checks; five viewport sizes; modal focus regressions |
| R-008 | YouTube contracts | Future | NOT IMPLEMENTED | architecture only |
