# NEWSFLOW Content Studio

[![Quality gate](https://github.com/borovojarkadij-png/content-studio/actions/workflows/ci.yml/badge.svg)](https://github.com/borovojarkadij-png/content-studio/actions/workflows/ci.yml)

PHASE 1 строит Telegram News Hub как modular monolith. Основной режим — ручная
модерация; автоматическая публикация не включена по умолчанию.

Актуальный объём проекта (уточнение пользователя 2026-10-08): только Telegram
Content Studio. YouTube исключён из реализации и оценки оставшейся работы.

## Local development

1. With Docker Desktop running, explicitly run `scripts/initialize-local.ps1`
   once to provision ignored `.env` credentials and a stable master key. Existing
   files are retained; missing keys with existing state fail closed. Alternatively,
   provision `.env` and `secrets/newsflow_master_key` manually.
2. Back up the master key separately; do not replace it after Telegram sessions
   or secrets have been stored. Container startup never generates it.
3. Install backend: `cd backend; python -m pip install -e .[dev]`.
4. Run checks: `python -m pytest -v` and `python -m ruff check src tests`.
5. Build the UI: `cd frontend; npm install; npm run build`.
6. With Docker Desktop installed, run `scripts/start-dev.ps1`.

Pushes to main and `codex/**`, and pull requests, run the backend and frontend
quality gates in GitHub Actions, including synthetic Docker persistence jobs for
OpenAI and OpenRouter adapters (no external AI requests).
Windows Docker Desktop build/startup/storage restart checks now pass in an
isolated fixture stack; live Telegram authorization and job execution recovery
are not yet verified. See [Docker verification](docs/DOCKER_VERIFICATION.md).

`docker compose down/up` retains PostgreSQL, Redis and media volumes in tested fixtures.
Persistent business recovery is designed around PostgreSQL, never Redis alone.
Do not use `down -v` for ordinary stop/update operations. Keep the master key
separate and stable; backing up encrypted data without its key is insufficient.

Development uses `scripts/start-dev.ps1` (base + dev override, Windows polling,
backend reload). For production configuration, run `docker compose --profile
production up --build -d --wait`; nginx serves the built UI on loopback port 8080
and proxies the API. Configure TLS/authentication before exposing it on a VPS.
Migrations run before API and worker startup. The worker automatically plans
eligible approved candidates. Network rewriting is disabled by default; explicitly
set `NEWSFLOW_REWRITE_ENABLED=1` and `NEWSFLOW_REWRITE_PROVIDER=OPENAI` or
`OPENROUTER` in the local environment only after configuring encrypted provider
Settings and a stable master key. OpenRouter only tries the saved free model list,
never paid OpenAI fallback. Recreate the worker to apply environment changes.
Successful rewrites are PENDING review, not automatically approved or published.
See [rewrite verification](docs/OPENROUTER_REWRITE_VERIFICATION.md) for boundaries.
The operational stack currently keeps network rewriting disabled.

Repeat safe synthetic acceptance: `./scripts/verify-persistence.ps1 -CrashRecovery`.
This uses a separate database/project/key, not real Telegram sessions or AI.

## Dark-navy UI preview and verification

All eight sections are implemented using real React components. Preview without
Telegram/AI calls: `cd frontend; npm ci; npm run dev -- --host 127.0.0.1`, then
open `http://127.0.0.1:5173/?demo=1`. DEMO is explicitly labelled and stores edits
only in memory. Reload restores fixtures; saving DEMO does not save real settings.

Real UI integrations include Inbox reads, encrypted rewrite-provider Settings
and per-channel Planner configuration/review. Other operational forms remain partial.
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
PHASE 1 is not yet complete; synthetic Docker storage and injected structured
rewrite recovery do not prove live authorization/provider execution or automatic
publication. Planner's «В стиле жёлтой прессы» button saves a channel's future
rewrite style; it does not change existing drafts or itself spend API credits.
