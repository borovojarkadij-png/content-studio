# Safe media selection — current increment

Two policy intents are persisted per mapping and snapshotted per candidate:

- `REUSE_SOURCE`: choose only registered photo assets of the exact content revision.
- `LICENSED_LIBRARY`: deterministic Russian/Unicode keyword matching against
  locally registered photo tags. Ranking is overlap count then immutable asset ID.
  No match returns `NO_MATCH`, never silently switches to unrelated/source photos.

Local lookup alone is **not** the requested internet-search agent. A free Commons
topic-search/download provider and guarded acquisition service now populate this
persistent library with explicit attribution; see INTERNET_MEDIA_VERIFICATION.md.
Durable acquisition worker/recovery is verified separately. Visual-semantic
ranking and UI controls remain pending.

## Storage and API

`media_assets` is a PostgreSQL/SQLAlchemy registry of relative storage identity,
SHA-256, MIME signature, source revision, origin, declared license, attribution
and tags. The application never writes or modifies originals in this increment.
Actual files reside under explicit `NEWSFLOW_MEDIA_ROOT`; Compose declares a
shared `media_data` named volume mounted read-only in API and writable in worker.
No missing directory is automatically replaced by ephemeral storage.

`POST /api/telegram/media-assets` registers an existing file with explicit rights.
It is not upload/download or an assertion that a donor grants reuse permission.
Source reuse requires declared `OWNED` or `PERMISSION`; CC-BY/PERMISSION require
credit. Supported local formats are PNG/JPEG, limited to 16 MiB. Validation checks
signature/extension/hash and actual single-frame decoding, with a 25-million-pixel
ceiling checked before pixel allocation. APNG, damaged/header-only images and
decompression bombs fail closed. Original bytes are never re-encoded.

`GET /api/telegram/publication-candidates/{id}/media-selection?query=…&limit=…`
reads that candidate's snapshotted policy, checks fresh EditorialGate, source,
current per-output approval/technical constraints and READY/SCHEDULED state,
selects registered files and verifies hashes. These bindings are rechecked after
decoding so cached ORM state cannot hide revocation or a source/policy edit. It does not
call any remote service, create jobs, download media or publish a post. Full
render/publication must still perform its own gate/file checks at execution time.

Registration is immutable/idempotent: same identity/rights returns the same row;
different metadata/hash conflicts instead of silently replacing an original.
Traversal, absolute/Windows/network/URL keys and resolved paths outside the
configured root are rejected. Missing/changed files produce visible errors.

Migration `e82a9c7b3061` adds the registry without altering existing records.
Downgrade is refused when it contains rows, to prevent losing rights metadata.
Back up both database and media bytes before operating on real state.

## Verification

2026-10-07: 132 backend tests passed, including 15 media tests, HTTP persisted
registry/selection, guarded populated downgrade and existing isolated migration
checks. Backend lint passed; two actual-API browser regressions passed with the
new migration. No production files, secrets, remote downloads, paid AI calls or
Telegram publications were used.

Initial Compose config passed for dev and production using `.env.example`, `--quiet`
and `--no-env-resolution`. This validates topology only: Docker Desktop CLI is
now installed, but its Linux engine pipe is unavailable even after starting
Desktop. `.env`/master-key provisioning, build/startup and volume/restart recovery
were then **NOT VERIFIED / BLOCKED BY ENVIRONMENT**. This historical blocker
was subsequently resolved: actual synthetic media/config/session/job storage
passed Docker rebuild/down-up/crash tests. See DOCKER_VERIFICATION.md; live media
acquisition and transport remain pending.

### 2026-10-08 decode and fresh-state regression checkpoint

Test-first failures reproduced header-only PNG/JPEG acceptance and cached
editorial/review revocation bypasses. Added real PNG fixtures and adversarial
pixel/frame/decode, stale-source and mid-decode mutation coverage. Backend 472
tests, exact backend-directory CI lint, compile and isolated migration round-trip
PASS. Targeted media/review regression gate: 84 PASS.

Actual Windows Docker Desktop acceptance PASS in isolated
`newsflow-verification-mediaguards20261008`, ports 18016/15189/18096:
`verify-persistence.ps1 -CrashRecovery -SemanticGuard -MediaGuard`. Dev/prod build,
migrations/health, proxy DNS change, down/up, Redis/worker restart, PostgreSQL
crash, encrypted synthetic session and unfinished durable jobs passed. Recovered
media bytes/hash/rights and real selection/status API passed; revoked approval
returns 409 and creates no provider calls. Invalid persisted PNG was not registered
or overwritten. Packaged PostgreSQL drift PASS. Fixture stopped with all volumes
and histories retained; never reseed it. Network AI/Telegram calls and sends: zero.
Operational deployment of this checkpoint is pending the next provider gate.
