Refresh the lease clock after SQL waits and immediately before authorizing IO or finalization — ADDRESSED. `backend/src/newsflow/services/durable_editorial_runner.py:335` now reads the clock after the blocking job `FOR UPDATE`; `:372` refreshes it again after provenance SQL, canonical validation and assessment, and `:373` fences the owned transition. An expired claim produces LOST_LEASE without transitioning or releasing the job. `_check` refreshes ownership after canonical resolution at `:258`; `_before_io` checks expiry at the closed-session boundary at `:264`, and both factory and classify paths call it at `:278` and `:295`. Existing receipt replay still precedes ownership/expiry fencing (`:252` and `:340`), preserving exact stored outcomes and preventing repeat IO.

New breakage in the fix diff — None. The added finalization fence applies to REVIEW, REJECT, RETRY and BLOCKED, retains immutable claim provenance and late diagnostic usage, and introduces no SQL session or lock around provider construction/classification.

Out-of-scope observations — None.

Check — Read the complete supplied `review-c9c16d1..e29779b.diff` through EOF, the task brief, the appended fix report, and the scoped re-review instructions. Applicable AGENTS.md checks found no instruction files at repository/ancestor/affected-directory paths. No git diff was re-derived, no source crawl or test rerun was performed, and this report is the sole write.

Check — In `backend/tests/test_durable_editorial_runner.py`, the diff adds `test_expiry_during_canonical_sql_check_fences_io_and_finalization`, `test_expiry_at_closed_session_boundary_prevents_external_io`, `test_postgres_finalizer_waiting_on_row_lock_refreshes_lease_clock` for review/reject/retry/blocked, and `test_completed_receipt_replays_unchanged_after_lease_expiry`. These assert LOST_LEASE, unchanged job ownership and lease, exact claim provenance, zero classify calls when expiry precedes IO, retained known usage after IO, and no repeat classifier call on replay. The held-row tests observe `pg_blocking_pids` before advancing the injected clock and releasing the unchanged row.

Check — The appended report names the covering files, commands, native results and log hashes: behavioral RED 5 failed/1 passed; focused GREEN 6 passed; covering GREEN 326 passed/5 explicit PG-only skips/native0. Root independently reports the frozen amended PostgreSQL selection 10 passed/no skips/native0, including all four held-row cases. This re-review verifies that those reported selections cover the changed behavior; it does not independently rerun them or promote the historical c9 full-suite result to amended-byte acceptance. Exact amended remote CI/full-suite acceptance remains root-owned and pending.

Scoped spec compliance — PASS: the finding's required lease fences, regression coverage and exact receipt replay are addressed.

Scoped task quality — APPROVED: no new Critical, Important or Minor breakage identified in the fix diff.

Fix round — All findings addressed, no new Critical/Important breakage.
