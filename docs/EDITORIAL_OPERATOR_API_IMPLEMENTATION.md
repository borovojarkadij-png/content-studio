# Protected editorial-policy operator API implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development. One writer, behavioral tests,
> frozen verification and independent task review; continue autonomously.

**Goal:** Expose the accepted policy CAS service to an explicitly authenticated
single operator, without changing editorial or execution authority.

**Architecture:** Separate dedicated secret-file principal; reuse the existing
bounded bearer-file mechanics through a small shared helper and preserve the
illustration review contract. Narrow strict FastAPI GET/PUT delegates all policy
validation/transactions to EditorialPolicyConfigurationService.

**Tech Stack:** Existing FastAPI/Pydantic/SQLAlchemy, pytest, migrated SQLite and
strict create-only PostgreSQL harness. No new dependency/schema/frontend.

**Spec:** EDITORIAL_OPERATOR_API_DESIGN_20261013.md; approved PHASE1 R-001/R-004,
QUALITY_GATES.md and EDITORIAL_LIVE_ACCEPTANCE_20261012.md.

## Global Constraints

- Telegram Content Studio only; preserve the accepted UI/design.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force-push, PR or push by workers.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify real models or activate automatic approval.
- No real keys, sessions, provider calls, publication or operational SQL in tests.
- Never generate/rotate a real key, read real env files or print credentials.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN, CI evidence and live acceptance.
- No schema/migration/provider/prompt/worker/frontend/Compose changes or actual
  policy, credential, authorization or permission activation.
- New operator authority is distinct from illustration review/master/provider
  credentials. Existing illustration review public behavior must remain intact.

### Task 1: Dedicated operator authentication and strict persistent policy API

**Files:**
- Create backend/src/newsflow/security/bounded_bearer.py.
- Modify backend/src/newsflow/security/illustration_reviewer.py only to extract
  its bounded file/header mechanics, retaining its public contract.
- Create backend/src/newsflow/security/editorial_operator.py.
- Create backend/src/newsflow/api/editorial_policy.py.
- Modify backend/src/newsflow/app.py only router inclusion, exact-route scoped
  no-store middleware and private static validation response for
  /api/settings/editorial-policy.
- Create backend/tests/test_editorial_policy_api.py.
- Modify .github/workflows/ci.yml only append tests/test_editorial_policy_api.py
  and tests/test_illustration_review_api.py if not already present to the existing
  strict migrated PostgreSQL command; retain all commands and20-minute timeout.
- Own SDD task-1-report.md; root owns other docs.

**Interfaces:**

```python
class BearerFileUnavailable(RuntimeError): ...
class BearerHeaderUnauthorized(PermissionError): ...
def read_bearer_file(path, *, forbidden_paths=()) -> bytes: ...
def require_bearer(authorization, token: bytes) -> None: ...

@dataclass(frozen=True, slots=True)
class EditorialOperatorPrincipal:
    actor_id: int
class EditorialOperatorUnavailable(RuntimeError): ...
class EditorialOperatorUnauthorized(PermissionError): ...
def authenticate_editorial_operator(authorization) -> EditorialOperatorPrincipal: ...
```

- Shared helper has no environment/SQL/provider access. Move the existing bounded
  32–128ASCII token read, optionalLF, stat/nonregular/symlink/reparse refusal,
  O_NOFOLLOW/O_BINARY/opened-inode check and constant-time Bearer comparison,
  rather than copy a second block. Static errors only. No credential generation,
  caching or directory traversal. Handle malformed/oversized/unreadable/looped
  synthetic paths as unavailable, without path/token leakage. Preserve existing
  illustration environment semantics, principal/error classes and401/503 behavior.
- Operator reads only NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE and
  NEWSFLOW_EDITORIAL_OPERATOR_ID; ID exact positive signed64-bit decimal.
  Reopen configured token each request; exclude effective stripped master path
  and existing illustration-secret path, resolved aliases and samefile/hardlinks.
  File separation alone does not claim independent token bytes. Never read an
  unrelated provider/session/env credential or create a substitute.
- Router prefix /api/settings/editorial-policy. Authenticate before obtaining
  database_session/storage; a pristine session is passed to the existing service.
  Missing/malformed server auth503; valid config with missing/wrong header401,
  WWW-Authenticate:Bearer. No query-token/cookie/basic authentication accepted.
