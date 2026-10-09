# Task 2 — fresh library review publication consumer

Review base: `f2f2092db85fda1fe369fc8b5485a91471f1d32d` (Task 1 production
source at `96974fd`; intervening parent commit contains documentation only).
Branch: `codex/dark-navy-ui`. No push, merge, operational migration, credentials,
reviewer activation, real provider call or Telegram send.

## Implementation

- New `illustration_publication.py` reads newest candidate REVIEW only; newer
  rejection/uncertainty or revocation prevents old approval fallback. It resolves
  current canonical binding twice, including bounded decoded image bytes, and
  assesses strict `HumanIllustrationReview` using the existing domain contract.
- PublicationPreflight preserves all independent existing gates. Exact approval
  clears the narrow library hold, binds review ID and immutable eleven-field
  binding, visibly appends `Иллюстрация.` and retains complete license credit.
  Final actual photo media type and complete UTF-16 caption pass filters/limits.
  Library digest includes review ID/binding/full caption/photo type. Original
  source tuple digest algorithm remains exactly unchanged (no None fields added).
- PublicationEnvelope explicitly adds optional review ID/binding. Encrypted
  snapshot schema is version 2 with exact required fields. Version 1 retains its
  original exact schema and maps only absent review fields to None. Nested strict
  binding, duplicate/unknown/bool/missing/inconsistent fields are refused. Historical
  reading never becomes authorization, and the existing durable runner rechecks
  current envelope/digest/snapshot after upload immediately before send.
- ConfiguredTelegramPhotoPublisher rechecks current exact review before returning
  photo bytes and again after reading, verifies canonical complete labeled caption,
  and retains bounded actual decoded-byte/hash/rights validation. No DB transaction
  crosses upload or another network boundary; the existing runner closes sessions.
- MediaJobReader reports `HUMAN_ILLUSTRATION_REVIEW_REQUIRED`; exact current approval
  clears only that narrow diagnostic. Existing strict frontend DTO accepts the new
  diagnostic and consistent null/selected state. Planner explanatory text distinguishes
  current review from readiness and event-photo truth, with no new approval/send UI.
- New migrated library regression module joins the existing strict PostgreSQL CI
  list through `mapping_store` and the create-only namespace harness. No new schema,
  harness target, resource deletion or operational fixture was introduced.

## TDD and concrete commands

Backend commands run from `backend`, with:

```powershell
$env:TEMP='D:/Codex-Recovery/content-studio-20261008'
$env:TMP=$env:TEMP
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/task2-pycache'
$env:PYTHONPATH='D:/Codex-Recovery/content-studio-20261008/telethon-145'
python -m pytest tests/test_illustration_publication.py -q
```

Initial actual behavioral RED: **9 failed, 4 passed / 8.70s**. The approved durable
publication and mutation-during-upload cases failed on the existing unconditional
`ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED` hold; the diagnostic case exposed
the old code. All initial safety cases without approval already refused sends.
After implementation, **12 passed/1 fixture failure**: the test's UNDECLARED media
license violated the existing SQL constraint during upload. The synthetic mutation
was corrected to a SQL-valid OWNED license on the library asset, which exercises
the intended rights gate without an unrelated database failure.

Focused GREEN: the five affected families (`test_illustration_publication.py`,
`test_publication_preflight.py`, `test_publication_request_snapshot.py`,
`test_configured_photo_publication.py`, `test_media_job_read.py`) passed **64 /31.12s**.
Expanded library and snapshot GREEN later passed **50 /45.82s**. An intermediate
retry test incorrectly waited two seconds, before the existing runner's minimum
30-second retry; it was corrected to 31 seconds and verified in the final full run.

Additional actual caption-reader RED:

```powershell
python -m pytest tests/test_illustration_publication.py -k removed_label -q --tb=short
```

**1 failed/32 deselected/2.08s**, `DID NOT RAISE PublicationBlocked`. This exposed
missing exact caption checking in the configured reader; the canonical caption
guard then passed with the library/snapshot GREEN. An earlier test attempt used a
receipt fake requiring a durable SENDING job for a direct reader test; it was
corrected to exercise the actual bound-byte reader boundary before accepting RED.

Frontend actual RED from `npm test -- src/mediaApi.test.ts src/MediaPreparation.test.tsx`:
**3 failed/11 passed** (new code/null diagnostic rejected and new review warning
absent). After DTO/text implementation **14 passed**. Additional null/unselected
consistency RED: **1 failed/8 passed**, promise resolved instead of rejected; the
strict consistency guard then passed in the final frontend suite.

