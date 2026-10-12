**FAILED/BLOCKED receipt coherence — ADDRESSED.** `backend/src/newsflow/services/editorial_history.py:242` now requires both outcomes to belong to the final attempt and match the job’s current state.

### Finding Verdicts

- **Malformed terminal histories fail closed:** ADDRESSED. Four regressions cover FAILED/BLOCKED receipts on QUEUED jobs and before a later attempt (`backend/tests/test_editorial_history.py:447`).
- **Legitimate retained histories remain readable:** ADDRESSED. Six controls exercise actual runner transitions, including receipt-less BLOCKED/exhausted FAILED histories and late LOST_LEASE receipts after terminal REVIEW (`backend/tests/test_editorial_history.py:490`).

### New Breakage in the Fix Diff

- Critical: None.
- Important: None.
- Minor: None.
- The production change only expands the existing terminal-outcome validation; it does not require receipts for legitimate receipt-less FAILED/BLOCKED jobs (`backend/src/newsflow/services/editorial_history.py:242`).

### Out-of-Scope Observations

- None.
- ⚠️ Exact final-source remote CI remains pending with root; this scoped review does not establish that gate.

### Verification Checks

- The appended report names covering tests and records behavioral RED, covering GREEN, targeted PostgreSQL GREEN, static checks, and frozen hashes (`.superpowers/sdd/EDITORIAL_DIAGNOSTIC_HISTORY_IMPLEMENTATION/task-1-report.md:183`). Root independently verified their provenance.
- No tests rerun, helpers dispatched, or checkout/index/HEAD changes made.

### Verdict

**Fix round:** All findings addressed, no new Critical/Important breakage.

**Updated spec compliance:** ✅ Compliant within the reviewed task scope; final CI remains root-owned.

**Updated task quality:** Approved.
