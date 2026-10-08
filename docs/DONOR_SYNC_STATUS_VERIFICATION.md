# Persisted donor synchronization diagnostics

2026-10-08; branch `codex/dark-navy-ui`, parent
`08cf9c9e3d9a49ade2b1535726d85ed19f68612e`; correct origin
`borovojarkadij-png/content-studio`.

## Implemented

GET `/api/telegram/donors/{id}/sync-status` reads retained enforcement,
account health and authenticated checkpoint/lease/error state. New baseline,
legacy resynchronization, active lease, expired recovery, retry, unresolved gap,
foreign checkpoint, unavailable account, cooldown, ready and unenforced legacy
workflow remain distinct. Exact processing block comes from the shared source
guard, not a second permission implementation. Known gap remains blocked even
when orchestration is off. All four kinds of legacy evidence (including empty
polls and recorded-baseline outbox facts) prevent a fabricated new baseline.

The no-store endpoint does not mutate state, run Telegram RPC, reset checkpoints,
grant editorial approval or create jobs. It never returns session ciphertext,
lease tokens, keys or raw provider/storage errors. `network_checked=false` is
explicit: READY describes stored continuity, not current Telegram connectivity.

Existing live Donors UI loads only the selected donor, with separate refresh,
loading/error/retry states and no reset/send action. Refresh preserves unsaved
names. Identity-keyed state and abort fencing prevent an earlier donor's READY
from appearing after selection/unmount/failed refresh. Strict DTO rejects wrong
identity, contradictions, unsafe extra fields and malformed types. Configured
API base is respected. DEMO data/behavior and reference-based styling unchanged.

## Actual verification

- Initial 12 backend cases RED (missing implementation/HTTP route), now GREEN;
  18 dedicated / 46 combined source-enforcement/wait tests PASS.
- Fresh full backend **1006 PASS**, session **8285**, 91.00 seconds.
- Exact CI Ruff scope, changed-file format, compile, explicit fresh D: migration
  upgrade/check/downgrade/upgrade/check PASS; no schema change required.
- Component/contract test-first RED -> GREEN; directory integration RED -> GREEN.
  API-base regression RED -> GREEN; fixture callback type corrected after actual
  TypeScript failure, no check disabled. Fresh full frontend **82 unit PASS**.
- Browser integration RED (missing diagnostics) -> GREEN using actual migrated
  isolated FastAPI/Vite, then **27 browser PASS**, session **44315**, 37.2 seconds.
  Desktop 1440 / mobile 390 refresh/manual draft/switch/reload/GET-only/WCAG AA/
  overflow assertions PASS. Changed API-base default path is unchanged; targeted
  browser rerun and final build/format verify latest files.
- Final typecheck/build/format and npm audit (0 vulnerabilities) PASS.
- Screenshots visually inspected:
  `D:/Codex-Recovery/content-studio-20261008/donor-sync-browser-green-1758/studio-real-persisted-dono-4bbd9-ever-authorize-live-actions/donor-sync-1440.png`
  and sibling `donor-sync-390.png`. D: holds new evidence because C: is constrained;
  no operational data/key/volume removal or reclaimed-space claim.

## Runtime boundaries and next task

Exact predecessor 08cf9c9 CI **37751511536** completed **SUCCESS in all five jobs**
(actual gh view), including create-only PostgreSQL sync/wait down/up recovery.
3adf692 CI **37750506085** also completed SUCCESS. This is Linux evidence only.
Current Windows Docker remains **NOT VERIFIED / BLOCKED BY ENVIRONMENT**; latest
C: ~0.59 GB free does not prove repaired/writable Docker storage. All operational
flags unchanged, no real publication/provider tests performed. PHASE 1 unfinished.

Next: inspect this checkpoint's exact CI, then implement read-only live Overview
and known AI usage aggregation from durable SQL records. Define historical counts
precisely; unknown charges/provider calls must never appear as zero or a complete
invoice. No invented topic/chart/health metrics or DEMO fallback.
