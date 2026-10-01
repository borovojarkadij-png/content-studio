# Architecture

NEWSFLOW is a modular monolith: FastAPI exposes APIs, PostgreSQL is the source
of truth, Redis is transport/cache/coordination, and async Telegram/worker
processes consume PostgreSQL-backed outbox events. React is a separate UI.

## Hard editorial boundary

`TechnicalFilter → ExactDedup → EditorialGate → RewriteService → Scheduler → PublicationService`.
Technical filters and exact dedup run first. `EditorialGate` is mandatory before
rewrite and publication. The invariant is absolute:

`REJECT → rewrite_allowed=false → no RewriteJob → zero OpenAI rewrite calls`.

Both orchestration and `RewriteService` enforce it; `PublicationService` checks
the current decision, cancellation, expiry, schedule and idempotency again.

## Persistence

All business entities, state transitions, audit events, outbox records,
idempotency keys, sessions (encrypted) and recovery state belong in PostgreSQL.
Redis is not an authority. The encryption master key is supplied separately and
must not be regenerated after encrypted data exists.

## Module boundaries

`content`, `editorial`, `telegram`, `media`, `routing`, `scheduler`, `ai`, and
`analytics` expose domain/service contracts. Future YouTube uses shared
`ContentItem`, `ContentEntity`, `ContentTopic`, `EditorialDecision`,
`DistributionRule` and `ScheduleSlot`, rather than a separate policy engine.
