### Task 2: Transactional bounded window repository and concurrency contracts

**Files:** Create backend/src/newsflow/services/intake_selection_ledger.py, backend/tests/test_intake_selection_ledger.py and backend/tests/test_intake_selection_ledger_postgres.py. Modify .github/workflows/ci.yml ONLY to append the two new ledger migration/PG test paths to the existing unattended-postgres pytest command. Own task-2-report.md only. Task1 models/migration are consumed unchanged; any required correction goes back through root to original writer.
**Consumes:** Task1 models/guards, accepted domain.intake_selection API, existing unattended_postgres.create_postgres_namespace(raw) and explicit NEWSFLOW_UNATTENDED_POSTGRES_URL convention.
**Produces:** RecordedIntakeWindow, IntakeLedgerConflict, IntakeLedgerCorrupt, DurableIntakeSelectionLedger exact signatures/spec semantics. Repository called only from synthetic tests, no activation.

- [ ] Read full spec and actual Task1 schema/report. Test-first importability RED if needed, then literal behavioral RED against minimal declarations:
```python
rows = tuple(IntakeCandidate(i, "b"*64, i) for i in range(1,11))
with factory.begin() as session:
    value = DurableIntakeSelectionLedger(session).record_window(
        mapping_id=1, policy_binding_sha256="c"*64, window_key="a"*64,
        candidates=rows, policy=IntakeSelectionPolicy(50,"HYBRID"), now=NOW)
    assert value.result.selected_ids == (10,9,8,7,3)
    assert value.sequence == 1 and value.replayed is False
```
  Seed migrated synthetic account/donor/output/mapping1 and retainedREJECT; tests never fabricate approved source permissions.
- [ ] Implement strict validation/canonical size-bounded payload/duplicate-key-safe decoder and recomputation, session ownership and mapping→stream locking, original-carry replay/conflict, previous-window carry verification, insert-before-advance atomic sequence and honest corruption exceptions. No swallow IntegrityError/reset/default, SQL per-candidate or external IO. Exact snapshot and all counters/policy/hash/version/reasons must match recomputed kernel.
- [ ] Tests: three literal modes/100best30; int/float/permutation replay; four one-row30% windows produce0,0,0,1 quotas/carry30,60,90,20; replay old window after later commits does not advance. Changed input/policy binding conflicts preserve all rows. Rollback/fault afterinsert leaves no advancement/window; recreated session/reopen preserves exactresult. Invalidinactive/dirtytransaction, IDs/time/digests/tampered dataclasses, 1000accepted/1001rejected and fixed query budgets. Corrupt stored snapshot/hash/result/carry/version/linkedprevious/stream policy fails closed without changing history; use isolated corruption fixtures without claiming SQL guards are bypassable through public API. All cases assert REJECTfalse/zero rewritejobs/provider/usage/outbox.
- [ ] PostgreSQL-only contracts create fresh UUID namespaces through existing helper, retain all schemas. Separate connections/backendPIDs and condition/barrier events (no sleeps) prove same-window exactlyonecommitted decision/replay and different-window serialized fractionalcarry; rollback/contention and immutable rawSQL. Explicit missing URL is SKIP, never PASS. Writer writes tests but root owns actual Windows PG invocation after scopedreview.
- [ ] Existing unattended-postgres CI command explicitly lists test modules, so append tests/test_intake_selection_ledger_migration.py and tests/test_intake_selection_ledger_postgres.py without removing existing paths or changing any permissions, retries, timeout, skips or steps. Backend job already collects all tests. Verify YAML parse and retained command coverage.
- [ ] Run focused new repository+kernel/migration tests then covering existing durable ingestion/editorial/filter/sampling/hype suite. Run one combined backend checkpoint at end only if root releases frozen source/fullgate; no writer repeated fullsuite. Ruff/format/compile/diff. Freeze all owned hashes; own report exact evidence/native exits/limits; commit only four named product/test/workflow files plus own report. Root actual PG/installed package/reopen/final review/exact CI follow.
