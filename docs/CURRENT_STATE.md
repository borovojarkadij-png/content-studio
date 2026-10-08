# Current state

## VERIFIED WORKING

- Bounded default-disabled deletion-first worker seam OFFLINE: 17 dedicated /
  29 tick+replay / full backend 935 PASS (23980), exact CI Ruff/changed format/
  compile/explicit isolated D: drift PASS. Real encrypted factory/TL read/history,
  no legacy/non-final/failure fallback, deletion-before-history, durable retry/
  SQL-reopen and seven-donor fair scan verified; implicit account join bug fixed
  by explicit donor join. See CHANNEL_SYNC_TICK_VERIFICATION.md. Main loop inactive.
- Durable exact quarantined-revision replay OFFLINE: 12 dedicated / 61 combined /
  full backend 918 PASS (41004), exact CI Ruff/changed format/compile/explicit
  isolated D: drift PASS. Atomic obligations, partial mapping crash/SQL reopen,
  real obligation/completion insert faults, bound current idle sync/session/filter
  fencing, fair bounded scan, unknown MANUAL_REVIEW and protected REJECT zero-job/
  zero-usage verified. See SOURCE_SYNC_REPLAY_VERIFICATION.md. Worker wiring pending.
- Known channel gap/foreign-baseline shared source quarantine OFFLINE: final
  full backend 906 PASS (21914), 70 targeted, exact CI Ruff/changed format/compile/
  explicit isolated D: drift PASS; 65 frontend units / 26 browser PASS (91631),
  format/typecheck/build/audit 0. Cached PASS/retry/API/manual/media/final-send
  zero-provider and historical receipt zero-resend verified. Real read-only Inbox
  distinct sync state, reload/WCAG/narrow screenshots visually inspected. See
  SOURCE_SYNC_GUARD_VERIFICATION.md. Durable retained-observation replay pending.
- Authenticated read-only checkpoint and create-only new-donor baseline OFFLINE:
  53 targeted / full backend 886 PASS (12463), exact CI Ruff/changed format/
  compile/explicit isolated D: Alembic round-trip/drift PASS. SQL-reopen identity,
  legacy-zero-RPC, concurrent winner/session/poll/source/mapping fencing, real
  encrypted factory and durable health/outbox rollback verified. See
  CHANNEL_BASELINE_VERIFICATION.md. No worker activation or live/Windows claim.
- b6b4d98 CI 37715889965 completed SUCCESS in all four jobs (actual gh view).
  Deletion 0efb0b6 CI 37714969203 and cursor add59c6 CI 37715433401 also
  completed SUCCESS (actual gh list). Linux CI is not current Windows proof.

- Retained source-deletion Inbox/API/UI OFFLINE: full backend 833 PASS (54870),
  frontend 62 units / final browser 25 PASS (41662), format/typecheck/build/audit,
  CI Ruff/compile/explicit D: drift PASS. Historical text/PASS/jobs retained;
  deletion is a distinct blocked state, not fabricated EDITORIAL REJECT. Real
  migrated API/GET-only/reload/WCAG/narrow checks and desktop/mobile screenshots
  visually inspected. See SOURCE_DELETION_INBOX_VERIFICATION.md. Windows blocked.
- Difference provider checkpoint 2d744c2 CI 37714319250 completed SUCCESS in all
  four jobs; this is Linux Docker evidence, not current Windows deployment proof.

- Leased deletion-first channel-pts consumer OFFLINE: 30 targeted / full backend
  831 PASS (66930), exact CI Ruff/targeted format/compile/explicit D: migration
  round-trip/drift PASS. Current identity/session/lease and mapping/filter binding,
  partial SQL-reopen fan-out replay, TooLong/missing-baseline/zero-RPC and actual
  outbox storage fault verified. See CHANNEL_DIFFERENCE_RUNTIME_VERIFICATION.md.
  No baseline fabrication, worker activation or live/Windows acceptance claimed.

- Durable source-deletion tombstones/shared freshness OFFLINE: 22 targeted /
  full backend 801 PASS (10602), exact CI Ruff/targeted format/compile/explicit
  D: migration round-trip/drift PASS. Deleted replay/cached PASS/stale retry/
  real review API/manual planning/media/final send guards verified; historical
  exact receipt recovery remains zero-resend. See SOURCE_DELETION_VERIFICATION.md.
  Leased cursor application and current Windows/live acceptance remain pending.
- Observed-ack version-2 probe checkpoint 6266b5a CI 37713732217 completed
  SUCCESS, including both Linux Docker/PostgreSQL variants. This is not Windows
  Docker Desktop verification; current Windows remains environment blocked.
- Observation checkpoint 33757e6 CI 37713401088 completed SUCCESS in all four jobs.

- Bounded read-only channel difference contract OFFLINE: full backend 779 /
  exact CI Ruff/targeted format/compile/explicit D: migration drift PASS.
  New/edited/deleted identities, pts/bounds/final, TooLong/unknown/foreign
  fail-closed, encrypted factory and bool/unbound user regressions verified.
  No durable cursor/deletion application or worker enabled yet; see
  TELEGRAM_CHANNEL_DIFFERENCE_VERIFICATION.md. Live/Windows Docker NOT VERIFIED.

- Versioned create-only publication probe logic OFFLINE: 751 backend /
  exact CI Ruff/targeted format/compile and PowerShell parser PASS.
  Independent SQL reopen verifies encrypted original requests/observed ack,
  zero-resend completion, legacy-manifest refusal and no reseeding. New actual
  PostgreSQL/Docker procedure NOT VERIFIED yet; Windows environment blocked.
  See PUBLICATION_PROBE_OBSERVATIONS_VERIFICATION.md.

