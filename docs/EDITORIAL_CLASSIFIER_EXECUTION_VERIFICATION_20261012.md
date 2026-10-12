# Durable diagnostic execution verification — 2026-10-12

Status: CORRECTED LOCAL/ACTUAL PG PASS / REVIEW ACCEPTED / CI PG DEADLINE CORRECTION PENDING.
Repository borovojarkadij-png/content-studio, branch codex/dark-navy-ui.
Task baseline e8b761728c6630473620adb04b518b8262c2283b.
Implementation contract: EDITORIAL_CLASSIFIER_EXECUTION_IMPLEMENTATION.md.
Original source c9c16d122ba6b3cee5bd6a3a157d72ca41268166;
accepted correction e29779b7a570f850e51e542fcc50e77c68c06dd6;
root evidence commit388cb3cc92490ad8f8a9cd8106308863b1b5100e pushed and remote-ref
verified. Exact CI38304194927 completed CANCELLED:8SUCCESS/1PGdeadlinecancel,
not whole-run accepted.

Its exact remote backend now2468 PASS/11 explicit PG-only SKIP/545.67s,
lint/compile/migration/no-drift PASS. Root read native terminal and downloaded
new benchmark artifact11772106662:24/24/calls0/no qualification. StrictPG job
canceled by old ten-minute deadline after continuous progress to91%; no terminal
PG pass or concurrency execution is claimed. Full new-source acceptance awaits
the bounded CI-budget correction and exact subsequent run; see CI_RECOVERY.

## Original independent review and subsequent correction

The complete2243-line BASEe8b7617..c9c16d1 task diff was independently reviewed.
Spec compliance FAIL / task quality Needs fixes: one Important lease-clock
finding, no Critical/Minor. _finish samples time before a blocking row lock;
_check can authorize IO using time sampled before canonical SQL validation.
If the wait crosses expiry, the old worker can finalize or classify after its
lease has expired. Original writer completed fix round1 and deterministic regression.
The original green suites below do not invalidate the finding or prove amended
source. Covering correction tests, actual fresh-PG regression and scoped
re-review have now completed below. No unrelated whole-suite rerun
is required for the narrow fix; exact amended remote full CI remains required.

## Frozen local gate and provenance

One complete writer-owned frozen backend suite actually terminated native0:
2462 PASS/7 explicit PostgreSQL-only SKIP/444.14s, no warnings. Root read the
original native terminal summary and verified its hash, not a repeated suite:
D:/Codex-Recovery/content-studio-20261008/editorial-execution-full-6d5a38802c234c85baab8f2db0d707e7/native.log,
SHA256084A9BF09531B413BE6BEE5DF7E77F75BE3D000D1CA28B1AAB34E1B12E00AC36.
Root also rechecked all9 frozen source/test/migration/CI files unchanged after
commit. Writer report SHA25675E1E3F20400109FB5F9DD6065A8EBC581FD22F588B562FFDB36196406CC9A1B.

Root inspected original behavioral RED(native1, QUEUED0 vs REVIEW1) and
covering534 PASS/1 SQLite PG-only SKIP/85.53s/native0 logs/hashes. Detailed
commands, static native0 gates and preserved corrected iteration failures are
in the committed SDD task-1-report.md. Windows long-nodeid setup errors, invalid
usage provider TypeError RED, missing test path/native4 and tooling typos remain
failures in that chronology; final GREEN does not rewrite them.

The7 local skips are1 new controlled PostgreSQL claimant test,1 historical real
TRUNCATE guard and5 historical planner/media concurrency controls. The new test
passed in root's actual120-case PG gate below. Existing six have prior actual-PG
proof and remain in exact new-source CI; local skips themselves stay skips.

## Acceptance boundaries

This runner executes diagnostic classification, not approval propagation.
No diagnostic PASS can change editorial permission, create a RewriteJob or
publish. Actual model accuracy/qualification and live authorization remain
separate. Tests use synthetic source content and injected classification only;
no real provider credential, Telegram session or operational queue is involved.

