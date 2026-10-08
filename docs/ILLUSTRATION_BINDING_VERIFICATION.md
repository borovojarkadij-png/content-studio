# Canonical illustration review context — 2026-10-08

## Implemented scope

`services/illustration_binding.py` resolves the existing immutable review-domain
binding from current canonical SQL and persistent decoded bytes, not client
hashes or search keywords. This is a read-only offline service seam. It adds no
API, reviewer authentication, stored approval, model qualification, network call,
worker flag or publication permission. The library publication hold is unchanged.

The resolver refuses any pending caller inserts/edits/deletions before its first
query, preventing implicit autoflush or overwriting caller work. It reuses shared
current editorial/source/per-channel approval/technical checks, then independently
requires a real canonical donor/output mapping with `LICENSED_LIBRARY`, known
unprotected single text/photo source and one unambiguous approved draft. Video,
album, deleted/stale sources and unknown/forbidden hidden links remain blocked.
It also checks deterministic fact anchors and technical filters against both
draft and final draft-plus-credit text; this is not semantic fact certification.

Only the latest persisted candidate media job may supply an asset. Its state,
mode and exact existing acquisition binding must match the current source/draft.
Its selected asset must be a genuine library registry row with CC0/CC-BY rights
and bounded explicit attribution. Canonical version-1 metadata hashing includes
origin, storage key, MIME, license, attribution and null source identity. Bytes
are never inferred from a job's success flag: existing bounded PNG/JPEG decoder,
containment, dimensions/size/frame and SHA/MIME checks are reused twice, with
fresh SQL revalidation after each read. Changed metadata invalidates prior human
review even if photo bytes remain identical.

The result is an internal exact human-review **context**, not confirmation that
the photo depicts the actual event. Current context does not substitute for
authenticated human relevance review or benchmarked visual-semantic accuracy.
A future durable writer must re-resolve, audit the decision and enforce all hard
gates; the future publication path must independently revalidate immediately
before transport. No operational source/profile rights or authorization changed.

## Actual verification

- Initial real behavior RED: requested resolver module is absent; the first
  canonical binding and pending-work tests fail at that missing boundary.
- First implementation: 41 PASS and two fixture defects. Foreign mapping mutation
  violated the actual donor/output UNIQUE constraint; corrected fixture uses an
  existing foreign-channel mapping. Reject-first case used the wrong status name;
  existing real ingestion returns `REJECTED_EDITORIAL`. Neither correction changes
  production guards, schema, constraints or ingestion behavior.
- Combined resolver/domain/media-status/publication-preflight **178 PASS /19.53s**,
  before four extra existing-behavior characterization cases.
- Final dedicated migrated SQL **47 PASS /31.61s**: canonical reopen/no DML, clean
  session and strict IDs, current unsafe source/mapping/editorial/draft/media/credit
  cases, independent SQL changes during decode, rights-only binding invalidation,
  missing/replaced bytes, second decode and reject-first zero jobs/usage.
  Synthetic image provider calls occur only in explicit fixture setup; resolver
  emits no search/download/rewrite/publication calls. Counts/history remain intact.
- Extra ambiguous-draft fixture initially tried a second same-channel/source job
  and was correctly rejected by the migrated UNIQUE constraint. Corrected test
  creates a foreign job plus contradictory draft association, which the read
  boundary refuses. No constraint or check was disabled.
- Earlier full run 20088 collected that invalid fixture before its correction:
  **1 FAILED /1558 PASS /232.86s**. This failed run is preserved, not treated as
  success or as a production constraint failure. The corrected 47-case dedicated
  run passed; fresh complete corrected-source run **46215: 1559 PASS /192.84s**
  with actual isolated Telethon 1.45 and D: test/bytecode storage, exit 0.
- Exact CI-context Ruff, changed-file format, D: compile: PASS.
- Fresh explicit D: isolated migration upgrade/check/downgrade/base/upgrade/check:
  PASS, no drift. No schema change or operational migration introduced.
- Fresh frontend **205 PASS**, format and TypeScript/Vite build PASS. No UI code
  changed and no fresh browser/screenshots claimed for this internal service.
- Independent read-only source/test/CI review: no actionable Critical, Important
  or Minor findings. Review executed no tests or live calls. SQL freshness assumes
  the repository's configured default transaction isolation; this read context
  is not a transaction lock or final transport permission. Final full backend
  verification above completed after the fixture correction and review.
- Expanded strict create-only PostgreSQL CI includes the new migrated file; real
  PostgreSQL execution remains pending its exact checkpoint, not inferred from
  local SQLite. Existing namespace/role/target restrictions are unchanged.

Verified source committed/pushed as
`44fb130ab0dda51e9910f05e08d106e3d96077a8` to
`borovojarkadij-png/content-studio`, branch `codex/dark-navy-ui`.
Exact CI **37798052676** is IN_PROGRESS at first actual inspection; all eight
jobs running, including expanded PostgreSQL **113382585290**. No new CI PASS
claim or Windows acceptance inference. The next run must inspect its conclusion
and any subsequent documentation checkpoint before proceeding.

## Prior checkpoint CI and limitations

Previous review-contract source `06cbd1e903408e818cc1b3465f7dc7af44d8834f`, exact
CI **37795331144**, all **eight jobs SUCCESS** at fresh inspection, including
backend **113373178871** and PostgreSQL **113373178630**. Its revised real
PowerShell refusal test executed in Linux CI without skipping. This is proof of
that previous exact checkpoint, not of this new resolver or current Windows
Desktop acceptance.

No real Telegram/AI/media network calls, production jobs, credentials or rights
were used/changed. Fresh read-only Windows `docker version` still fails because
the `dockerDesktopLinuxEngine` pipe is absent. No restart/reset/deletion attempted.
Current Windows Docker and required live authorizations remain separately
**NOT VERIFIED / BLOCKED BY ENVIRONMENT**. PHASE 1 is not complete.

## Precise next step

Inspect exact new CI (especially expanded PostgreSQL) and preserve any genuine
failure evidence. Then implement bounded immutable durable human illustration
review history: exact trusted canonical binding, explicit verdict/illustration
acknowledgment/rationale/reviewer provenance, revoke rather than overwrite, audit
and regression/migration/reopen/crash checks. Do not accept a reviewer identity
or approval from unauthenticated client fields. Do not release library publication
until the authenticated workflow and fresh preflight/transport boundary are
fully integrated and verified. Real visual-semantic/model qualification remains
separate and cannot be earned by these synthetic review fixtures.
