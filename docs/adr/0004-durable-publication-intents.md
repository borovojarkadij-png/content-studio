# ADR 0004: Durable publication intent and uncertain delivery

Status: accepted; injected implementation verified locally and on Windows Docker.

## Context and constraints

The original PublicationService is an in-memory domain prototype. Redis, a Python
set or a completed HTTP request cannot prove durable Telegram delivery. A worker
may lose the response after Telegram accepted the message. Retrying this case
as though nothing was sent risks duplicate posts. Real sends are not a test step.

Editorial rejection must prevent further rewrite and publication; a previously
valid queued task is not permission to use an old decision. Approval is channel
specific. Source, mapping, filters, account session, target peer and original
media rights can change between scheduling and execution.

## Decision

PostgreSQL owns one publication job per planned item and its stable positive
64-bit request nonce. Enqueue checks fresh constraints; execution checks them
again and an authenticated transport MUST invoke the execution guard immediately
before its send RPC, after connection, identity/permissions and media preparation.
No database transaction remains open during the transport call.

The local preflight requires a current mapped SCHEDULED candidate, due PLANNED
slot, known unprotected single text/photo source, PASS/rewrite_allowed decision,
current per-output approved rewrite, deterministic fact anchors and technical
filters on both source and final caption INCLUDING attribution. Conservative
limits: 4096 UTF-16 units for text, 1024 for photo caption, six-hour slot expiry.
These are fail-closed policy defaults, not a claim of all Telegram account limits.
Cached encrypted session/peer presence does not prove live authorization.

Source photos require the current successful rights-bound acquisition job and
validated exact bytes. Library illustrations are blocked until explicit relevance
approval is implemented; topic search does not prove event-photo relevance.

| State | Allowed recovery |
| --- | --- |
| QUEUED | Claim due job; stable nonce and binding never regenerated |
| CLAIMED | Expired claim recoverable within two-attempt budget; old token fenced |
| SENDING | Committed before remote boundary; expiration becomes NEEDS_RECONCILIATION |
| NEEDS_RECONCILIATION | Never automatically resend; exact late trusted receipt may finalize unknown outcome |
| SUCCEEDED | Positive matching account/channel/nonce/message receipt and delivery outbox committed with plan/candidate PUBLISHED |
| BLOCKED / FAILED | No automatic reset or nonce replacement |

Only a transport-proven NOT_SENT response may produce a bounded delayed retry
(for example a send RPC FloodWait). Timeouts, connection loss, malformed receipts
and even validation exceptions after entering transport are ambiguous, not proof
of zero delivery. Known retry delay is persisted; it never resets attempts or
changes nonce. Callback-origin policy rejection before RPC is a known block.
Late receipt preserves factual delivery even if lease or policy changed AFTER
the send; it is not new permission to send. Published and unknown-delivery slots
still consume quota, including cancelled/revoked slots awaiting reconciliation.

Telegram documents client random_id deduplication and recovery through
updateMessageID/getDifference. This implementation does not equate a duplicate-ID
exception with an identified message, nor claim end-to-end exactly-once behavior.
See [sendMessage](https://core.telegram.org/method/messages.sendMessage) and
[updates recovery](https://core.telegram.org/api/updates).

## Alternatives and consequences

Blind retry on timeout was rejected. Never retrying a proven pre-send FloodWait
would unnecessarily strand recoverable jobs. Keeping SENDING intent only in
Redis would lose the distinction on crash. Conservative quarantine may strand
an actually unsent request until verified reconciliation, deliberately preferring
no duplicates over invented success. Arbitrary injected providers are trusted
adapters, not a public extension/security boundary: acknowledgement without the
final guard is quarantined, but cannot undo an unauthorized provider side effect.

## Migration and rollback

Migration a6d315c8fa04 adds publication_jobs without modifying old records.
Row constraints bind leases, two-attempt budget, known states, positive nonce,
canonical target and positive completion receipt. Downgrade refuses ANY job
history. Empty table downgrade is supported. Use a forward fix, not history
deletion, after intent creation. Master key, sessions, operational data and
transport-enable flags are unchanged.

## Verification boundary

Real SQL tests exercise guards, state/nonce durability, stale-owner fencing,
post-send uncertainty, late acknowledgement, invalid receipts and published
quota. The Docker probe uses PostgreSQL/restarts and a synthetic injected sender,
not Telegram/AI network calls. Authenticated sender, opt-in publication worker,
RPC permission checks, difference reconciliation and real authorization remain
pending; neither fixture sessions nor this ADR qualify them as live working.

2026-10-08 follow-up: encrypted text-only authenticated transport contract exists
and passed offline real-runner regressions. It is explicitly injected, not wired
to a live worker/API. Exact response mapping is required; uncertainty still never
authorizes resend. See TELEGRAM_TEXT_TRANSPORT_VERIFICATION.md. Photos, live
authorization, opt-in worker and difference reconciliation remain pending.
