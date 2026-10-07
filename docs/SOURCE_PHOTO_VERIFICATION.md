# Exact source-photo acquisition checkpoint

## Scope and invariants

Single non-album Telegram photos can be downloaded through the read-only provider
boundary and registered in persistent storage without changing their bytes.
Immutable revisions now retain signed media identity and protected-content status.
Legacy unknown values are not guessed or backfilled. Protected content, albums,
unapproved/stale drafts, unhealthy accounts and editorial rejects fail closed.
Donor accessibility is not reuse permission: acquisition requires explicit OWNED
or PERMISSION rights; PERMISSION also requires attribution. Source-photo reuse
and internet illustration acquisition remain distinct modes.

The adapter bounds chunks and total content to 16 MiB, closes streams and refetches
the source identity after download. Acquisition checks current bindings before
RPC and after RPC/decoding/registration; no DB transaction spans network I/O.
Original bytes enter create-only content/rights-addressed storage, with actual
single-frame PNG/JPEG decoding before registry commit. Existing files are never
overwritten. No login, rewrite, automatic approval or publication occurs.

## Verification actually executed on Windows, 2026-10-08

- Backend: **548 tests PASS**, exact CI-directory Ruff lint PASS, compile PASS,
  diff whitespace check PASS. Includes changed identity/protection, source changes
  during RPC, reject/review/policy/account revocation, corrupt existing storage,
  invalid decoding, exact bytes and repeated acquisition regressions.
- Isolated Alembic upgrade/check/downgrade/re-upgrade/check PASS. Populated media
  identity downgrade refuses history loss; legacy revisions retain unknown values.
- Frontend: **40 unit / 21 browser tests PASS**, format/typecheck/build PASS,
  production audit zero. No UI implementation claim for this acquisition seam.
- PowerShell procedure parsing and CI YAML syntax PASS.
- Actual Docker Desktop acceptance: `newsflow-verification-sourcephoto20261008`,
  ports 18018/15191/18098, CrashRecovery + SourcePhotoGuard PASS. Dev/prod build,
  migrations/health/proxy, down/up, Redis/worker restart, PostgreSQL crash and
  Redis-loss recovery PASS using isolated synthetic fixtures.
- Source identity/protection, exact persisted photo bytes/hash, explicit rights,
  approved per-output binding and selected registry asset survive down/up and
  worker restart. Independent PostgreSQL row-lock probes during injected RPC
  prove no acquisition transaction holds account/candidate/editorial locks over
  that RPC. Revoked editorial acquisition makes zero provider requests; the actual
  media-selection API returns 409. Fixture stopped preserving volumes/history.
- Packaged fixture and operational PostgreSQL drift checks PASS. Operational
  backend migrated/rebuilt; health and inbox through port 8080 return HTTP 200.
  All four operational network enablement flags remain 0. No synthetic records
  were inserted into the operational database; no secrets or master key changed.

Album checkpoint `80a4a5b500cdcb186a7ea3a52b858ceb61027478` CI 37703200551
completed SUCCESS in all four jobs. Original album CI 37702733554 failed its two
Docker jobs because of probe ordering; correction retained all assertions and
resumed the existing fixture without reseeding. Source-photo CI is separate and
must be recorded after this checkpoint is pushed.

## Remaining limitations

This checkpoint is an acquisition seam, not a durable source-photo worker or UI.
Persistent rights configuration, fenced job orchestration and API/UI controls are
next. Full album manifests, deletion/update recovery and video download remain
pending. Real Telegram authentication/download is NOT VERIFIED: no authorized
account credentials are provisioned. Synthetic recovery does not qualify a live
AI model or authorization session. PHASE 1 is not complete. `/docs` remains the
source of truth while Obsidian sync is pending.
