# Retained album observation read API

2026-10-08, existing `codex/dark-navy-ui` branch, correct origin
`https://github.com/borovojarkadij-png/content-studio.git`.

## Scoped behavior

`GET /api/telegram/source-albums?content_key=<immutable-revision-key>` projects
retained latest member revisions for the exact SQL-owned account/donor/group.
This reuses existing source revisions and deletion tombstones; no new schema,
group-completeness policy, UI design, automatic approval or worker activation.
Opaque keys resolve through the shared SQL identity helper, never delimiter
splitting. Ambiguous/missing keys return 404, stale/nonalbum/corrupt/over-bound
observations 409; unconfigured/unmigrated storage 503, never fake DEMO success.
Successful DTOs are no-store and contain no sessions, access hashes, keys,
file paths, media download identifiers or URLs.

Observed sparse members retain captionless photos and video captions in source
message order. Only latest revisions are included; editing a member out of the
group removes it from this observation, not history. Deleted members retain
their historical captions with an explicit deletion flag. At most eleven rows
are fetched; an eleventh is refused, never silently truncated. Ten observed
members still do NOT prove completeness. Known sync quarantine is reported;
its absence is not a source/authorization/completeness certificate.

Every response has `membership_complete=false`, `rewrite_allowed=false`,
`publication_allowed=false`, `ALBUM_NORMALIZATION_REQUIRED`. Reads never invoke
editorial/AI/media/provider operations or create jobs. Actual grouped ingress
retains photo/video/captionless observations but refuses them before editorial
classification, with zero decisions/rewrite jobs/usage. This is NOT full album
normalization, download, video support or grouped publication.

Read services also refuse a session with caller-owned pending new/dirty/deleted
objects before any query. Actual autoflush/overwrite bug reproduced RED for all
three states, then minimal fail-closed guard GREEN; manual pending changes are
retained, not committed or discarded. Concurrent independent anchor edit
between lookup and projection is refused instead of selecting its old group.

## Verification

- Actual migrated isolated SQLite, SQL-session reopen and real configured
  FastAPI GET/error/POST-refusal regressions: **27 new / 75 combined PASS**,
  session 684347. Sparse/foreign/group identity, latest edits/deletion, ten/
  eleven members, stale anchor, ambiguous opaque keys, malformed persistent
  metadata/private error redaction, sync enforcement, protected rejection,
  pending caller work and actual deterministic-first ingestion included.
- Empty reader/absent route RED -> implemented DTO/HTTP GREEN. Initial missing
  module was collection failure, not accepted behavior proof; explicit behavior
  RED was run after defining the interface. Pending-work three-case RED -> GREEN.
- Exact CI Ruff/changed format/D: bytecode compilation PASS. Initial lint and
  missing test-selector filenames were corrected and actual selected suite run;
  no empty run is counted as PASS.
- Existing strict create-only PostgreSQL namespace harness extended to these
  tests in the separate PG CI job. Corrective 8038585 / CI 37774826743 / job
  113302940590 completed SUCCESS: actual migrated PostgreSQL **50 PASS / 29.82s**
  (five vertical + 18 isolation + 27 retained album cases). All eight CI jobs
  completed SUCCESS, inspected via gh. Linux only, not current Windows proof.
- Full backend **1219 PASS**, 118.23s (59333), D: basetemp
  `D:/Codex-Recovery/content-studio-20261008/album-observation-full-1519`;
  UI source unchanged. No new migration; actual test schemas migrated using
  current Alembic head. Prior corrective
  e2225d0 / 37771372421 workflow completed all-eight SUCCESS, including actual
  nine full-stack restart/crash boundaries and 139 units/30 browser checks.

No operational database, session, key, permission, network flag or channel
setting changed. Current Windows Docker remains NOT VERIFIED / BLOCKED BY
ENVIRONMENT. PHASE 1 not complete; full immutable group manifests, trusted
membership evidence, media acquisition and guarded grouped publication pending.

## Exact PostgreSQL CI fixture correction

ed0beac / CI 37774362437 / PG job 113301402293 FAILED with **49 PASS / 1 FAIL**:
invalid synthetic `media_id` was 21 chars, exceeding PostgreSQL varchar(20), so
the fixture INSERT/UPDATE failed before the intended API corruption check.
SQLite does not enforce that declared character limit. Use a 15-char still
noncanonical marker; keep both the database length and runtime identity guards,
never skip the case or loosen the production model. Corrected local 27 PASS.

Same run frontend job 113301401799 failed the existing mapping-save test: it
found a form control before the technical-filter read finished and clicked
while its ancestor fieldset was disabled. Await `matches(':disabled')=false`
(own button.disabled alone misses the fieldset); controlled deferred-filter
regression confirms disabled/no PATCH before read and real save afterward.
14 targeted tests PASS. No production UI/loading guard changed. Corrective
actual PG/full CI 8038585 / 37774826743 completed all-eight SUCCESS; original
failures remain failures.

## Existing Inbox read-only context

Latest grouped SQL revisions now report `album_observed=true` and derive
`rewrite_allowed=false` even for retained historical PASS. Decision/source/job
history remains unchanged. Frontend validates the optional boolean (old API
without it remains compatible), applies an independent `canProcess` refusal,
and exposes an on-demand metadata reader only in real mode. No new design/CSS
or changes to the eight DEMO reference compositions.

The client accepts exact public keys, ordered unique bounded members and exact
signed64 group IDs, never parses source ownership from key delimiters or rounds
IDs through Number. Unexpected/private fields, malformed/protected/deletion
flags, missing anchor and forged complete/rewrite/publication permissions fail
closed. Abort on key/revision change or unmount, duplicate pending-read refusal,
discarding failed-refresh history and redacted transport errors prevent stale
or fabricated success. This component has GET only; no download/upload/RPC/AI,
manual save, approval, scheduling or publication path.

Verified locally: backend new grouped historical PASS regression RED -> GREEN;
**32 relevant / full 1220 PASS**, 122.87s (75576), exact lint/changed format/D:
compile and explicit D: upgrade/check/downgrade/upgrade/check PASS. UI interface
stub **5 behavior RED -> GREEN**, client/inbox initial **25 behavior RED -> GREEN**;
full **184 frontend units / format / typecheck-build / audit0 PASS**. Real migrated
API + Vite proxy sparse album browser initially PASS; full browser found one
existing deletion-filter expectation assuming one fixture tombstone. New retained
album deletion correctly adds a second: assert exactly both expected historical
cards and exclude the nondeleted anchor, no production filter relaxation.
Targeted corrected two browser checks PASS; final full **31 browser PASS / 44.9s**
(14022). Actual migrated fixture/Vite proxy GET-only, selected exact immutable
revision/no-store/reload, sparse photo/video/captionless/deleted/protected metadata,
album-only block without gap quarantine, WCAG AA and no horizontal overflow at
1440/390 PASS. Both final captures visually inspected; blocked notice uses
existing error styling, not success green. Files:
`.artifacts/ui-dark-navy/album-observation-20261008-1527/album-observation-1440.png`
and `album-observation-390.png`. Temp/browser outputs remain on D:. Exact new
CI for this UI increment pending; no current Windows Docker acceptance claimed.
