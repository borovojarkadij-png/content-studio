# Telegram engagement observations — approved-scope increment

## Outcome and scope

Original approved Hype Engine/view-velocity requirements need observed source
performance, not absolute views or random news selection. Current provider
normalizes immutable message content but collects no engagement counters. This
increment supplies bounded read-only observations, honest velocity calculations,
and durable append-only history. It does not claim complete HypeScore, event
clustering, learned donor baselines or automatic selection yet; those consumers
follow this evidence seam. No frontend redesign or operational activation.

The human authorized autonomous implementation of the already-approved metrics,
HypeScore and planning scope. Additional approval ceremonies from brainstorming
and writing-plans are superseded by that explicit no-intermediate-questions
instruction. This is a scoped extension of the existing Telegram adapter and
PostgreSQL ownership, not replacement of the approved architecture.

## Alternatives and decision

1. Add counters to TelegramMessage: small, but mutable counters can invalidate
   equality/media download/source revision fences and cause duplicate rewrites.
2. Cache statistics only in Redis: cheap, but loses history/recovery authority.
3. Separate validated observations and PostgreSQL history: chosen; existing
   source/content identity and jobs remain unchanged, missing metrics stay NULL.

## Contract

Frozen `TelegramEngagementObservation` carries canonical positive numeric string
account ID (<2**63), canonical marked broadcast donor ID (-2**63 through
-1000000000001), message ID (1..2**31-1), aware UTC-normalized `published_at` and
`observed_at`, and nullable views/forwards/reactions. Exact integers only; known
counts are 0..2**63-1, never booleans. Publication cannot be after observation.
Only aggregate counts are retained, never users/reactors, text or credentials.

Separate `TelegramEngagementProvider.fetch_engagement(account_id,
donor_identifier,message_id,*,observed_at)` returns that contract. Read-only
Telethon helper uses the existing adapter's bounded authenticated `_run` and
peer resolution, then exactly one get_messages for the requested ID. Verify
actual chat/message identity before relabeling. No getMessagesViews/increment,
login/join/send/download/retry/new client machinery. Actual original `date`
(not edit_date) supplies publication time. Missing views/forwards/reactions
remain unknown; valid explicit zero remains zero. Partial `MessageReactions.min`
or absent reaction aggregate is unknown; complete bounded (<=100) real SDK
ReactionCount results are summed, overflow/malformed data fails. Existing
ConfiguredTelegramProvider delegates with current encrypted session/peer CAS.
Separate deterministic fake seeds explicit observations and rejects unseeded
or mismatched requests. Existing TelegramMessage, FakeTelegramProvider and
content/media/provider protocol behavior stay unchanged.

`engagement_velocity(previous,current)` returns nullable per-minute views,
forwards and reactions plus explicit tuple `reset_metrics`; same complete
identity/publication time and strictly increasing aware times required. Missing
either count gives unknown. Decrease gives unknown and a reset marker, never a
negative trend. Known equal counts give zero. `engagement_acceleration(first,
second,third)` computes change in adjacent velocities divided by the distance
between interval midpoints in minutes; unknown/reset gives unknown. Immutable
result dataclasses; no invented baselines, ML, AI, score or hidden clock.

## PostgreSQL history

Add one source row keyed to existing incoming post with immutable published_at;
add snapshots keyed by incoming post and observed_at, nullable counters, temporal
and nonnegative signed64 SQL checks. FK RESTRICT and append-only UPDATE/DELETE
triggers on both supported dialects. No existing row backfill or identity change.
New migration follows actual current head. Downgrade refuses retained history;
empty additive tables can be removed. Existing source/editorial/jobs untouched.

`TelegramEngagementHistory(session).record(observation)->bool` uses the caller's
transaction, validates again, locks existing incoming row, verifies canonical
account/channel/message against a real configured donor/account, and inserts
source/snapshot atomically. Unknown incoming identity fails (no fabricated post).
Existing first publication time cannot change. Exact replay is no-op/False;
same timestamp conflicting counters fail; new/out-of-order observations retained
without editing old rows. No commits, RPC, outbox/rewrite/approval/publication.
`history(incoming_post_id,*,limit=60)` returns latest bounded observations in
chronological order (limit exact int 1..1000); SQLite round-trip naive internal
timestamps are interpreted as UTC only at this storage boundary.

## Verification and continuation

TDD negative and meaningful behavior tests; bounded Fake SDK/time/flood/auth/
identity/NULL/reset/acceleration tests; existing provider/media/source equality
regressions. SQLite migration up/drift/down-refusal and SQL append-only checks.
Explicit create-only PostgreSQL tests through existing strict helper, CI appended
to existing PG command (not skip-as-proof). Controller runs actual Windows PG
after source review in fresh namespaces; no production target or namespace reuse.
One combined backend suite after Task2, focused covering tests after each task.
All tests synthetic; no real Telegram/AI/sends. Continue with durable opt-in
snapshot scheduling and transparent donor-relative HypeScore consumers after
this increment; missing live observations never become fabricated statistics.
