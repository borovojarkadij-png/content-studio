# Authenticated illustration review

The backend provides a default-disabled single-human review boundary. It does
not grant publication permission, qualify a model, or attest that an image shows
the reported event. No real reviewer credential was created or activated.

An operator must separately provision a persistent regular secret file outside
Git and configure `NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_FILE` and a positive signed
64-bit `NEWSFLOW_ILLUSTRATION_REVIEWER_ID`. The file contains 32–128 ASCII characters
from letters, digits, underscore and hyphen, optionally followed by one LF.
Use an independently generated high-entropy credential; never a provider key,
Telegram credential or application master key. Runtime never generates a token.
The loader refuses the configured master-key path and aliases to the same inode,
oversized/malformed files, symlinks, nonregular files and Windows reparse points.
It bounds reads, verifies the opened inode and uses constant-time bearer comparison.
Error responses omit credential values and file paths; validation responses omit
request input. Review notes and operation keys must not contain secrets.

Secret storage and its parent directory require owner-controlled filesystem ACLs;
the application does not provision or enforce host ACLs. Keep the API on localhost
or behind an authenticated TLS termination boundary. Bearer possession represents
the one configured human; this is not multiuser login, browser session management,
or an identity-provider integration. Do not send this credential over plaintext
remote connections. Authentication is scoped to these routes, not the legacy
application configuration APIs. Anyone with trusted database administration or
process execution can bypass an application authentication boundary.

The optional `compose.illustration-review.yaml` mounts the separate persistent
reviewer secret read-only into **api only**. It requires explicit
`NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_SOURCE` and reviewer ID interpolation. The
default Compose file has no reviewer secret dependency. After separately
provisioning the inputs, the development combination is
`docker compose -f compose.yaml -f compose.dev.yaml -f compose.illustration-review.yaml --profile dev up -d`;
the production combination is
`docker compose -f compose.yaml -f compose.illustration-review.yaml --profile production up -d`.
These commands are documentation, not operational actions performed by this task.
No worker, migration service or frontend receives this credential.

For rotation, replace the separately provisioned file with a new independently
generated credential and distribute it to the one authorized reviewer through a
trusted channel. The loader reopens the file for every request: old bearer values
stop authenticating immediately for host-file deployments. Recreate the API
container if the mounted secret implementation retains the old file inode.
Keep the same reviewer ID when rotating the same human's credential. A changed
reviewer ID deliberately conflicts with prior operation-key replay.

The authenticated routes are:

- `GET /api/illustration-review/candidates/{candidate_id}` returns the canonical
  binding freshly resolved from SQL and decoded local media. It is a context
  assertion endpoint; a reviewer UI is outside this task.
- `POST /api/illustration-review/candidates/{candidate_id}/reviews` accepts only
  `displayed_binding`, `operation_key`, `verdict`, `illustration_acknowledged` and
  `review_note`. Verdict is `APPROVED_ILLUSTRATION`, `REJECTED` or `UNCERTAIN`;
  approval requires explicit true acknowledgment. Every displayed binding field
  is compared against current canonical context, never used as authority.
- `POST /api/illustration-review/records/{review_id}/revocations` accepts only
  `operation_key` and `review_note`. The configured human may revoke any review.
  The record retains the parent's exact binding even after rejection, stale
  source/draft/rights or media changes; no continued eligibility is required.

Successful responses have `Cache-Control: no-store`. Missing/unavailable server
configuration returns 503. With valid server configuration, missing, malformed
or wrong bearer credentials return 401. Invalid/unknown request fields return
422, canonical eligibility/staleness or operation conflicts return 409, and
missing records return 404. Storage errors, including serialization races,
return 503 and require retry using the same operation key.

Operation keys are 1–128 ASCII characters, beginning with an alphanumeric and
continuing with alphanumeric, underscore, dot, colon or hyphen. Notes are nonblank
and at most 2048 characters; control characters other than LF/tab are refused.
The authenticated internal principal supplies reviewer ID. Server supplies UTC
review time and `AUTHENTICATED_HUMAN_V1` provenance; neither is accepted from JSON.

The writer refuses pending caller mutations **and an existing caller transaction**
before beginning SQL. It owns commit/rollback of review and transactional outbox
audit together. SQLite uses `BEGIN IMMEDIATE`; PostgreSQL uses SERIALIZABLE without
candidate-first locks that invert existing approval lock order. PostgreSQL may
serialize a concurrent canonical change after the historical review or abort a
race. The writer rechecks canonical SQL/media before persistence and again after
both inserts. SQL cannot atomically lock external filesystem bytes; a change
after the final read leaves stale historical evidence that a future publication
consumer must refuse through fresh binding resolution.

Review/revocation rows remain append-only under existing migrated storage guards.
The outbox audit stores a bounded immutable-review-ID reference, event type and
operation-derived unique digest, not credential material or another decision
payload. Exact replay returns the original record and timestamp, with current
revocation state; different principal/kind/binding/verdict/acknowledgment/note
conflicts. Replay never undoes revocation or promotes a rejected/uncertain review.
No new rewrite job/provider call/publication job is produced by these routes.

Task 2 implements the separate fresh publication consumer described in
ILLUSTRATION_PUBLICATION_CONSUMER.md. It clears only the exact current human
illustration-review gate and preserves every independent publication constraint.
The review endpoints themselves create no publication job or network send.

NEXT_STEP: parent independent review/actual Windows PostgreSQL and packaged
verification of Task 2, then protected controls in existing MediaPreparation and
an owned library-review/immutable-snapshot Docker restart probe. Credentials and
designated live test destinations remain separate, unprovisioned boundaries.
