# Read-only Inbox technical holds — 2026-10-08

Subsequent actual GitHub inspection: exact source ec4e560 CI 37791084343
completed all-eight SUCCESS, including expanded PostgreSQL job 113358327396
116 PASS /54.26s. This is isolated Linux acceptance, not current Windows proof.

## Implemented

The existing Telegram Inbox GET now returns additive `technical_reason_codes`
derived from the latest retained SQL revision. Fixed, non-secret diagnostics:
video manual-only, unconfirmed album membership, protected source, visible/hidden
YouTube, malformed visible/hidden URL, unknown legacy link observation and corrupt
link metadata. It never returns captured hidden destinations or tries to repair
them. An empty list is **not** a complete per-channel readiness certificate.
Mapping-specific filters and all current worker/publication gates remain separate.

Historical editorial status/reasons, original text, source state and existing
jobs remain unchanged. Technical holds force the read projection's
`rewrite_allowed=false`; they do not fabricate `EDITORIAL_REJECT`. The reader
refreshes cached SQL observations and refuses new/dirty/deleted caller work before
any query, preventing implicit flush or overwrite during diagnostics. Request
and response use `no-store`.

The real Russian dark-navy Inbox displays the causes in an accessible read-only
region, explicitly labels historical editorial truth, and distinguishes technical
blocking from editorial rejection. Strict optional DTO validation accepts only
unique bounded known reason codes; malformed/unknown metadata fails closed.
Nonempty diagnostics independently block `canProcess` even if a contradictory
historical PASS/allow flag arrives. Older API responses remain compatible; no
DEMO data or commands are mixed into real diagnostics. Existing apply/editor/
schedule/publish actions stay disabled. No new action/permission/API write,
provider call, source download or publication was added.

## Actual RED → GREEN

- 28 migrated SQL/HTTP cases initially failed missing no-store/diagnostic projection
  and stale cached observation. Covers PASS/REJECT/no decision, independent link/
  video/album/protection combinations, SQL NULL and corrupt private metadata,
  repeated GET, zero new jobs/outbox and retained SUPERSEDED history.
- Three real pending-session cases reproduced implicit read autoflush; clean-session
  refusal fixed without flushing or replacing caller work.
- Fourteen client/UI cases initially failed contradictory PASS permissions,
  invalid diagnostic list acceptance and missing no-store request.
- Initial browser exposed invalid h3/p nesting inside the paragraph-based Notice.
  Seven DOM regression assertions failed; the new block now uses a styled div,
  preserving the shared Notice component. Final browser explicitly asserts no
  console errors. An additional DEMO round-trip/late response characterization
  confirms existing keyed workspace isolation; no unrelated race fix was needed.
- Required independent source review found no Critical/Important issue and the
  same nesting defect, corrected and reverified. Reviewer did not execute tests.

## Verification

All tests use owned isolated synthetic state; no operational DB migration or
real Telegram/AI/media call occurred.

- Combined Inbox/hidden-link/video-exclusion/deletion: **103 PASS /15.91s**.
- Full backend with isolated actual Telethon 1.45 SDK: **1402 PASS /145.57s**,
  completed session 48858. Main installed SDK remains unchanged.
- Exact CI-context Ruff, changed-file Ruff format, D: bytecode compile: PASS.
- New explicit D: isolated DB upgrade/check/downgrade/base/upgrade/check: PASS,
  no schema drift. No new application migration required.
- Frontend: **200 PASS**, Prettier, TypeScript/Vite build PASS; production audit
  **0 vulnerabilities**.
- Final migrated real FastAPI + SQLite + Vite browser: **33 PASS /55.0s**,
  session 72664. New Inbox check covers four retained technical-hold sources,
  reload, unchanged historical PASS, GET-only/no writes, disabled actions,
  no console errors, WCAG A/AA and no horizontal overflow at 1440/390.
  Earlier 33 PASS /54.1s included React nesting warnings and is not final proof.
- Expanded create-only PostgreSQL CI includes all **31** new SQL/HTTP tests.
  Actual ec4e560 / CI 37791084343 / PG job 113358327396 completed SUCCESS:
  **116 PASS /54.26s**, including all 31 new migrated SQL/HTTP cases. Local
  SQLite and this Linux PG proof do not count as current Windows Docker evidence.
- Preceding corrected source 30280de / CI **37787946778** and docs f2ce40d / CI
  **37788650164** now actually inspected: all eight jobs completed SUCCESS,
  including Linux synthetic full-stack/restart/PG and both provider variants.
  Original d871dd1/19d6eda collection failures remain recorded failures.

## Screenshots and limits

Both final captures visually inspected and retained:

- `.artifacts/ui-dark-navy/inbox-technical-holds-20261008/inbox-technical-holds-1440.png`
- `.artifacts/ui-dark-navy/inbox-technical-holds-20261008/inbox-technical-holds-390.png`

Original browser artifacts remain in the owned D: `inbox-holds-browser-final`
directory. Eight existing DEMO section layouts remain covered by the full suite;
no redesign or PNG-as-interface background was introduced.

Video stays discard/manual-only; this does not authorize video rewrite/download/
upload/publication. Legacy unknown links require a genuinely new trustworthy
Telegram observation, never a blanket [] backfill or repair/override button.
Live authorization, real model qualification, illustration relevance and latest
Windows runtime remain separately pending. Current Windows Compose E2E remains
**NOT VERIFIED / BLOCKED BY ENVIRONMENT**. PHASE 1 is not complete.
