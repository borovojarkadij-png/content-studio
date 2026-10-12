# Protected editorial-policy operator API — design

Status: prepared while the preceding internal service completes its frozen gates.
No API implementation, credential creation, deployment or activation yet.

## Approved scope and bounded extension

Telegram-only PHASE1 requires persistent editable configuration and audit, with
REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
The existing internal EditorialPolicyConfigurationService supplies validated
snapshots, content-bound versions, exact ETags/CAS and atomic outbox metadata.
Expose that service only behind a dedicated single-operator credential. Preserve
the existing accepted navy UI; UI controls follow as a separate verified task.

This is a bounded integration with the existing FastAPI, pristine request-scoped
SQL session and single-human secret-file authentication patterns. It is not a
new user-management system, public model registry or model-qualification feature.
Human-approved autonomous implementation replaces repeated design confirmation;
no operational secret or authorization will be provisioned by this work.

## Options and decision

1. Dedicated operator bearer and narrow GET/PUT: chosen; explicit authority,
   existing deployment pattern, default-disabled without a provisioned secret.
2. Reuse the illustration reviewer bearer: rejected; illustration review does
   not authorize editing editorial policy or protected entities.
3. Add multiuser login/roles: deferred; unnecessary architecture for the approved
   local single-operator PHASE1 and would change more interfaces than required.

Extract only bounded bearer-file reading/header comparison from the existing
illustration reviewer into a shared security helper. Keep its existing principal,
environment names, validation/error behavior and public routes unchanged. Separate
editorial authentication supplies a distinct trusted principal; client JSON cannot
set actor_id, policy_version or qualification/execution/rewrite permissions.

## Trust boundaries and assets

- Untrusted HTTP body/header -> dedicated operator authentication -> internal
  strict policy service -> current PostgreSQL singleton and atomic outbox event.
- Protect policy/protected aliases, actor provenance, credentials, master key,
  stable Telegram sessions, existing decisions/jobs and false permissions.
- Runtime reads only the explicitly configured dedicated secret file. Never
  discover files, create keys, scan environment credentials or call providers.
- Exclude the effective master-key path and illustration-review secret path,
  including equivalent resolved paths/hardlinks. Require independently generated
  operator token; file separation alone does not prove independent token bytes.
- The existing bounded file validation/O_NOFOLLOW/opened-inode identity,
  regular-file/reparse/symlink refusal and constant-time comparison are retained.
  Host owner-controlled ACLs/TLS remain deployment requirements, not code claims.

## Operator contract

Configure NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE and positive signed64-bit
NEWSFLOW_EDITORIAL_OPERATOR_ID separately. Never generate a default. The secret
format remains32–128 ASCII letters/digits/underscore/hyphen, optional one LF;
reopen on each request for explicit rotation. No browser query token or cookies.
An absent/malformed/unreadable server configuration returns503. With valid
configuration, absent/wrong/malformed Bearer returns401/WWW-Authenticate:Bearer.
Authentication must complete before obtaining SQL storage or processing a save.

GET /api/settings/editorial-policy returns the exact internal service DTO.
PUT /api/settings/editorial-policy accepts exactly enabled, provider, model,
protected_entities and expected_etag. All are required; expected_etag nullable
for create-only. Pydantic strict/extra-forbid, no whitespace/type coercion.
Nested protected entity objects accept only entity_id and aliases. Complete
provider/model/entity/byte/alias constraints remain authoritative in the service.
No availability/catalog claim or arbitrary supplied policy version is accepted.

The dedicated authenticated principal, never JSON, supplies actor_id. No-op
does not emit an event; stale/null-when-existing returns409. Invalid input or
corrupted policy returns422 with static errors; storage/migration failure503,
never success/conflict masquerading as a save. Return successful service result
only after its transaction committed. Every response, including auth/validation/
conflict/storage errors, carries Cache-Control:no-store. Validation responses
must not echo input, aliases, header tokens, paths or exception detail/context.

All returned diagnostic_only=true, real_model_qualified=false,
execution_authorized=false and rewrite_allowed=false. Saving enabled=true is
diagnostic configuration only: no worker flags, diagnostic/rewrite jobs, current
decisions, claims/receipts, provider decrypt/calls, model releases or publications
are changed. Existing fresh binding checks invalidate stale diagnostics as usual.

## Verification and release boundary

Behavioral RED -> targeted migrated SQLite/API/auth guards -> unchanged reviewer
regressions -> actual strict create-only PostgreSQL/API -> one frozen backend
full gate -> independent spec/quality review -> exact authorized-branch CI.
Use only synthetic files/keys/data and injected boundaries; no real HTTP send.
Test auth-before-SQL, static/private errors, complete strict input, expected ETag
create/update/conflict/no-op, reopen/audit actor, rollback on injected outbox
failure, separate principals/token scope, rotation/alias/invalid-file refusal,
REJECT/no new jobs/zero calls and stale resolver/factory/runner bindings.

Optional Compose mount and existing Settings UI controls are later integration
work, not silently claimed by this API. Missing operator credential is an honest
default-disabled503, not a reason to use the illustration/master/provider key.
No live model qualification or PHASE1 completion follows from this change.

Rollback is removal of unused endpoints/helper integration on this branch; no
schema/data migration or production state update. Cost of the chosen single-user
boundary if unsuitable is replacement with a future identity provider; no existing
business data or runtime authorizations have been converted.
