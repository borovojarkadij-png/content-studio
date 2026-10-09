# Task 3 implementation report — 2026-10-09

Status: DONE. Implementation source commit: `59cfbab31d96ef9f1d3cee359b637b728348ffc4`
(`feat: add protected canonical illustration review workflow`). Baseline:
`cb0516d1584273d62ab2ddb9fd605a68891fae8c`, branch `codex/dark-navy-ui`.
No push, branch switch, schema change, operational credential generation,
worker/provider activation or real publication/send occurred.

## Implemented

Dedicated `IllustrationPresentation` service and three reviewer-authenticated
no-store reads under `/api/illustration-review/candidates/{id}`:

- `/presentation`: current canonical source text, current approved per-output
  draft, exact eleven-field binding, output channel identity/title, current
  license/credit/MIME and latest immutable review including revocation status.
  Reuses every accepted resolver gate and repeated decoded-file/SQL validation,
  bounds source/draft UTF-8 to 262144 bytes each, and checks exact text digests.
- `/photo`: requires an explicit matching strong `If-Match`; missing, wildcard,
  weak and stale validators fail closed. The ETag hashes the entire bounded
  presentation including latest review status, so review/revocation as well as
  source/draft/rights/channel changes invalidate an older displayed context.
  Exact bounded response bytes are decoded/hashed by the existing local-photo
  guard; the full canonical context is checked before and after that read.
  Returns matching ETag, no-store, safe photo MIME and nosniff, no remote image
  URL or public storage key. No network/provider work occurs inside the service.
- `/latest-review`: authenticated bounded latest immutable REVIEW plus revoked
  status, independently of current source/draft/media eligibility. It continues
  working after editorial rejection or absent media-root configuration, enabling
  the existing immutable revocation workflow without presenting a stale draft.

The shared media helper now has `_photo_content` returning the exact bytes already
validated by the accepted PNG/JPEG single-frame/size/decode/containment guard;
`_read_photo` retains its original digest/MIME return contract. Accepted writer
and consumer gates are preserved; existing review and revocation routes perform
all writes, with no new identity/auth system.

Dedicated strict client validates exact response keys/types, candidate and channel
ownership, all binding fields, UTF-8 source/draft SHA-256, bounded streamed photo
MIME/signature/SHA-256 and matching ETag. It refuses malformed/foreign/coerced
responses and verifies successful write responses against the exact payload.
Bearer is only in Authorization; requests omit cookies, refuse redirects, omit
referrer and use no-store. Server bodies/transport exception text are never shown
as errors, so a server or transport echo cannot put the token in error UI.

The dedicated panel is narrowly integrated into existing MediaPreparation for
library candidates, with existing palette/navigation/CSS untouched. Its token is
masked, autocomplete off, bounded to the server contract and held only in panel
memory. Disconnect/candidate change/unmount clear context/object URL/token and
abort requests; token edits clear context and abort/discard prior responses.
Approval requires the actual loaded protected photo, an explicit illustration-
not-event-photo acknowledgment and a nonblank bounded note. Reject/uncertain do
not grant illustration permission. Latest historical review can be read and
revoked after current presentation fails. The panel has no publication action
and is never mounted in DEMO.

One safe random UUID operation key is generated per action. A write with an
ambiguous outcome retains the exact original payload for explicit same-operation
retry; there is no automatic retry or saved-success claim. New actions are blocked
until resolved/disconnected. Synchronous request ownership blocks duplicate clicks
and concurrent actions; generation/abort checks discard old candidate/token and
post-save refresh responses. A known 409 clears context and requires reload.
Confirmed writes refresh authenticated latest review and existing media status;
the UI distinguishes a confirmed write from a failed subsequent refresh and
explains that abort cannot undo a possible server commit.

## TDD and focused evidence

