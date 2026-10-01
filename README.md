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

Every push and pull request runs the backend and frontend quality gates in
GitHub Actions. Docker-dependent acceptance tests remain explicitly blocked
until Docker Desktop is available on the development workstation.

`docker compose down/up` is expected to retain PostgreSQL and Redis volumes.
Persistent business recovery is designed around PostgreSQL, never Redis alone.
