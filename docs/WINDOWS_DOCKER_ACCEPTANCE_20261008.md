# Windows Docker acceptance — 2026-10-08

## Candidate and safety

Application source: `9e33fbaede4e00ee76a1ced0f21ffcc9c76f4107`
(storage implementation `ffe2caf0d160cf7666f179eb71c9264d8cc752fb`).
Reviewed verification-helper implementation source:
`7cc4b612190b81a818cd8f520a2be73b9c952ceb`; backend business logic and frontend
source were unchanged in the helper corrections.
Branch `codex/dark-navy-ui`, origin
`https://github.com/borovojarkadij-png/content-studio.git`.
Windows Docker Desktop 4.91.0 / Linux Engine 29.8.0 / WSL2.

All fixtures were checked absent before creation, including containers, named
volumes, networks, artifact directories and loopback ports. Existing operational
containers and old fixtures were not started, reseeded or migrated. These new
fixtures use a public deterministic synthetic key and synthetic database roles;
all Telegram/AI/media/publication network-worker flags remain zero. No real
credentials, authorization, AI calls or Telegram publications were used.

## Actual results at this checkpoint

- `newsflow-verification-unattended-win-20261008a`, ports 18232/15399/18332,
  PostgreSQL loopback 5432: `verify-unattended.ps1` completed exit 0.
  **1 PASS /4 deselected /398.08s**, nine actual full-stack down/up,
  Redis-worker restart and PostgreSQL SIGKILL/recovery boundaries. Original SQL
  state, separate two-output rewrites, semantic checks, source-photo bytes,
  FloodWait job budgets/reconnect, immediate/delayed automatic daily planning,
  exact synthetic publication receipts and protected reject zero-job/zero-usage
  assertions all passed. Packaged Alembic check: no drift. Deselected scenarios
  are not claimed by this one scenario; the expanded PostgreSQL gate is separate.
- `newsflow-verification-win-admission-20261008a`, ports 18235/15396/18335:
  `verify-persistence.ps1 -CrashRecovery -AdmissionGuard` completed exit 0.
  Retained media/semantic admission state and idempotency survive down/up,
  Redis-worker restarts and PostgreSQL crash; late rejected rows remain blocked.
- `newsflow-verification-win-sync-20261008a`, ports 18234/15397/18334:
  `verify-persistence.ps1 -CrashRecovery -ChannelSyncGuard` completed exit 0.
  Original synchronization/deletion/quarantine/replay state, independent writer
  concurrency and bounded original rewrite-sync wait recovery all passed.
- General OPENAI and OPENROUTER families, ports 18233/15398/18333 and
  18236/15395/18336, both completed exit 0 (sessions 20622/40927).
  Build/config/migrations/health, actual changed-API-IP proxy recovery, stable
  encrypted synthetic session/peer/config/media, original durable job/outbox,
  Redis AOF and Redis loss, PG crash, expired rewrite/semantic/media/ingestion/
  import/photo/publication leases, stale owners/source edits, mapping filters,
  quota/observed acknowledgement and zero resend assertions all passed.
- Expanded strict Windows PostgreSQL gate **217 PASS /235.80s**, session 73622,
  including actual PostgreSQL TRUNCATE refusal, migrated storage references,
  binding, hidden links, retained album, fan-out and five vertical scenarios.
- Fresh frontend **205 PASS**, format and TypeScript/Vite build PASS. Actual
  production container frontend HTTP/health and separate dev/production config
  checks PASS. Production CSS/JS hashes exactly match the unchanged local build:
  `be111c7230ebd0c852495befb243c61aebe61834b4f7e5c0919512f4a747e3de` /
  `0b698687a5e580cbfc70075b9f9b82576b78c2d3546d785c41dd88fffdd9a6ff`.
  No UI redesign. Browser eight-section evidence remains exact CI proof, not a
  new Windows screenshot claim.
- Intermediate full backend 96833 **1622 PASS/1 PG-only SKIP /368.82s** is
  preceding barrier source, not the final reviewed correction. Run 39692 was
  invalidated by further script corrections during execution: **7 failed /1619
  passed /1 skipped /341.19s**, old collected fake CLI routes against corrected
  on-disk helper. Failure retained; never use a mixed candidate as acceptance.
  Final frozen-source gate **26833: 1627 PASS /1 PostgreSQL-only SKIP /386.99s**,
  exit 0. The skipped PostgreSQL-only boundary is separately verified in the
  strict actual PostgreSQL gate above; it is not inferred from SQLite.
  A subsequent test-only cold-runner correction is described below; this full
  run precedes that added regression and does not prove the later test source.

Fixture paths are `.artifacts/docker-verification/<exact project>/`.
PowerShell transcripts are retained in
`D:/Codex-Recovery/content-studio-20261008/windows-{openai,openrouter,sync,admission}-20261008a.log`.
No fixture volumes have been removed. Synthetic markers are not Telegram login
proof or operational model qualification.

Actual shipped combined-fixture image IDs (not registry tags):

