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
