### Spec Compliance

- ❌ Issues found: the required unexpired-lease fence can use an obsolete clock value after SQL work or a blocking row-lock wait. This can permit classifier IO or an owned terminal transition after lease expiry: `backend/src/newsflow/services/durable_editorial_runner.py:246`, `:255`, `:257`, `:287`, `:315`, `:324`, `:338`.
- ✅ All nine declared production/test/migration/CI file changes appear in the package, together with the required implementer report. The historical migration-test adjustment preserves the pinned roundtrip and performs metadata checking after upgrading to actual head: `backend/tests/test_editorial_admission_migration.py:62`.
- ✅ The new runner assesses actual bounded receipt evidence, ignores the classifier's returned verdict, and maps effective non-REJECT results to diagnostic REVIEW: `backend/src/newsflow/services/durable_editorial_runner.py:287`, `:356`. The integration regression checks the original MANUAL_REVIEW/false decision and zero new RewriteJobs: `backend/tests/test_durable_editorial_runner.py:68`.
- ⚠️ Cannot verify from this diff alone: historical RED/native logs, frozen-file provenance, actual Windows PostgreSQL execution/restart persistence, and new-source remote CI. The dispatch says the controller already checked the original logs, hashes, PostgreSQL120 and restart/reopen evidence; remote CI remains controller-owned and was not claimed as completed here.
- ⚠️ Cannot verify the entire shared-writer lock-order graph from this scoped diff. The focused resolver check below found no explicit additional row locks in the resolver body; this is not a whole-codebase lock-order proof.

### Strengths

- Immutable claim provenance is separated from the one-per-claim receipt; receipt and outbox insertion share the owned transition transaction: `backend/src/newsflow/services/durable_editorial_runner.py:324`, `:366`, `:378`.
- The additive migration guards SQLite replacement as well as mutation, guards PostgreSQL TRUNCATE as well as mutation, and checks both history tables before downgrade DDL: `backend/alembic/versions/f6a42c91b805_add_editorial_attempt_history.py:142`, `:153`, `:156`, `:160`.
- Independent committed source/policy/ownership changes are tested around construction and classification; session closure and real persisted rollback behavior have focused tests: `backend/tests/test_durable_editorial_runner.py:335`, `:706`, `:758`.
- Competing PostgreSQL claimants are synchronized with Events around an actual acquired row lock, without probabilistic sleeps: `backend/tests/test_durable_editorial_runner.py:799`.

### Issues

#### Critical (Must Fix)

- None found in this task-scoped review.

#### Important (Should Fix)

- **Refresh the lease clock after SQL waits and immediately before authorizing IO or finalization.** `backend/src/newsflow/services/durable_editorial_runner.py:315` captures `now` before the blocking `FOR UPDATE` at `:324`; `_owned` at `:338` subsequently compares lease expiry with that old instant. A separate transaction can hold the job row lock until the lease expires, then release it without changing the row. The old execution still passes `_owned`, writes REVIEW/REJECT (or another owned transition), clears the lease, and commits an immutable receipt, although the required result is LOST_LEASE with no job overwrite. The same stale-clock risk occurs in `_check` at `:246`–`:257`: ownership is checked before the canonical resolver finishes, and the caller can then invoke `classify` at `:287` after expiry. Read the clock after obtaining the row lock and after canonical validation, and check expiry at the closed-session boundary immediately before factory/classifier IO. Preserve exact receipt replay semantics. Add deterministic regressions that advance an injected clock while a finalizer waits on a held row lock and while a pre-IO SQL/resolver check runs; assert LOST_LEASE, unchanged job ownership, and zero classify calls for expiry before IO.

#### Minor (Nice to Have)

- None found requiring a separate change.

### Assessment

**Task quality:** Needs fixes.

**Reasoning:** The diagnostic permission boundary, append-only provenance, atomic storage failure handling, and synthetic regression coverage are well structured. The stale clock at the lease fences is a correctness defect in the explicit concurrency contract and should be fixed before approving this task.

### Review checks and scope

- Read the reviewer instructions, task brief, and implementer report; reviewed the supplied BASE `e8b761728c6630473620adb04b518b8262c2283b` → HEAD `c9c16d122ba6b3cee5bd6a3a157d72ca41268166` package through EOF (2,243 lines) in bounded chunks. Subsequent package scans extracted line anchors only; no changed source files or Git state were read separately.
- Named risk: adding a job lock around the accepted resolver could introduce an opposite source/configuration lock order. Focused unchanged-code check: `backend/src/newsflow/services/editorial_admission.py:110`–`:246`; the resolver body uses ordinary reads and canonical binding checks, with no explicit `FOR UPDATE` calls. No broader writer/helper crawl performed.
- Named risk: bounded malformed evidence might raise or provide unsafe reason text when reassessed inside the receipt transaction. Focused unchanged-code check: `backend/src/newsflow/services/editorial_classification.py:180`–`:327`; the accepted parser bounds nesting, rejects duplicate keys/constants/invalid encoding, and returns fixed manual reason codes for parse/schema/binding failures.
- Same named pre-lock-clock risk checked in both `_check` and `_finish` within the reviewed diff. There is no `_prepare` function in this implementation. `_claim_next` at `backend/src/newsflow/services/durable_editorial_runner.py:186` instead accepts explicit caller-supplied `now` and acquires job rows with SKIP LOCKED at `:203`; it does not have the same blocking-row-lock fence.
- No tests rerun, no provider calls, no database operations, no helpers/subagents, no source/index/HEAD/branch changes. Sole write: this review report.
