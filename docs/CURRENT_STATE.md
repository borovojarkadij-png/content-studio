# Current state

## VERIFIED WORKING

- Pure-Python EditorialGate rejects hostile/negative protected-entity content.
- RewriteService blocks rejected content before calling its provider.
- IngestionPipeline applies video rejection and exact dedup before EditorialGate.
- PublicationService rechecks editorial status and idempotency before transport.
- FastAPI `/healthz` endpoint and frontend production build.
- Master-key loader never autogenerates an unavailable/empty secret.
- SQLAlchemy row constraint rejects `REJECT` with `rewrite_allowed=true`.
- Uvicorn starts the FastAPI application successfully on a free local port.
- Immutable Telegram source identity/revisions, mapping percentages, safe manual-review
  transitions and bulk donor identifier parsing.
- FakeTelegramProvider fixtures for messages, edits, duplicate delivery and isolated FloodWait.
- Telethon adapter boundary rejects unprovisioned account sessions before a live client is created.
- SQLAlchemy TelegramAccount, DonorChannel, OutputChannel, ChannelMapping and
  OutboxEvent foundation constraints; donor bulk import HTTP endpoint.
- Offline IngestionService idempotency, edit revisions, technical prefilters and
  EditorialGate reject path with no rewrite outbox event.
- SessionCipher encrypts persisted Telegram string sessions with the separately
  provisioned master key and fails visibly if the key changes or is malformed.
- Exact duplicate detection in the ingestion service runs before EditorialGate,
  preventing redundant editorial/AI work.
- GitHub Actions quality gate executes backend lint/tests/compile/migrations and
  frontend test/build for every push and pull request.

## PARTIALLY IMPLEMENTED

- Compose topology and persistent-volume declarations.
- Russian dashboard shell and architecture documentation.

## NOT IMPLEMENTED

- Durable editorial workflow integration with ingestion and a transactional
  rewrite-request outbox; Telethon transport; OpenAI adapter; queues; scheduler;
  media; real dashboard workflows; Telegram E2E.

## KNOWN ISSUES

- Docker Desktop is not installed on this workstation, so Compose startup and
  persistence/restart E2E are pending environment availability.
- Port 8010 was occupied by an external local process during startup validation;
  the application started successfully on port 8123.
- Obsidian vault location is unavailable; `/docs` is the source of truth.

## NEXT STEP

Wire the durable SQL ingestion repository to deterministic filters, exact dedup,
EditorialGate and guarded rewrite-job creation in one transaction. Add adversarial
tests proving technical rejects and editorial rejects produce neither RewriteJob
nor rewrite-request outbox event.
