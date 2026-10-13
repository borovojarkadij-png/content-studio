### Spec Compliance

- ✅ Spec compliant. All requested files are present; the sole CI change appends the PostgreSQL test path once, preserving the existing invocation (`.github/workflows/ci.yml:249`).
- ✅ Projection validates inputs and policy before cold-start returns, reads fresh scalar columns under `no_autoflush`, limits target history to two eligible observations, and preserves explicit-clock freshness/staleness semantics (`backend/src/newsflow/services/telegram_hype.py:54–115`).
- ✅ Baseline implements the exact account/donor/publication/time filters, clamped 30-day boundary, deterministic descending order, 2001-row fetch, 2000-row processing prefix, chronological adjacency, and truncation receipt (`backend/src/newsflow/services/telegram_hype.py:118–164`).
- ⚠️ Actual PostgreSQL, packaged execution, and source CI remain controller-owned gates. The new PostgreSQL contracts are correctly present; this review does not claim their execution (`backend/tests/test_telegram_hype_postgres.py:21,48,72,115,140`).

### Strengths

- Read-only transaction ownership is explicit and tested against dirty/pending caller objects, forbidden flush/commit/rollback methods, SQL statement capture, and database read-only mode (`backend/tests/test_telegram_hype.py:259`; `backend/tests/test_telegram_hype_postgres.py:72`).
- Meaningful cases cover stale identity caches, cached snapshot edits, cold starts, unknown/reset/zero rates, independent messages, donor-size fairness, inclusive time boundaries, and deterministic truncation (`backend/tests/test_telegram_hype.py:193,231,301,325,347,363,428,439`).
- Only freshness and measured relative velocities are populated; unavailable evidence remains unknown (`backend/src/newsflow/services/telegram_hype.py:92–108`; `backend/tests/test_telegram_hype.py:113`).
- Named outside-diff risk checked: imported fixtures must enforce editorial/provider invariants. `seed`, `zero_rewrite_calls`, and `assert_preserved` retain synthetic source/revision, REJECT/rewritefalse, zero jobs/usage, and zero rewrite calls (`backend/tests/test_telegram_engagement_history.py:20,81,104`).

### Issues

- Critical: None.
- Important: None.
- Minor: None.

### Assessment

**Task quality: Approved.**

The implementation is focused, bounded, deterministic, and preserves caller transaction ownership. No source fixes are required; PostgreSQL and integration execution remain outstanding validation gates. No tests rerun or checkout mutations performed.
