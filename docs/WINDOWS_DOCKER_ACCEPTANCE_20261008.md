# Windows Docker acceptance — 2026-10-08

## Candidate and safety

Application source: `9e33fbaede4e00ee76a1ced0f21ffcc9c76f4107`
(storage implementation `ffe2caf0d160cf7666f179eb71c9264d8cc752fb`).
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
  18236/15395/18336, are **in progress**, not yet complete at this checkpoint.
- Expanded strict Windows PostgreSQL gate and corrected-source full backend
  suite are **in progress**, not inferred from CI or the preceding SQLite gate.

Fixture paths are `.artifacts/docker-verification/<exact project>/`.
PowerShell transcripts are retained in
`D:/Codex-Recovery/content-studio-20261008/windows-{openai,openrouter,sync,admission}-20261008a.log`.
No fixture volumes have been removed. Synthetic markers are not Telegram login
proof or operational model qualification.

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

`verification-postgres-crash.ps1` now validates the exact original container ID,
isolated project and PostgreSQL service labels, then kills it and waits boundedly
for fresh observations of **that same ID** in exited/137 state before Compose up.
Missing/foreign targets, kill/inspect failures, unexpected exits and timeout fail
closed. Both persistence families and the unattended restart hook use the helper.

Actual regression: initial missing-barrier RED, then **10 PASS /5.21s**; combined
PowerShell/configuration/channel probe gate **60 PASS /16.64s**, Ruff PASS.
Actual Windows runtime: three additional crash/recovery cycles on the retained
new admission fixture, each followed by its existing read-only terminal verify,
all PASS. No seed/replacement/volume removal or real provider execution.

## Remaining gates

Complete the two general Windows families, expanded PostgreSQL and full backend
gates; inspect exact corrective CI before declaring it green. Keep authenticated
human illustration review/audit and final transport integration pending. Library
illustration publication hold remains in effect. Real Telegram login/restart,
explicit test-channel transport and reviewed fixed-model semantic benchmark
remain separate user/credential acceptance. PHASE 1 is not complete.
