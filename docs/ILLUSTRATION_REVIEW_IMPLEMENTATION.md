# Illustration review implementation — 2026-10-09

This is the bounded continuation of CURRENT_STATE NEXT_STEP, not a replacement
architecture. The user's 2026-10-09 publication authorization permits implementing
the library publication consumer after verified authenticated review. It does not
waive independent gates or authorize testing sends to operational channels.

## Global Constraints

REJECT → rewrite_allowed=false → no new RewriteJob → rewrite calls=0.
Never accept client reviewer ID/provenance/hashes as authentication.
No real credentials generated, exposed, changed or activated.
No real Telegram/AI calls or publications in tests; use isolated synthetic data.
Preserve editorial/source/draft/fact/technical/rights/sync/clean-session gates.
No redesign, main merge, force push, volume deletion or operational migrations.
Use only codex/dark-navy-ui and origin borovojarkadij-png/content-studio.

## Task 1: Authenticated canonical review/revocation and audit

Implement a narrow default-disabled single-human reviewer boundary, durable review
writer and HTTP workflow in the existing backend. Read existing domain binding,
resolver, immutable SQL review records, API conventions and regression fixtures.

Authentication uses an explicitly provisioned separate local/persistent secret file
and a server-configured positive reviewer identity. Missing configuration fails
closed. Never reuse provider/master keys, generate a token, accept identity from
request bodies or treat a provenance string as authentication. Bearer comparison
must be constant-time; bound and validate secret file contents, reject unsafe file
types/symlinks and don't leak credentials/paths in errors, audit or responses.
Document local-only/TLS deployment assumptions, key rotation and no auto-generation.
Provide a separate opt-in Compose reviewer override mounting only API's reviewer
secret read-only, stable and untracked; explicit server reviewer identity is required.
Do not add a required reviewer mount to default Compose or edit operational .env.
Document development/production override usage and test available config validation.

Expose authenticated canonical context read plus review and revocation endpoints.
Strict request schemas reject unknown reviewer/provenance/timestamp fields.
Client displayed binding is only an optimistic concurrency assertion: resolve it
fresh from SQL and decoded bytes and compare every field; never use it as authority.
Use a trusted internal principal rather than a JSON reviewer ID. Server supplies
review timestamps and provenance. Validate verdict/acknowledgment/note/operation key.
Store review/revocation append-only using IllustrationReviewRecordModel. Preserve
the exact parent's binding for revocation even when the current candidate is stale;
do not make revocation depend on continued editorial eligibility. An authenticated
configured reviewer may revoke any record in this single-reviewer deployment.

Writer owns an atomic transaction on a clean session, uses current canonical
records and appropriate serialization/revalidation, and never commits pending
caller work. Idempotent exact replay returns the original record, never a new
timestamp; conflicting operation payload/principal/binding/kind is rejected.
Revocation is irreversible and cannot be undone by replay; a revoked/rejected
review never becomes an approval. Review and audit must commit/rollback together.
Use the existing transactional OutboxEventModel as the durable audit event, with
unique operation-derived event identity and bounded internal payload/reference;
the immutable review row is the canonical decision history. No schema change unless
an actual missing storage invariant demands it.

TDD: actual failing behavioral tests before implementation, then focused GREEN.
Test missing/wrong/malformed/authenticated credentials, forged identity/provenance,
dirty sessions, exact replay/conflict, stale displayed context, canonical rejection,
acknowledgment refusal, rights/file/draft/source changes, revoke after editorial
reject, atomic audit failure rollback, reopen persistence, zero new rewrite/provider/
publication side effects. Use real migrated isolated SQL and existing library fixture.
Run full backend once on final source and lint/format/compile. Record concrete
commands and RED/GREEN output in the task report. Keep publication hold for Task 1.

Document implemented auth configuration/security limits, observed tests and exact
NEXT_STEP in CURRENT_STATE and IMPLEMENTATION_PLAN. No operational secrets required
to implement or test this task.

## Task 2: Fresh library approval consumer before publication

After Task 1 review is accepted, integrate current authenticated immutable review
evidence into library preflight, exact request snapshots and the transport's final
guards. Replace only the unconditional library hold for an exact current approved
illustration with explicit acknowledgment; every independent hard gate remains.
Resolve latest REVIEW for this candidate, never fall back to an older approval
after a newer rejection/uncertain review or revocation. Read exact canonical binding
again and assess via the existing strict domain contract, not a client DTO.
Never infer event-photo truth or model qualification. Include current review identity
and binding in the immutable publication request, and refuse any revocation/change
before/after upload or stale retry. Original-source photo/text behavior is preserved.
Existing affected boundaries: PublicationPreflight, ConfiguredTelegramPhotoPublisher,
PublicationRequestSnapshots, MediaJobReader diagnostics and frontend media DTO/text.
Persist review identity explicitly as optional envelope fields and version encrypted
snapshot schema; strict decode supports original version-1 historical requests with
the original exact schema, maps only absent review fields to None, and never uses
history reading as authorization. Reject unknown/duplicate/bool/inconsistent fields.
Existing final durable runner guard re-prepares after upload before send and compares
the exact digest; include review identity/binding in that digest, without DB locks
across network. The configured library photo reader must recheck canonical review
and actual bounded decoded bytes before upload, not merely remove its source-only
check. Make read-only media hold diagnostics truthful: no library approval is a
review-required hold, exact approval clears only that narrow hold, not full readiness.
For a library photo, final caption visibly labels it `Иллюстрация.` and retains
required license credit. Check actual final photo media type and complete caption
against mapping filters and Telegram UTF-16 limits; never truncate facts or treat
an approved illustration as a photograph of the reported event.
Adjust existing strict frontend DTO and explanatory text/tests without redesigning,
adding unprotected review controls or changing accepted screen composition.
Actual RED/GREEN regressions for approved send through fake transport and zero sends
for no/rejected/uncertain/revoked/stale/wrong-channel reviews, editorial reject,
rights/credit/file mutations and crash/retry/duplicate delivery are required.
No live send or operational activation; live acceptance stays pending credentials
and explicitly designated test channels. Update docs after verification.

