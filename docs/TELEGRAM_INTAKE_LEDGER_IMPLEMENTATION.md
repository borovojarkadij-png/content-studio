# Durable Telegram Intake Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task-by-task. Steps use checkbox syntax.

**Goal:** Persist bounded ranked comparison windows and transactional carry for replay/audit without granting work authority.
**Architecture:** Two retained tables and a caller-transaction repository around the verified pure kernel; no current caller activation.
**Tech Stack:** Python3.12/SQLAlchemy/Alembic/SQLite/PostgreSQL/pytest; no new dependency.
**Spec:** docs/TELEGRAM_INTAKE_LEDGER_DESIGN_20261013.md

## Global Constraints

- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch codex/dark-navy-ui; no main merge/force-push/PR.
- Telegram-only, accepted dark-navy UI unchanged, synthetic data only. No real credentials/login/provider calls/sends/operational queues/volumes/data.
- REJECT→rewrite_allowed=false→no new RewriteJob→rewrite calls0. Comparison selected=true is never authority.
- One source writer; no helpers/reviewer spawning. Root owns docs/evidence/CI/runtime gates, writers own only task files and own report.
- No API/worker/config/ingestion/planner/editorial changes or policy activation. No speculative dependencies or skipped/disabled assertions.
- Exact generation/frozen evidence, D: TEMP/TMP/basetemp. PostgreSQL namespaces are create-only UUID synthetic targets, never public/drop/reseed.

### Task 1: Retained comparison schema and guarded migration

**Files:** Modify backend/src/newsflow/persistence/models.py only to add the two spec classes/imports; create backend/alembic/versions/c9d45e37f201_add_telegram_intake_selection_ledger.py and backend/tests/test_intake_selection_ledger_migration.py. Modify ONLY the retained-version assertion in test_telegram_sampling_migration.py and test_telegram_sampling_postgres.py as described below. Own task-1-report.md only.
**Consumes:** Existing Base/channel_mappings, current Alembic head b8c34d26e190 and sampling migration/test conventions.
**Produces:** TelegramIntakeSelectionStreamModel and TelegramIntakeSelectionWindowModel exact fields/constraints/triggers from spec. No repository/caller yet.

- [ ] Fully read spec storage/transaction constraints and actual current head/models/relevant migration fixtures. Confirm single head before writing; no existing row backfill.
- [ ] Write actual behavioral RED against migrated raw SQL, not nonexistent-import collection error. Example desired invariant:
```python
with engine.begin() as connection, pytest.raises(DBAPIError):
    connection.execute(text("UPDATE telegram_intake_selection_windows SET carry_out=99"))
```
  First temporary discovery test may assert inspect(engine).has_table(...) is True; retain its RED separately, then implement declarations and demonstrate an actual immutability/state refusal RED before adding guards. Synthetic seed helper must create mapping/account/donor/output in a migrated isolated store; no prod URL fallback.
- [ ] Add only two models and exact guarded migration from spec. Portable/SQLite-specific checks reflected in metadata with ddl_if as existing conventions. No type/affinity assumptions. Initialstream carry0/sequence1; immutable policy/identity; exact nextwindow linkage before streamadvance; immutable windows including no-op and OR REPLACE; parent/missing/duplicate guards; downgrade refuses any history before DDL.
- [ ] Parameterized tests cover malformed/uppercase/NUL/blob hashes, invalid IDs/carry/sequence/payload/time, streamnoninitialinsert, changed identity/policy/created_at, missing/existing replacement, invalid window sequence/carry, updates/noops/deletes/replacements, missing linked window atadvance and wrong carry. Valid window insert then streamadvance succeeds. Snapshot JSON semantics are repository responsibility, not schema algorithm proof.
- [ ] Prove upgrade/reopen preserves old source/REJECT/false decision and zero rewrite_jobs/rewrite_usage/outbox_events; monkeypatch provider rewrite to forbidden. Empty downgrade/re-upgrade/check passes; nonempty downgrade raises preserving tables/history/head. Migration autogenerate/check should find no drift; no original data mutation.
- [ ] Existing sampling migration/PG populated-downgrade tests currently hardcode previous head b8c34d26e190 despite upgrading to head. Capture version before attempted downgrade and assert the identical version afterward, preserving their job/state/assertions. This is a necessary new-head compatibility correction, not a relaxed rollback guarantee. No other existing assertion changes. Record any observed old-head failure before correction.
- [ ] Run new migration cases plus targeted existing sampling/configuration/runtime migration tests once; Ruff0.17 check/format, compile, migration check and diff. Use Python3.12/Telethon1.45 overlay where pytest shared conftest needs it. No full backend/Windows backup/resource/container/PG gate repeated by writer.
- [ ] Self-review/freeze owned source hashes, exact commands/native exits/RED/intermediates/GREEN/no-skips-or-explicit-skips/limits in own report. Commit only five named product/test files plus own report; return DONE/commit/onelinechecks/concerns. Root independently scoped-reviews before Task2 source ownership.

### Task 2: Transactional bounded window repository and concurrency contracts

**Files:** Create backend/src/newsflow/services/intake_selection_ledger.py, backend/tests/test_intake_selection_ledger.py and backend/tests/test_intake_selection_ledger_postgres.py. Own task-2-report.md only. Task1 models/migration are consumed unchanged; any required correction goes back through root to original writer.
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
- [ ] Run focused new repository+kernel/migration tests then covering existing durable ingestion/editorial/filter/sampling/hype suite. Run one combined backend checkpoint at end only if root releases frozen source/fullgate; no writer repeated fullsuite. Ruff/format/compile/diff. Freeze all owned hashes; own report exact evidence/native exits/limits; commit only three files/report. Root actual PG/installed package/reopen/final review/exact CI follow.