All Python commands below ran from `backend` with:
`TEMP=TMP=D:/Codex-Recovery/content-studio-20261008`,
`PYTHONPATH=D:/Codex-Recovery/content-studio-20261008/telethon-145`,
task-specific `PYTHONPYCACHEPREFIX=.../task3-pycache` and local
`NEWSFLOW_UNATTENDED_POSTGRES_URL` unset. Frontend commands ran from `frontend`.
Runtime: Python3.12.10, Node24.19.0, Ruff0.16.6.

- RED `python -m pytest tests/test_illustration_presentation.py -q`: 42 FAIL
  /20.12s, expected HTTP404 rather than protected presentation/photo/latest routes,
  including missing/wrong auth, absent/stale validator and current-gate mutations.
- GREEN same command with `--tb=short`: 42 PASS/23.64s. Added during-read
  source/credit/file replacement and media-root-independent latest regressions:
  46 PASS/26.43s.
- Additional RED `python -m pytest tests/test_illustration_presentation.py
  -k 'stale_display_validator and review' -q --tb=short`: 1 FAIL/1.53s, old
  validator incorrectly returned HTTP200 after a new review. ETag was amended
  to cover the entire representation; final presentation suite 47 PASS/26.74s.
- Combined targeted `python -m pytest tests/test_illustration_presentation.py
  tests/test_illustration_review_api.py tests/test_illustration_binding.py
  tests/test_illustration_publication.py -q --tb=short`: 208 PASS/126.20s before
  the extra review-status ETag regression; final local full gate includes all209.
- Client RED `npm test -- src/illustrationReviewApi.test.ts`: initial missing
  module diagnosis followed by exported scaffold (3 FAIL/15 PASS); a permissive
  raw-fetch baseline then produced 18 behavioral FAIL/41ms, notably malformed
  JSON/foreign bindings/weak validators/changed or oversized photo responses
  being accepted. Strict implementation GREEN 18 PASS. Three array-as-enum
  regression cases were then RED (3 FAIL/18 PASS), fixed with exact string enum
  checks; final client21 PASS.
- Panel RED `npm test -- src/IllustrationReviewPanel.test.tsx`: 10 FAIL/74ms,
  absent protected controls/acknowledgment/actions. GREEN with the real strict
  client and fetch boundary fixtures: panel10 PASS; final panel13 includes late
  read, stale-write conflict and post-save candidate switch.
- Integration RED `npm test -- src/MediaPreparation.test.tsx`: 1 FAIL/6 PASS,
  library surface did not provide token panel. GREEN after narrow integration.
  Added real MediaPreparation post-write status ownership regression: delayed
  old-candidate refresh is aborted and cannot replace the new source-media
  candidate or restore old saved/token/photo UI.
- Final focused `npm test -- src/MediaPreparation.test.tsx
  src/IllustrationReviewPanel.test.tsx src/illustrationReviewApi.test.ts`:
  42 PASS/1.24s. Tests assert real UI state and actual fetch payloads, not just
  mock presence; fakes replace only HTTP transport and object-URL surfaces.

## Frozen final checks

Backend/frontend implementation was frozen before the long gates and parent PG
run. Subsequent changes were CI wiring, requested screenshot capture statements,
documentation/evidence only; no implementation or shared backend test mutation.
The final code tested is retained in immutable source commit `59cfbab`.

- `python -m pytest -q --tb=short`: 1793 PASS, 1 PostgreSQL-only SKIP,
  361.83s. No test disabled or removed. Parent independently executed the strict
  migrated Windows Docker PostgreSQL gate against frozen source: presentation47,
  reviewAPI81, publication34 and binding47, exactly209 PASS/334.61s/no SKIP/exit0.
  Parent validated the read-only fixture URL and used create-only UUID schemas
  without real providers. This is parent evidence, separate from the local suite.
- `python -m ruff check src tests ../scripts/ui_illustration_fixture_api.py`:
  PASS. Modified Python files' `ruff format --check`: all5 PASS.
  `python -m compileall -q src ../scripts/ui_illustration_fixture_api.py`: PASS.
- An additional repository-wide `ruff format --check src tests` found nine
  pre-existing untouched format differences (ingestion/telegram/model_catalog
  and six older tests). None belongs to this change; their bytes were preserved.
  CI's required full Ruff lint check passes; no full-format success is claimed.