- Exact direct-response publication observations/no-resend recovery OFFLINE:
  full backend 750 / exact CI lint/targeted format/compile/explicit D: migration
  round-trip/drift PASS. Real SQL insert failures/crash, historical reject/edit,
  corrupt/missing/conflicting receipt, bounded fair cursor and active lease
  verified. Frontend 58 units/format/typecheck/build, final browser 24 PASS
  (17486). See PUBLICATION_OBSERVATION_VERIFICATION.md.
  No actual sending enabled; current Windows Docker/live NOT VERIFIED.

- Encrypted immutable publication request snapshots OFFLINE: full backend 737 /
  Ruff/targeted format/compile/explicit D: Alembic round-trip/drift PASS.
  Same-transaction snapshot+intent+outbox, historical reads after rejection,
  strict JSON/key/nonce/binding and legacy-zero-send verified. Migration
  b7e426d9ab15 preserves legacy history and refuses populated downgrade.
  See PUBLICATION_SNAPSHOT_VERIFICATION.md; Windows Docker/live remain blocked.

- Strict default-disabled publication main-loop wiring OFFLINE: backend 720 /
  Ruff/targeted format/compile/explicit D: migration round-trip/drift PASS (51530),
  frontend 56 units/23 browser/format/typecheck/build/audit PASS (5676).
  Actual main loop verified with synthetic SQL/encrypted session/TL network only;
  missing flag inert, invalid flag rejected. Working .env/secrets unchanged,
  no actual send enabled. Current packaged/operational/live NOT VERIFIED.

- Bounded fair publication tick/admission seam OFFLINE: full backend 717 /
  Ruff/targeted format/compile PASS (15953), 14 targeted tick regressions PASS.
  Encrypted text/photo dispatch, no disabled DB access, expiry/fair cursor and
  uncertain-history zero-resend verified; main-loop runtime flag pending.
  See PUBLICATION_TICK_VERIFICATION.md; no sending was enabled.

- Guarded original-photo transport OFFLINE: full backend 703 / Ruff / targeted
  format / compile PASS (55064). Current source asset/rights/bytes, attribution,
  exact nonce/caption/photo receipt and post-upload state fencing verified in SQL
  with synthetic network. Unknown send never resends/reuploads on restart.
  No runtime flag/API enabled. See TELEGRAM_PHOTO_TRANSPORT_VERIFICATION.md.

- Guarded encrypted text-only transport OFFLINE: 35 targeted transport/factory
  regressions, full backend 684 / Ruff / compile PASS. No worker/send API enabled.
  Exact nonce/channel/text receipt, final post-auth reject/source/session/review
  fencing, delayed FloodWait and timeout zero-resend proven with synthetic RPCs.
  See TELEGRAM_TEXT_TRANSPORT_VERIFICATION.md. Live/packaged NOT VERIFIED.

- Read-only publication delivery API/real Planner UI: 646 backend / 55 frontend
  unit / 23 browser tests, lint/format/typecheck/build/compile/audit PASS.
  Retained publication Windows Docker HTTP/status/API-worker-restart/PG drift PASS
  (session 21927), stopped preserving volumes/history. See PUBLICATION_STATUS_VERIFICATION.md.
  Latest operational deployment FAILED due to external disk-full/Docker read-only
  filesystem (session 40773); its current deployment/health is NOT VERIFIED.

- Publication local gate: fresh preflight, durable intents/nonce/leases, uncertain
  delivery quarantine, late exact receipt and published quota regressions PASS.
  Backend 642/CI lint/format/compile/isolated migration PASS; frontend 50 unit /
  22 browser/format/typecheck/build/audit PASS. Actual Windows Docker publication
  crash/down-up/lease/zero-resend/rejection recovery PASS; final packaged quota
  regression/PG drift PASS before and after down/up. Isolated publication20261008
  stopped retaining all history/volumes. Operational a6d315c8fa04 migration/images,
  drift/health/inbox PASS, all five flags 0. Authenticated publication NOT verified.
- Media UI aa075af9f15cb346cec184a1e109e26c74bdf658 CI 37707297625 completed
  SUCCESS in all four jobs. This predates the publication increment.

- Candidate media queue/progress and protected preview implemented in real
  Planner. Backend 587/lint/compile/isolated migration PASS; frontend 50 unit /
  22 browser/format/typecheck/build/audit PASS. See MEDIA_PLANNER_VERIFICATION.md.
  Windows Docker CrashRecovery/SourcePhotoGuard acceptance PASS in
  newsflow-verification-mediaui20261008: generic queue/exact no-store preview,
  stale-owner/rejected queue/preview guards PASS. Packaged PG drift PASS; stopped
  retaining all volumes/history, never reseed.
  Operational images rebuilt: migrations/PG drift/health/inbox PASS, five flags 0.
- Source-job checkpoint fdf8f06667bec6b42c4c59a4f3cdf41a559f9234 CI 37706050198
  completed SUCCESS in all four jobs. This predates the new media UI increment.

- Durable source-photo runner, versioned explicit mapping rights, real queue/status
  API, default-disabled worker and real Connections rights form implemented.
  Backend 581 tests/lint/isolated migration round-trip PASS; frontend 42 unit /
  21 browser/format/typecheck/build/audit PASS. Actual source-job Windows Docker
  recovery PASS in newsflow-verification-sourcejobs20261008; fixture stopped with
  history/volumes retained. Operational API/worker/frontend rebuilt/migrated:
  PG drift/health/inbox PASS, all five network enablement flags 0.
  See SOURCE_PHOTO_JOBS_VERIFICATION.md. Combined fixture rerun is separate.
- Provider checkpoint f4124e8 CI 37704439283 completed FAILURE: backend/frontend
  SUCCESS, both Docker jobs failed synthetic user-ID collision with mapping probe.
  Regression reproduced; distinct source fixture identity now implemented. Fresh
  combined Windows CrashRecovery/MappingGuard/SourcePhotoGuard PASS in
  newsflow-verification-sourcecombo20261008 (18020/15193/18100).

