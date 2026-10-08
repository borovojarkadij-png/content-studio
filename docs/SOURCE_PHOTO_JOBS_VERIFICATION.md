# Durable exact-source photo jobs and explicit rights

## Implemented boundary

`MediaAcquisitionJob` now has a mode and immutable rights snapshot. Legacy jobs
remain LICENSED_LIBRARY with no invented source permission. Source and internet
runners cannot claim each other's work. Source jobs commit their two-attempt
budget before RPC, fence leases before/after RPC and decoding, and commit asset
registration plus terminal completion atomically. Expired owners make no RPC and
cannot register late results. A timeout has bounded persisted retry; FloodWait
preserves the longest current-account cooldown and never poisons a replaced or
invalid session. No transaction/row lock spans provider RPC.

Mapping rights default to UNDECLARED. Explicit OWNED or PERMISSION (with credit)
is required. A versioned revocation/renewal invalidates queued jobs even if the
same declaration is later restored. Current canonical donor/account/output must
match the route. Original media selection and read-only job status recheck current
rights, source, editorial, draft approval, technical constraints and file bytes.
Changed attribution cannot select an asset registered with old provenance.

Actual endpoints:

- `GET/PUT /api/telegram/mappings/{id}/source-media-rights` stores declarations,
  not proof of legal ownership and not Telegram permission/authentication.
- `POST /api/telegram/publication-candidates/{id}/source-photo-acquisition`
  queues configured work only; HTTP 202 does not mean downloaded or published.
  It reports that exact job, not another mode's later history.
- Existing `GET .../{id}/media-acquisition` reports persisted progress and
  guarded selected eligibility; historical SUCCEEDED is retained after revocation.

The real Connections UI edits rights separately from route/filter settings,
preserves failed/manual drafts, supports explicit revocation and reload, and does
not imitate authentication, download, rewrite or send. The source worker requires
explicit `NEWSFLOW_SOURCE_PHOTO_ENABLED=1`, stable cipher and existing Telegram
credentials/session. It is **0 by default and remains disabled operationally**.

## Verification, 2026-10-08

- Backend: **581 tests PASS**, exact CI-directory lint PASS, isolated migration
  upgrade/check/downgrade/re-upgrade/check PASS. Targeted adversarial tests cover
  lease expiration during RPC/registration, rights tampering/revocation, stale
  editorial, retry exhaustion, FloodWait restart, mode isolation and actual API.
- SQLite regression reproduced lost unnamed legacy CHECK constraints during
  table recreation. The migration explicitly preserves them; invalid attempts,
  states, short digests, running-without-lease and success-without-asset all fail.
  Downgrade refuses any populated source-rights/source-job history.
- A worker regression caught a frozen tick-time clock accepting an expired lease;
  runtime now uses live time. The separate synthetic success test controls its
  clock rather than depending on execution being within one minute of midnight.
- Frontend: **42 unit / 21 browser tests PASS**, format/typecheck/build PASS,
  production audit zero. Actual isolated migrated API exercises rights save,
  reload and revocation. Desktop/mobile accessibility and screenshots PASS;
  `.artifacts/ui-dark-navy/live-config-connections-{1440,390}.png` visually inspected.
- Actual Windows Docker `newsflow-verification-sourcejobs20261008`, ports
  18019/15192/18099: CrashRecovery + SourcePhotoGuard PASS. A committed source
  claim survives down/up, new owner recovers attempt 2, old owner makes zero RPC,
  exact bytes/rights/selected result survive worker restart; revoked editorial
  makes zero acquisition requests and actual selection API returns 409.
  Separate PostgreSQL writer acquires account/candidate/editorial/job/rights locks
  during injected RPC. Packaged PostgreSQL drift PASS; fixture stopped preserving
  all volumes/history. No real sessions, external AI calls or sends.
- Operational API/worker/frontend rebuilt and migrated: packaged PostgreSQL
  drift PASS, health and inbox through 8080 HTTP 200, **all five network flags 0**.
  No operational synthetic records, session/key replacement or volume deletion.
- Earlier source-provider checkpoint `f4124e8dd1474fc188e28f20688b2e573a6c72cf`
  CI 37704439283: backend/frontend SUCCESS, both Docker jobs FAILURE. Combined
  probes reused synthetic Telegram User ID 600600. A real configuration-service
  regression reproduced the conflict. Source probe now has distinct 600601 and
  refuses reseeding; independent histories are not overwritten. Fresh combined
  Windows Docker `newsflow-verification-sourcecombo20261008` (18020/15193/18100),
  CrashRecovery + MappingGuard + SourcePhotoGuard PASS: filters/source identities
  coexist, durable claim recovery/old-owner zero RPC/exact assets/current API and
  revoked editorial guard PASS. This checkpoint's GitHub CI remains separate.

## Remaining work

Candidate media-progress/queue UI, full internet-image semantic/visual relevance,
caption attribution and guarded durable publication execution are still pending.
Album manifests/deletions/video are not unlocked by single-photo support.
Live Telegram download/authentication is NOT VERIFIED; credentials/session require
manual provisioning. No operational semantic model has been qualified. PHASE 1
is not complete. Obsidian remains pending; `/docs` is the source of truth.
