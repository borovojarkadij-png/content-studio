# Isolated PostgreSQL vertical-slice CI

2026-10-08; `codex/dark-navy-ui`; correct origin
`https://github.com/borovojarkadij-png/content-studio.git`.

The existing five actual durable-service vertical scenarios now support an
explicit PostgreSQL target in an independent GitHub CI job, alongside SQLite.
No service/provider/guard is mocked inside the app; only external AI/photo/sender
boundaries are synthetic. Protected reject, per-output rewrite, current semantic
qualification, exact photo/rights, quotas/delay, SQL reopen, duplicate ticks and
FloodWait recovery use exactly the same scenarios.

## Isolation contract

- Optional `NEWSFLOW_UNATTENDED_POSTGRES_URL` is test-only, never application
  configuration. Missing selects isolated SQLite; present but empty/invalid fails,
  without fallback or contacting an operational database.
- Only postgresql+psycopg, literal localhost/127.0.0.1:5432, database
  `newsflow_unattended_ci`, role `newsflow_fixture` and public synthetic CI password
  are accepted. No supplied connection query/search-path override or remote host.
- PostgreSQL 16-alpine is an independent GitHub service container, not the user's
  Compose project. Each scenario creates a new `unattended_<UUID hex>` schema;
  no IF NOT EXISTS, DROP, TRUNCATE, delete, reset, reused namespace or public-schema
  migration. Schema creation errors propagate. Namespaces are retained until the
  disposable GitHub runner/service is destroyed.
- Scoped URL is checked through actual `current_schema()` before migrations.
  Every subsequent engine/session reopen uses the exact search-path binding.
  Alembic's explicit URL/percent guard remains authoritative.
- Five scenarios require actual migrations/SQL. Failure to connect or execute is
  a test failure, never a skip or synthetic PostgreSQL success. No operational
  Telegram/AI flags, keys, data, sessions or qualification changed.

## Local evidence and current runtime status

- 18 target/schema isolation cases plus five migrated SQLite vertical cases:
  **23 PASS**, including non-local/operational/coercible/malformed/query-override
  refusal without echoing supplied credential details.
- Full backend: **1153 PASS**, 99.09 seconds, session 40836, isolated D: basetemp
  `D:/Codex-Recovery/content-studio-20261008/pg-vertical-full-1407`.
- Exact CI Ruff / changed format / D: bytecode compile / workflow YAML parse /
  explicit D: Alembic upgrade/check/downgrade/upgrade/check: PASS.
- Prior full frontend unchanged: 139 units / 30 browser PASS (57315), two subsequent
  relevant real migrated-API/browser checks PASS. New CI reruns the full frontend.
- Actual new PostgreSQL job: **PENDING exact push and CI inspection**. Local target
  validation and SQLite PASS are not evidence of PostgreSQL execution.
- Previous 58df443 CI 37765616929 backend/frontend/admission/sync jobs SUCCESS;
  567e263 CI 37766368319 backend/frontend/admission SUCCESS. Other jobs running at
  latest inspection; neither is yet recorded as overall success here.

## Remaining acceptance

Engine/SQL reopen is not PostgreSQL container down/up or crash recovery for this
combined scenario. Separate existing probes already test retained queue/nonce/
ack/cursor recovery, but do not automatically qualify this new whole pipeline.
A separate create-only combined Compose restart procedure remains pending.
Linux CI is not current Windows Docker Desktop proof. Windows remains
**NOT VERIFIED / BLOCKED BY ENVIRONMENT** (about 0.47 GiB free on C:, writable
Docker storage not confirmed). Do not retry deployment or reset/prune/delete
volumes/databases/keys to make tests pass. PHASE 1 is not complete.
