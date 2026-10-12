# Whole-branch correction checkpoint — 2026-10-09

Scope: Telegram Content Studio, authorized branch `codex/dark-navy-ui` and
origin `https://github.com/borovojarkadij-png/content-studio.git`. No design,
operational queue, session, credential or publication activation changes.

## Baseline and review

Frozen baseline `7af4324cac284b8bd3085eecb80e14c166149ccc`, GitHub Actions
run37924345507: all nine jobs SUCCESS. Logs verify backend1929 PASS/1
PostgreSQL-only SKIP/433.72s, strict migrated PostgreSQL332 PASS/323.18s,
frontend243/format/build, existing browser33 and protected illustration browser1,
unattended full-stack1 PASS/4 deselected/354.31s and every recovery family.
Illustration job136 focused PASS/44.68s and actual packaged synthetic restart
acceptance passed. Visible runner deprecation warnings remain, not disabled.

Independent whole-branch risk review covers be730b8..7af4324,120 commits/412
files with explicit non-exhaustive line coverage. Four Important findings:

- I1: legacy per-output fan-out could create rewrite jobs without current
  eligible editorial evidence.
- I2: semantic verification could construct/call an AI provider after current
  technical filters changed.
- I3: encoded or scheme-relative custom-domain URLs bypassed host filtering.
- I4: planner candidate→editorial locks opposed media editorial→candidate locks.

One combined corrective wave and one scoped re-review are required. Baseline
success is not proof of that new code. Review and correction reports remain in
the plan-owned `.superpowers/sdd/ILLUSTRATION_REVIEW_IMPLEMENTATION/` workspace.

## Parent actual PostgreSQL RED

Before planner production changes, parent validated the existing synthetic
container identity, Compose project labels and loopback5432 mapping:
`newsflow-verification-unattended-win-20261008a-postgres-1`,
ID`4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e`.
The strict public synthetic target validator creates only fresh UUID namespaces;
no prior schema/fixture mutation, drop or cleanup is permitted.

From backend, explicit `NEWSFLOW_PLANNER_MEDIA_POSTGRES_URL` matching the
existing `unattended_postgres.py` contract:
`python -m pytest tests/test_planner_media_postgres.py -vv`.
Actual Windows Python3.12.10/PostgreSQL result: old-order deadlock control PASS,
current production order FAIL, SQLSTATE`40P01`;1 PASS/1 FAIL/4.91s, exit1.
This reproduces the reported lock inversion with two event-controlled concurrent
transactions, not a guessed deadlock or SQLite-only claim. Native evidence:
`D:/Codex-Recovery/content-studio-20261008/planner-media-red-20261009a.log`.
Failed test schemas and original evidence are retained. Corrected GREEN,
independent re-review and exact new CI remain pending. Parent requested stronger
actual lock-owning connection PID/timeout proof before final GREEN.

Subsequent corrected, strengthened harness: both lock-owning transactions record
their actual distinct backend PIDs at row-lock acquisition; each actual engine
connection has bounded15s lock/20s statement timeouts. Same explicit target,
fresh namespaces, no cleanup. Parent reran the full two-case command:2 PASS/
3.00s/exit0. Old-order control still detects SQLSTATE40P01, corrected production
planner completes with media NO_MATCH, one legitimate attempt/search, candidate
SCHEDULED and reservation PLANNED. Native evidence:
`D:/Codex-Recovery/content-studio-20261008/planner-media-green-20261009a.log`.
This supersedes pending GREEN, not the retained original RED. New dedicated CI
step is wired; its actual remote execution and scoped review remain pending.

## Remaining acceptance

October12 resume: residual5fa8995 independently ADDRESSED, no new scoped
Critical/Important/Minor. Full report residual-i4-rereview.md verifies all three
hashes and actual PG logs; current source unchanged. All original I1–I4 addressed,
not full PHASE/operational acceptance. Above1000 snapshot backlog refuses a tick
atomically, an explicit availability limit. Interrupted prior reviewer disappeared
without report/live agent, so only the missing review was resumed, not source work
or expensive suites. Docker restored after recurring runtime socket error;
DOCKER_STARTUP_RECOVERY_20261012.md retains narrow reversible procedure/evidence.
Retained c original-image startup/health/double original-state reopen passed
October12 exit0, runtime9de0045 unchanged. New exact CI pending.