- Exact source-photo acquisition seam, immutable signed media identity/protection
  and history-preserving migration verified: 548 backend tests/lint/compile PASS,
  40 frontend unit/21 browser/format/typecheck/build/audit PASS. Actual Windows
  Docker CrashRecovery + SourcePhotoGuard PASS in isolated
  newsflow-verification-sourcephoto20261008; original bytes/rights/identity survive
  down/up/restart, no DB locks across injected RPC, revoked editorial zero-provider
  and real selection API 409. Fixture stopped preserving all history/volumes.
  Packaged fixture/operational PostgreSQL drift PASS; operational backend rebuilt
  and migrated, proxied health/inbox HTTP 200, all four network flags still 0.
  See SOURCE_PHOTO_VERIFICATION.md. Source worker/API/UI not yet implemented.
- Album follow-up 80a4a5b CI 37703200551 completed SUCCESS in all four jobs.
  Original c2bd2da CI 37702733554 completed FAILURE in both Docker jobs due to
  the reproduced probe ordering bug, corrected without weakening assertions.

- Actual album Windows Docker acceptance resumed after a probe-order correction:
  recover/worker-restart/verify/edit/down-up/verify-edit PASS, packaged PostgreSQL
  drift PASS, real inbox retained both grouped photo/video members without
  editorial/rewrite. Fixture stopped retaining histories/volumes, never reseeded.
  Operational media/album backend rebuilt: packaged PG drift/flags 0/health/inbox
  HTTP 200 PASS. Media CI 37702104802 completed SUCCESS in all four jobs.

- Bounded sparse album observation implemented in provider/Telethon/encrypted
  factory/fake, never claiming complete membership. Grouped captions cannot
  reach editorial/rewrite individually; grouped blank/video sources are retained.
  Legacy/missing-candidate stale tasks and manual review cannot bypass the gate.
  Backend 500 tests/lint/compile/format/isolated migration round-trip PASS.
  Actual album Windows Docker acceptance in progress, not verified yet; see
  TELEGRAM_ALBUM_VERIFICATION.md. Full durable album workflow/download pending.
- CI 37701614150 for corrective UI checkpoint d03719f completed SUCCESS in all
  four jobs. Media checkpoint d430d88973bf60b7623fbe321019d9be67ab1a52 pushed;
  CI 37702104802 backend PASS, remaining jobs in progress at last inspection.

- Bounded actual single-frame photo decoding and fresh pre/post-selection
  editorial/source/review/technical bindings verified. Backend 472 tests,
  lint/compile/isolated migration gate PASS; actual Windows Docker media guard
  down/up/crash/lease recovery and real media/status API PASS in isolated
  newsflow-verification-mediaguards20261008. Packaged PostgreSQL drift PASS;
  stopped retaining all volumes/history. Zero AI/Telegram network calls/sends.
  See MEDIA_SELECTION.md. Operational deployment pending next provider gate.
- Corrective checkpoint d03719f pushed; CI 37701614150 backend/frontend PASS,
  Docker jobs still running. Earlier 37701042107 completed FAILURE due to the
  reproduced fixture import-order issue; do not call it an overall PASS.

- UI checkpoint 96fece5e888a02ac056dc3a634622e5b8af808e2 pushed to correct origin.
  CI 37701042107 frontend PASS; backend Lint failed because checking the fixture
  from repository root classified Alembic imports differently from CI's backend
  directory. Exact backend-directory lint reproduced and passed after restoring
  import ordering; corrective fixture-only checkpoint follows. Docker jobs still
  running at last inspection, not an overall CI PASS. Import CI 37700522102 for
  b20885e completed SUCCESS in all four jobs.

- Real configuration UI wired for Accounts/Donors/My Channels/Connections:
  public health, metadata create/rename, pending donor import, route create and
  delivery/media/technical-filter editing. Manual drafts/partial failures/late
  responses remain protected; no fake authorization/AI/send or DEMO fallback.
  Frontend 40 units / 21 actual browser regressions PASS, format/typecheck/build
  PASS, production audit zero. Eight desktop/mobile working screenshots inspected.
  Operational production UI rebuilt and four sections opened read-only with zero
  writes; actual configuration APIs HTTP 200. See CONFIGURATION_UI_VERIFICATION.md.

- Read-only broadcast-channel username resolution, immutable canonical identity/
  full-hash validation, encrypted factory peer persistence and durable import
  jobs/leases/fencing implemented locally. Aliases share one donor without
  replacing manual titles; resolved identity and outbox commit atomically.
  Unprovisioned/foreign/min/user peers cannot become operational donors. Opt-in
  worker processes at most four due imports before donor polling, default still 0.
  Late poll failures now preserve longer cooldown/invalid-session state and cannot
  invalidate a concurrently replaced session. Backend 462 tests PASS, lint/compile
  and isolated migration round-trip PASS. Actual Windows Docker import recovery,
  PostgreSQL drift and resolved import/donor API PASS in isolated
  newsflow-verification-donorimports20261008; fixture stopped retaining volumes
  and history. No live authorization, Telegram network/AI calls or sends.
- Encrypted account-scoped Telegram input peers and bounded accessible-dialog
  resolution implemented. RPCs verify the provisioned user's identity; corrupt/
  foreign cache and concurrently replaced sessions fail closed. Backend 425-test
  peer checkpoint PASS. Actual Windows Docker peer restart/crash recovery PASS in
  newsflow-verification-peers20261008, including injected PostgreSQL lock probe
  and donor ingestion guard; packaged PostgreSQL drift PASS, fixture stopped with
  volumes/history retained. This is NOT live Telegram authorization.
- Persisted mapping technical-filter API/ingestion and fresh pre/post-rewrite,
  draft-review and calendar guards implemented. Unicode/trailing-dot blocked-host
  bypasses and concurrent-policy/manual-review bypasses reproduced and fixed.
  Backend 442 tests / lint / compile / isolated migration round-trip PASS. Actual
  Windows mapping-filter down/up acceptance, peer crash recovery, packaged
  PostgreSQL drift and real filter API PASS in isolated
  newsflow-verification-mappingfilters20261008; stopped retaining history/volumes.
  Frontend 26 units / 19 browser regressions / format / typecheck / build PASS.
