# Combined unattended full-stack restart acceptance

2026-10-08; branch `codex/dark-navy-ui`; correct origin
`https://github.com/borovojarkadij-png/content-studio.git`.

## Implemented procedure

`scripts/verify-unattended.ps1` creates a **new** dedicated
`newsflow-verification-unattended-*` stack using the existing Compose foundation,
both dev/production profiles, PostgreSQL named storage, Redis AOF, web/API/worker,
the packaged migrations and exact public synthetic key. Existing fixture
directories, project containers/volumes or even unlabeled fixture-named volumes
are refused. Nothing is reseeded, dropped, pruned or reset.

The host pytest controller runs the already verified original-photo FloodWait
vertical scenario in a fresh create-only PostgreSQL schema. Before each of nine
engine/session phases, the explicit guarded hook invokes `restart-unattended.ps1`:
full `down/up`, Redis/worker restart, PostgreSQL SIGKILL/recovery and production
proxy health. The same scoped database URL, jobs, ciphertext, source identity,
approval evidence, plans, nonce/ack history and source photo files are reused.
Host media is inside the exact directory bind-mounted into API/worker. Final
phase revalidates persisted receipts and zero duplicate sends after another
actual restart. Final packaged public-schema Alembic drift is checked.

The packaged daemon uses its empty public foundation in the same isolated DB;
the synthetic scenario uses a separate test schema through actual durable
services/worker functions controlled by host pytest. All packaged network flags
remain 0. This is not opt-in live daemon behavior or Telegram/AI authorization
proof. Providers are synthetic, timers use the explicit synthetic clock and no
real message/photo is downloaded, uploaded or sent. Original job budgets are
checked; this is not a new provider model qualification.

## Safety boundaries and local checks

- Exact family/length, named local synthetic SQL role/database, original scoped
  namespace, owned marker/non-coercible version/nonce/ports, public key, service
  list, named nonexternal PostgreSQL volume, persistent media bind and flags 0.
  Invalid opt-in is refused before namespace creation. Missing opt-in touches
  neither Docker nor SQL. Existing ownership/config/key cannot be regenerated.
- Original media/ownership/config/key paths may not be redirected by symlinks.
  Failed/timed-out subprocess is a failure with redacted diagnostic output;
  no fallback, SQLite success or continued pipeline after restart failure.
- Real PowerShell is executed in tests; only read-only Docker-config output is
  replaced. Unsafe launcher/restart project and missing ownership are actually
  refused before Docker, with no fixture creation. Type coercion regression
  demonstrated `version=true` wrongly accepted without explicit type fence;
  RED -> restored typed fence -> GREEN. No destructive operation used in tests.
- 29 new hook/PowerShell cases; **52 combined PASS** (70173), including existing
  PostgreSQL target guards and all five isolated SQLite vertical scenarios.
- Full backend **1182 PASS**, 118.00s (25632), D: basetemp
  `D:/Codex-Recovery/content-studio-20261008/compose-vertical-full-1420`.
- Exact CI Ruff/changed format/D: bytecode compile, actual PowerShell parse,
  eight-job YAML parse and fresh explicit D: migration round-trip/drift PASS.
- Fresh frontend **139 units / 30 browser PASS** (6715), format/typecheck/build
  PASS and audit 0. Real migrated API, WCAG and eight-section responsive checks
  included; outputs `D:/Codex-Recovery/content-studio-20261008/compose-controller-browser-1424`.

## Actual runtime status

Actual a9fbb90 CI 37769576690 job 113285528034 **FAILED** at the first restart
hook after healthy full-stack build/startup. Captured subprocess output hid the
guard reason. Safe known static reason codes now cross that boundary; arbitrary
output/credentials remain redacted. Four diagnostic regressions RED -> GREEN,
56 combined PASS (22433), Ruff/format PASS. New diagnostic CI pending; no
assertion disabled and no accepted combined restart proof yet. This ordinary
implementation failure is distinct from the Windows external blocker.

Prior dd78455 / 37766880597 and 1cedac8 / 37767782693 completed SUCCESS in all
seven jobs; 567e263 / 37766368319 completed all-six SUCCESS (actual gh inspection).
dd78455's real PostgreSQL vertical job ran 23 PASS in 14.97s. Earlier combined
Compose recovery still remains separately pending until this new CI is inspected.

Current Windows Docker remains **NOT VERIFIED / BLOCKED BY ENVIRONMENT**:
C: about 0.47 GiB free, writable Docker storage not confirmed. New positive
launcher/restart was NOT run on this Windows machine. No operational files,
Docker volumes/databases/sessions/keys, qualified models or flags changed.
PHASE 1 is not complete. Obsidian remains pending; `/docs` is source of truth.

On an appropriately provisioned machine, install the existing backend dev
dependencies, then use a never-before-used fixture project:

```powershell
pwsh -NoProfile -File scripts/verify-unattended.ps1 -Project newsflow-verification-unattended-new-name
```

Requires a healthy writable Docker daemon and free loopback ports 5432, 18032,
15199, 18132. It deliberately retains stack/storage/evidence after success or
failure. Never rerun with the same project, delete evidence or reset its state.
