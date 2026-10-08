# Library illustration publication hold — 2026-10-08

## Scope and behavior

The existing media-status GET exposes additive `publication_hold_reason_code`
for the current candidate's `LICENSED_LIBRARY` policy. It uses the exact fixed
`ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED` code already enforced by
PublicationPreflight; that rejection condition is unchanged. The diagnostic
exists before acquisition and after a genuinely selected synthetic asset. A
successful media job or valid preview never becomes relevance approval.

The reason follows current candidate policy, not the last job's acquisition
mode. `REUSE_SOURCE` returns null for this specific library hold; null does not
certify publication readiness, permissions, source/review validity or delivery.
No new boolean publication permission or approval action exists. Existing queue,
rights/selection/preview/lease/attempt guards remain unchanged.

GET is now no-store. The strict optional client field rejects unknown or
contradictory policy/diagnostic values, while old responses remain compatible.
The real Planner media panel explains the missing relevance confirmation and
permanent current publication block. Removed misleading advice suggesting a
manual glance could complete an approval workflow that does not yet exist.
Original/illustration modes, preview and manual settings remain independent.

## Actual verification

- New actual API regression RED on missing no-store/hold projection → GREEN:
  no-provider read before queue, fake-only acquisition, selected asset with hold,
  current policy change with historical library job retained, no extra provider
  calls. Combined media-status/publication-preflight: **27 PASS /5.13s**.
- Five new client/UI cases RED → GREEN: invalid/null/fake-approved library
  diagnostics fail closed; real component displays missing relevance workflow
  instead of implying approval. Combined targeted frontend: **13 PASS**.
- Full backend, isolated actual Telethon 1.45 SDK: **1403 PASS /177.79s**,
  completed session 9946. Installed dependencies unchanged.
- Exact CI-context Ruff, changed format, D: bytecode compile, CI YAML parse: PASS.
- Explicit new D: isolated upgrade/check/downgrade/base/upgrade/check: PASS,
  no drift. No schema change/application migration introduced.
- Frontend: **205 PASS**, format, TypeScript/Vite build PASS. Fresh production
  dependency audit: **0 vulnerabilities**.
- Actual migrated FastAPI + SQLite + Vite browser: **33 PASS (1.0m)**,
  completed session 81157. Existing isolated media E2E extended with hold
  before/after exact 64-pixel preview and refresh, narrow overflow/WCAG checks.
  Only the existing synthetic plan configuration/selection is written; no new
  publication/relevance/media-provider command is sent. No actual AI, Telegram
  source download or publication occurs.
- Required independent read-only source review: no actionable findings; reviewer
  ran no tests or provider calls.
- Prior Inbox ec4e560 / CI **37791084343**, exact expanded PostgreSQL job
  **113358327396** SUCCESS: **116 PASS /54.26s**, including all 31 new migrated
  SQL/HTTP cases. Backend/frontend/admission/sync jobs also completed SUCCESS
  when inspected; other restart jobs still running. Do not infer whole success.

## Evidence and remaining work

Both final screenshots visually inspected:

- `.artifacts/ui-dark-navy/library-publication-hold-20261008/library-publication-hold-1440.png`
- `.artifacts/ui-dark-navy/library-publication-hold-20261008/library-publication-hold-390.png`

Owned originals are retained in D: `library-hold-final-browser`. No redesign,
operational migration/data/secret/flag change or provider qualification occurred.
This exposes an existing restriction; it does **not** implement visual-semantic
image matching, a relevance-review workflow or unattended library publication.
Continue their independent offline implementation. Live authorization and current
Windows Compose E2E remain **NOT VERIFIED / BLOCKED BY ENVIRONMENT**, distinct
from historical Windows and successful synthetic Linux acceptance.
PHASE 1 is not complete.