Frozen residual full gate recovered from original writer process89870:
1989 PASS/6 explicit PostgreSQL-only SKIP/428.88s/exit0. Report contains complete
command/output and intermediate setup failure; three source hashes independently
match. Expanded targeted175 PASS/5 PG-only SKIP/32.13s; lint all src/tests/alembic,
changed3 format/compile/diff check PASS. Actual migrated PG and concurrency runs
cover default SQLite's six skipped cases. New scoped review/CI pending.

Exact prior source e1604efe99db1332702d0eed6ee2f2e861950dc0 CI37927968218
completed all9 SUCCESS. Actual logs: backend1984 PASS/3 PG-only SKIP/473.44s;
strict migrated PG332 PASS/326.50s and old concurrency2 PASS/3.05s;
frontend243 units/33 browser+1 protected-review browser; full-stack restart
1 PASS/4 deselected/342.06s; illustration136 focused and packaged pending
down-up/PG crash/fake execution/final down-up/double read-only reopen PASS.
The new residual concurrency cases were not present in this commit. Intentional
constraint/deadlock-control errors in PG container logs do not change actual
pytest successes; no failure waiver or disabled job. Visible runner warnings
remain. Historical candidate acceptance is not PHASE completion.

Corrected transaction-wide source: actual strict Windows PostgreSQL GREEN full
named harness5 PASS/6.50s/exit0; reconciliation/READY/mixed automatic pair and both
older controls. Original RED schemas/log preserved. Separate332-case migrated
PG completed332 PASS/423.04s in residual-postgres-20261009a.log. Corrected hashes
planner059fb675/harnessd234f762/guards6c46441f match the frozen report.

Fresh Windows Docker project newsflow-verification-illustration-win-20261009c,
ports18239/15396/18339: preflight PASS; build/migrations/health/authenticated review
and audit/encrypted snapshot/photo/pending down-up/PG crash/fake execution/final
down-up/no-drift terminal create PASS. Native D:residual-windows-build-20261009c.log.
Original runtime.json SHA2569de0045ca2fe24c0ab8f0187e759cbc6b6421e76b71b9cbd17c3057a76176e6a;
independent read-only reopen preserves it. No rebuild/reseed of retained c.
Intentional root turn interruption lost original65402/5591 process handles; both
native terminal outcomes are present and matching processes absent, but no
process exit code is invented. Subsequent fresh read-only double verification
completed PASS/exit0 in residual-windows-retained-20261009c.log. Original fixtures,
volumes/manifests preserved. Real RPC0/live SKIP, new source review/CI still pending.

Corrected transaction-wide source: actual strict Windows PostgreSQL GREEN full
named harness5 PASS/6.50s/exit0, including reconciliation/READY/mixed automatic
pair and both older controls. Native log
`D:/Codex-Recovery/content-studio-20261008/planner-pair-green-20261009a.log`.
Original RED schemas/log preserved; no existing fixture mutation/reset. Source
prelocks the bounded snapshot's jobs, editorials and drafts before shared
policy/release/candidate locks; late/rebound identities wait for another tick.
This successful test does not replace final source review/CI. Parent separate
332-case migrated PG covering run65402 is ongoing, native residual-postgres-
20261009a.log; final complete backend gate remains sole writer's responsibility.
Exact prior e1604ef CI37927968218 last snapshot7/9 SUCCESS, remaining two Docker
provider families still in progress; not residual proof or final completion.

Subsequent scoped review final-rereview.md: I1–I3 ADDRESSED; I4 NOT ADDRESSED.
Per-candidate ordering still reverses across loop iterations retaining a shared
automatic-policy row. This is a concrete residual, not a new distinct finding.
Root refuses I4 acceptance and records a human-autonomy ruling in the ledger:
continue one focused regression-driven correction despite SDD's administrative
one-final-wave cap, because the user explicitly requires ordinary bugs to be
fixed autonomously. No operational authority is expanded; cost is extra QA time.

Actual new PRE-FIX strict Windows PostgreSQL two-source AUTOMATIC tests, unchanged
f8 planner, same validated4c1a412 fixture, fresh UUID schemas: reconciliation,
READY and mixed all FAIL with SQLSTATE40P01; old/manual controls2 PASS.
Combined3 FAIL/2 PASS/13.23s/exit1, native evidence
`D:/Codex-Recovery/content-studio-20261008/planner-pair-red-20261009a.log`.
Actual lock-owning PIDs/timeouts/barriers are retained; synthetic semantic
evidence qualifies only test fixtures, never a real model. Original writer owns
the focused correction; new GREEN/frozen source/review/CI are pending.