- Source-observation metadata now preserves media type, album ID and source
  update time on immutable revisions (legacy migrated media is UNKNOWN, not
  fabricated text). Media-only edits invalidate old revisions. Older/missing
  timestamps cannot roll back known source; equal-time conflicting payloads
  require manual review even without an edit flag. Recent 50-message replay
  observes old-message edits without resetting the new-message cursor.
  Backend 414 tests / lint / compile and isolated migration round-trip PASS.
  Actual Windows Docker source-observation acceptance PASS: media-only video/
  album/timestamp edit survived down/up, old source remained stale with no new
  editorial/rewrite. Actual PostgreSQL drift and injected health/session-refresh
  concurrency probe PASS. Fixture stopped with history/volumes retained.
- GitHub Actions 37696430337 for f19af6d completed SUCCESS in all four jobs,
  including durable ingestion recovery. It predates source-observation changes.

- Durable donor new-message polling/cursors, bounded history, current mapping
  intake, partial fan-out replay, leases/fencing and persisted FloodWait/retry
  are implemented. Windows Docker ingestion acceptance PASS in isolated
  newsflow-verification-ingestion20261008 (down/up, stale owner, incomplete mapping
  recovery, REJECT/manual inbox retention), actual PostgreSQL drift PASS; stopped
  with volumes retained. Never rerun seed. See INGESTION_RUNTIME_VERIFICATION.md.
- Read-only Telethon RPC/auth/history and encrypted current-session factory,
  CAS-protected session refresh, opt-in ingestion tick (default disabled), separate
  optional credential mount and health network/DB-lock separation implemented.
  Contract tests are synthetic, NOT live login. Latest backend 406 / frontend 26
  / browser 19 PASS; lint/compile/format/build and isolated migration gate PASS.
  Latest operational images rebuilt and migrations applied; all services healthy,
  actual PostgreSQL drift PASS, proxied health/inbox HTTP 200. All four network
  enablement flags remain 0; no real authorization or send was enabled.
- GitHub Actions 37695104475 for ingestion-safety 3606cee and 37694461555 for
  health b9d4b93 both completed SUCCESS in all four jobs. Next increment CI separate.

- Durable ingestion now defaults unclassified content to MANUAL_REVIEW, retains
  its source for inbox review and creates no rewrite. Unknown annotation values
  fail closed in EditorialGate. Rejected/technical/exact-duplicate edits now
  invalidate old source revisions instead of leaving them publishable.
  Test-first regressions and backend 372-test gate PASS; see
  INGESTION_RUNTIME_VERIFICATION.md. This is not a semantic text classifier.
- GitHub Actions 37694252178 for durable-media commit 56a8ef7 completed SUCCESS
  in all four jobs. Health checkpoint b9d4b93 run 37694461555: backend/frontend
  passed, Docker jobs still in progress at last inspection.

- Telegram health regressions reproduced/fixed: implicit SQLAlchemy transactions
  previously lost FloodWait cooldown on session close, and cached accounts could
  hide external cooldown updates. Dedicated health mutations now commit/rollback,
  refresh locked rows and normalize persisted UTC timestamps. Naive input time
  fails before DB/provider access. Backend 364 tests PASS; targeted 6 health tests,
  lint/compile PASS. This proves fake-provider persistence, not live Telegram auth.
- Durable-media commit 56a8ef7955576ab423c6e99383a19ff74120c717 pushed to the correct
  origin branch. CI run 37694252178 is IN PROGRESS: backend passed; remaining jobs
  must be checked, not reported as overall PASS yet.
- Durable internet-media jobs, bounded committed attempts, 60-second leases,
  stale-owner fencing, 30-second persisted transient retry and atomic selected
  asset/completion are implemented locally. Worker opt-in defaults disabled.
  Read-only acquisition-status API checks current source/editorial/review and
  persistent byte integrity; historical success alone never permits selection.
  Latest backend 361 tests / lint / compile / isolated migration gate PASS;
  19 Chromium browser regressions passed again. Actual Windows Docker media-job
  recovery PASS: down/up, old-owner fencing, selected-asset bytes/hash/rights,
  atomic durable completion and real status API survive worker restart. Revoked
  automatic approval blocks acquisition and API selection without network calls.
  PostgreSQL drift passed in isolated and rebuilt operational stacks; health and
  proxied inbox returned 200. Synthetic fixture stopped, volumes retained.
- GitHub Actions 37692967241 for 5faf7227 completed SUCCESS in all four jobs;
  this precedes the durable media-job increment.
- Free internet-image provider/acquisition boundary implemented and tested:
  allowlisted Commons topic search, explicit rights/credit, bounded decoded photos,
  fresh editorial/source/review gates and atomic create-only persistent storage.
  32 new tests / full backend 346 PASS; lint/format/compile PASS. Actual free live
  search and 2,643,989-byte CC-BY photo decode passed in memory, no operational
  data changed. Worker/UI/visual-semantic ranking still pending; illustrations
  are not claimed to depict actual post events. See INTERNET_MEDIA_VERIFICATION.md.
- GitHub Actions 37692242447 for 59f4d481 completed SUCCESS in all four jobs,
  including both leased-semantic Docker variants. Media increment CI is separate.
- Durable semantic verification runtime now implemented: PostgreSQL jobs, committed
  two-attempt budget, 60-second leases/fencing, exact binding rechecks, per-attempt
  known usage, encrypted pinned-model factory and opt-in worker (default disabled).
  Approval/candidate activation and successful job completion are atomic. Errors
  and uncertain verdicts remain manual; no operational model has been qualified.
