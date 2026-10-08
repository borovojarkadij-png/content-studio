# Read-only per-draft fact-verification diagnostics

2026-10-08; branch `codex/dark-navy-ui`; correct remote
`https://github.com/borovojarkadij-png/content-studio.git`.

## Implemented boundary

`GET /api/telegram/rewrite-outputs/{id}/semantic-status` reads retained job
history and the current shared verifier binding: editorial constraints, current
source revision, pending draft, deterministic fact guard, pinned qualified release
and per-channel policy. It does not create jobs, reserve attempts, invoke providers,
recover leases, record evidence, approve or publish. Short SQL locks use the same
binding reader as the worker; the request ends without a commit or mutation.

`READY_SNAPSHOT` is explicitly not execution permission. Network status is not
checked; worker state is unknown. History retains terminal jobs and committed
attempts even after editorial rejection, changed drafts or revoked qualification.
An expired RUNNING lease is diagnostic only. Attempts are not paid-call counts.
No claim token, source/draft text, hashes, arbitrary stored error or credentials
are projected. HTTP responses are no-store; missing/invalid/unavailable state
has redacted 404/422/503 errors. POST is not supported.

Existing real Planner renders the disclosure on demand per stable draft/channel.
Refresh clears the old snapshot and preserves unrelated unsaved plan settings.
Collapse, rebinding and unmount abort requests; late replies are ignored. Strict
DTO validation rejects unknown fields, contradictory authority, wrong identities,
invalid budgets, malformed dates, coercible arrays and private parser messages.
DEMO stays separate and never calls this API. No new retry/qualification/approval
action was added by this diagnostic.

## Actual verification

- 18 dedicated backend regressions; 80 combined status/admission/semantic runner/
  approval regressions PASS. Cached-session refresh, changed source/editorial/
  release/policy, terminal and expired history, invalid IDs/clocks, no mutations
  and real HTTP/no-store/error behavior verified.
- Initial component/client missing-module RED -> GREEN. Additional malformed-array
  and private JSON parser regressions reproduced three failures -> fixed -> GREEN.
  All 120 frontend unit tests PASS, including 23 dedicated diagnostic tests.
- Full browser suite: 29 PASS with migrated isolated FastAPI + Vite + Chromium.
  On-demand GET-only reads, MANUAL/REJECT/already-reviewed states, dirty-form
  preservation, channel switch/reload, DEMO separation, WCAG A/AA and 390px
  overflow checked. React development StrictMode may abort/repeat a safe initial
  GET; it never issues a mutation or AI request.
- Full backend run: 1088 PASS in 94.06s (session 81213), fresh isolated D: basetemp.
- Exact CI Ruff, changed-file format, D: bytecode compile, explicit fresh D:
  migration upgrade/check/downgrade/upgrade/check PASS. Frontend format,
  typecheck/build and production dependency audit (0 vulnerabilities) PASS.
- Desktop and mobile screenshots opened and visually inspected:
  `D:/Codex-Recovery/content-studio-20261008/semantic-full-browser-1318/studio-real-planner-fact-d-e3759-and-and-separated-from-DEMO/semantic-status-live-{1440,390}.png`.
  Same composition was inspected from the targeted run in `semantic-browser-1311`.
  Existing navy panels/typography/navigation remain unchanged.

Create-only admission probe now verifies the real API status before admission and
after original queued jobs survive restarts. Two independent HTTP fixture tests
PASS with no queue creation by GET. Its exact new Linux PostgreSQL CI execution
is pending the new commit. Previous f009949 admission CI 37759675552 and bdb66a9
semantic CI 37758555880 completed SUCCESS overall (actual gh inspection).

## Remaining limits

No operational flags or model qualifications changed. No live provider calls,
Telegram login/download/upload/send or paid tests. Current Windows Docker remains
**NOT VERIFIED / BLOCKED BY ENVIRONMENT** (disk/storage recovery), independently
of successful Linux CI. PHASE 1 is not complete. Operational auth, reviewed real
fixed-model qualification, full album/video transport and other documented work
remain pending. `/docs` remains source of truth; Obsidian sync is optional/pending.
