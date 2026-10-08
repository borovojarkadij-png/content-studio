# Persisted unresolved channel gap: shared source quarantine

2026-10-08; branch `codex/dark-navy-ui`, parent
`9c4dcf12c07e289298f3c3c0aae1c4d1232cd23a`; correct origin
`borovojarkadij-png/content-studio`.

## Reproduced and fixed

13 targeted failures demonstrated that a retained historical PASS could reach
new rewrite fan-out, stale/retry AI provider construction, manual review/planning,
source download, API approval and publication despite `GAP_UNRESOLVED`. The gap
also disappeared as soon as the next worker acquired its lease, before Telegram
responded. Three more failures exposed mapping/policy failure clearing the gap
and ingress reaching the classifier. A foreign-donor reassignment regression
then showed old source identity could lose its ledger association.

Shared fresh source validation now checks both current donor identity and the
immutable ledger identity, rejecting unresolved gaps, foreign/ambiguous/orphaned
baseline bindings. Existing history without a difference ledger is not silently
certified as synchronized; strict new-donor bootstrap refuses that legacy state.
The known gap survives lease acquisition, provider/pipeline failures, mapping
changes and non-final recovery. Only a validated fully persisted final chunk
with unchanged current bindings clears it. Cursor reset is not exposed.

Ingress retains exact observations/revisions during the gap but stops before
classifier, fingerprint consumption and new rewrite/publication tasks. This is
not EDITORIAL REJECT: historical text, PASS and completed jobs are preserved.
Current-source consumers fence review, planning, semantic/media/automatic review,
rewrite and final publication through their existing shared validation. Cached
PASS direct job creation has the same protection. An already observed trusted
receipt still reconciles delivery without another send.

Read-only Inbox projects `SOURCE_SYNC_REQUIRED` and effective rewrite=false.
Frontend shows a distinct Russian status/filter/explanation and disables actions
even for contradictory PASS/permission data. Original/history remain visible;
DEMO fixtures/reference layouts remain unchanged. No fabricated successful sync,
new reset/send action, operational flag/secret change or real provider call.

## Actual verification

- Fresh complete backend **906 PASS**, exec session 21914, unique D: temp tree.
- Final combined sync/difference/deletion regression **70 PASS** (25dc3d).
- Exact CI Ruff, changed-file format, compile and explicit isolated D: migration
  upgrade/drift PASS. No migration or operational database changed in this increment.
- Frontend **65 unit PASS**, format/typecheck/build and production audit **0**.
- Complete browser **26 PASS**, session 91631, actual migrated isolated FastAPI +
  Vite, no HTTP interception for new sync test. GET-only/reload, disabled controls,
  original text, WCAG AA, narrow containment and all eight section regressions.
- Visually inspected `.artifacts/ui-dark-navy/live-inbox-sync-gap-1440.png` and
  `live-inbox-sync-gap-390.png`: readable warning/history/controls, no clipping
  or horizontal overflow. Existing eight-section screenshots refreshed.
- Parent baseline CI 37742573673: backend/frontend SUCCESS, both Linux Docker
  jobs still in progress at last inspection; **not overall PASS** yet.

## Remaining boundary

Durable bounded replay of observations retained without an editorial decision
during a gap is still pending. They must not be forgotten after final recovery;
replay must use immutable stored revisions, current mappings/filters and fresh
editorial constraints, never fabricate PASS or bypass the zero-rewrite invariant.
Worker orchestration/legacy resynchronization and current Windows Docker/live
acceptance remain pending. PHASE 1 is not complete.
