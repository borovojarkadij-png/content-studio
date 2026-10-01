# Requirements matrix

| ID | Requirement | Phase | Status | Evidence |
| --- | --- | --- | --- |
| R-001 | Editorial hard gate | 1 | PARTIAL | domain/editorial.py; durable ingestion workflow tests |
| R-002 | Zero rewrite calls after reject | 1 | PARTIAL | rewrite/pipeline and durable retry tests |
| R-003 | Safe publication revalidation | 1 | PARTIAL | publication tests |
| R-004 | Durable PostgreSQL/outbox | 1 | PARTIAL | SQL workflow, migrations, transactional outbox tests |
| R-005 | Telegram accounts and sessions | 1 | PARTIAL | schema, stable key loader and SessionCipher tests |
| R-006 | Compose persistence | 1 | PARTIAL | compose.yaml; Docker unavailable |
| R-007 | Russian dashboard | 1 | PARTIAL | frontend shell |
| R-008 | YouTube contracts | Future | NOT IMPLEMENTED | architecture only |
