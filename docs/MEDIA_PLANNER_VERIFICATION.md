# Guarded media queue and Planner progress

## Scope

Real Planner slots now use their stable `candidate_id` to read persistent media
jobs, explicitly queue preparation and refresh current eligibility. Source-photo
reuse and open-library illustration are separate configured intents, not a
fallback that invents copyright permission. No Telegram send is implemented or
enabled by this increment.

- Generic POST `publication-candidates/{id}/media-acquisition` returns HTTP 202
  with the exact persisted job. Current candidate policy chooses the runner;
  another mode's historical job never changes that choice.
- Duplicate requests return the same binding/job, without resetting attempts.
  Terminal history cannot be used to obtain an unbounded retry budget.
- GET status distinguishes current `media_policy`, historical `acquisition_mode`,
  `queue_allowed` and `selected_allowed`. Queue eligibility requires fresh local
  source/editorial/review/technical and, for source photos, account/rights checks.
- GET `media-preview` returns only validated bounded persistent PNG/JPEG bytes.
  It checks current selection before/after reading, containment and registry hash;
  uses `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.
- Browser preview independently checks MIME and SHA-256 with a bounded 16 MiB
  stream. Object URLs are released on refresh, candidate switch and unmount.
  Failed writes/previews clear stale eligibility and never claim success.
- Library topic matches are labelled illustrations requiring manual relevance
  review. No claim that a photo depicts the actual reported event is made.
- Network workers remain separately opt-in; QUEUED does not mean downloaded,
  authorized or published. DEMO data are not mixed into the live Planner.

## Regressions reproduced and corrected

1. Missing generic queue/preview endpoints originally returned HTTP 405/404.
2. Status omitted current queue eligibility and selected policy from history.
3. A root disappearing between status and byte read raised unhandled HTTP 500;
   now fails closed as HTTP 409.
4. Frontend lacked guarded preview, exact MIME/hash checking and queue controls.
5. New isolated photo fixture initially used the ID exercised by channel-create
   E2E; full browser suite reproduced real HTTP 409. Fixture identity is now
   distinct; the original create-channel assertion remains unchanged.

## Verification

- Backend: 587 tests PASS; exact CI-context Ruff PASS; touched format PASS;
  compile PASS; isolated migration upgrade/check/downgrade/base/re-upgrade/check
  PASS. No schema change was needed for the queue/preview increment.
- Frontend: 50 unit tests PASS; 22 Chromium browser tests PASS; format,
  TypeScript/build PASS; production dependency audit zero vulnerabilities.
- Real isolated migrated FastAPI browser tests verify queued job persistence
  after page reload and a real 64-pixel decoded fixture preview that disappears
  on refresh. No network media provider, AI call or Telegram send was used.
- Screenshots inspected at desktop and 390-pixel widths:
  `.artifacts/ui-dark-navy/live-media-preview-1440.png`,
  `.artifacts/ui-dark-navy/live-media-preview-390.png`,
  `.artifacts/ui-dark-navy/live-planner-1440x900.png`,
  `.artifacts/ui-dark-navy/live-planner-390x844.png`.
- Actual Windows Docker `newsflow-verification-mediaui20261008`
  (API 18021, dev 15194, production 18101): CrashRecovery/SourcePhotoGuard PASS.
  Real generic queue 202/idempotency, exact preview bytes/no-store after down/up,
  lease recovery, rejected queue/preview 409 and zero external calls/sends PASS.
  Packaged PostgreSQL drift PASS; fixture stopped retaining all history/volumes.
- Operational production API/worker/frontend rebuilt; migrations/packaged PG
  drift/health/proxied inbox PASS. All five network enablement flags remain 0;
  no env, master key, session, provider setting or business data was changed.
- Previous source-jobs checkpoint fdf8f06667bec6b42c4c59a4f3cdf41a559f9234:
  GitHub Actions 37706050198 completed SUCCESS in all four jobs. This does not
  qualify the current uncommitted media UI or any real provider/model.

## Limits

No live Telegram authorization/source download is verified. No unattended
publication worker, media relevance approval, full album/video handling or
semantic image matching is claimed. Source permissions are explicit operator
declarations, not independent proof of ownership. API owner authentication and
safe key reveal require their own increment. Obsidian sync remains pending;
`/docs` is the source of truth. PHASE 1 remains incomplete.