- Latest checkpoint: 314 backend tests, lint/compile and isolated migration
  upgrade/check/downgrade/base/re-upgrade/check PASS; frontend 26 units and
  19 Chromium E2E plus format/typecheck/build PASS. Test-first regressions fixed
  cached ORM draft/editorial/source values hiding external edits or revocations.
- Actual Windows Docker leased-semantic acceptance PASS in
  newsflow-verification-semantic-lease20261008: real down/up/expired claim recovery,
  old-owner fencing, atomic automatic approval, persisted usage and release
  revocation blocking a reservation. Synthetic only; no AI/Telegram network calls.
  Fixture stopped with history/volumes retained. Latest cache fixes packaged on
  operational stack; startup/health and actual PostgreSQL drift check PASS.
- GitHub Actions 37690647842 for 0196f238 completed SUCCESS in all four jobs
  (backend, frontend and both Docker provider variants). This predates the new
  leased-semantic increment; track its next CI run separately.
- Semantic evidence/guarded automatic approval contract implemented: default
  MANUAL per-channel policy, trusted exact-model release registry (no public
  qualification/verdict endpoint), immutable source/draft/release digest binding,
  explicit approval method and current-review scheduling reconciliation. Synthetic
  evidence survives actual PostgreSQL down/up; revocation blocks its old slot.
  See SEMANTIC_APPROVAL_VERIFICATION.md. No operational model is qualified;
  runtime wiring is now complete above; live accuracy/release qualification pending.
- Fresh local semantic checkpoint: 298 backend tests passed after the separate
  verification-adapter increment; that adapter's targeted 60-test gate passed too.
  Frontend 26 units / 19 Chromium E2E, format/typecheck/build passed with migrated
  isolated API. Backend lint and compile passed as well.
- GitHub Actions 37688114933 for a72cf2e completed SUCCESS: backend, frontend,
  synthetic Docker OPENAI and OPENROUTER jobs all passed. This predates the current
  semantic increment; its CI result must be tracked separately after pushing.
- Source-edit adversarial bypass was reproduced and fixed before automatic
  approval work: old/missing source revisions cannot record/approve drafts,
  activate candidates or obtain/retain active publication slots. Shared immutable
  source lookup rejects missing/ambiguous identities, stale reservations become
  BLOCKED_SOURCE without deleting history. Backend 233 / browser 19 passed.
  See SOURCE_GUARD_VERIFICATION.md; no automatic approval or send is enabled.
- Source-edit guard also passed on actual PostgreSQL in the rebuilt isolated
  OpenRouter verification stack. API projected approve_allowed=false and returned
  HTTP 409 for the old draft; the old PLANNED reservation became BLOCKED_SOURCE.
  Fixture history/volumes retained and stack stopped; no network AI/Telegram send.
  Updated operational images are healthy; PostgreSQL drift check still passes.
- Planner empty-state wording now distinguishes an empty review queue from an
  unimplemented worker; provider/source setup and explicit network enablement are
  required. Regression failed before the wording fix. Frontend 26 / browser 19,
  format/typecheck/build and audit passed again with current source fixtures.
- Earlier source-guard CI checkpoint was superseded by the four-job successful
  a72cf2e run above; do not interpret old in-progress reports as current status.
- OpenRouter commit a9c6e72 GitHub run 37686789050: backend and both synthetic Docker
  provider jobs passed; frontend browser installation is still in progress.
  Do not claim an overall CI PASS until the run actually completes.
- Bounded strict free-only OpenRouter adapter is now connected to the encrypted
  factory and explicitly selected opt-in worker. One overall fallback deadline,
  zero price caps, no paid/cross-provider fallback, terminal invalid/fact-changed
  responses and persisted actual provider/model/style usage are tested offline.
  Backend 227 / frontend 26 / browser 19 checks passed; production audit zero.
  See OPENROUTER_REWRITE_VERIFICATION.md. Operational networking remains disabled.
- Windows Docker free OpenRouter structured recovery passed in isolated project
  newsflow-verification-openrouter20261008: down/up, PostgreSQL crash, Redis loss,
  encrypted settings/session/media persistence, expired claim fencing and exactly
  one synthetic structured completion with durable usage/PENDING draft. No external
  provider calls or Telegram sends. Latest code packaged/deployed on operational
  stack, all services healthy and actual PostgreSQL drift check passed.
- GitHub Actions 37685672269 passed all three jobs for OpenAI/style commit 187d51e,
  including Linux synthetic restart/crash/leased structured recovery.
- OpenAI strict structured rewrite adapter, encrypted-settings factory and explicitly
  opt-in worker are implemented and tested offline. Default worker still plans only;
  network rewriting remains disabled in the operational stack. Known tokens persist
  per attempt; unknown tariff is NULL. No Telegram send is enabled by that flag.
- Per-channel natural tabloid style is saved by real Planner API buttons and retained
  after reload. It never bypasses editorial/fact/review gates or modifies old drafts.
  Backend 207 / frontend 26 / browser 19 tests passed; see AI_REWRITE_VERIFICATION.md.
- Windows Docker acceptance of encrypted OpenAI factory/style/known usage and
  structured synthetic HTTP recovery passed in newsflow-verification-openai20261007.
  Latest code deployed on operational stack; PostgreSQL schema drift check passed.
- GitHub Actions 37684482444 passed all three jobs for Linux verification IPAM fix
  1a88983. Previous runner run 37683423581 failed only on unconfigured test subnet;
  the fixture override fixed it. This CI success predates the OpenAI/style increment.

- Fact-anchor guard blocks changed numeric/date/link/mention/quote facts after
  rewrite and retains zero provider calls for rejected/disabled editorial decisions.
  It explicitly does NOT prove full semantics or authorize automatic approval.
- Durable rewrite runner component persists bounded attempt budgets before calls,
  uses PostgreSQL leases/fencing, handles retries/source edits/stale rejects,
  and atomically creates only per-output PENDING drafts/completion outbox events.
  Recovery through injected synthetic providers was exercised after a real Docker
  worker restart and lease expiry. Default daemon still runs planning only.
