# NEWSFLOW Content Studio

[![Quality gate](https://github.com/borovojarkadij-png/content-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/borovojarkadij-png/content-studio/actions/workflows/ci.yml)

PHASE 1 строит Telegram News Hub как modular monolith. Основной режим — ручная
модерация; автоматическая публикация не включена по умолчанию.

## Local development

1. Copy `.env.example` to `.env` and set database credentials.
2. Create `secrets/newsflow_master_key` once with a stable 32-byte base64 key.
   Do not replace it after Telegram sessions or secrets have been stored.
3. Install backend: `cd backend; python -m pip install -e .[dev]`.
4. Run checks: `python -m pytest -v` and `python -m ruff check src tests`.
5. Build the UI: `cd frontend; npm install; npm run build`.
6. With Docker Desktop installed, run `scripts/start-dev.ps1`.

Pushes to main and `codex/**`, and pull requests, run the backend and frontend
quality gates in GitHub Actions. Docker-dependent acceptance tests remain explicitly blocked
until Docker Desktop is available on the development workstation.

`docker compose down/up` is expected to retain PostgreSQL and Redis volumes.
Persistent business recovery is designed around PostgreSQL, never Redis alone.

## Dark-navy UI preview and verification

All eight sections are implemented using real React components. Preview without
Telegram/AI calls: `cd frontend; npm ci; npm run dev -- --host 127.0.0.1`, then
open `http://127.0.0.1:5173/?demo=1`. DEMO is explicitly labelled and stores edits
only in memory. Reload restores fixtures; saving DEMO does not save real settings.

The supported real UI integration is `GET /api/telegram/incoming-posts`.
Vite proxies `/api` to `http://127.0.0.1:8000`; for a different local API port set
`$env:NEWSFLOW_API_PROXY_TARGET='http://127.0.0.1:8123'` before starting Vite.
Compose dev uses `http://api:8000`. Unsupported live mutations are disabled, and
API errors never switch to DEMO automatically.

Run `npm run format:check`, `npm test`, `npm run build`, then
`npx playwright install chromium; npm run test:e2e`. Browser tests need Python 3.12
and the installed backend from step 3; they start an actual API with a migrated,
temporary synthetic SQLite database on 5181 and Vite on 5180. They do not read
real Telegram sessions, touch the local newsflow.db or call paid providers.

Screenshots and the browser report are written to `.artifacts/ui-dark-navy/`
and uploaded as a GitHub Actions artifact. See
[UI verification](docs/UI_DARK_NAVY_VERIFICATION.md) for coverage and limitations.
PHASE 1 is not yet complete; Docker Desktop persistence E2E is not verified.
