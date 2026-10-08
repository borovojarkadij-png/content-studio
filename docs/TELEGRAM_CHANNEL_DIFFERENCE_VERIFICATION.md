# Bounded read-only channel difference contract

2026-10-08; branch `codex/dark-navy-ui`, parent
`6266b5a0689409bc7af89b7e3dadec5ab7f2f206`; correct origin
`borovojarkadij-png/content-studio`.

## Implemented

TelegramProvider/Fake/Telethon/current encrypted factory expose one read-only
channel_difference call, with canonical account/channel binding, positive signed
32-bit channel pts, ordinary-user request limits 10..100 and force=False.
Authentication remains manual; no login/join/upload/send or provider call runs
inside a DB transaction. Stable session/peer CAS refresh and the existing request
deadline, FloodWait conversion and disconnect behavior remain in use.

The immutable bounded chunk carries start/next channel pts, explicit final and
retry delay, exact new/edited TelegramMessage observations and channel-scoped
deletion IDs. Normalization validates source peer, message IDs/timestamps/media,
edit timestamps, deletion identity, update pts and response/observation bounds.
Unknown/common-box updates are not relabeled as channel deletions. Empty deletions,
duplicate/bool IDs, naive/missing edit timestamps, regressing/non-progressing pts,
foreign/oversized/malformed responses fail closed rather than truncate history.

TooLong raises a dedicated unresolved-gap error; latest-message snapshots are not
presented as complete missed-update/deletion history. Unseeded Fake cursors do not
fabricate a successful empty result. Difference reads require a provisioned user
binding before connection. Regression found/fixed Python bool user ID matching an
integer ID in the shared authorization boundary; actual get_me.id must be int.

This increment does not persist/advance cursors, apply source deletions, create
rewrite/publication tasks, authorize publishing, observe nonce delivery receipts
or wire a new worker flag. It is a provider contract prerequisite, not completed
unattended gap recovery. Unknown metadata update support/bootstrap remains pending.

## Actual verification

- Initial 15 missing-contract regressions RED, then GREEN.
- Empty-deletion cursor advance and bool/unbound user bugs reproduced RED/fixed.
- Final 28 new difference regressions; combined RPC/encrypted factory gate 42 PASS.
- Fresh full backend **779 PASS**, session 70003, unique D: temp tree.
- Exact CI Ruff/targeted format/compile PASS. Explicit isolated D: Alembic upgrade/
  drift check PASS; no schema migration or operational target in this increment.
- Frontend unchanged; previous 58 unit / 24 browser gate remains historical evidence.
- Windows packaged/live authorization/difference acceptance: NOT VERIFIED /
  BLOCKED BY ENVIRONMENT/AUTHORIZATION. No operational sessions/keys/flags changed.

Official references: [independent update sequences](https://core.telegram.org/api/updates),
[channel difference request](https://core.telegram.org/method/updates.getChannelDifference),
[TooLong response](https://core.telegram.org/constructor/updates.channelDifferenceTooLong),
[channel deletion update](https://core.telegram.org/constructor/updateDeleteChannelMessages).
The approved implementation deliberately refuses a TooLong reset until a durable
resynchronization policy exists; no text/time-based publication reconciliation.

Next: durable channel cursor/lease and irreversible source-deletion tombstones.
Apply all deletion observations before message fan-out; atomically invalidate
current source eligibility without deleting revisions/jobs/history. Check tombstones
in ingestion and shared source freshness used by all rewrite/media/review/planning/
publication guards. Advance pts only after every observation/mapping is durable.
