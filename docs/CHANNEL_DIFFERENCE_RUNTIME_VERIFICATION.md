# Leased channel-pts application (offline)

2026-10-08; branch `codex/dark-navy-ui`, parent
`0efb0b6ce311c1be452a31b124f3f93633c5b9b9`, correct origin
`borovojarkadij-png/content-studio`.

## Contract and safety

`ChannelDifferenceRunner` consumes one bounded read-only provider chunk using a
60-second PostgreSQL claim. A persisted baseline binds donor, account, provisioned
Telegram user and canonical channel. Claims additionally bind the stable encrypted
session digest, pts and fencing token. Current user/channel/session/health/cooldown,
lease and starting pts are rechecked before every durable write. No database locks
are held across the remote request. No session/key regeneration, login or send.

All deletion identities and exactly-once deletion outbox events commit **before**
any message enters mapping fan-out, even if a chunk both mentions and deletes the
same message. Partial message/mapping commits are retained; crashes leave pts
unchanged. Expired claims replay idempotently with the current mappings. Lease
renewal is fenced after each committed mapping. Fan-out is bounded at 100 mappings;
message/deletion chunks respect the configured 10..100 provider limit.

Only after the complete chunk is durable and the current mapping/filter binding
is unchanged does pts advance. Mapping or filter changes retain pts and require
replay. Unclassified text remains MANUAL_REVIEW, not assumed editorial PASS;
technical/deletion rejection cannot create rewrite tasks or trigger classifiers.

Final chunks report DIFFERENCE_COMPLETE and persist server retry delay. Non-final
chunks report DIFFERENCE_CONTINUE and resume from committed pts on the next bounded
call. FloodWait/session/provider/storage failures retain pts and persist bounded
retry/quarantine codes. A replaced session or stronger concurrent health state is
not overwritten by stale RPC completion.

Missing baseline reports BOOTSTRAP_REQUIRED with zero RPC calls. TooLong reports
GAP_UNRESOLVED, retaining the original cursor; neither resets pts nor silently
accepts a latest-message snapshot. This increment deliberately does **not** invent
baselines from message IDs, expose a public cursor initializer/reset, activate a
new worker or claim complete live gap recovery. Read-only bootstrap and legacy
resynchronization policy are separate pending work.

Migration `eab7590cde48` adds only an empty trusted-cursor table. Bounds and paired
lease columns are enforced by database constraints. Any populated cursor history
blocks downgrade; source tombstones and old source/publication histories remain
untouched. Empty round-trip is supported. Operational databases were not migrated.

## Actual evidence

- Initial 12 missing-consumer/model regressions RED; missing migration-table RED.
- Mid-fan-out filter change incorrectly advanced pts: reproduced RED, fixed by a
  fresh complete mapping/filter binding, then GREEN (new route case also tested).
- **30 targeted PASS**: deletion-first ordering, partial two-output crash/replay
  through an independently reopened SQL engine, stale lease, changed session/user/
  donor/health, FloodWait, malformed/foreign/oversized chunks, real SQL outbox fault,
  no network-held DB lock, TooLong, missing baseline and continuation/retry delay.
- Exact CI Ruff/targeted format/compile PASS. Explicit unique D: CLI Alembic
  upgrade/check/downgrade/base/re-upgrade/check PASS. Migration regression preserves
  old deletions, refuses populated downgrade and checks database constraints.
- Fresh full backend **831 PASS**, session 66930, exit 0, unique D: temp tree;
  frontend unchanged in this increment.
- Windows packaged PostgreSQL/down-up/worker acceptance: **NOT VERIFIED / BLOCKED
  BY ENVIRONMENT** (almost-full C:, failed Docker storage). Actual authenticated
  Telegram update handling remains pending. No operational flags or secrets changed.

Next: expose retained source deletion truth in the read-only inbox/API/UI; then
trusted bounded read-only bootstrap, with no automatic reset of legacy histories.