## Task 3: Protected human review presentation and existing UI controls

After Task 2 independent review is accepted, complete the human workflow in the
existing MediaPreparation surface. This is not a redesign or a general auth system.
Keep existing palette, navigation, component composition and DEMO isolation.
Use small dedicated illustration presentation service, API client and React panel,
with narrow integration into the existing component. Do not grow a monolithic form.

The authenticated backend must return canonical source text, per-channel approved
draft, exact eleven-field binding, current library license/credit and latest review
with revocation status. Revalidate SQL/text digests/asset metadata against the binding
before returning a bounded presentation. Never present a historical draft as current.
Add an authenticated bounded photo preview bound to the displayed canonical context,
not a remote image URL or public storage path. Require an explicit matching context
validator (strong ETag/If-Match) for preview and refuse missing/stale validators.
Revalidate current canonical context and exact decoded/hash bytes before and after
reading, return no-store bytes and the matching validator. No transaction crosses
network work. Existing unprotected media preview is not reviewer authentication.
Provide a bounded authenticated latest-review read independent of current source
eligibility so a known immutable review can still be revoked after editorial reject.
Use existing writer review/revocation endpoints; no schema change or new identity.

The React panel asks for the separately provisioned reviewer bearer, using a masked
input with autocomplete disabled. Token stays in this panel's memory only; never
URLs, logs, error text, local/session storage, analytics or default credentials.
Clear token/context/object URL on disconnect, candidate change and unmount; abort
inflight reads/writes and discard late responses. Explain missing server config,
401,409,503 and network failure honestly, never imply authorization or saved success.

Load canonical source, draft, channel identity, license/credit and exact photo before
enabling a review. The client strictly validates response schemas, candidate identity,
source/draft text digests and bounded photo MIME/hash against the binding. Render text
as text, never HTML. Approval requires an explicit illustration-not-event-photo
acknowledgment and a nonblank bounded note. Rejected/uncertain decisions do not grant
permission. A dedicated revoke action works on the latest immutable review even
when current presentation is unavailable. Viewing or selecting media never approves.
Generate one safe unique operation key per action and retain that exact payload for
explicit retry after ambiguous network failure; never automatically resubmit or
reinterpret failure as success. Block double clicks, stale context, candidate/token
switch races and concurrent actions. Abort cannot undo a committed server operation;
explain uncertain outcomes and offer a fresh authenticated latest-review read.
On verified success refresh authoritative review/media status; on stale conflict
invalidate displayed context and require a fresh load. No publication/send action.
DEMO never mounts the authenticated panel or fabricates persisted review success.

TDD: actual failing behavioral tests for authenticated presentation/preview hash,
missing/wrong auth, missing/stale validator, source/draft/rights/file mutation and
stale revocation; strict client malformed/foreign/hash refusal; UI acknowledgment,
bounded notes, actual request payloads, double submit, abort/late response, candidate
and token changes, explicit idempotent retry, revoke after stale context and no token
persistence. Use migrated synthetic SQL and existing fixture, no real credentials.
Add isolated real API browser flow for approve/reject/revoke, truthful media hold,
zero publication jobs/provider calls and narrow-screen keyboard/accessibility.
Preserve old screenshot evidence before any output directory is overwritten.
Run targeted checks during iteration, then one frozen full backend, frontend unit/
format/typecheck-build and relevant browser gate. Record RED/GREEN and commands;
update CURRENT_STATE/IMPLEMENTATION_PLAN with exact remaining restart acceptance.

## Task 4: Owned illustration review/snapshot restart acceptance

After Task 3 review, extend only isolated synthetic verification infrastructure
with a create-only explicitly owned library review and immutable publication
snapshot fixture. Reuse existing strict resource guards and persistent secret,
PostgreSQL/media volumes; never operational project, queues or credentials.
Prove canonical review, audit, encrypted snapshot and photo survive down/up; prove
revocation/stale evidence prevents fake transport after restart and abandoned
SENDING remains quarantined without resend. Execute actual Windows Docker build,
migrations/no drift, health and restart boundaries. Keep resources/evidence
recoverable; no down -v, prune, truncate, overwrite or live send. Add relevant
regression tests/CI procedure without bypassing checks. Report actual PASS/FAIL/
SKIP separately from credentials-dependent live acceptance and record NEXT_STEP.
