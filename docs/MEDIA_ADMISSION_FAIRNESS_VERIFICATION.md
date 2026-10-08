# Bounded fair automatic media admission

2026-10-08; branch `codex/dark-navy-ui`; parent
`351b137aaa90ae3682973dbe88844d428bfdaa71`; correct origin
`borovojarkadij-png/content-studio`.

## Actual defect and implementation

Old automatic admission selected the first N READY/SCHEDULED rows without jobs
on every tick. Rejected/stale rows stayed eligible for that coarse query but
failed fresh guards, so later valid rows could never receive a job. Real SQL
fixtures reproduced the missing fair-window behavior; actual seven-iteration
main-loop tests reproduced seven IDLE outcomes instead of reaching the later row.

Both licensed illustration and declared-rights source-photo admission now scan
at most 16 candidate IDs per ordinary worker tick (explicit windows allow 1..100).
Typed windows expose scanned/blocked candidate IDs, queued job IDs and the last
scanned candidate cursor. An empty tail wraps to zero on the following tick,
not an unbounded same-tick loop. The count-returning `enqueue_pending` contract
is preserved for existing explicit consumers.

Main owns two independent scan states for internet illustrations and original
photos. Admission advances before provider execution; a provider crash cannot
reset scan progress. This is only transient enumeration state, not queue truth:
job identities, leases, attempt budgets, bytes, rights and outcomes stay in SQL
and persistent media storage. Restart starts a bounded rescan, never resets jobs.

Every enumerated ID still passes existing fresh editorial/source/review/policy
binding. Original photos still require the current versioned mapping's explicit
OWNED/PERMISSION rights. A rights revocation or editorial reject after enumeration
is rejected before job creation or provider access. Any historical job of that
candidate/mode excludes automatic re-admission, even after a changed draft; no
terminal/exhausted history is implicitly retried or erased. Existing explicit
API operations retain their own fresh guards; this does not add a retry API.

## Evidence

- Dedicated core regressions reproduced missing window method RED -> GREEN.
- Actual main-loop regressions reproduced repeated first-page IDLE RED -> GREEN.
  Both media paths can run together: library wrap cannot reset source-photo scan.
- 28 dedicated regressions PASS: 100 rejected earlier rows, late valid admission,
  independent SQL reopen, finite wrap, canonical cursor/limit rejection before
  DB access, disabled inert state, retained BLOCKED/FAILED/NO_MATCH history,
  post-scan reject/rights revocation and provider-crash committed attempt.
- 41 combined media/Overview/wait-probe regressions PASS (42727).
- Full backend before the separate PG correction: 1039 PASS (79452), 94.66 s.
  Fresh complete combined tree after correction: **1040 PASS (83958)**, 97.87 s.
- Exact CI Ruff command PASS; all six changed Python files format check PASS.
- Standard in-place compile hit ENOSPC for one C: bytecode output; rerun with
  `PYTHONPYCACHEPREFIX=D:/Codex-Recovery/content-studio-20261008/pycache-2058`
  completed PASS. This is not proof that Windows storage has been repaired.
- Explicit fresh D: Alembic upgrade/check/downgrade/base/re-upgrade/check PASS
  (42727); no schema change, operational DB never targeted.

All providers/files in tests are isolated synthetic fixtures. No Telegram login,
real download, paid rewrite, send or operational flag activation. Protected reject
fixtures create no RewriteJob and no RewriteUsage; media admission spends no
provider attempt. Previously retained history is not deleted.

## Limits and next step

Current Windows Docker remains **NOT VERIFIED / BLOCKED BY ENVIRONMENT**. Exact
new commit GitHub CI is pending; Linux success is not current Windows evidence.
No new UI or frontend behavior; its previous actual 97-unit/28-browser gate is
preserved and CI will execute it again.

The same first-page starvation pattern remains in semantic-verification
admission for old PENDING drafts failing fresh source/editorial/release bindings.
Next: reproduce it with real SQL, then bounded fair semantic admission and
default-disabled worker/main-loop state, preserving qualified fixed release,
per-output evidence and exhausted/terminal histories. Never qualify a model using
these fixtures or enable operational network workers as tests.
