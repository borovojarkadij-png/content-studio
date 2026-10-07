# Docker and scheduler verification — 2026-10-07

## Scope and safety

Docker Desktop 4.91.0 / Linux engine 29.8.0 runs on this Windows workstation.
Checks used isolated Compose project `newsflow-verification-20261007`, database
`newsflow_verification`, synthetic credentials, a separately mounted fixed test
master key, and ports 18000 / 15173 / 18080. No real Telegram authorization,
provider credentials, AI calls or publications were used. Existing local
development data and the UI at port 5173 were not modified.

## Startup repair

Desktop startup originally failed while renaming stale zero-byte socket reparse
points in `%LOCALAPPDATA%/Docker/run` and `docker-secrets-engine`. With Desktop
fully stopped and absence of backend processes verified, the runtime directories
were renamed, not deleted. Desktop recreated them and its engine became reachable.
No factory reset, volume deletion, WSL unregister or diagnostic upload occurred.

Retained quarantine directories:

- `C:/Users/borov/AppData/Local/Docker/run-quarantine-20261007`
- `C:/Users/borov/AppData/Local/Docker/run-quarantine-20261007-attempt2`
- `C:/Users/borov/AppData/Local/docker-secrets-engine-quarantine-20261007`

This is an observed recovery, not proof of the underlying filesystem cause or a
permanent fix for every Desktop startup failure. A similar directory-renaming
workaround is reported in [Docker feedback issue 554](https://github.com/docker/desktop-feedback/issues/554).
Shutdown used the [documented Desktop stop command](https://docs.docker.com/reference/cli/docker/desktop/stop/).

## Implementation changes

- Backend images package Alembic scripts; a dedicated migrations service upgrades
  the explicit `DATABASE_URL` before API/worker startup. Missing URL refuses a
  silent local SQLite fallback. Repeated upgrade and encoded passwords are tested.
- `compose.dev.yaml` provides backend reload and Windows file polling. Vite uses
  polling in development. Production builds real static frontend assets and serves
  them through nginx, proxying `/api` and `/healthz`; default exposure is loopback.
- nginx healthcheck uses `127.0.0.1`, resolving an observed IPv6 localhost failure.
- The worker runs timer-driven PostgreSQL planning every 30 seconds. It uses each
  automatic channel's timezone, skips past slots, serializes per-plan quota writes,
  rechecks EditorialGate, tolerates an invalid channel independently and repeats
  idempotently after restart. It does not execute rewrite jobs or send publications.
- Build surfaced a `source-map-js` advisory; lockfile updates only that dependency
  to 1.2.2. Local `npm audit` reported zero vulnerabilities afterwards.

## Actually verified on Docker Desktop

| Check | Result |
| --- | --- |
| Dev + production `docker compose config --quiet` | PASS |
| Backend and production frontend image build | PASS |
| Startup + Alembic upgrade against PostgreSQL 16 | PASS |
| API, PostgreSQL, Redis, production proxy health | PASS |
| Actual PostgreSQL-backed inbox read | PASS |
| Rebuild/recreate with state retained | PASS |
| Redis restart + worker restart; Redis AOF marker | PASS |
| `docker compose down` without `-v`, then `up --wait` | PASS |
| PostgreSQL SIGKILL, restart, persisted state probe | PASS |
| Redis `FLUSHDB` in this synthetic stack only; durable state retained | PASS |
| Synthetic encrypted session decryptable with the same separately mounted key | PASS |
| Config, media file + SHA-256 registry, DISPATCHED job and outbox retained | PASS |
| Worker container produces timer ticks against persisted automatic plan | PASS |
| Changed API IP without proxy recreation, health and actual inbox through nginx | PASS |
| Injected synthetic rewrite runner: persisted claim, restart, lease recovery and fenced completion | PASS |

The probe checks exactly one unfinished job, its AWAITING_REWRITE candidate,
two outbox events including exactly one `rewrite.requested`, saved delay/priority,
the daily plan/timezone and original media bytes/hash. It refuses any database
name other than `newsflow_verification` and requires an explicit fixture flag.

## Repeatable acceptance procedure

From PowerShell, with Docker Desktop running:

```powershell
./scripts/verify-persistence.ps1 -Project newsflow-verification-local -CrashRecovery
```

Use `-ApiPort`, `-WebPort`, `-ProductionPort` to avoid occupied ports. The script
provisions only deterministic, public synthetic fixtures under ignored
`.artifacts/docker-verification/<project>/`. It never regenerates an existing
key; a mismatched fixture key refuses to proceed. It builds both profiles, seeds,
checks restart, down/up, optional isolated PostgreSQL crash and Redis loss, and
checks the nginx API proxy. The isolated stack and named volumes remain available
for inspection afterwards. It never uses `down -v` or prunes Docker resources.
The same synthetic procedure is configured as a separate GitHub Actions job.
`-RewriteRecovery` additionally consumes the fixture's pending job using a local
synthetic provider after an actual 60-second lease expiry and worker restart.
Use a fresh project for that terminal procedure; it creates only a PENDING draft.
See REWRITE_RECOVERY_VERIFICATION.md. This is not automatic live-provider execution.

The PowerShell procedure was also run end-to-end on Windows as project
`newsflow-verification-script20261007`, ports 18001 / 15174 / 18081,
including `-CrashRecovery`: PASS. Public fixture secrets are not operational keys.

Final combined acceptance for the fact-guard/runner increment passed on Windows
as `newsflow-verification-final20261007`, ports 18004 / 15177 / 18084, with both
`-CrashRecovery -RewriteRecovery`. It forced an API IP change without replacing
nginx, preserved storage through down/up, PostgreSQL SIGKILL and Redis loss,
then recovered an expired persisted claim after worker restart. The old owner
was fenced; exactly one synthetic provider call produced a persistent PENDING
draft. Network AI calls and Telegram publications were zero.

GitHub run 37683423581 then exposed a Linux-only fixture failure: an exact-IP
holder is refused on a network without user-configured IPAM. This was not data
loss. The verifier now supplies a persisted fixture-only network override with
an explicit random private subnet; operational Compose networking is unchanged.
The corrected full procedure passed on Windows as
`newsflow-verification-ipam20261007` (18005 / 15178 / 18085), including actual
address change, crash recovery, lease expiry and fenced PENDING completion.
GitHub Actions 37684482444 subsequently passed all three jobs, including the
corrected Linux persistence/recovery procedure for commit 1a88983.
The following OpenAI adapter/style/usage increment also passed extended Windows
acceptance as newsflow-verification-openai20261007 (18006 / 15179 / 18086),
using structured synthetic HTTP responses and encrypted synthetic credentials.
Real provider requests remain unverified; the operational worker is disabled
for network rewriting and still has no Telegram publication transport.

## Local operational instance

After verifying there were no existing `newsflow` volumes/containers or local
`.env`/master key, explicit `scripts/initialize-local.ps1` provisioned fresh local
credentials once. A second invocation retained byte-identical `.env` and key.
They remain untracked/ignored. This script refuses to generate a missing key if
old environment/state exists, and refuses unreadable/malformed keys.
The operational instance uses its own `newsflow` named volumes, not test fixtures.
No synthetic account/data is seeded into it.
`docker compose --profile production up -d --build --wait` passed. The operational
UI is available at `http://127.0.0.1:8080` without `?demo=1`; API health returns
`ok` and the real PostgreSQL inbox returns an empty list, not fixture posts.
Both verification stacks were stopped afterwards; their volumes/fixtures remain.

## Local quality gate

- Backend: 139 tests passed; lint including migrations/probe, compile passed.
- Subsequent fact-guard/runner increment: 179 backend tests, lint and compile passed.
- Isolated migration upgrade/drift-check/downgrade/re-upgrade/drift-check and actual
  PostgreSQL drift check passed after ORM index declarations were aligned.
- Frontend: 24 tests, format/typecheck/build and 19 Chromium E2E tests passed.
- Existing rejection/duplicate/stale-job adversarial regressions remain passing.

## Not yet verified / not implemented

Synthetic session persistence is not real Telegram authorization persistence.
Storage persistence alone was initially verified; subsequent injected synthetic
runner acceptance now demonstrates leased execution recovery. The default daemon
still does not invoke network rewrite providers; live job execution is pending.
Automatic planning is not automatic publication or automatic editorial approval.
The fixture's AWAITING_REWRITE candidate remains unscheduled. Live Telegram login,
provider secrets, actual media acquisition and transport verification remain pending.
nginx initially cached a recreated API's old address and returned 502. Dynamic
Docker DNS resolution fixes it; acceptance reserves the old IP with an exact
disposable holder and checks a new API IP while keeping the same proxy container.
Configuration follows the [nginx proxy/resolver contract](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).
Production TLS, authentication, backup/restore acceptance and hardened deployment
remain pending. **PHASE 1 is not complete.**