- GET returns the exact service read() DTO, not a duplicated projection.
  PUT accepts exactly required enabled, provider, model, protected_entities,
  expected_etag (nullable create-only). Nested entities exactly entity_id/aliases.
  Strict Pydantic/extra-forbid/no whitespace or bool/int/string coercion. Use
  existing service provider/model/alias/byte validation; no duplicated authority.
  Client actor_id/policy_version/permission fields or unknown fields return422.
- PUT actor_id comes solely from EditorialOperatorPrincipal. Call configure()
  with the expected_etag exactly supplied. No-op preserves event count; stale or
  null-when-existing409; complete invalid input/corrupt stored policy422; missing
  storage/migration/SQL failure503. Fixed private error messages, never str(exc),
  original input, Pydantic context, paths, source/alias/token values. Unrelated
  storage errors must not become409 or fake successful save.
- Success returns only after service commit; all responses, including auth,
  request-validation/conflict/storage errors, Cache-Control:no-store. New static
  validation handler and no-store middleware are limited to this route or its
  trailing-slash redirect, leaving existing redaction/unrelated API behavior
  unchanged. Cover framework405 and trailing-slash307/308 as well as route errors.
- diagnostic_only=true, real_model_qualified=false, execution_authorized=false,
  rewrite_allowed=false. Neither route edits decisions/jobs/claims/receipts/flags,
  schedules diagnostics, decrypts keys, calls a provider or activates publication.
  Metadata-only existing outbox audit records authenticated actor/hash, not keys.

**TDD and verification:**

- [ ] Actual TestClient behavioral RED for unavailable default-disabled policy
  configuration route (expected503, not an absent import only), then GREEN.
- [ ] Reuse migrated store from test_editorial_policy_configuration/admission;
  monkeypatch configured_session_factory to that isolated engine only. Synthetic
  tmp secrets only; real request dependency/auth/service/SQL, no canned save.
  Clear or replace every consulted environment path/ID before authentication,
  including operator/reviewer/master settings; never use host credentials.
  Example read/write assertions:

```python
current = client.get('/api/settings/editorial-policy', headers=operator_header)
assert current.status_code == 200
body = dict(enabled=False, provider='OPENAI', model='synthetic-model',
            protected_entities=[], expected_etag=current.json()['etag'])
saved = client.put('/api/settings/editorial-policy', headers=operator_header, json=body)
assert saved.status_code == 200
assert saved.json()['rewrite_allowed'] is False
assert client.put('/api/settings/editorial-policy', headers=operator_header,
                  json=body).status_code == 409
```

- [ ] Cover missing/wrong/malformed auth before SQL/provider access; separate
  reviewer/operator principal authority, rotation, identity limits, missing/
  invalid/oversized/nonregular/symlink/reparse/hardlink/master-alias exclusions,
  effective path whitespace and bounded reads. No real credential file access.
- [ ] GET missing/legacy/corrupt; strict full invalid/unknown input incl actor/
  version/permissions; both accepted providers; create/update/no-op/stale/null
  ETags; reopened canonical SQL/audit actor/single event; all responses no-store
  and no private error leakage. Inject outbox SQL failure and verify atomic
  rollback/no successful acknowledgement; remove injected fault, read original
  ETag/state, explicitly retry once and verify exactly one committed change event.
- [ ] Existing protected REJECT decisions unchanged; no RewriteJob/diagnostic
  job created, provider construction/decrypt/rewrite calls0. Fresh service/runner
  binding refuses an earlier diagnostic after HTTP disable/model/entity update.
- [ ] Target new API + policy service + unchanged illustration review API/storage
  and current admission/factory/runner tests. Actual strict PostgreSQL new-file
  API + existing reviewer API root gate on fresh owned UUID schemas after freeze;
  PostgreSQL lock behavior remains in accepted policy service's dedicated tests.
- [ ] Ruff0.17 full existing CI lint, changed format/compile, exact CI/YAML/diff
  check. Freeze changed source/test/CI hashes; ONE full backend suite from backend
  cwd with explicit Telethon1.45. Preserve all RED/failed/interrupted/native logs;
  no quiet warning suppression, assertion disable or skip-as-pass.
- [ ] Final report exact commands/counts/native/hashes/limitations, self-review;
  commit only owned files/report, no push. Root checks evidence, independent
  spec/quality review and exact authorized-branch CI before next integration.

Deferred: optional persistent Compose operator mount and protected Settings UI,
actual fixed-model benchmark/qualification and live authorized test Telegram.
Default-disabled/unprovisioned endpoint is not a working public configuration
workflow, model qualification or PHASE1 completion.
