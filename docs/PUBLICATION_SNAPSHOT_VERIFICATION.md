# Immutable publication request snapshots

2026-10-08; branch `codex/dark-navy-ui`, parent HEAD
`6aaaefabc5df9636ee794e2edab630311798f5c8`, correct origin
`borovojarkadij-png/content-studio`.

## Contract

Enabled publication ticks now require and use the externally provisioned stable
SessionCipher for an encrypted, versioned exact PublicationEnvelope plus nonce.
The snapshot is inserted in the same transaction as the durable intent and queued
outbox. A cipher failure rolls back all three; duplicate enqueue never overwrites
history. No session, key, credential or access hash is added to the snapshot.
The envelope includes text, source/draft/output identity, due/expiry, selected
media hash and the original policy binding; it is not an authorization grant.

Worker execution compares this immutable envelope with fresh preflight before
SENDING and again in the final transport guard. Absent/corrupt/foreign-key
snapshots, changed nonce/binding, unknown/duplicate JSON fields and invalid
types/timestamps fail closed with safe errors and zero provider calls. Historical
reads remain possible after editorial rejection or draft edits; they do not
reenable sending, retry, rewrite or automatic approval.

Migration `b7e426d9ab15` only adds `publication_request_snapshots`, with job PK/FK,
binding and bounded ciphertext checks. Existing intents/nonces/outbox remain
unchanged: no legacy request is guessed from current mutable content. A legacy
QUEUED intent without a snapshot becomes BLOCKED under the configured worker.
Legacy ambiguous history remains quarantined. Downgrade refuses any publication
intent/snapshot history before dropping anything. Roll forward on populated data.
The optional no-cipher runner remains an injected offline test/probe seam, not
the configured worker path. No public snapshot or resend API was introduced.

## Actual verification

- Six request-snapshot cases initially RED on the missing constructor/module;
  migration preservation case RED on missing snapshot table.
- Targeted request/schema/key/rollback/reject and migration gate: 17 PASS.
- Full backend gate: **737 PASS**, session 78398, isolated fresh D: temp tree.
- Ruff, targeted format, compile: PASS.
- Explicit isolated D: Alembic upgrade/check/downgrade base/re-upgrade/check:
  PASS, session ac480d. No operational SQLite/PostgreSQL target used.
- Configured tick/main-loop and legacy publication tests included in full gate.
- Current Windows Docker/packaged/live send validation: **NOT VERIFIED / BLOCKED
  BY ENVIRONMENT** (C: low space, Docker storage read-only/Desktop unavailable).
  Working .env, publication flag, secrets and operational volumes unchanged.

Snapshots are prerequisite evidence, not a completed update-difference mechanism.
Telegram account seq/pts/qts and channel pts have distinct update domains; absence
of a matching random-ID observation cannot prove non-delivery. Next: persist
trusted exact delivery observations and reconcile them without another send;
leave evidence-free ambiguity quarantined. Never match by text or timestamp.
