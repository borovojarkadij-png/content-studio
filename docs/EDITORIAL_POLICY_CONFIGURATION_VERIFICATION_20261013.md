# Internal editorial-policy configuration verification — 2026-10-13

Status: SOURCE INDEPENDENTLY ACCEPTED; EXACT CANDIDATE CI PENDING;
NOT OPERATIONALLY ENABLED.
Repository borovojarkadij-png/content-studio, branch codex/dark-navy-ui.
BASE56f48999890db57c0b9c0741cad453eb23c35f0a. Requirements in
EDITORIAL_POLICY_CONFIGURATION_IMPLEMENTATION.md, own112-line SDD brief.
Sole /root/editorial_policy_configuration owns service/test/single CI list append
and own task report. Root owns this report/current-state/nativePG/remoteCI.

## Scope and boundaries

Internal existing-singleton configuration service, strict complete validation,
content-bound versions/legacy compatibility, optimistic ETags and exact raw-JSON
SQL CAS; atomic metadata-only outbox event. No schema/API/auth/worker/provider/
prompt/UI/Compose or actual policy/credential changes. Public operator controls
require separately implemented dedicated authorization. No configuration save
grants model qualification, editorial PASS, rewrite or publication permission.
Tests use migrated synthetic data and injected provider boundaries only.

## Root runtime precondition

Actual Engine29.8.0/Linux responds. Read-only ownership validation confirmed exact
container4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e,
/newsflow-verification-unattended-win-20261008a-postgres-1, postgres16-alpine,
project/service labels, sole persistent volume
newsflow-verification-unattended-win-20261008a_postgres_data at
/var/lib/postgresql/data and sole127.0.0.1:5432 binding. Ownership manifest owner
content-studio-unattended-v1/nonce205b74d7765f4055b1209a90de6a2935 matches.
pg_isready accepts connections; read-only inventory1785 retainedUUIDschemas/
maxOID1372163. No new root namespaces, migrations or data writes performed yet.
No operational stack startup or repeated recovery; prior manifests preserved.
Current freespace C13.30GB/D148.23GB, no cleanup/prune.

## Verification pending

Root read original behavioral red.log from
D:/Codex-Recovery/content-studio-20261008/
editorial-policy-task1-7cdf9988b7bd49deaeb0e420f3328396/:
1FAIL/0.66s, expected EditorialPolicyConflict did not raise for stale ETag on
actual migrated SQL. This is an unsafe in-test CAS seam reproducing behavior,
not absent-import failure. SHA256
0D9C6566660EDDDFCD88C89DCAA8850A7384041937A0D6C5240ECFD3889E6789.
Raw log has no native marker; actual native result remains writer-report owned.
Initial expanded focused-1.log ends90FAIL/4explicitPG-onlySKIP/33.55s;
ordinary implementation failures are being diagnosed by sole writer, not PASS.
No freeze/full/rootPG yet; preserve RED and intermediate failure history.

Writer first GREEN, independently read by root: focused-3.log91PASS/
4explicitSKIP(3PostgreSQL-only/1nonapplicableINSERT)23.26s; writer actual native0,
Telethon1.45.0 printed.
SHA256 AAB3A4D11773F9F7E3BA29FF4A6B0C8DBF90F8D3A4714FB367BF9810554AD0BB.
Additional actual behavioral red-edges.log2FAIL/93deselected1.01s/native1
reproduced raw SQLiteBoolean2 coercion and same-ETag/rawJSON CAS omission;
SHA256 D65957AA77B7A7AECB25E81884D29540D4436FAA7C6486839C602456DDC15FDB.
These failures precede the GREEN fixes. Static/focused combined gate, freeze,
full backend and actual WindowsPG are still pending, not inferred from this run.

Frozen after final combined368PASS/9explicitSKIP(8PG-only/1nonapplicableINSERT)
94.83s/native0,
Ruff0.17/full existing lint plus illustration lint/format/compile/YAML/diff0:
service FDB4C4CC50920D43E1A22E322CDEB66D0165AA518B3383F9250439DCEA8D0303;
test 23AA4060E9F52FAFC6369040E5E1C743A0D3BE79D84D489F6D22C78A6B575115;
CI 0874A52835D234315BF8BC8D1A829C8F63BB9D3E206A9DD6F95D51ED2244C68D.
Root verifies all three against current bytes and revalidates exact PG
ownership/manifest/onevolume/loopback/readiness/baseline1785|1372163 before IO.
Actual strict PG new-file session1460 is running in backend cwd, explicit
Telethon1.45, process-local synthetic URL/finally restore, create-only UUIDs,
unique D:/Codex-Recovery/content-studio-20261008/
editorial-policy-root-pg-286c57f6fe874862903deff524648e6c/.
Writer runs the sole full backend gate concurrently; no source edits while
gates run. At that checkpoint neither gate was PASS.