- Latest local backend gate: 179 tests, lint and compile passed; 24 frontend units
  and 19 browser E2E passed. See REWRITE_RECOVERY_VERIFICATION.md for boundaries.
- nginx now follows changed API addresses without proxy restart. Actual 502 on API
  recreate was diagnosed and fixed; isolated regression forces an IP change.
- Explicit isolated migration upgrade/drift-check/downgrade/re-upgrade/drift-check
  passes. ORM donor-import/publication-plan indexes now match existing migrations;
  a drift regression and CI check were added without resetting database state.
- Current protected-entity policy is rechecked as well as stored PASS/allow flags
  across rewrite, dispatch, planning, draft approval, activation, media selection
  and publication. Forged/inconsistent PASS cannot bypass hostile-entity blocking.
- PostgreSQL migration drift check in the operational container passed too.
- GitHub Actions 37680562785 passed all three jobs for Docker/planner foundation
  commit 4b093c5 (backend, frontend and synthetic Docker persistence).

- Windows Docker Desktop now runs: actual dev/production builds, packaged
  migrations on PostgreSQL, health/proxy/inbox reads, rebuild/recreate, down/up,
  Redis/worker restart and PostgreSQL SIGKILL recovery passed in an isolated
  synthetic stack. Encrypted synthetic session, configuration, media bytes/hash,
  pending rewrite job and outbox survived; Redis loss did not lose durable state.
  This is storage recovery, not real Telegram login or unfinished-job execution.
  See DOCKER_VERIFICATION.md for commands, safety scope and remaining limitations.
- Timer-driven automatic planning now runs without UI clicks, using per-channel
  timezone, future slots, durable quota serialization and current EditorialGate.
  Restart/idempotency, stale reject, invalid timezone isolation and naive timestamp
  regressions pass. The worker has no rewrite/publication transport yet.
- Foundation local quality gate: 139 backend tests, 24 frontend tests and 19 Chromium
  E2E passed; backend lint/compile, frontend format/typecheck/build and npm audit
  (zero vulnerabilities) passed. Production nginx and Windows reload configuration
  are implemented; stable externally mounted keys are not generated at startup.
- Operational local stack `newsflow` was explicitly initialized without replacing
  any existing state and started in production profile. UI: http://127.0.0.1:8080;
  actual PostgreSQL inbox is empty (no DEMO seed), health is ok. Repeated secret
  initialization preserves bytes; key/environment are ignored by Git. Isolated
  test stacks are stopped with their volumes retained.

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
- Source-photo reuse and licensed local-library lookup now have durable immutable
  metadata, bounded read-only file validation, SHA-256 integrity checks, rights/
  attribution constraints and guarded HTTP selection. They never substitute a
  different source revision, download remotely, call AI or send Telegram messages.
  Media migration preserves existing state and refuses populated downgrade.
  Backend regression: 132 passed; lint and two migrated actual-API browser
  regressions passed. See MEDIA_SELECTION.md for precise boundaries.
- Compose dev/production configuration parsed successfully with sample env and
  `--no-env-resolution --quiet`; shared persistent media volume is declared.
  This is config-only evidence, not a daemon or volume-persistence check.
- GitHub Actions run 37678283573 passed both jobs for Planner/review commit bf4396c.
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

- Compose runtime/persistence acceptance: synthetic storage and injected runner
  recovery verified; real Telegram authorization/live provider execution pending.
- Live dashboard workflows remain partial: Inbox reads, AI-provider Settings
  and review/plan configuration in Planner use actual API state. Donors, Channels,
  Connections and Accounts still need live frontend wiring; their operational
  configuration APIs already exist.

## NOT IMPLEMENTED

- Live authorized Telethon ingestion/publication acceptance, publication transport,
  live-model semantic qualification and visual-semantic image relevance remain
  pending. Read-only ingestion and guarded media acquisition runtimes exist but
  are disabled operationally; they are not live acceptance evidence.
  Semantic verification runtime and guarded auto-approval are implemented but
  disabled/unqualified operationally (provider contracts/plan selection exist).
  PostgreSQL-backed inbox read is now verified on Docker Desktop; live ingestion
  and transport execution remain pending.

## KNOWN ISSUES

- Live OpenAI smoke is blocked by current credentials: authorized local `апи.txt`
  exists but no supported key candidate was found in UTF-8/UTF-16 encodings.
  No provider call or credential persistence occurred. Continue offline independent
  tasks; live verification needs a usable credential via Settings/local secret.

- Docker Desktop stale runtime socket failure was recovered using stopped-service
  directory quarantine; see DOCKER_VERIFICATION.md. Synthetic Compose acceptance
  now passes. Fresh operational `.env`/stable master key were explicitly provisioned
  once, separately from synthetic fixtures; a second initialization retained them.
  Telegram authorization/provider credentials are not provisioned. Synthetic
  fixture credentials must not be reused for operational data.
- Port 8010 was occupied by an external local process during startup validation;
  the application started successfully on port 8123.
- Obsidian vault location is unavailable; `/docs` is the source of truth.
- DEMO changes exist only in window memory; reload restores fixtures. No
  real account connection, publication or AI generation. The separate Docker worker
  executes actual durable plan selection, not the DEMO calendar.
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