- API: `sha256:045c17ee2e59f2d53d1560552a2c0fce1c3405666df83323a6be3b786ded1def`.
- Worker: `sha256:b3879f3e1f0ee7c533e0bb3ca452e093a9ab42349f3615d8de006d1b211eafd5`.
- Production web: `sha256:549d1c68a55ed08ca8f49b1447c58aac2a861021f90e0a0732c1fa187d63cf8f`.
- PostgreSQL: `sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`.
- Redis: `sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499`.

Packaged SQLAlchemy 2.1.4 / Alembic 1.20.0 / Telethon 1.45.0 / Pillow 12.3.0,
migration head `c5e81b29a704`. Source equality is not operational deployment proof.

## CI crash race and correction

Exact storage source CI `37804071273` completed all eight jobs SUCCESS; actual
PostgreSQL job `113403606230`: **217 PASS /145.41s**. Subsequent docs checkpoint
CI `37805519893` OpenRouter job `113408633078` actually failed. It remains a
failure, despite the unchanged application source and preceding green CI.

The log shows successful SIGKILL RPC, then Compose reporting PostgreSQL Running,
then `dependency failed to start ... exited (137)`. The recovery command raced
the daemon's asynchronous exit-state observation; no storage assertion failed.
Do not rerun blindly, sleep a guessed duration, disable checks or accept exit 137
as recovery success.

`verification-postgres-crash.ps1` now resolves one full original container ID
through native `ps -aq --no-trunc` with exact project/service filters, validates
its labels/running state, kills that ID directly and waits boundedly
for fresh observations of **that same ID** in exited/137 state before Compose up.
Missing/foreign targets, kill/inspect failures, unexpected exits and timeout fail
closed. Both persistence families and the unattended restart hook use the helper.

Review exposed service re-resolution at kill and an unbounded synchronous inspect;
both independently reproduced RED and corrected. Every native CLI command uses
remaining overall deadline, shell-free ProcessStartInfo.ArgumentList, async
captured output and late-result refusal. Errors never emit child output. Owned
live-root CLI cleanup is best effort, not general orphan-tree management; actual
crash calls use native ps/inspect/kill, not Compose plugin children.

Actual Windows execution exposed two more concrete CLI boundary failures:
Get-Command returned docker.exe plus an extensionless Unix launcher, and default
native ps returned only twelve ID characters. Real resolution RED regression and
strict native-argv RED corrected single-application selection and --no-trunc.
Invalid-project tests now trap the real process boundary before any Docker call.

Final dedicated **15 PASS /8.24s**; combined PowerShell/configuration/channel
probe gate **65 PASS /29.20s**, Ruff/format/compile PASS. Final independent static
review: no remaining actionable findings, no reviewer runtime commands performed.
Actual final helper Windows runtime: three retained admission crash/reverify
cycles all PASS (37933). Final unattended hook also ran down/up/Redis-worker/
direct-ID PG crash/health on the original retained stack (49095), exit 0; all
175 owned PostgreSQL namespaces remain present, original storage/key retained.
No seed/replacement/volume removal or real provider execution. Earlier three
cycles (90936) prove only the initial correction, not this final helper.

Exact 7cc4b61 CI `37809146965` backend job `113421162710` failed:
**1 failed /1626 passed /1 skipped /288.38s**. The delayed-exit ordering test
used a one-second total deadline, including cold Linux PowerShell cmdlet/JSON
initialization. That is not a product latency requirement. A controlled 1200ms
initial-inspect regression reproduced RED on Windows. State-order/error tests
now use the unchanged production 30-second default; timeout and late-result
tests still use one second, and native-child blocking still uses 200ms. No
production helper/limits/checks were changed. Review also found a possible false
PASS if timeout occurred before the delayed post-kill observation. Two marker
assertions reproduced RED; timing tests now require the kill and actual completed
post-kill response before accepting timeout. Cmdlet/JSON initialization alone is
primed outside their measured invocation, no Docker observation/authority granted.
Final independent static review: no actionable findings. Dedicated corrected
**16 PASS /13.00s**, Ruff/format PASS. Full run 15501 started before those final
marker assertions and remains preceding test-source proof only. Fresh exact
corrective CI must verify the final test source;
do not relabel the failed workflow or infer Linux proof from Windows success.

Only the three completed new OPENAI/OPENROUTER/sync stacks were stopped to reduce
idle resources; their containers and volumes are retained. Unattended/admission
fixtures remain available. C: has about 7.5 GB free at the final local inspection; no
prune, deletion, compaction or original volume cleanup was performed. Further
large builds require storage capacity, not destructive automatic cleanup.

## Remaining gates

Windows synthetic application gates above are complete. Final implementation
source CI `37809146965` has a failed backend test and remaining runtime jobs
pending at this checkpoint. Re-verify the cold-runner test correction locally and
on exact new CI before calling its gate green. Keep authenticated
human illustration review/audit and final transport integration pending. Library
illustration publication hold remains in effect. Real Telegram login/restart,
explicit test-channel transport and reviewed fixed-model semantic benchmark
remain separate user/credential acceptance. PHASE 1 is not complete.
