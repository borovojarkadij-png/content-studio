# ADR 0002: Durable publication planning before transport

## Context

Each output channel needs a clear daily publication cadence and an optional
automatic candidate selector. Telegram transport, real AI rewriting and final
moderator approval are not yet operational, so a scheduler must not imply that
a publication happened merely because it was selected.

## Decision

Store one publication plan per output channel with `MANUAL` or `AUTOMATIC`
mode, a daily limit, IANA timezone and distinct daily-minute slots. Store
candidates and reserved slots separately. Automatic planning ranks candidates by
priority, rechecks the current durable EditorialGate decision immediately before
each reservation, and creates idempotent `PLANNED` records only. It performs no
Telegram send, OpenAI call or rewrite-job creation.

Mapped ingestion creates a candidate in `AWAITING_REWRITE` only after its
technical checks and EditorialGate pass. A rewrite-completion worker can promote
it to `READY` only when the persisted rewrite job is `SUCCEEDED` and the current
editorial decision still allows rewrite. This keeps unfinished or subsequently
blocked content outside the selector.

The EditorialGate decision is shared by an immutable source revision, but every
output mapping gets an independent rewrite job and outbox event. This allows
each output channel to use its own selected rewrite model and editorial style;
completion of one job cannot make another channel's candidate schedulable.

## Consequences

- A stale `REJECT` or `rewrite_allowed=false` candidate cannot consume a slot.
- An editorial reject never creates a candidate or rewrite job; a later stale
  reject blocks any awaiting candidate instead of making it schedulable.
- One source mapped to several outputs has several independent rewrite jobs,
  but never bypasses the shared current editorial decision.
- Re-running a day returns its existing durable reservations rather than adding
  duplicates; unique database constraints arbitrate concurrent planners.
- If an already reserved candidate is later editorially blocked, the scheduler
  records `BLOCKED_EDITORIAL`, releases only its active slot and deterministically
  fills that vacancy with the next eligible candidate. Historical blocked slots
  do not conflict with active-slot uniqueness.
- A later rewrite/approval/publisher worker must still perform its own current
  hard-constraint validation before transport.
- Mapping-aware candidate production remains a later worker integration because
  legacy ingestion identities are not yet linked to durable configuration IDs.

## Verification

Unit/integration tests cover priority ordering, daily limits and slots, manual
mode, stale editorial rejection, idempotency and migration upgrade/downgrade on
an isolated SQLite database. The final migration refuses an unsafe downgrade if
multiple blocked historical reservations share a slot, rather than deleting
audit evidence to recreate the older uniqueness rule.
