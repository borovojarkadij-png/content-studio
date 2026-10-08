# Create-only rewrite-sync-wait restart acceptance

2026-10-08; branch `codex/dark-navy-ui`, parent
`3adf69234e9bcfd610194e2cfbd476e0175c4a4e`; correct origin
`borovojarkadij-png/content-studio`.

## Implemented synthetic procedure

The dedicated ChannelSyncGuard family now ends with an additional versioned,
create-only pending-rewrite fixture; existing historical suites stay separate.
It refuses an existing manifest/account instead of replacing jobs/sessions.

Seed uses real configuration/baseline/ingestion/difference/rewrite services with
synthetic providers only. Four original jobs are admitted while their exact
sources are current. A synthetic read timeout persists RETRY_PROVIDER; all four
jobs then wait durably with SOURCE_SYNC_REQUIRED, zero provider calls and attempt
vector `(0,0,0,2)`. One source is subsequently editorial-rejected (protected entity,
negative sentiment/framing), one deleted through real tombstone service, one has
an exhausted explicit two-attempt budget. Their history is not removed.

The PowerShell procedure performs down/up and independent pending verification,
waits for the persisted retry to become due without resetting it, then clears
the synchronization error only through an actual validated synthetic difference
chunk pts=10→12. The same four job IDs/key bindings finish as SUCCEEDED/PENDING,
BLOCKED_EDITORIAL, SUPERSEDED and FAILED respectively. Exactly one synthetic
rewrite is permitted; rejected/deleted/exhausted cases never construct a provider.
No real AI call or fake publication is used. Worker restart and another down/up
verify retained result/budget/history. No automatic review approval occurs.

CLI requires explicit isolated PostgreSQL verification DB, all seven network
flags 0 and the stable separately mounted public fixture secret. Wrong DB/key,
unsafe flag or unsupported mode is refused before connecting. Missing/future
due time cannot be rewritten for test convenience. Actual read-only Inbox and
rewrite-output APIs verify denied sources and PENDING review after recovery.

## Actual local evidence

- Missing probe and API contracts RED → GREEN.
- **7 dedicated / 33 combined targeted PASS**, including independent SQL reopen,
  version/reseed/early-recovery refusal, actual FastAPI read before/after recovery
  and CLI DB/network/key/mode rejection.
- Fresh full backend **988 PASS**, session **77961**, 88.00 seconds.
- Exact CI Ruff scope (including both new probes), changed-file format/compile,
  PowerShell parser and explicit fresh D: migration round-trip/drift PASS.
- Historical base/source/decision/job identifiers preserved; no operational DB,
  secrets, volumes or enablement flags modified. Frontend unchanged.

## Runtime evidence

Follow-up actual inspection: exact probe **08cf9c9e3d9a49ade2b1535726d85ed19f68612e**
CI **37751511536 completed SUCCESS in all five jobs**, including the dedicated
PostgreSQL sync/wait recovery job. Prior 3adf692 CI **37750506085** completed
SUCCESS. This supersedes the pending observations below, not Windows/live limits.

Prior baseline/replay/concurrency checkpoints ab13403 CI **37748969125** and
60596f5 CI **37749741849** completed SUCCESS in all five jobs (actual gh list).
Prior wait implementation 3adf692 CI **37750506085** backend/frontend/dedicated sync
SUCCESS, two old Docker variants still in progress at inspection. Those runs
predate this additional wait fixture; its actual PostgreSQL down/up acceptance
is pending the new exact commit's CI. No overall PASS claimed prematurely.

Current Windows Docker remains **NOT VERIFIED / BLOCKED BY ENVIRONMENT**, latest
C: ~0.48 GB free, not enough evidence of repaired/writable Docker storage. Linux
CI is not Windows proof. Live Telegram/AI qualification and explicit legacy gap
recovery remain external/unfinished; PHASE 1 is not complete.

## NEXT_STEP

Push this increment and inspect its exact dedicated wait/recovery CI job; fix any
failure without relaxing safety assertions. Then implement read-only donor sync
health/status API backed by persisted enforcement/baseline/lease/error/health:
missing new baseline, legacy resync required, active/recovery due, transient retry,
unresolved gap and ready must be distinct. Never expose token/session/key or claim
live connectivity/Windows verification from configured metadata. Connect truthful
status to the existing Donors UI without a redesign or DEMO/live mixing, with
test-first API/React/browser regressions. Operational flags remain 0.