Root must inspect the frozen native full-suite evidence, independently review
the complete task diff, execute the new strict migrated Windows PostgreSQL
cases and track this task's exact new remote CI. Prior admission or adapter
results cannot substitute for these checks. Ordinary test failures must remain
recorded with their correction and actual rerun result.

## Actual Windows PostgreSQL scope prepared

The previously owned synthetic container is running and healthy:
4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e,
project newsflow-verification-unattended-win-20261008a, service postgres.
Only loopback127.0.0.1:5432 is exposed. The sole persistent mount remains
newsflow-verification-unattended-win-20261008a_postgres_data at
/var/lib/postgresql/data. Engine29.8.0 actually responds.

Before this task's PostgreSQL tests, read-only baseline:1523 unattended UUID
schemas, maximum namespace OID1148480. New writes must use freshly created,
validated UUID namespaces through tests/unattended_postgres.py. No old schema
reuse, DROP/reset, original manifest replacement or public migration is allowed.
Retained application fixtures and operational services are not test targets.

## Actual Windows PostgreSQL runner gate

Root checked all9 writer-frozen source/test/migration/CI SHA256 values before and
after the run; no code changed during execution. Strict opt-in
NEWSFLOW_UNATTENDED_POSTGRES_URL targeted the validated existing synthetic DB;
temporary environment restored in finally. Actual Python3.12/Telethon1.45,
pytest -q -ra tests/test_durable_editorial_runner.py with unique D: temp/cache:
120 PASS/86.96s/native exit0, no skip or warning. The previously SQLite-skipped
controlled independent-claimant case really executed on PostgreSQL.

Native log:
D:/Codex-Recovery/content-studio-20261008/editorial-execution-root-pg-4b7ffd71be514c50abc3972a470795d7/native.log.
SHA256A252A7E6F4A007F762038C0CA9D12D76717F320857EAA7E2F7DD11ED5B58F6BB.
New namespace count101; retained total1624/maxOID1232970. No older schema was
reused or migrated and no real credential/provider/Telegram operation occurred.

## Actual claim/receipt PostgreSQL restart and double reopen

Root's bounded read-only evidence probe:
.artifacts/editorial-execution-20261012/pg_restart_probe.py,
SHA25692F50DEED96DB2D0CB62F36F3F5A0CC29D57BE5EED2F2B927C402CEB32B5DD76.
It validates exact synthetic database/user, all101 new UUID namespaces above
OID1148480, migration head f6a42c91b805, and snapshots all rows in11 fixed tables.
Probe lint/format/help passed after removing one unused noqa and formatting;
those orchestration corrections did not change production source or tests.

Snapshot -> exact owned docker restart --timeout10 -> healthy -> two fresh
independent read-only probe processes: all native exit0 and identical manifest.
Container StartedAt changed19:43:56.680752414Z ->20:10:17.755334231Z.
Manifest:
D:/Codex-Recovery/content-studio-20261008/editorial-execution-pg-restart-20261012a.json,
SHA256458DB7405B743D6E0E1F47DC55727B6AA432B30E90499B2BC9813018A77DD3F0.

Preserved103 jobs,78 immutable claims,73 append-only receipts (4 with observed
usage),103 editorial decisions,104 source revisions,102 fingerprint bindings,
100 policy rows and279 outbox events. Job states:3 QUEUED/4 RUNNING/44 BLOCKED/
16 FAILED/1 REJECT/35 REVIEW. Receipt outcomes:18 BLOCKED/14 FAILED/2 LOST_LEASE/
1 REJECT/3 RETRY/35 REVIEW. Rewrite usage remains0. The single existing RewriteJob
was deliberately seeded BLOCKED by the existing-work negative-control fixture
(test_durable_editorial_runner.py, change="rewrite"); the runner/probe did not
create it. Probe DB writes0/provider calls0.

This proves this new schema/history survives actual Windows Docker PostgreSQL
restart; it is not later application-image/main-loop/live-provider acceptance or
external exactly-once IO. Independent review and exact new-source CI still
need their own terminal verdicts.

