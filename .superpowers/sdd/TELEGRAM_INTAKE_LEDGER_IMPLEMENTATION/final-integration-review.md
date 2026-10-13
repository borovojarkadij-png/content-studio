### Spec Compliance

Compliant for the durable intake ledger increment, range `8fc3c9d..e2f9665`.

- Models, migration guards and repository contracts agree on identity, signed64 bounds, canonical payloads, immutable history and carry advancement.
- Recording requires a clean explicit caller transaction, locks mapping→stream, validates prior evidence, inserts the window before advancing carry, and leaves transaction ownership with the caller.
- Replay recomputes the accepted kernel using original carry. Load uses one coherent joined snapshot.
- CI appends both requested modules while preserving existing coverage.
- No caller, worker, policy, UI or publication activation appears in this increment.

### Strengths

- Strict bounded decoding and full canonical result comparison reject corrupted evidence: [intake_selection_ledger.py:186](C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend/src/newsflow/services/intake_selection_ledger.py:186).
- Migration retention, replacement protection and guarded downgrade align with repository ordering: [migration:154](C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend/alembic/versions/c9d45e37f201_add_telegram_intake_selection_ledger.py:154), [repository:272](C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend/src/newsflow/services/intake_selection_ledger.py:272).
- Native concurrency tests use independent backend PIDs and actual PostgreSQL blocking evidence: [PostgreSQL tests:58](C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend/tests/test_intake_selection_ledger_postgres.py:58).

Independently verified actual evidence:

- PostgreSQL log/JUnit: **18 PASS, zero failures/errors/skips**, comprising seven schema, ten repository and one sampling-version case. All 18 namespace names match the receipt; recorded retention is 2082→2100 with public catalog unchanged.
- **332/332 PostgreSQL source hashes and 331/331 package hashes match current files.** HEAD is `e2f9665580574c5d61ec642bd34bfdb1b73355cd`; backend/workflow diff against it is empty.
- Package receipt confirms build/smoke native0, image `3fb1d00d…`, network none, read-only, no volumes/secrets. Smoke script and log support literal selection, fractional carry, rollback and fresh-process replay.
- Restart receipt and all three independently hashed logs agree: native0/0/0, same image/container, carry20→50→50 and windows4→5→5. Synthetic REJECT/false and zero jobs/usage/outbox remain asserted.
- All seven verification-document evidence hashes match their actual files.

### Critical

None found.

### Important

None found.

### Minor

None requiring action.

### Assessment

**Scoped implementation: Approved.**

No cross-task defect found. Approval covers this comparison-storage increment; it does not certify durable ingress, targetmix, live authorization or PHASE completion.

**Outstanding release gates:** full backend completion and exact new hosted CI. No backend completion receipt existed at review time, so this review makes no full-backend PASS claim.

Read the complete design, two-task plan, progress rulings, verification record and 3,807-line diff package through EOF. Additional reads were limited to the kernel dependency and specified evidence/controllers. No tests rerun, source/index/HEAD mutations or helper agents.