## Final verification

- Source frozen before final full backend run: **1746 passed, 1 PostgreSQL-only
  skipped /302.04s**, exit **0**. Command: `python -m pytest -q --tb=short`, session
  89031. No backend source/test edits after that full run began; documentation followed.
- `python -m ruff check src tests`: **All checks passed**.
- `python -m ruff format --check` on all nine changed/new backend files: **9 already
  formatted**. A broad format-check diagnostic also identified pre-existing untouched
  formatting in unrelated files; no broad reformat was performed.
- `python -m compileall -q backend/src`, using task-specific pycache: exit **0**.
- `npm test`: **208 passed /17 files /2.94s**.
- `npm run format:check`: **all matched files use Prettier**.
- `npm run build`: **tsc --noEmit and Vite PASS**, CSS hash remains
  `index-Clz7HfYA.css`; updated JS is `index-DqXgln3u.js`.
- `npx playwright test --grep 'guarded real media preview'`: **1 passed /5.8s**,
  real synthetic API/fixture bytes, desktop/mobile screenshots and unchanged
  composition. Existing 100 artifacts preserved create-only before the browser
  run at `D:/Codex-Recovery/content-studio-20261008/task2-browser-before-20261009-1249`.
  Current captures are under `.artifacts/ui-dark-navy/test-results/
  studio-guarded-real-media--1e3e2--and-releases-it-on-refresh/` named
  `library-publication-hold-1440.png` and `library-publication-hold-390.png`.
  Desktop capture visually inspected: established dark Planner composition and
  truthful warning remain; no pixel-identical claim.
- `git diff --check`: exit **0** (ordinary repository LF-to-CRLF notices only).

## Coverage and self-review

Approved configured transport sends exactly once through the real durable runner,
stores/reopens encrypted review evidence, and delivers complete label/credit.
No/rejected/uncertain/revoked/stale/foreign-channel evidence produces zero uploads
and sends. During-upload revocation/editorial reject/rights/credit/file/newest
reject/uncertain produces zero send RPCs. Permissions-time revocation refuses
bytes before upload (committed SENDING intent conservatively quarantined).
Different fresh approval cannot rebind the old queue. Known non-delivery retry
refuses later revocation, and unknown receipt/abandoned SENDING restarts never
reupload/resend. Corrupt nested review snapshots are blocked before transport.
Actual photo type, label filter and full caption limits remain hard gates.
Original exact version-1 queued source text/photo snapshots decode and execute
after restart; their original digest tuple is preserved. Existing original-source
unknown-outcome tests remain in the full suite.

Self-review checked newest-REVIEW ordering/no fallback, revocation lookup, exact
domain types, independent canonical gates, binding/credit/file races, absence of
locks across network, optional frozen nested envelope fields, strict v1/v2 schema
and source digest compatibility. Snapshot reading cannot promote stale evidence:
every runner preparation and final guard obtains current canonical evidence.

## Remaining boundaries

Parent owns independent review and actual Windows PostgreSQL/packaged acceptance;
those are not claimed by this report. Live acceptance remains pending separately
provisioned reviewer/Telegram credentials and designated test destinations. No
real keys were generated or activated. Protected reviewer UI and a new owned
library-review/snapshot Docker restart probe are the next bounded work, as directed
by the parent. Task 2 added no unprotected writer forms or redesign.

## Scoped files

`backend/src/newsflow/services/{illustration_publication,publication_preflight,
publication_request_snapshot,telegram_publication_factory,media_job_read}.py`;
`backend/tests/{test_illustration_publication,test_publication_request_snapshot,
test_configured_photo_publication,test_media_job_read}.py`;
`frontend/src/{mediaApi.ts,mediaApi.test.ts,MediaPreparation.tsx,
MediaPreparation.test.tsx}`; `frontend/e2e/studio.spec.ts`; `.github/workflows/ci.yml`;
`docs/{CURRENT_STATE,IMPLEMENTATION_PLAN,ILLUSTRATION_REVIEW_AUTH,
ILLUSTRATION_PUBLICATION_CONSUMER,ILLUSTRATION_REVIEW_VERIFICATION_20261009}.md`;
this task report. Parent-owned recovery/implementation-plan files were not changed.
