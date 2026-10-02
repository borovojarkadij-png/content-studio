# Dark-navy UI verification — 2026-10-02

Scope: existing Content Studio, branch `codex/dark-navy-ui`, starting HEAD
`e51fb2162ef85b5b3ba118133a526bfc730cbbd7`. Publishing target is exclusively
`borovojarkadij-png/content-studio`; no merge into main, no force push.

## Implementation and comparison

The package's CODEX_PROMPT_RU, README_RU and DESIGN_NOTES_RU were read and all eight
PNGs visually inspected. React components implement the navy shell, navigation,
panels, typography, cards, selected states and actual form controls. No PNG is
used as a page background. Decorative macOS controls/Pro offers are omitted.

| Reference | Implemented composition / verification |
| --- | --- |
| 01 overview | Four derived counters, line chart, donut, moderation queue and channel summary |
| 02 inbox | Queue with previews, immutable original, separate AI suggestion/manual draft, destinations/actions |
| 03 donors | Counters, filterable directory and selected source settings; bulk import preview |
| 04 my channels | Dense directory, selected panel, four tabs, windows/quiet hours and derived weekly map |
| 05 connections | Sources/routes/editor; distinct intake and target-mix sliders, explicit Save/Cancel |
| 06 planner | Dated weekly/day grid, channel filter, unscheduled list, derived weekly counts, editable records |
| 07 accounts | Masked statuses, filters and explanatory connection steps; wizard only on explicit action |
| 08 settings | Category navigation and selected form, draft preserved across categories, complete Cancel |

Manual screenshot comparison corrected sidebar width, Inbox text/media size,
donut centre, paused-route colour and narrow layouts. Settings deliberately show
one selected category, rather than the contradictory all-form reference layout.
Photos are not included as independent usable assets: labelled local SVG DEMO
illustrations are an acknowledged visual difference. This is not a pixel-perfect
claim. All eight final screenshots were visually inspected; narrow Inbox and
Channels layouts were also inspected.

## Available quality gate

| Command / check | Result |
| --- | --- |
| backend `python -m pytest -q` | PASS: 55 |
| backend `python -m ruff check src tests ../scripts/ui_fixture_api.py` | PASS |
| backend `python -m compileall -q src tests ../scripts/ui_fixture_api.py` | PASS |
| isolated Alembic upgrade head / downgrade base / upgrade head / check | PASS; local newsflow.db untouched |
| frontend `npm run format:check` | PASS |
| frontend `npm test` | PASS: 18 |
| frontend `npm run build` | PASS: TypeScript + Vite production build |
| frontend `npm run test:e2e` | PASS: 18 Chromium tests; no skipped cases or retries |
| axe WCAG 2/2.1 A/AA tags | PASS: default DEMO view of all eight sections |
| independent code review | Three Important findings fixed and re-reviewed; no outstanding Critical/Important in reviewed fixes |
| GitHub Actions on implementation commit bee24ba32884ab6ecc1735e4843695fca4592458 | PASS: backend and frontend jobs, including browser regressions and uploaded evidence |
| Docker / PostgreSQL / Redis / worker restart and persistence E2E | NOT VERIFIED / BLOCKED BY ENVIRONMENT |
| live Telegram login / real publication / paid AI | NOT RUN; intentionally excluded |

Browser tests exercise an actual FastAPI process, Alembic migrations, isolated
SQLite and the Vite proxy, not just request mocks. A synthetic rejected revision
renders read-only and cannot be rewritten/scheduled. Separate request mocks cover
HTTP failure/retry and malformed contracts. DEMO navigation has zero `/api/`
traffic. Existing backend adversarial reject/zero-rewrite tests remain passing.

Automated accessibility does not replace screen-reader/manual assistive testing
and is not a blanket accessibility certification.

## Regression fixes

- Missing page language/title/viewport metadata: fixed and checked with axe.
- Settings category accessible names: explicit names, full-field Cancel tested.
- Invalid calendar dates silently normalized by JavaScript: strict round-trip
  date and clock validation; regression includes February 30 and 24:00.
- Empty quiet hours/fractional limits: cannot be saved or used for scheduling.
- Modal callback identity reset focus while editing: stable listener, focus trap,
  Escape and focus restoration tested.
- AI Apply could overwrite manual edits: explicit confirmation; rejection now
  retains a disabled manual draft and removes pending DEMO plans.
- Repeated Inbox scheduling reset saved time: hydrates each target's existing
  record and retains separate manually edited date/time drafts across targets.
- Calendar cards overlapped: overlapping visual slots open an individual record
  list; existing IDs remain unique. Early/late times and calendar year are derived.

## Screenshot evidence

Directory: `.artifacts/ui-dark-navy/` (ignored by Git; CI uploads only this test
evidence directory as `ui-dark-navy`, retention 14 days).

Five subdirectories: `1366x768`, `1440x900`, `1586x992` (reference size),
`1920x1080`, `390x844`. Each contains:

```text
01_overview.png
02_inbox.png
03_donors.png
04_my_channels.png
05_connections.png
06_planner.png
07_accounts.png
08_settings.png
```

Forty screenshots, plus `report/index.html` and failure traces when a run fails.
GitHub Actions runs the same gates on main/codex pushes and pull requests; a
configured workflow is not by itself evidence of a successful remote run.

Actual successful remote run:
[Quality gate 37024393524](https://github.com/borovojarkadij-png/content-studio/actions/runs/37024393524).
The `ui-dark-navy` artifact was uploaded successfully. The runner emitted
non-failing maintenance notices about action Node runtimes and the upcoming
ubuntu-latest image transition; these are not application failures.

## Real API versus DEMO / remaining limitations

- Real integration: existing read-only moderation inbox endpoint, request abort,
  response validation, loading/empty/error/retry, no synthetic fallback.
- DEMO: all other section data and mutations, scheduling/approval, safe wizard
  walkthrough and manual form persistence within the current window only.
- No real authentication, rewrite generation, publication, durable scheduler,
  notification delivery or settings persistence is simulated as successful.
- No drag-and-drop scheduler: clicking a job edits its date/time explicitly.
- Language selection is a DEMO parameter, not a completed English localization.
- PostgreSQL/Compose recovery, live secrets/login and Obsidian are still pending.

Next PHASE implementation is durable service-owned configuration APIs, then live
UI wiring backed by tests. This UI increment does not complete PHASE 1.