Read-only status + explicit Alembic target guard committed/pushed as
e14bdf47dbe383b17ad18ab22d6ba93d20ae7cad to correct origin.
Text transport/factory committed/pushed f9a4075f7f860ce351f98e74a2273e0946b59f94.
Photo checkpoint committed/pushed de51ad6f9ea983214ea432797d504c9cc685cdf2.
Tick checkpoint committed/pushed 69fa0f1cc808155cb991b012d497bb41863aec7d.
Main-loop opt-in (default 0) and honest read-only UI wording implemented, full
720 backend + 56 frontend units / 23 browser / explicit migration gate PASS.
Main-loop checkpoint committed/pushed 6aaaefabc5df9636ee794e2edab630311798f5c8.
Encrypted snapshot checkpoint committed/pushed eda7574c64910cb59471f91d27d3f12db7ad1977.
Direct-response observation/no-resend recovery implemented and gate verified
(750 backend, 58 frontend, final browser 24 PASS in 17486).
Observation checkpoint committed/pushed 33757e6c873d108b6db1fcdce2eb28f1732a3c2a.
Probe checkpoint committed/pushed 6266b5a0689409bc7af89b7e3dadec5ab7f2f206;
its CI 37713732217 completed SUCCESS in all four jobs (Linux Docker included).
Read-only difference contract committed/pushed 2d744c20bf5adcb2a5e770db505fb7e95459e3e7;
its CI 37714319250 backend/frontend PASS, Docker variants in progress at inspection.
Deletion checkpoint committed/pushed 0efb0b6ce311c1be452a31b124f3f93633c5b9b9;
CI 37714969203 completed SUCCESS (actual subsequent gh inspection).
Cursor checkpoint committed/pushed add59c6f7b860df6da86669e2d968ce77c04af5f;
CI 37715433401 completed SUCCESS (actual subsequent gh inspection).
Retained deletion truth implemented in real read-only moderation inbox/API/UI,
with full 833 backend / 62 frontend units / final 25 browser PASS; committed/pushed
b6b4d98f6b6d59fcb091d9c3cf1aaa832fb2a0bc, CI 37715889965 all-four SUCCESS.
Trusted read-only checkpoint/create-only baseline now verified OFFLINE with
53 targeted / full 886 backend tests plus explicit D: round-trip/drift PASS.
Baseline committed/pushed 9c4dcf12c07e289298f3c3c0aae1c4d1232cd23a;
CI 37742573673 backend/frontend SUCCESS, both Docker jobs in progress at inspection.
Shared unresolved-gap/foreign-baseline freshness now verified OFFLINE with full
906 backend / 65 frontend units / 26 browser gate PASS. Checkpoint this increment,
gap checkpoint committed/pushed 697fdd11572ce26f4dc1626ff0e5fd677f5aa6c0;
CI 37744183380 backend/frontend SUCCESS, Docker jobs still in progress at inspection.
Baseline CI 37742573673 subsequently completed SUCCESS (actual gh list).
Durable bounded retained-revision replay now verified OFFLINE with full backend
918 PASS plus exact CI lint/format/compile/isolated D: drift; committed/pushed
7215570b932e9000d485be5beb249930e0c1ad87, CI 37745127358 in progress at inspection.
Gap checkpoint CI 37744183380 subsequently completed SUCCESS (actual gh list).
Bounded default-disabled new-only bootstrap → difference → history → exact replay
worker facade now verified OFFLINE: 17 targeted / full 935 backend plus isolated
lint/format/compile/drift PASS. Checkpoint it, then implement durable opt-in sync
enforcement/legacy quarantine BEFORE connecting main loop. Missing/foreign/error/
incomplete baselines under enforcement must fence all API/worker/publication paths
through shared persisted state, including donors outside the current bounded scan.
Turning a runtime flag off must not erase persisted quarantine or manufacture
legacy continuity. No automatic legacy baseline reset/resync or real sends.
Then main-loop/config wiring with all operational flags remaining 0; verify
disabled/no-DB, restart, stale/API/worker zero-provider and ordering adversarial tests.
before downstream planning/rewrite. Never activate operational flags as a test.
Never initialize/reset legacy cursor from latest-message IDs or TooLong, never
advance pts until all observations/mappings persist. No public cursor-reset or
provider-send endpoint, no operational worker/flag activation.
Full durable gap/deletion application and live verification are pending. Windows Docker stays
blocked; no deletion/prune/volume reset or live provider-send workaround.
Do not guess message identity by text/time. Use D: for
temporary data. Difference reconciliation follows; no live sends
as tests. Do not retry Docker deployment until host space and writable storage
are confirmed; do not delete/prune volumes or user data.
Architecture is approved; do not repeat completed media/publication setup.

2026-10-08 recovery update: Docker version reports Desktop unable to start;
8080 health timed out. New browser rerun failed 2 tests at context close with
ENOSPC (21 passed), not application assertions; rerun outputs moved to D:.
Plain Alembic validation mistakenly targeted backend/newsflow.db despite an
environment URL; downgrade/re-upgrade executed there. Read-only post-inspection
found all business tables empty, but no pre-snapshot proves previous contents.
Docker PostgreSQL was not touched by that command. See ALEMBIC_TARGET_GUARD.md.
Two CLI regression failures reproduced/fixed; 7 targeted migration tests PASS.
Explicit-target guard and dedicated CI URL implemented. Fresh full gate 649 tests
PASS (34879), lint/targeted format PASS; explicit D: migration upgrade/check/
downgrade/base/re-upgrade/check PASS. Frontend 55/format/typecheck/build PASS;
browser all 23 PASS after moving temporary/output files to D: (68626).
Guarded text sender initial 19/factory 4 test-first RED cases now GREEN; 35 final
targeted / 684 full backend PASS. No live send flag, HTTP endpoint or worker added.

Last committed HEAD before this difference increment: 6266b5a0689409bc7af89b7e3dadec5ab7f2f206,
codex/dark-navy-ui, correct origin borovojarkadij-png/content-studio.
CI 37710524239 for e14bdf4 completed SUCCESS in all four jobs (gh inspection).
CI 37710873887 for f9a4075: completed SUCCESS in all four jobs (actual gh run list).
Actual current Windows packaging remains independently blocked.
CI 37711279784 for de51ad6, 37711738606 for 69fa0f1 and 37712004387 for 6aaaefa:
completed SUCCESS in all four jobs (actual gh run list/view). This does not
resolve current Windows Docker environment failure.
CI 37712575263 for eda7574: completed SUCCESS in all four jobs (actual gh view).
CI 37713401088 for 33757e6: backend/frontend SUCCESS, both Docker jobs in progress
at last inspection; this predates the extended version-2 publication probe.
CI 37708938271: completed SUCCESS in all four jobs (actual gh inspection).
Preceding aa075af CI 37707297625 and fdf8f06 CI 37706050198 all-four SUCCESS.

