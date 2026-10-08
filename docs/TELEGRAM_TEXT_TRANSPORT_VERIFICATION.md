# Guarded Telegram text transport

2026-10-08, branch codex/dark-navy-ui. Offline contract verification only.

## Implemented

Explicitly injected TelethonTextPublisher and ConfiguredTelegramTextPublisher use
the existing current encrypted session/peer factory. No credentials generated,
no worker opt-in/HTTP send endpoint, no default runtime construction. A provisioned
expected user is mandatory; live authorization/user identity precede permission
checks. Destination must be the exact non-minimal broadcast channel, with creator
or post_messages permission and no left/megagroup state.

The single raw SendMessageRequest uses the persisted random_id, exact plain text,
no preview, no Markdown parsing, no reply/schedule/forward and no paid Stars or
paid floodskip. The fresh runner guard is invoked after permission RPCs immediately
before this request. No database locks cross the injected network boundary.

Only one matching UpdateMessageID and one exact outgoing channel post confirm a
receipt: account/channel/nonce/message ID and exact text must match. Missing,
duplicated, foreign or altered acknowledgements do not fabricate success. Short
responses without the exact channel/nonce mapping are deliberately uncertain.

Only an explicit FloodWaitError from the send RPC becomes proven-not-sent retry.
Timeouts remain uncertain; restart never resends them. Stable nonce, two-attempt
budget, delayed retry and atomic durable receipt are owned by the existing runner.
Pre-send permission/authentication failures are conservatively quarantined once
SENDING was committed; no automatic reset exists at this checkpoint.

## Actual verification

- 19 initial transport tests RED (missing implementation), then GREEN.
- Four encrypted factory/real-runner tests RED (missing factory), then GREEN.
  Initial integration exposed a synthetic client missing the real session.save
  side effect; fixture corrected without weakening production guards/assertions.
- 35 transport/factory tests PASS: permission/session/reject gates, exact TL request,
  malformed acknowledgements, missing encrypted values, source/review/session/user/
  cancellation changes during permissions, durable timeout quarantine and FloodWait.
- Combined targeted existing runner/provider regression gate: 69 PASS before the
  additional race tests. Full final backend gate: 684 PASS, Ruff and compile PASS.
- No schema changes. Previous explicit D: migration round-trip/check passed; same
  schema remains. Frontend unchanged from 55 unit/23 browser/format/build PASS.
- No actual Telegram connection, paid AI call or publication used for these tests.

## Remaining boundary

Docker Desktop is unable to start after host disk-full/read-only containerd failure;
current packaged/operational acceptance is BLOCKED BY ENVIRONMENT, not a PASS.
Real Telegram credentials/login remain pending. Photo/album/video sending,
opt-in publication tick and update-difference reconciliation are not implemented
by this text-only transport. UI correctly keeps live_publication_available=false.
Do not promote synthetic receipts/sessions as genuine authorization or enable
real sending merely to test it. PHASE 1 is not complete.

Contract sources checked: [sendMessage](https://core.telegram.org/method/messages.sendMessage),
[updateMessageID](https://core.telegram.org/constructor/updateMessageID),
[Telethon RPC errors](https://docs.telethon.dev/en/stable/concepts/errors.html).
