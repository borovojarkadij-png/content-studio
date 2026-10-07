# Configuration UI checkpoint — 2026-10-08

## Scope and actual API

The existing dark-navy shell and explicit in-memory DEMO remain separate. Working
Donors, My Channels, Connections and Accounts now read the real configuration API.
No fabricated subscribers, synchronization times, connection success or publications
are shown. Data lives in PostgreSQL, not browser storage.

- Accounts: list public health/session-provisioned flags, rename, create metadata
  with a known Telegram User ID. Creation is explicitly NOT authentication.
- Donors: list/rename, select an existing account, bulk import and display durable
  pending/resolved/invalid imports. A committed import plus a failed refresh is
  displayed as partial success, not falsely rolled back.
- Output channels: list/rename/create an immutable account/channel identity. No
  sending permission is inferred. Daily limits/slots remain in the real Planner.
- Connections: create/select a route, save intake/target percentages, delayed or
  immediate eligibility, priority and source/library media policy. Immediate
  eligibility never bypasses rewrite review or means an immediate Telegram send.
- Technical filters: real GET/PUT allowed types, blocked domains and custom ad
  markers. Builtin advertising checks remain mandatory. The API's normalized
  domains/markers are authoritative. Failed writes keep the manual form.

Route and filter mutations are separate, explicitly labelled transactions. No
editorial override or `rewrite_allowed` control exists. No publication, provider
invocation or Telegram login is triggered by these configuration forms.

Dirty forms survive section navigation. Dirty/loading/writing state blocks route
selection and refresh; explicit cancellation restores persisted values. Abort and
identity checks fence late responses after unmount/mode switching. Switching mode
cannot roll back a write already accepted by the server; the confirmation says so.
Unsafe/unrepresentable JS integer IDs fail closed rather than being rounded.

## Verification performed

- Test-first initial missing configuration/API tests failed, then passed.
- `npm test`: **40 PASS** (includes malformed response/identity, write failures,
  dirty navigation, queue partial success, failed filter read and late-response
  cancellation regressions).
- `npm run format:check`, `npx tsc --noEmit`, `npm run build`: PASS.
- `npm audit --omit=dev`: zero vulnerabilities.
- `npm run test:e2e`: **21 PASS**, repeated after the last source edits. Actual
  FastAPI + isolated freshly migrated SQLite + Vite proxy verifies account/output
  creation, rename/reload, pending donor import, route creation, delay/priority,
  canonical IDNA filter persistence/reload and independent route settings.
- Existing eight DEMO sections, manual-draft protection, hard-reject behavior and
  zero API traffic in DEMO still pass. Working configuration sections pass axe
  A/AA checks and no horizontal overflow at 1440x900 and 390x844.
- Eight new working screenshots manually inspected:
  `.artifacts/ui-dark-navy/live-config-{donors,channels,connections,accounts}-{1440,390}.png`.
  Existing eight-section/five-viewport reference regression screenshots regenerated.
- Operational `newsflow` production UI rebuilt on Windows Docker. Browser opened
  all four actual sections on `http://127.0.0.1:8080/` read-only, with **zero writes**;
  actual configuration endpoints returned HTTP 200. Screenshots:
  `.artifacts/ui-dark-navy/operational-config-{donors,channels,connections,accounts}-1440.png`.
  No synthetic fixture was added to the operational database.

The in-app browser automation runtime could not initialize (kernel asset path
error); local Chromium/Playwright performed browser verification instead.

## Remaining boundaries

Live Telegram login/session provisioning and sending-rights verification remain
pending. Working views do not claim they are connected. Resolved imports require
an existing authorized session and explicitly enabled ingestion worker. Public
username import is distinct from numeric output configuration. API owner
authentication/secret reveal, live model qualification, media relevance and
guarded publication execution require their own increments. Backend rejection
guards remain authoritative; frontend controls cannot authorize a reject.

This is a configuration increment, **not PHASE 1 completion**.