## Fix round1 — fresh lease clock after waits

Original review finding reproduced before correction:5 FAIL/1 PASS/native1,
with actual unexpected factory/classifier IO and incorrect finalization after
expiry. Root read the original RED summary; raw log SHA256
E0DF0FA5CA438E8677736DA1170FA3B98DB1BCA545E794C57D060A54A13B11B5,
D:/Codex-Recovery/content-studio-20261008/editorial-execution-fix1-red-23a6c6bfdd284222a9a70b4b3bca0028/native.log.
Corrected focused SQLite6 PASS/native0; covering runner/adapters/contract326
PASS/5 explicit PostgreSQL-only SKIP/41.65s/native0. Root read the native covering
log/hash7B7BCFA7662E202BF9D2BDABC1EF26FD33A02A604A0B1D355729F639BEC074D1.
One old competing-claimant plus four new held-row cases are the SQLite skips;
those cases are not represented as local passes.

Root independently executed the10 new selected regressions on actual strict
Windows PostgreSQL, including all four held-row review/reject/retry/blocked
outcomes:10 PASS/120 deselected/7.58s/native0/no skips or warnings. Events plus
observed pg_blocking_pids prove the finalizer really waits on an independent
transaction before injected time advances. Also covered canonical-check and
closed-session expiry before factory/classifier IO, finalization expiry and
unchanged exact receipt replay. Zero real provider calls.

Validated the exact original synthetic container/mount/health before execution;
fresh UUID schemas only:1624/maxOID1232970 ->1634/maxOID1241341. Original schema
history/manifests remain retained, no reset/reuse/cleanup or operational writes.
Environment restored in finally. Frozen runner SHA256
A7327B9E5F7251ABF42DAD35760E8FC7F902C0925CE505ADB17DADA1451ACC3E and runner-test
SHA256990369208D2D04CC461314A09E904CD98B918A22571BD041EE99E2FB60CBCAC7
were checked unchanged before and after actual PostgreSQL tests.

Root native log:
D:/Codex-Recovery/content-studio-20261008/editorial-execution-fix1-root-pg-26790f6ce24b4e798dce486945f6f4cc/native.log,
SHA2561B06422483B2383334D67413BCA2D277C6896A774AF4774A9A297272F38855C5.
No unchanged whole-backend/restart/UI suite repeated. Original full2462 gate
continues to identify c9 source, not amended bytes. Scoped fix re-review passed
below; exact amended-source remote full CI remains pending.

## Independent scoped correction acceptance

Fresh independent reviewer read the32981-byte c9..e297 fix package throughEOF,
brief and appended report. Original stale-clock finding ADDRESSED; scoped spec
PASS/task quality APPROVED; no new Critical/Important/Minor or out-of-scope
observations. Root read the complete review report:
.superpowers/sdd/EDITORIAL_CLASSIFIER_EXECUTION_IMPLEMENTATION/task-1-rereview-round-1.md.
Original review report remains retained rather than overwritten. The reviewer
did not repeat reported tests or infer an amended full-suite result. Root
confirmed all9 final source/test/migration/CI hashes, exactly two changed from
the original freeze. Final report SHA256
7B614EC29F82910EFE5B28289C5D6F345F17C0D8BDFA9B263247DAA0BAA6ACE8.
This accepts the corrected diagnostic seam locally; exact new-source CI and
later main-loop/application/live acceptance stay separate.

## Remaining acceptance gates

- Original RED, covering/static and frozen complete backend native evidence:
  PASS/inspected as above. Explicit local PostgreSQL-only skips remain skips.
- Actual strict migrated Windows PostgreSQL runner tests and retained-history
  restart/double reopen: PASS as detailed above, not a pending gate.
- Independent task-scoped spec/quality: original Important corrected, scoped
  re-review PASS/APPROVED as above; no open finding.
- Root-owned documentation, exact commit/push and new nine-job CI evidence.

PHASE1 is not complete. No runtime activation, automatic approval, live model
qualification, real provider call or publication is claimed by this document.