Fresh Windows session30008 completed create/build/migration/no-drift/health,
authenticated review/audit/snapshot/photo setup, pending down-up and PG crash,
fake execution and final down-up PASS/exit0 on frozen f8 application source.
Subsequent read-only verify double reopen PASS; session86218 guarded original-
image validation then separate Redis/worker restart, health and two reopens
PASS/exit0. These post-execution restarts do not claim pending Redis-worker
boundaries. Runtime.json SHA256
`56d2f973d68fa6eac5a0b35fc0fe37dee6d78001cdd0f47114365e57b792da06`
remains unchanged. Original20261009a and unrelated loopback PG unchanged.
Native build log43063 bytes plus retained log on D: remain. Real RPC0, live SKIP.
New source after the residual fix invalidates affected image/source claims.

Parent documentation commit e1604efe99db1332702d0eed6ee2f2e861950dc0 pushed only
correct origin/branch. Initial403 was active thrixicpa-del, not successful upload
elsewhere. Existing authorized borovojarkadij-png keyring credential used only
in a temporary process/helper with API identity check; no persistent account,
credential or authorization changed, no token printed. Exact run37927968218
is in progress, not all-nine success and not residual proof.

Correction commit `f8aa00bbba59321f0a53c4bc206d8d76f08e83cc` contains only the
four-finding source/test/CI wave and its full report. Final backend1984 PASS/
3 explicit PG-only SKIP/397.90s, exit0; lint/changed8 Python format/compile and
fresh UUID SQLite migration cycle/no-drift PASS. Root checked final parser,
planner and concurrency-test file hashes match the frozen report; frontend diff
is empty. The three SQLite SKIPs are PG TRUNCATE and the two lock-order cases,
each separately exercised on actual PostgreSQL. Original full failure was
explicitly ABORTED, not a completed PASS or complete failure count.

One fresh scoped reviewer phase1_cross_task_rereview owns7af4324..f8aa00b,
package61903 bytes, report final-rereview.md pending. Root actual fresh Windows
preflight passed for new distinct project
`newsflow-verification-illustration-win-20261009b` (API18238/dev15395/prod18338);
source-frozen create/build/runtime session30008 is in progress. Original20261009a
fixture and unrelated loopback PG remain untouched. Native full output:
`D:/Codex-Recovery/content-studio-20261008/cross-task-windows-build-20261009b.log`.
New exact remote CI remains pending; no review/runtime success is inferred.

Continuation checkpoint: combined correction regressions182 PASS/2 explicit
PG-only SKIP reported by implementer, source lint/changed-file format/compile and
fresh UUID SQLite upgrade/downgrade/upgrade/check passed. The initial full suite
exposed an overbroad URL userinfo refusal against the existing unambiguous
`youtube.com@example.org` host-identity contract; this is a genuine compatibility
FAIL, not an accepted success. Writer owns the narrow correction, focused
regressions and final frozen full rerun; no completed source commit yet.
Parent independent332-test strict migrated PostgreSQL covering run is ongoing,
session38525, native log
`D:/Codex-Recovery/content-studio-20261008/cross-task-postgres-20261009a.log`.
Because its launch preceded the compatibility correction, treat it as
intermediate evidence until final source identity is reconciled. No remote new
CI or scoped independent review result is claimed.

Subsequent parent session38525 completed332 PASS/377.96s/exit0. Actual migrated
PostgreSQL covers the unattended vertical slice, isolated target guards, retained
album/fan-out/hidden-link holds, canonical illustration binding/storage/review API
and guarded publication. No missing-PostgreSQL SKIP occurred in this opt-in run.
Its process imported the pre-compatibility parser, so retain it as intermediate
evidence for unchanged planner/storage/publication paths, not the final parser
gate. Final full backend75142 remains owned by the implementer; root cannot
poll that agent-scoped process ID and will reconcile its reported output/hash
before generating the scoped review package. No duplicate full suite is launched.

No PHASE1, live provider, real-model qualification or operational release claim.
Live Telegram credentials and explicitly designated test destinations remain
separate. After this correction wave, source-bound pre-rewrite classifier
contract/offline qualification harness remains the next independent increment.
