# Hidden Telegram source links — 2026-10-08

## Implemented

Provider-neutral immutable TelegramMessage now carries bounded link_destinations
separately from its caption. Telethon captures actual MessageEntityTextUrl and
inline keyboard URL-bearing buttons, deduplicated without changing source prose.
At most 100 entities/buttons/destinations, 20 rows, 2048 characters per URL;
unknown/corrupt/unbounded shapes and missing URL values stay unknown, not empty.
No browser, redirect resolution, download, AI or Telegram send is involved.

Technical ingress checks hidden destinations before editorial classification:
mandatory YouTube/invalid-address rejection and custom forbidden-domain policy.
Backslashes fail INVALID_LINK to avoid Python/browser host-parser disagreement.
Mapped/legacy/missing-candidate late guards and Inbox projection read exact
persisted metadata. Hidden-only edits are distinct immutable source observations;
sync replay preserves metadata and refuses corrupt containers without creating
a replacement revision or classifier/job. Source-photo reread equality includes
links, so a changed hidden destination cannot be hidden by an unchanged caption.

## Migration and safe compatibility

Versioned migration a8d310f62c94 follows eab7590cde48 and adds nullable JSON to
incoming_post_revisions. Old rows remain SQL NULL: historical absence of captured
metadata is not proof that there were no hidden links. Those sources fail closed
until ordinary authenticated ingestion observes new metadata and creates a new
revision. No in-place backfill, source/job deletion, legacy retry revival, manual
approval or operational flag enablement. Known observed empty links persist [].
Downgrade refuses to discard any observed non-NULL metadata, even an empty list;
unknown-only round-trip is supported and tested on an isolated database.

Actual regression caught Python None being replaced by the column list default.
The first evaluates_none correction produced JSON null, not SQL NULL, confirmed
by an independent reviewer and raw IS NULL RED. Final repository explicitly uses
sqlalchemy.null(), with raw storage and unknown-only migration downgrade proof.
This distinguishes SQL NULL and JSON null as documented in
[SQLAlchemy JSON NULL handling](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.JSON.NULL).

Corrupt JSON dictionaries are not coerced to tuple/empty metadata on replay:
actual WAIT_SYNC/revision replacement RED now INVALID_OBLIGATION with the original
row and evidence intact. Publication/editorial/source/fact/review constraints
are unchanged; technical retention is not a fabricated editorial decision.

## Verification

- Initial 13 feature RED -> GREEN. Explicit unknown insertion RED -> corrected;
  raw SQL NULL regression separately RED -> GREEN, unknown-only downgrade PASS.
- Hidden custom-domain regression RED -> GREEN, SDK corrupt/bounded cases PASS.
- Actual TextUrl/button/backslash and retained-task regression 3 RED -> GREEN.
- Missing URL on a URL-button actual RED -> unknown metadata, not empty.
- Corrupt sync replay RED -> history-preserving refusal.
- Final hidden/migration/replay/photo combined: 62 PASS /7.14s (435b50).
- Final full backend 1371 PASS /122.69s (83080); earlier 1360 PASS /117.97s
  snapshot precedes final adversarial additions. Exact new CI still pending.
- Ruff source/tests/Alembic/scripts, 12-file format, D: bytecode compile,
  isolated explicit-target D: upgrade/check/downgrade/upgrade/check and CI YAML
  parsing PASS. No schema drift or operational database migration attempted.
- Fresh actual FastAPI/current migrated isolated DB/Vite browser: 32 PASS /47.2s;
  subsequent older contradictory video hint removed (actual unit RED -> GREEN),
  fresh 185 units/format/build/audit0 PASS; final browser 32 PASS /47.8s (33867).
  Current desktop/narrow captures in `.artifacts/ui-dark-navy/hidden-links-20261008/`;
  final narrow layout visually inspected, unchanged design.

Hidden-link SQL tests use the migrated create-only mapping_store fixture, which
selects a strict separately named PostgreSQL namespace only when the validated
CI environment URL exists, otherwise isolated SQLite. GitHub PostgreSQL job now
includes test_hidden_donor_links.py; actual new PG acceptance is still pending.
Exact committed/pushed source checkpoint:
`d871dd1d2ae26af6bb5a8c680a6ff7f223d53cd4`, `codex/dark-navy-ui`, correct
origin `https://github.com/borovojarkadij-png/content-studio.git`. Preceding
New CI 37786943304 backend/PG jobs FAILED collection because Telethon 1.45
removed KeyboardButtonUrl. The actual downloaded SDK introduces nested
KeyboardInlineButton/InlineButtonTypeUrl destinations; compatible fixtures then
reproduced 2 missing-capture behavior RED. Minimal bounded capture supports both
new and old formats; 110 relevant PASS with isolated 1.45, 24 hidden tests PASS
with installed 1.44. Full isolated 1.45 1371 PASS /119.78s (41174), fresh exact
Ruff/format/D: compile PASS, independent read-only review no actionable findings.
Corrective CI acceptance still pending. Docs-only 19d6eda /37787154561 also
backend/PG FAILED at inspection. No older
dependency pin, skipped test or gate relaxation. Preceding
e8064d7 /37784840224 completed all-eight SUCCESS, actual gh inspection; this
does not substitute for the new metadata/migration CI.
No local PostgreSQL/Windows Docker success inferred from SQLite or Linux CI.

## Remaining limits

No link-shortener redirect following: unknown remote destinations are not proof
of a YouTube-free target. Legacy NULL revisions deliberately block automation
pending fresh observation. No full-album membership inference, video publication,
live Telegram login/download/send or production flag changes. PHASE 1 remains
incomplete; current Windows runtime/persistence NOT VERIFIED / BLOCKED BY
ENVIRONMENT (Docker daemon missing), not an implementation failure.