Root actual strict WindowsPG session1460 completed native0:
93PASS/2explicitSKIP53.41s. Both PostgreSQL race/arbitration parameterizations
and held-row lock case ran, not skipped. Only skips are rawSQLiteBoolean2
(PostgreSQL cannot store non-Boolean) and INSERT fault case when the scenario
is UPDATE-only. Fixtures create95 new UUID namespaces,1785|1372163 ->
1880|1451681; no drops/reuse/operational writes. All three frozen hashes
unchanged before/after, process-local target restored in finally.
native.log SHA256
036CC27F404481137EE6425C859D8895576D1F011D58CA64ADF0C75BBEFE5200;
exit.log PYTEST_NATIVE_EXIT=0, same unique root directory. Actual tool native0
independently inspected; no provider calls/sends. Full backend/review pending.

Sole full backend gate completed:2835PASS/15SKIP452.29s/native0, backend cwd
and explicit Telethon1.45.0. Root read native full.log terminal NATIVE_EXIT=0
and post-full-hashes.log; all three frozen hashes still match. Full log SHA256
F2919AF3DDE4EAC0A0E8DE2B926394018365C94938C6E51F6FE6E22A89D5EF68
in writer's unique evidence directory. No pytest warnings. Fifteen skips are
11 inherited PostgreSQL-only cases,3 new PostgreSQL locking/concurrency cases
and1 nonapplicable policyINSERT when testingUPDATE. New actual rootPG gate
ran all three new PostgreSQL cases; prior exact evaluatorCI638+5 covers inherited
unchanged PG tests, not a substitute for subsequent candidate CI. Corrected
earlier shorthand that labeled all focused skips PG-only. No second full run.
Final owned commit/report and fresh independent review remain pending.

Writer committed exactly service/test/singleCIappend/own201-line report as
c090eeb18d19fcb23f8238ad24e7a4698f112d38. Root read report through EOF,
corrected native-marker attribution and verified four-path commit inventory.
Complete56f4899..c090eeb review package64434bytes generated with absolute SDD
script, not HEAD~1. Fresh read-only /root/editorial_policy_configuration_review
(gpt-6.1-sol/high/forknone/nohelpers) reviews spec and quality; no repeated suite.
Not accepted before its verdict.

Fresh review returned spec compliant/task quality Approved, no Critical/
Important/Minor findings. Verbatim task-1-review.md retained. Root resolves its
provenance/gate warning: exact origin/branch/commit inventory were inspected,
original native RED/full/PG logs and three frozen hashes read above; no skipped
gate became PASS. Exact new-source CI remains pending after push, live acceptance
remains separately blocked by credentials/manual test destinations. Neither is
waived by source acceptance. Task1 complete,56f4899..c090eeb, review clean.
Continue separate operator API, not public policy mutation without authority.

## Reproduction of actual root PG gate

After the exact ownership/frozen-hash/readiness/baseline checks described above,
the process-local synthetic NEWSFLOW_UNATTENDED_POSTGRES_URL was set to the
accepted test-only loopback role/database and restored in finally. From backend:

```powershell
python -c "import sys;sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145');import telethon;assert telethon.__version__=='1.45.0';print('Telethon',telethon.__version__,telethon.__file__,flush=True);import pytest;sys.exit(pytest.main(['-q','-rs','tests/test_editorial_policy_configuration.py','--tb=short','--basetemp',sys.argv[1],'-o','cache_dir='+sys.argv[2]]))" "D:/Codex-Recovery/content-studio-20261008/editorial-policy-root-pg-286c57f6fe874862903deff524648e6c/tmp" "D:/Codex-Recovery/content-studio-20261008/editorial-policy-root-pg-286c57f6fe874862903deff524648e6c/cache"
```

Native status was captured immediately after Tee-Object, written to separate
exit.log and returned as process exit; stdout/stderr retained in native.log.
Do not reuse this already-owned temp directory or existing schemas for a new
run. The stated command is the completed gate's provenance, not an instruction
to rerun it. Root pre/post inventory used exact owned container ID and:

```sql
SELECT count(*),max(oid) FROM pg_namespace
WHERE nspname ~ '^unattended_[0-9a-f]{32}$';
```

Writer behavioral RED/targeted/static tests, frozen three hashes and sole backend
gate from backend cwd. Root then actual strict migrated PostgreSQL new-file gate
using existing create-only UUID harness, independent frozen/native inspection,
final report/owned commit and fresh spec+quality review. No current PASS inferred.

## Separate evaluator CI

Accepted evaluatorbacdd185/root evidencea639591 pushednative0/exactremoteverified.
Exact new CI38312315852/heada639591 all9in_progress; root tracks alongside this
independent task. Prior history34ad run38310060502 all9SUCCESS actual logs/artifact
are recorded in CI_RECOVERY_20261012.md, not this policy service's acceptance.
Live credentials/manual testTelegram/destination actions remain consolidated in
EDITORIAL_LIVE_ACCEPTANCE_20261012.md; no actual provider call or send.
PHASE1 remains unfinished; disabled heartbeat stays disabled.
