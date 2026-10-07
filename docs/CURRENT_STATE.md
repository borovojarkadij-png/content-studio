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
- GitHub Actions quality gate targets main/codex branch pushes and pull requests;
  frontend gates include browser regressions, an isolated actual API fixture,
  automated accessibility checks and downloadable screenshots/reports.
- Durable SQL ingress uses a single transaction for technical filtering,
  source-identity deduplication, editorial decision persistence and guarded
  rewrite dispatch. Regression tests cover technical reject, editorial reject,
  duplicate delivery and editorial-reject retry with zero RewriteJob and zero
  rewrite-request outbox event.
- Account health uses persisted timestamps and per-account FloodWait cooldown;
  unavailable sessions become SESSION_INVALID without a retry loop. This is
  exercised through FakeTelegramProvider and a versioned migration.
- Telethon adapter normalizes offline text/photo/video message shapes, edits and
  album identifiers into the provider-neutral TelegramMessage contract. It does
  not connect or authenticate without an externally provisioned live session.
- Mapping-level deterministic filters reject unsupported media, explicit
  advertising markers and configured forbidden-link domains before editorial
  persistence, RewriteJob creation or any future AI call.
- Mapping-scoped SHA-256 fingerprints reject exact content duplicates from
  distinct source messages before EditorialGate. A retry of an editorial reject
  preserves its original REJECTED_EDITORIAL outcome; another mapping remains
  independently eligible.
- The Telegram moderation-inbox API projects each durable post's current state,
  latest immutable revision and editorial decision. It opens a request-scoped
  SQLAlchemy session from `DATABASE_URL`; integration coverage proves the
  configured-database path without a test-only dependency override.
- Durable Telegram configuration API contracts store accounts, donor/output
  channels, mappings and unresolved donor imports in PostgreSQL/SQLAlchemy.
  Natural Telegram identities are immutable; equivalent retry requests are
  idempotent, conflicts are explicit, configuration writes never create rewrite
  jobs or editorial decisions, and public API projections never return sessions.
- Durable per-output publication planning supports `MANUAL`/`AUTOMATIC` mode,
  daily limits, IANA timezones and fixed slots. It deterministically prioritizes
  editorially eligible candidates and stores `PLANNED` reservations only; it
  has no Telegram transport, OpenAI or rewrite-job side effect.
- A mapping that names an output channel creates a durable
  `AWAITING_REWRITE` publication candidate only after the technical filters,
  source deduplication and EditorialGate pass. A separate activation worker
  makes it `READY` only after the persisted rewrite job is `SUCCEEDED` and
  rechecks the current editorial decision; a stale reject becomes
  `BLOCKED_EDITORIAL`. Editorial rejects create neither a candidate nor a
  rewrite job.
- One accepted current source revision can fan out idempotently to multiple
  output mappings. It retains one shared editorial decision but creates a
  separate output-scoped rewrite job and rewrite-request outbox event for each
  channel, so channel-specific style/model choices and later rewrite results
  stay independent. Stale source deliveries after an edit cannot route a newer
  revision; locked editorial reads and unique candidate rows prevent a reject
  or concurrent retry from bypassing the gate.
- The output-scoped rewrite-job migration safely adopts a legacy job when it
  backed exactly one candidate. A legacy fan-out job becomes `SUPERSEDED` and
  emits fresh per-output `DISPATCHED` jobs; downgrade refuses to collapse that
  audit history.
- Rewrite-provider settings persist encrypted OpenAI/OpenRouter credentials and
  selected rewrite models without exposing plaintext through API projections.
  OpenRouter accepts only explicit free models (`:free` or `openrouter/free`)
  and retries the configured fallbacks in order when a model is unavailable.
  Catalog lookup is a read-only provider request; it is separate from rewrite.
- Rewrite-provider request validation is credential-safe too: malformed OpenAI
  and OpenRouter settings payloads return structured `422` details without
  echoing any submitted API-key value.
- Working-mode Settings now reads and replaces encrypted OpenAI/OpenRouter
  rewrite-provider configuration through real API endpoints. It never fetches
  or displays a stored key. A server-side, read-only model-catalog endpoint
  lists OpenAI models or free-only OpenRouter models after a provider has been
  configured; it does not invoke rewriting.
- Channel mappings now persist auditable delivery policy independently from the
  output channel's daily plan: `IMMEDIATE` or `DELAYED` eligibility (up to seven
  days), priority and a safe media-policy intent (`REUSE_SOURCE` or
  `LICENSED_LIBRARY`). The API validates these policies and preserves an
  existing delayed policy when a caller only changes traffic percentages.
- Durable ingestion snapshots the configured mapping policy onto every
  per-output candidate: mapping identity, priority, media intent and the exact
  UTC eligibility time. The automatic planner never reserves a slot before
  that snapshot's delay expires, selects another eligible candidate instead,
  and does not retroactively alter queued candidates when the mapping changes.
- A succeeded rewrite now creates a durable, output-channel-scoped draft that
  must be explicitly approved before its candidate can become `READY`. Both
  draft recording and approval recheck the current `EditorialGate` decision;
  a stale reject blocks them. This adds no provider call or publication side
  effect.
