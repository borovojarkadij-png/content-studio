# Per-channel approval policy in the real Planner

2026-10-08; branch `codex/dark-navy-ui`; correct origin
`https://github.com/borovojarkadij-png/content-studio.git`.

## Behavior and limits

Existing GET/PUT approval-policy endpoints are connected to a navy Planner panel.
The default is MANUAL. VERIFIED selects only releases already returned by the
trusted registry; no arbitrary model field, qualification endpoint, AI call,
worker enablement or publication action is introduced. No qualified releases
means automatic mode is unavailable. Persisted revoked policies remain visible
and can be explicitly returned to MANUAL, without fabricating qualification.
The setting and the daily plan are independent drafts; either dirty draft fences
channel navigation. Cancel, API errors, refresh, duplicate save and late response
handling preserve authoritative versus unsaved state. Policy saves invalidate
old per-draft diagnostic snapshots without changing source text or manual edits.

Strict client DTO validates IDs, exact fields, providers/fixed free OpenRouter
releases, prompt/benchmark versions, duplicate releases, policy and successful
PUT identity. It does not accept a client semantic verdict or pretend persistence
after a refused/mismatched response. HTTP/parser errors are redacted and contextual.
DEMO never renders this form or uses these endpoints.

## Reproduced defects and fixes

- Real same-session SQL read after independent policy/release revocation returned
  cached VERIFIED/release #1 instead of current MANUAL/no qualified releases.
  Failing regression -> fresh populate_existing policy/channel/registry -> PASS.
  Invalid channel identity is refused before SQL. Execution-time guards unchanged.
- Existing policy GET lacked no-store: real HTTP regression failed -> added header
  -> PASS. No new migration or operational secret change.
- New panel and existing queue could show the same bare HTTP error. Full unit
  suite exposed ambiguous message lookup; panel errors now name their own context,
  without hiding the queue failure or weakening its regression.
- Browser tests initially used exact implicit-label lookup (includes option text)
  and Playwright disabled matcher for OPTION (not supported as a disabled control).
  Accessibility tree confirmed the correct native combobox/disabled option.
  Tests now use its accessible role and actual native disabled property; real UI
  behavior was not changed to accommodate the test.

## Actual verification

- 6 new backend policy/cache/invalid-identity/HTTP regressions; 57 combined policy
  and review API tests PASS. Real TestClient select existing synthetic release,
  manual recovery, fresh revoked-release 409 and zero new semantic jobs/evidence.
- Full backend 1094 PASS in 94.58s, session 70662, isolated D: basetemp.
- Frontend 139 units PASS including 19 dedicated policy tests. Component/client
  missing implementation RED -> GREEN; no models, qualified choice/cancel/PUT,
  409 retention, revoked manual recovery, invalid/private contracts, duplicate/
  abort/late write, read retry and mismatched-success refusal verified.
- Full browser suite 30 PASS (42.1s, session 90537) with migrated isolated FastAPI,
  SQLite, Vite proxy and Chromium. Native automatic-choice unavailability, real
  manual PUT/reload, injected refused save, independent dirty drafts, channel
  fence, DEMO separation and zero AI/send/qualification requests checked.
- Exact CI Ruff + changed format + D: compile + fresh explicit D: migration
  upgrade/check/downgrade/upgrade/check PASS. Frontend format/typecheck/build and
  production audit (0 vulnerabilities) PASS. WCAG A/AA and 390px overflow PASS.
- Visually opened desktop revoked, mobile revoked and mobile saved screenshots:
  `D:/Codex-Recovery/content-studio-20261008/policy-browser-1331/studio-real-approval-setti-40e75--model-or-losing-plan-edits/approval-policy-revoked-{1440,390}.png`
  and `approval-policy-saved-390.png`. Full repeat evidence is in the equivalent
  test directory under `policy-full-browser-1335`. Existing palette/layout preserved.

The isolated UI fixture adds only an INACTIVE synthetic release and revoked policy
history. It cannot qualify an operational model. Operational configuration, secrets,
sessions, network flags and production data were not touched. Previous semantic
status 157ed68 CI 37761899546 backend/frontend/dedicated admission HTTP/restart/
channel-sync SUCCESS; two legacy Docker jobs still running at inspection. New
exact policy checkpoint CI pending. Current Windows Docker is independently
**NOT VERIFIED / BLOCKED BY ENVIRONMENT** (C: ~0.48 GiB free, storage not repaired).
PHASE 1 and live unattended acceptance are not complete.
