# Durable editorial diagnostic admission verification — 2026-10-12

Branch codex/dark-navy-ui, origin borovojarkadij-png/content-studio.
Task BASE1d00655e7722ea615f23a35f860800b01d1d1bff, implementation source
88ce23402a2dc2a3d52402b7a2b424c2e91149be. Canonical admission is independently
approved, no Critical/Important/Minor findings. Root checked all frozen hashes,
full backend and actual PG/restart evidence below. Exact new GitHub CI remains
pending. No classifier execution, real-model qualification or PHASE completion.

## Actual Windows PostgreSQL preflight

Root independently checked Docker Engine29.8.0. Existing retained synthetic
container4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e:

- project newsflow-verification-unattended-win-20261008a;
- service postgres, exact expected container name, postgres:16-alpine;
- exact existing project postgres_data volume mounted /var/lib/postgresql/data;
- only bound port127.0.0.1:5432, project ownership JSON matches;
- no existing listener before starting this exact stopped container;
- actual start succeeded, then running/healthy;
- read-only host SQL confirms database newsflow_unattended_ci and role
  newsflow_fixture, using the existing strict synthetic test target.

Only that PostgreSQL container was started. Other old application services stay
stopped; retained Windows c stack is separate and unchanged. No fixture reseed,
credential regeneration, public-schema migration, deletion or volume reset.
Before new admission PG cases, read-only namespace inventory:1347 existing
unattended namespaces, maximum namespace OID1009660. Future tests must create
fresh UUID namespaces through the existing strict helper, never reuse these.

Two preliminary inventory orchestration commands did not produce evidence:
one Python command had a quoting SyntaxError, another metadata list exceeded the
output budget. A small count/max-OID query then succeeded; no DDL/data writes
occurred in any of those inventory commands. These are not PostgreSQL test
failures or substitute acceptance.

## Actual Windows PostgreSQL final02 run

Root independently matched final02 admission service/test SHA256 values
8328ECC822EB9DD528F28D35C7CDED4266FE12145E0D77C7856E9496BE18E58F and
E7A658A1652C0F833FD321F1394BA07DD2F57CB238A5E49A13BBDD24573F077C.
Ran the entire admission file with strict NEWSFLOW_UNATTENDED_POSTGRES_URL,
explicit Telethon1.45 insertion, unique D: cache/temp paths and restored
process-local environment. Native result: **1 FAIL / 87 PASS / 60.67s / exit1**.

The sole failure is a test exception-class expectation for a 256-character
model. Actual PostgreSQL VARCHAR(255) rejects it before the CHECK constraint,
with sqlalchemy.exc.DataError / StringDataRightTruncation; SQLite rejects it
with IntegrityError. No invalid model was persisted or admitted. Root sent the
exact finding to the sole writer for a narrow dialect-aware assertion; no
production constraint or error propagation should be weakened. The original
failed result is retained, not relabelled PASS.

Native log:
D:/Codex-Recovery/content-studio-20261008/editorial-admission-root-pg-20261012b.log.
Fresh UUID schemas remain retained; no cleanup/reset. No provider/Telegram/
publication calls. One retry preflight used an incorrect backend-relative path
for Get-FileHash and stopped before setting the PG environment or running tests;
the corrected preflight matched the amended hash below.

Corrected test-only file SHA256:
A17DDB1B079F4E766EEAB81226FA48A7283658DD83EE3B7BCC10254DD37D9E99.
All production hashes unchanged. Actual strict PG rerun: **88 PASS / 62.03s /
exit0**, no skips or warnings. Exact native log:
D:/Codex-Recovery/content-studio-20261008/editorial-admission-root-pg-20261012c.log.
Only PostgreSQL overlength rejection expects DataError; SQLite/blank checks still
expect IntegrityError. This is not broader exception swallowing or a disabled
constraint.

## Actual new-job Windows PostgreSQL restart proof

After both test processes completed, root took a read-only snapshot restricted
to the176 fresh validated UUID schemas above baseline namespace OID1009660.
Each schema's migration head is d7b340a92e16. No old namespace/public schema is
read for data or altered by this probe. Nine fixed tables are compared in full:
original sources/revisions, decisions, exact fingerprint owners, explicit
diagnostic policies/jobs, outbox, rewrite jobs and known rewrite usage.

Snapshot retained118 diagnostic jobs:116 QUEUED and2 terminal REJECT,
174 policy rows,148 decisions,156 revisions,152 source identities,
146 fingerprint reservations and268 outbox events. Two RewriteJob rows are
deliberately seeded existing-work negative controls across the two test runs,
not jobs created by diagnostic admission; known rewrite usage rows0.

Root revalidated exact full container ID, project/service/ownership, original
volume and loopback port before restarting only the synthetic PostgreSQL above.
Native restart exit0; StartedAt changed from2026-10-12T19:30:00.700399825Z to
2026-10-12T19:43:56.680752414Z, then running/healthy. Two independent post-restart
connections each compared all original rows and returned PASS/exit0:

SHA256 E0CFE3AC0440AA835F8BD3808F57F67CB3D422EE12D39590809488F9F014B2FD.

Manifest retained at
D:/Codex-Recovery/content-studio-20261008/editorial-admission-pg-restart-20261012.json.
Read-only task probe retained at .artifacts/editorial-admission-20261012/pg_restart_probe.py,
SHA2569485DF3C98D236851ACB3AE0442F8B9CE159263F8C4151B1A0572CB1827C1244.
The Docker CLI warned that --time is deprecated; the accepted restart succeeded.
Use --timeout for future commands. No DB writes by the probe, providers, live
sends, deletions, reseeds or credential changes. The separate retained Windows c
application stack is untouched. This proves new pending-request persistence,
not completed classifier execution or later-source application-image acceptance.

## Frozen gate and scoped source acceptance

Native full02:2301 PASS/6 existing explicit PG-only SKIP/396.76s/exit0. Root read
the original completed log and independently matched SHA256
DB2792CD7E0A25F6EB87104A3FC850C968A4AB596E281FB6E7795718C2337B72.
This full run used final production hashes and the pre-amendment E7A6 admission
test hash; later amendment is test-only and has separate SQLite88/PG88 PASS.
119 new targeted/398 covering cases, Ruff0.17/changed format/compile/YAML/diff
and migration sentinel/no-drift/rollback-limit checks passed. The six unchanged
optional PG cases remain SKIP here; separate exact-source CI exercises them.

Independent task-1-review.md reads the full BASE..88ce package and reports
spec compliant/quality approved/no findings. Root owns native process chronology
and exact remote CI records; neither is inferred merely from the diff. Runtime
TOCTOU fences, execution, qualification and approval propagation remain deferred.
No provider/Telegram RPCs, real keys, operational destinations or UI changes.
