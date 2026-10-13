### Spec verdict

Compliant for the durable Telegram sampling increment. Reviewed the complete 4,796-line, 251,082-byte package for `f0ff9336b718cdee1b22594d77233316bf5bd712..fa3564d987f2a9e6414a98b8a0d4cecb24574422`, including all five commits, requirements, ledger rulings, implementation reports and scoped reviews.

### Strengths

- The additive schema preserves job identity, terminal states, monotonic counters and retained source associations. Its migration prevents destructive replacement/deletion and refuses populated downgrade before DDL: `backend/alembic/versions/b8c34d26e190_add_telegram_engagement_sampling.py:116`.
- Schedule advancement uses actual publication age, counts only unfulfilled elapsed thresholds and rejects early or overflowing schedules: `backend/src/newsflow/domain/engagement_sampling.py:18`.
- Admission and claim selection have explicit bounds. Claims commit attempts and ownership before provider execution; acquisition and finalization consistently use incoming→job→account lock order: `backend/src/newsflow/services/telegram_engagement_sampling.py:65`, `:111`.
- Success and failure paths revalidate ownership, lease, session, user and current source permission. Final clocks are sampled after lock acquisition; SQL failures preserve the committed recovery lease: `backend/src/newsflow/services/telegram_engagement_sampling.py:217`, `:301`, `:342`.
- The tick remains default-disabled, delegates durable authority to the runner, and requires the existing cipher/credential path when enabled. Worker changes preserve independent work and private interruption logging: `backend/src/newsflow/services/telegram_engagement_tick.py:37`, `backend/src/newsflow/worker.py:567`.
- Tests exercise migrated persistence, independent PostgreSQL connections, native SQL rollback failures, stale ownership, restart recovery and the REJECT→rewritefalse→zero jobs/calls boundary. CI adds the sampling PostgreSQL module once without removing prior checks: `.github/workflows/ci.yml:249`.

### Issues

Critical: None.

Important: None.

Minor: None.

### Integration assessment

The schema, schedule, runner and worker agree on step advancement, attempt resets, terminal retention, private outcomes and cursor ownership. History and job advancement share one transaction; aggregate collection introduces no editorial, rewrite or publication authority.

One focused outside-diff check addressed the configured-provider integration risk: `backend/src/newsflow/services/telegram_provider_factory.py:70–189`, `:226–232`. Its account/peer loading transaction closes before delegation; encrypted session and peer persistence use separate guarded transactions. The new runner conservatively rejects finalization when ciphertext changes. This check did not re-review the underlying historical adapter implementation.

Independently inspected retained acceptance evidence:

- PostgreSQL: JUnit confirms 20 tests, zero failures/errors/skips; receipt records native exit 0, 2,062 retained namespaces plus 20 fresh namespaces and unchanged public catalog.
- Packaged runtime: build/smoke native exits 0 on image `42365d5f4eab…`; actual smoke records six observations, one missed window, separate-process recovery, terminal replay without IO and zero rewrite jobs/calls.
- Container restart: the same fresh owned container completed three starts with exits 0/0/0; encrypted fixture/configuration remained readable, expired recovery made one fake provider call, and subsequent reopen made none.
- Combined backend: raw output and JUnit agree on 3,801 passed, 76 explicitly skipped, zero failures/errors. Skips remain classified as environment/contract exclusions, not passes.
- All 324 packaged input hashes match current files. All 12 PostgreSQL-tested source/test inputs also match packaged hashes; the thirteenth PostgreSQL receipt input is the subsequently changed CI workflow.

No tests were rerun; no source, index or HEAD changes were made.

### Assessment

**Increment quality: Approved.** No cross-task correctness or integration defect was found. The reviewed increment is ready for the authorized exact-generation push/CI gate.

This is not whole-branch merge approval or PHASE/live qualification. Exact-generation CI, the historical PHASE branch review and operational qualification remain separate outstanding gates.
