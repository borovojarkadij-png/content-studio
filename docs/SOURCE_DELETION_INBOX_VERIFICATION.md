# Retained deletion truth in Inbox

2026-10-08; branch `codex/dark-navy-ui`, parent
`add59c6f7b860df6da86669e2d968ce77c04af5f`; correct origin
`borovojarkadij-png/content-studio`.

The real moderation reader/API project current source tombstones as
`source_deleted=true`, `state=SOURCE_DELETED`, `rewrite_allowed=false`. The source
text, revision and historical editorial decision remain visible and unmodified;
deletion does not fabricate EDITORIAL REJECT. Current tombstones are reread even
inside an already-open reader session. Nothing is queued or sent by these GETs.

The existing dark-navy Inbox shows “Удалён у донора”, a conditional deleted-source
filter and explicit retained-history warning. Its processing guard refuses both
the deletion flag and legacy SOURCE_DELETED state even with contradictory
historical PASS/rewrite permission. Malformed flags fail API validation; no DEMO
fallback. Original text remains read-only and rewrite/manual scheduling controls
disabled. No new design, demo seed leakage or fake provider success.

Visual review also found stale live copy implying that an already-connected API
was missing. Live Inbox now honestly states its read-only status, unavailable
per-material route projection and disconnected Inbox send action. Demo wording/
reference layout remain unchanged. Existing Planner workflow is not replaced.

## Actual checks

- Backend service/HTTP missing-field RED → GREEN; retained original/source state/
  historical PASS/SUCCEEDED job verified unchanged, no publication jobs.
- Frontend missing deletion UI RED → GREEN; stale live-capability copy RED → GREEN.
- Fresh full backend **833 PASS**, session 54870. Ruff/targeted format/compile and
  explicit unique D: Alembic upgrade/drift PASS. No new schema or operational
  migration in this increment.
- Frontend **62 unit tests PASS**, format/typecheck/build PASS, production audit
  zero vulnerabilities. Prettier's initial two noncanonical files fixed and fresh
  complete format check passed; no checks were disabled.
- Initial full browser **25 PASS** (53133), including actual migrated FastAPI/
  service-seeded deletion through Vite, desktop/mobile/reload/GET-only/WCAG AA.
  Final copy-correction browser rerun **25 PASS**, session 41662; final desktop/
  mobile screenshots visually inspected again.
- Desktop/mobile screenshots saved to `.artifacts/ui-dark-navy/`:
  `live-inbox-deleted-1440.png`, `live-inbox-deleted-390.png`; visually inspected.
  All eight-section desktop/mobile evidence refreshed by full browser gate.
- No paid provider calls, real Telegram authorization, send, secret/flag changes,
  operational data writes or Docker-storage workaround. Current Windows deployment
  remains NOT VERIFIED / BLOCKED BY ENVIRONMENT.

Next: trusted bounded read-only channel baseline bootstrap. New donors may capture
an authenticated baseline before initial history, but legacy source histories and
TooLong gaps must never be silently declared recovered or reset.