1. PublicationPreflight, PublicationJobModel, durable_publication_runner and
   migration a6d315c8fa04 implemented and verified. Full backend 642 PASS,
   exact CI lint/format/compile/isolated migration PASS; frontend 50 units /
   22 browser/format/typecheck/build/audit PASS. See PUBLICATION_INTENTS_VERIFICATION.md.
2. Windows Docker session 26571 completed PASS: scripts/verify-persistence.ps1
   -Project newsflow-verification-publication20261008 -ApiPort 18022 -WebPort 15195
   -ProductionPort 18102 -CrashRecovery -PublicationGuard. Follow-up quota probe
   RED on old image, then session 69524 corrected rebuild/quota/verify/PG drift /
   another down-up/quota/verify PASS. Stopped retaining history/volumes; never reseed.
3. Operational deployment 97908 PASS: rebuilt/migrated a6d315c8fa04, packaged
   PG drift/health/inbox200, five flags 0, stable secrets/business data unchanged.
4. Durable publication checkpoint committed/pushed to correct origin; track exact
   CI 37708938271. Never claim overall PASS before both Docker jobs finish.
5. Read-only job/receipt/quarantine API + real Planner component verified.
   Full backend 646 (session 83300), frontend 55 units/23 browser (26929),
   lint/format/typecheck/build/compile/audit PASS. Screenshots desktop1440/mobile390
   inspected; joined text and warning semantics fixed. Retained Docker HTTP status
   probe/restart/PG drift session 21927 PASS without reseeding, fixture stopped.
   Operational deployment 40773 FAILED containerd metadata read-only filesystem;
   C: subsequently full, report write initially failed. Latest operational image/
   health acceptance NOT VERIFIED / BLOCKED BY ENVIRONMENT. Pytest fixture archive
   retained on D:; do not claim successful move/reclaimed space. No data/secret deletion.
6. Then guarded authenticated
   transport, offline/fake tests and disabled-by-default worker/reconciliation.
   No real sends as test side effects. PublicationService is still only a domain
   prototype, not the durable/live transport.

## COMPLETED MEDIA CHECKPOINT (do not repeat)

1. Windows Docker session 75313 completed PASS:
   scripts/verify-persistence.ps1 -Project newsflow-verification-mediaui20261008
   -ApiPort 18021 -WebPort 15194 -ProductionPort 18101 -CrashRecovery
   -SourcePhotoGuard. Do not reseed this fixture. Updated source
   probe verifies real generic queue 202/idempotency, exact no-store preview,
   restart recovery and rejected queue/preview 409.
2. Packaged worker PostgreSQL drift PASS; mediaui20261008 stopped retaining
   all history/volumes. MEDIA_PLANNER_VERIFICATION.md updated. Do not repeat seed.
3. Operational deployment 99215 completed PASS: rebuilt production API/worker/
   frontend, packaged PG drift, health/proxied inbox 200; all five flags 0.
   Env/master key/sessions/data unchanged; do not repeat this deployment.
4. Verified changes committed/pushed to origin
   https://github.com/borovojarkadij-png/content-studio.git on codex/dark-navy-ui,
   aa075af9f15cb346cec184a1e109e26c74bdf658; CI 37707297625 all-four SUCCESS.
   Preceding fdf8f06 CI 37706050198 is all-four SUCCESS.
5. Continue strict fresh publication-execution preflight, durable idempotency /
   delivery acknowledgement and crash reconciliation, offline adversarial tests,
   disabled-by-default worker. Never send real posts as a testing side effect.
   Current PublicationService is only an in-memory domain prototype; it is not
   a durable publisher and may not be presented as one.

Fresh local media checkpoint: backend 587 tests/lint/compile/isolated migration
PASS; frontend 50 unit/22 browser/format/typecheck/build/audit PASS. Exact original
photo and illustration intents remain separate. Topic search is not semantic
event-photo verification. Media preview itself does not authorize publication.

All previously completed Docker fixtures retain histories/volumes; do not reseed
or use down -v, prune, reset or rotate any secret. Combined source/mapping
sourcecombo20261008 also completed PASS and packaged drift PASS; stopped.
Older f4124e8 CI 37704439283 failed an isolated synthetic identity collision,
fixed by fdf8f06; do not relabel that older run as successful.

Consolidated external/live-verification limitations:
- C: disk-full / Docker containerd read-only filesystem prevents operational image
  acceptance. Use D: for new isolated test temp files. Recover storage without
  deleting operational volumes/databases/keys, then recheck daemon/health before
  retrying latest read-only status deployment. Existing synthetic PASS remains
  historical evidence, not proof that Docker currently works.
- Current authorized Downloads/апи.txt contains no usable supported-format key;
  live OpenAI test remains pending. Never echo/store credentials in Git.
- Telegram api_id/api_hash and live encrypted authorization require user setup;
  no synthetic account/session may be promoted as genuine authorization.
- User donors @stranaua / @milinfolive are recorded in USER_CHANNELS.md, not fake
  operational configuration. No authorized source download is claimed.
- No real semantic model release is qualified; synthetic fixtures never qualify
  unattended approval. Library illustrations still need relevance review.
- Obsidian vault unavailable: pending integration, /docs remains source of truth.

Full album manifests/deletion/difference/batching/video, semantic dedup/events/
hype, rate/cost/cache dashboard and final unattended publication remain pending
per IMPLEMENTATION_PLAN.md. Continue independent tasks without asking routine
questions. PHASE 1 IS NOT COMPLETE; full live authorization/provider acceptance
is NOT VERIFIED, separate from verified synthetic Windows Docker recovery.