- `npm test`: 19 files, 243 tests PASS/2.95s.
- `npm run format:check`: PASS. `npm run build`: tsc/no-emit and Vite PASS.
- `npx playwright test`: entire existing33 PASS/1.1m, including real Planner,
  existing media guard, all eight desktop/mobile sections and WCAG.
- `npx playwright test --config=playwright.illustration.config.ts`: final1
  PASS/9.7s after requested pre-approval1440/390 capture additions; corresponding
  Prettier check PASS. Isolated actual FastAPI/migrated SQL and Vite proxy, real
  authenticated source/draft/photo presentation, keyboard approve, reject,
  approve again, source editorial rejection, fresh latest read and revoke.
  Final durable evidence is exactly four review/revocation rows, zero publication
  jobs and provider calls only synthetic fixture setup `[search, download]`.
  Actual narrow390 overflow/WCAG checks and DEMO-no-token-panel pass. No live
  provider/client/sender is initialized. Playwright emits only the existing
  NO_COLOR/FORCE_COLOR Node environment warning; no test/browser error.
- `git diff --check`: PASS. CI YAML parses and registers a separate protected
  browser step, new fixture lint and always-uploaded dedicated evidence. Remote
  CI execution has not been claimed; no push was performed.
- Final additional `python -m compileall -q backend/src backend/tests
  scripts/ui_illustration_fixture_api.py` from repository root: PASS.

## Evidence preservation

Before each output overwrite, the entire previous `.artifacts` tree was copied
to a fresh explicitly absent D: directory; nothing historical was deleted:

- `D:/Codex-Recovery/content-studio-20261008/task3-captures-20261009-1323/.artifacts`
- `D:/Codex-Recovery/content-studio-20261008/task3-captures-20261009-1327/.artifacts`
- `D:/Codex-Recovery/content-studio-20261008/task3-captures-20261009-1334/.artifacts`

Current screenshots/report are under `.artifacts/illustration-review-ui/`:
`review-canonical-before-approval-1440.png`,
`review-canonical-before-approval-390.png`, `review-stale-revoked-390.png`,
in `test-results/review-real-protected-illu-d7c61--preserve-publication-gates/`.
Parent visually inspected all three new canonical1440/canonical390/stale-revoked390
views: navy retained and new controls not clipped. The blue fixture photo is
synthetic, never event-photo evidence. This does not claim a whole eight-section
visual comparison. Existing evidence remains recoverable in create-only D: copies.

## Files and self-review

Source commit changes18 scoped files: backend API/new presentation service/shared
local-photo helper/new presentation tests; dedicated frontend client/panel plus
their tests and test-only fixture; existing MediaPreparation/integration tests;
dedicated browser config/spec and isolated fixture launcher; frontend formatting
script paths; existing CI wiring; CURRENT_STATE and IMPLEMENTATION_PLAN.
The report is committed separately to reference the exact immutable source SHA.
Parent-owned `docs/ILLUSTRATION_REVIEW_IMPLEMENTATION.md` and
`docs/ILLUSTRATION_CONSUMER_PARENT_20261009.md` are excluded from both child commits.

Self-review checked strict type/identity/hash boundaries, secret handling, absence
of persistence/log/HTML/token URL use, all operation payloads, generation ownership,
object URL cleanup, latest-read/revoke independence, old shared-photo contract,
no provider/publication side effects and correct new CI invocation. It caught the
array enum coercion and complete-representation ETag issues; both have actual RED
then GREEN regressions. No unresolved Task3 implementation issue is known.

NEXT: parent independent Task3 review, then Task4 create-only owned synthetic
Windows Docker HTTP/review/audit/encrypted-snapshot/photo restart acceptance,
stale/revoked fake-transport refusal and abandoned SENDING zero resend. This work
does not claim packaged restart acceptance, real-model qualification, operational
deployment, live Telegram authorization or real publication acceptance.
