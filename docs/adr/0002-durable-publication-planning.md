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

## Consequences

- A stale `REJECT` or `rewrite_allowed=false` candidate cannot consume a slot.
- Re-running a day returns its existing durable reservations rather than adding
  duplicates; unique database constraints arbitrate concurrent planners.
- A later rewrite/approval/publisher worker must still perform its own current
  hard-constraint validation before transport.
- Mapping-aware candidate production remains a later worker integration because
  legacy ingestion identities are not yet linked to durable configuration IDs.

## Verification

Unit/integration tests cover priority ordering, daily limits and slots, manual
mode, stale editorial rejection, idempotency and migration upgrade/downgrade on
an isolated SQLite database.
