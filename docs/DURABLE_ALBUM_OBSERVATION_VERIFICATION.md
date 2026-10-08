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
  tests in the separate PG CI job. Actual new PostgreSQL execution PENDING.
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
