# Authenticated create-only channel baseline

2026-10-08; branch `codex/dark-navy-ui`, parent
`b6b4d98f6b6d59fcb091d9c3cf1aaa832fb2a0bc`; origin
`https://github.com/borovojarkadij-png/content-studio.git`.

## Contract and boundaries

Fake/Telethon/encrypted provider factory expose an immutable account/user/channel
checkpoint. Telethon authenticates the provisioned user and reads exactly one
`channels.getFullChannel` response; it validates the full broadcast channel,
canonical identity, positive signed-32-bit pts and bounded vectors. There is no
history read, send, upload, join, login, inferred pts or automatic reset.

`ChannelBaselineService.bootstrap` is internal and create-only. It locks and
captures the current donor/account/session digest and mappings, closes that
transaction before the RPC, then locks/revalidates everything in a new transaction.
Only a genuinely new donor can receive a baseline. Existing incoming posts,
tombstones, **any** history-poll cursor (even empty/unclaimed), or a retained
baseline outbox event without its cursor produce `LEGACY_SYNC_REQUIRED` with
zero remote reads. This conservative rule is intentional: an empty poll is not
proof that historical deletions were recovered.

Existing matching baselines return `ALREADY_INITIALIZED` without a remote call or
any pts/error mutation, including `GAP_UNRESOLVED`. Foreign persisted identity
returns `BASELINE_CONFLICT`, never an implicit overwrite. Context changes during
RPC, including the factory's own encrypted session refresh, prevent recording;
the next attempt may use the new current context. Concurrent bootstrap preserves
the first committed baseline. Cursor plus `channel.baseline_recorded` outbox are
one atomic transaction; a real SQL trigger fault leaves neither.

FloodWait/session failures persist account health only if the original context
is still current. Stronger/replacement state is not overwritten. Requests never
hold SQL locks across network activity; independent writer callbacks verify this.
No new public initializer/reset endpoint, worker activation, operational secret
change or live Telegram/AI call is introduced.

The baseline observes current pts, not successful legacy gap recovery. Initial
history/deletion-first worker orchestration and explicit gap quarantine remain
separate follow-up tasks; this seam must not be represented as completed
unattended operation.

## Verification

- Checkpoint contract initially 14 missing-contract failures, then GREEN.
- Baseline initially 15 missing-service failures, then GREEN.
- Durable account-health regression: 3 RED (missing persisted health / stale
  replacement failure), fixed and re-tested.
- 53 combined checkpoint/bootstrap regressions PASS using isolated SQL/Fake/
  real Telethon TL objects and encrypted factory; no external provider calls.
- Fresh full backend **886 PASS**, exec session 12463, unique D: temporary tree.
  Exact CI Ruff / changed-file format / compile PASS; explicit isolated D:
  Alembic upgrade/downgrade-base/re-upgrade/drift PASS (same successful session).
- Frontend unchanged; 62-unit / 25-browser results belong to the preceding
  b6b4d98 checkpoint, whose CI 37715889965 completed SUCCESS in all four jobs.
- Windows Docker/current deployment and live authorization: NOT VERIFIED /
  BLOCKED BY ENVIRONMENT/AUTHORIZATION. Linux CI is not Windows evidence.

Protocol references: [channels.getFullChannel](https://core.telegram.org/method/channels.getFullChannel),
[channelFull pts](https://core.telegram.org/constructor/channelFull),
[independent channel update state](https://core.telegram.org/api/updates).
