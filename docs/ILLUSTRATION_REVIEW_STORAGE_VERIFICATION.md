# Immutable illustration review storage — 2026-10-08

## Scope and limits

This increment adds `IllustrationReviewRecordModel` and migration
`c5e81b29a704` after `a8d310f62c94`. It stores append-only review/revocation
history with all eleven canonical source/channel/draft/photo/rights metadata
binding fields, operation identity, verdict, explicit illustration acknowledgment,
reviewer provenance, note and timestamps. A revocation references an existing
original REVIEW with the exact same binding. It never overwrites that review.

Database protection refuses UPDATE, DELETE, replacement/upsert mutation and
PostgreSQL TRUNCATE. SQLite insert guards enforce the six canonical references
even on connections where foreign-key enforcement is disabled. Lowercase SHA-256,
positive identities, bounded nonblank operation/content/note, strict kind/verdict/
acknowledgment and SQLite integer reviewer type are enforced in migrated storage.
PostgreSQL uses native BIGINT; SQLite-specific `typeof` is not emitted there.

Downgrade protects the table before COUNT through DROP (PostgreSQL ACCESS
EXCLUSIVE; SQLite zero-row write transaction) and refuses populated history.
Only empty isolated test history is downgraded in verification. No operational
migration, reset, media edit, rights change or session/provider access occurs.

`AUTHENTICATED_HUMAN_V1` is a structural provenance label, **not authentication**.
There is no application writer, authenticated HTTP workflow, permission consumer,
new reviewer credential, automatic approval or publication permission in this
increment. Tests insert synthetic records directly. The existing library hold
`ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED` remains unchanged. This is not
visual relevance, event-photo truth or real-model benchmark qualification.

## Actual verification and defect history

- Initial RED: missing storage model; five real storage-boundary failures.
- An expired detached fixture read was corrected by capturing expected note before
  commit; production SQLAlchemy expiration behavior was not weakened.
- Independent review exposed SQLite OR REPLACE deletion and the COUNT/DROP race;
  both were reproduced before correction. PostgreSQL TRUNCATE bypass was fenced
  with its own statement trigger and strict PostgreSQL-only regression.
- Exact-parent-binding and positive-reference identity failures were reproduced
  and corrected without relaxing source/draft/editorial constraints.
- Ten actual RED cases reproduced positive nonexistent canonical references and
  raw nonboolean acknowledgments. Table-local insert guards and explicit boolean
  constraints corrected them.
- Final independent review found raw SQLite reviewer values `anonymous`, `0.5`
  and `1.5` accepted by integer affinity/positive comparison. Three actual RED
  failures (`DID NOT RAISE`) reproduced the defect. The SQLite integer-type CHECK
  is the minimal fix; raw insertion tests now exercise it.
- Final combined targeted storage/binding/domain run **84762: 208 PASS /1 SKIP /
  68.08s**, exit 0. The SKIP is actual PostgreSQL TRUNCATE, not a local success.
- Fresh exact CI-context Ruff (including existing probe scripts), changed-file
  format and D: bytecode compile: PASS. SQLite/PostgreSQL model DDL compilation
  confirms `typeof` appears only in SQLite.
- Fresh owned `D:/Codex-Recovery/content-studio-20261008/illustration-storage-owned-final.db`
  absent-target guard, upgrade head / check / downgrade base / upgrade head /
  check: PASS, no drift. No existing database reused.
- Frontend **205 PASS**, format and TypeScript/Vite production build PASS. No
  frontend source changes. Scoped restored Overview screenshot is separate from
  a full browser/eight-section UI gate; see CURRENT_STATE.md and QUALITY_GATES.md.
- Final independent read-only review: no remaining actionable Critical, Important
  or Minor findings in storage-only scope. Reviewer executed no tests; local
  suite evidence is from the main verification process, not inferred from review.
- Full corrected-source backend run **45505: 1612 PASS /1 SKIP /294.32s**,
  exit 0, actual isolated Telethon 1.45 and D: temporary/bytecode storage. Earlier
  full run **85602** started before the final reviewer-type fix and does not prove
  the final candidate: **1609 PASS /1 SKIP /280.89s**, exit 0.
- Strict create-only PostgreSQL CI now includes `test_illustration_review_storage.py`.
  Actual new-source PostgreSQL/Compose evidence remains pending commit/push and
  its exact CI. Existing target/namespace/role restrictions and checks unchanged.

## Previous checkpoint and external acceptance

Resolver source `44fb130ab0dda51e9910f05e08d106e3d96077a8`, exact CI
`37798052676`, all eight jobs SUCCESS at fresh inspection. This is preceding
source proof, not new uncommitted storage acceptance. Fresh Windows Docker read
still reports the absent `dockerDesktopLinuxEngine` pipe. Current Windows
acceptance remains NOT VERIFIED / BLOCKED BY ENVIRONMENT, not an implementation
failure. Required live Telegram authorization and real-model qualification remain
independent pending gates. PHASE 1 is not complete.

## Next boundary

Local corrected-source full gates are complete. Inspect the exact new-source
PostgreSQL CI before promoting storage beyond offline verification. Then implement
transactional canonical review/revocation and
audit only behind trusted server-side reviewer authentication; never accept a
reviewer ID/provenance/client hashes as authority. Preserve clean-session rules,
idempotency, stale-decision fences and all existing holds until the authenticated
workflow and fresh preflight/transport acceptance have their own evidence.
