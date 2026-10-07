# Review and live Planner verification — 2026-10-07

Branch: `codex/dark-navy-ui`. Repository: `borovojarkadij-png/content-studio`.

## Implemented

- `GET /api/telegram/rewrite-outputs?output_channel_id=…` projects saved text,
  independent per-channel approval state and current server-calculated eligibility.
- `POST /api/telegram/rewrite-outputs/{id}:approve` accepts only `{}` and locks
  job/editorial/draft/candidate state. Approval plus candidate activation commit
  atomically. A retry is idempotent. Superseded or mismatched jobs and current
  editorial rejection return 409. Missing drafts return 404.
- `POST /api/telegram/rewrite-outputs/{id}:reject` terminally rejects a pending
  variant and blocks its awaiting candidate. It cannot revoke an already approved
  variant through this pending-review endpoint.
- `GET /api/telegram/publication-plans` and
  `GET /api/telegram/publication-plans/{id}/publications?day=YYYY-MM-DD` read
  persisted policy and local-timezone day reservations. GET never schedules or
  reconciles state; stale editorial safety is projected separately.
- Working-mode Planner uses these APIs and the existing configuration/plan-day
  mutations. It never sends Telegram messages or requests AI rewriting. Automatic
  mode currently means explicit slot selection, not a running timer worker.
- DEMO remains isolated in memory and never calls these APIs.

## Checks performed

- Backend `python -m pytest -q`: **115 passed**.
- Targeted review/planning/activation tests: **24 passed** before full regression.
- `ruff check src tests alembic ../scripts/ui_fixture_api.py`: PASS after fixing
  import ordering in Alembic env. `compileall`: PASS.
- Frontend `npm test`: **24 passed**. New tests cover no automatic mutation,
  valid save/approval/selection, unavailable API, disabled stale reject,
  DEMO isolation, retained per-channel configuration and stale async responses.
- `npm run format:check`, `npm run build` (TypeScript + Vite): PASS.
- Full `npx playwright test`: **19 passed**, including all eight DEMO sections,
  accessibility and actual FastAPI/migrated temporary SQLite/Vite integration.
- New E2E proves settings and approval survive frontend reload, stale REJECT
  stays disabled, slots load from the database, no provider/publication calls,
  desktop WCAG AA and no mobile horizontal overflow.
- Screenshots visually inspected:
  `.artifacts/ui-dark-navy/live-planner-1440x900.png` and
  `.artifacts/ui-dark-navy/live-planner-390x844.png`.
- Prior GitHub Actions run **37677475228**, commit **c1888c0**, completed
  successfully in the correct repository (both jobs; uploaded UI evidence).

## Limits

No real Telegram login, live API credentials, paid rewrite, real media download
or publication was used. Tests use temporary SQLite, not PostgreSQL/Docker.
Docker Compose/persistence/restart is **NOT VERIFIED / BLOCKED BY ENVIRONMENT**.
Operational workers, media execution and live configuration forms remain pending.
PHASE 1 is not complete.