- Durable review APIs list per-channel drafts with current approval eligibility.
  Explicit approve atomically persists approval and activates only the matching
  candidate; reject is terminal for pending drafts. Superseded/mismatched jobs,
  stale editorial rejects and injected control fields fail closed.
- Working-mode Planner reads actual output channels, policies and day reservations,
  saves per-channel daily limits/timezones/slots, reviews per-channel rewrites and
  explicitly requests deterministic slot selection. Reload retains database state;
  channel switching retains newly saved plans and discards stale responses.
  No Telegram send, AI call or DEMO fallback occurs.
- Local gate on 2026-10-07: 115 backend tests, 24 frontend tests and all 19
  Chromium E2E tests passed; backend lint/compile, frontend format/typecheck/build
  and isolated migration tests passed. The new live Planner E2E uses real
  FastAPI + migrated temporary SQLite + Vite proxy, checks WCAG AA and captures
  desktop/mobile screenshots. See PLANNER_REVIEW_VERIFICATION.md.
- GitHub Actions run 37677475228 passed both quality-gate jobs for c1888c0
  in the correct `borovojarkadij-png/content-studio` repository.
- Dark-navy frontend: all eight section compositions, shared linear icons,
  selected rows/cards, responsive panels and honest unavailable actions.
- In-memory DEMO workflows: donor import preview/partial success, independent
  routing percentages, channel forms/tabs/windows/quiet hours, planner edits,
  grouped overlapping jobs, account scenario viewer and explicit settings Save/Cancel.
- Manual draft survives navigation and editorial rejection; replacing it with
  an AI suggestion requires confirmation. Original source remains immutable.
- REJECT/PENDING blocks processing in UI; rejection removes DEMO schedules.
  Backend reject/zero-rewrite regressions remain passing; no provider calls were
  used for the UI checks.
- Browser contract and actual FastAPI -> migrated isolated SQLite -> Vite proxy
  -> inbox read path verified. API failure/malformed responses never inject DEMO.
- Local quality gate on 2026-10-02: 55 backend tests, 18 frontend tests,
  18 Chromium browser tests, format/typecheck/build, backend lint/compile and
  isolated migration upgrade/downgrade/upgrade/check passed.
- All eight default DEMO sections passed automated WCAG A/AA checks. Forty
  screenshots captured at 1366x768, 1440x900, 1586x992, 1920x1080 and 390x844.
  Screenshot comparison is manual, not a claim of pixel-perfect equivalence.
  See UI_DARK_NAVY_VERIFICATION.md for evidence, regressions and limitations.
- GitHub Actions run 37024393524 on implementation commit
  bee24ba32884ab6ecc1735e4843695fca4592458 completed successfully: backend and
  frontend jobs passed and the `ui-dark-navy` evidence artifact was uploaded.

## PARTIALLY IMPLEMENTED

- Compose topology and persistent-volume declarations.
- Live dashboard workflows remain partial: Inbox reads, AI-provider Settings
  and review/plan configuration in Planner use actual API state. Donors, Channels,
  Connections and Accounts still need live frontend wiring; their operational
  configuration APIs already exist.

## NOT IMPLEMENTED

- Operational Telethon ingestion/publication transport, rewrite execution worker,
  fact guard, durable job runner/recovery, timer-driven scheduler and media
  execution remain pending (provider contracts/plan selection already exist).
  PostgreSQL-backed inbox execution remains pending
  Docker Desktop availability, although the API contract is integration-tested
  against SQLite.

## KNOWN ISSUES

- Docker Desktop is not installed on this workstation, so Compose startup and
  persistence/restart E2E are pending environment availability.
- Port 8010 was occupied by an external local process during startup validation;
  the application started successfully on port 8123.
- Obsidian vault location is unavailable; `/docs` is the source of truth.
- DEMO changes exist only in window memory; reload restores fixtures. No
  real account connection, publication, scheduler execution or AI generation.
- Reference photos are not available as separate assets. DEMO uses labelled
  SVG illustrations; no reference PNG is used as an interface background.
- On 2026-10-03 an Alembic validation command was accidentally run against the
  ignored local `backend/newsflow.db` rather than an isolated test database,
  executing downgrade/re-upgrade. It was not tracked by Git and no backup was
  present in the workspace. Future migration checks use isolated temporary DBs.
- GitHub authentication was corrected on 2026-10-07 by selecting the already
  authenticated `borovojarkadij-png` account. Commits `492eb0b`, `e011ddb`
  and `bb33a17` were pushed successfully to the existing
  `borovojarkadij-png/content-studio` repository on `codex/dark-navy-ui`.

## NEXT STEP

The durable configuration, mapping-aware candidate source, publication-planning
contracts, mapping delivery-policy configuration and secure live AI-provider
settings and durable per-output rewrite approval state are complete locally.
Review/approval APIs and live Planner wiring are now verified locally.
Next PHASE 1 task: add the two safe media policies
(reuse source media and licensed local-library lookup) before any real download
or Telegram publication. Keep the current editorial recheck and never perform
real Telegram publication as a side effect of UI work.

PHASE 1 IS NOT COMPLETE. Docker Compose/persistence/restart E2E remains
NOT VERIFIED / BLOCKED BY ENVIRONMENT until Docker Desktop is available.
Live Telegram verification, secrets and Obsidian sync remain pending.
