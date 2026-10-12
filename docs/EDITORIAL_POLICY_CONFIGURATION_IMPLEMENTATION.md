# Persisted diagnostic editorial-policy configuration implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development. One writer, behavioral tests,
> frozen verification and independent task review; continue autonomously.

**Goal:** Configure the existing diagnostic policy through a strict internal SQL
service without hand-editing rows, lost updates or any new execution permission.

**Architecture:** Reuse EditorialClassifierPolicyModel singleton1 and the accepted
admission validator. Fresh-session optimistic configuration updates atomically
record a non-secret change event in the existing outbox. No schema or runtime
integration changes; a separately authenticated operator API/UI follows later.

**Tech Stack:** Existing SQLAlchemy/Alembic models, Python/pytest, migrated SQLite
and strict create-only synthetic PostgreSQL harness; no new dependency.

**Spec:** Approved PHASE1 configuration/audit/persistent-state requirements,
REQUIREMENTS_MATRIX.md R-001/R-004 and accepted editorial_admission.py binding.
QUALITY_GATES.md and EDITORIAL_LIVE_ACCEPTANCE_20261012.md remain binding.

## Global Constraints

- Telegram Content Studio only; preserve the accepted UI/design.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force-push, PR or push by workers.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify real models or activate automatic approval.
- No real keys, sessions, provider calls, publication or operational SQL in tests.
- Never generate/rotate a key, read real env files or print credentials.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN, CI evidence and live acceptance.
- No schema/migration, provider, prompt, worker, API, frontend or Compose changes.
- This internal service is not an authentication boundary or public endpoint;
  do not expose it until separate dedicated operator authorization is implemented.

## Decision and experiment

The existing singleton is only set directly in fixtures. Its policy_version and
protected_entities already bind every diagnostic job, but no supported service
validates or safely updates it. Missing credentials do not prevent this work.

Options: keep manual SQL (no CAS/audit); expose an unauthenticated settings PUT
(unsafe authority); add a new policy registry/schema (unnecessary now); reuse the
existing row with a validated, audited internal CAS service (selected).
Main risk: a policy update racing a diagnostic attempt. Existing fresh admission
and immutable request bindings must refuse stale work; configuration never edits
decisions/jobs or enables worker flags. A corrupted row is never an empty default.

Experiment: two clients read one ETag; exactly one conflicting update commits,
the loser cannot overwrite it, and exactly one change event accompanies it.
Also reopen migrated SQL and confirm configuration/zero new jobs remain intact.
Rollback: remove this unused internal service/tests only; no data migration or
operational policy is performed. Outbox event is change metadata, not a newly
claimed immutable comprehensive audit ledger or real-model qualification.

### Task 1: Strict singleton service, content-bound versions and atomic CAS

**Files:**
- Create backend/src/newsflow/services/editorial_policy_configuration.py.
- Create backend/tests/test_editorial_policy_configuration.py.
- Modify .github/workflows/ci.yml only to append
  tests/test_editorial_policy_configuration.py to the existing strict migrated
  PostgreSQL test command. Preserve every previous file/command and20-minute limit.
- Own SDD task-1-report.md only; root owns other docs.

**Interfaces:**

```python
class EditorialPolicyInvalid(ValueError): ...
class EditorialPolicyConflict(ValueError): ...

class EditorialPolicyConfigurationService:
    def __init__(self, session): ...
    def read(self) -> dict: ...
    def configure(self, *, enabled, provider, model, protected_entities,
                  expected_etag, actor_id) -> dict: ...
```

- Public errors are fixed static codes, never input/SQL/provider exception text.
  Do not catch unrelated storage IntegrityError as a successful update or generic
  conflict. Service does not read environment/credentials or construct providers.
- Both methods require a pristine Session: no active transaction/new/dirty/deleted
  objects. Refuse before SQL without flushing, committing or rolling back caller
  state. Each call owns its own session.begin() transaction and closes it before
  returning. This prevents accidental commit of unrelated raw SQL writes too.
- read() performs no inserts/outbox changes. Missing row projects configured=false,
  enabled=false, etag/provider/model/policy_version=null, protected_entities=[].
  Existing valid rows retain legacy policy_version exactly. Fresh query uses
  populate_existing; strict bool/provider/model/version/entity validation reuses
  editorial_admission._policy_request with fixed internal dummy source/key, never
  emits those values. Corrupt storage fails visibly, never resets itself.
- A configured projection has exactly configured, enabled, etag, provider, model,
  policy_version, protected_entities, diagnostic_only, real_model_qualified,
  execution_authorized, rewrite_allowed. diagnostic_only=true and the final three
  fields=false for both missing and configured rows. Return detached deep JSON
  snapshots: caller mutation cannot change ORM state or another response.
- ETag is lower-case SHA256 of canonical exact stored values enabled/provider/
  model/policy_version/protected_entities (JSON sort_keys, ensure_ascii=false,
  separators comma/colon, allow_nan=false). Expected ETag is exact64lowerhex or
  null for create-only; wrong type/format is EditorialPolicyInvalid.
- Validate the complete new input before any policy/outbox write. enabled exact
  bool; actor_id exactint1..2**63-1; provider/model/protected_entities and sizes
  use the accepted admission/request constraints (including free-only pinned
  OpenRouter, unique entities and unambiguous aliases). No whitespace coercion,
  arbitrary provider/catalog/model-availability claim or raw supplied version.
- Canonicalize new entities by entity_id and aliases by their exact strings;
  preserve source language/Unicode, not a normalization that changes aliases.
  New/content-changed version is 'editorial-policy-v1:' plus SHA256 of canonical
  provider/model/protected_entities. Enabled-only changes retain current version.
  An identical fresh request is a no-op, including legacy rows: no event, no
  silently replaced legacy version. Restoring the same canonical content yields
  the same derived version, not a new random authority.
- Lock/fresh-read singleton1. Null expected_etag cannot replace an existing row;
  stale ETag conflicts without changing data. For updates use a conditional SQL
  UPDATE matching all captured row values, including exact raw JSON text cast
  to Text; rowcount must equal1. PostgreSQL JSON does not have a generic equality
  operator, and SQLite with_for_update alone is not CAS. Capture raw JSON text
  using SQL CAST, do not reconstruct its storage whitespace. The ETag comparison
  remains canonical while the SQL condition protects every actual stored value.
- Concurrent create uses singleton PK as arbiter; only a verified competing
  singleton after rollback turns its create conflict into EditorialPolicyConflict.
  A failed unrelated outbox insert must propagate/rollback instead, never become
  an acknowledged save. No retry, delete, repair or overwrite on conflict.
- In the same transaction append OutboxEventModel event_type
  'EditorialPolicyConfigured', aggregate_key
  'editorial-policy:{actor_id}:{before_etag_or_none}:{after_etag}', idempotency_key
  'editorial-policy-update:' plus a fresh uuid4().hex. This is metadata only:
  no source, aliases, provider response or credentials. UUID is an operation ID,
  not a secret/key. Every committed non-no-op change has one event, including
  repeated disable/enable cycles; no uniqueness collision from repeated ETags.
- Flush and reread committed-intended values before transaction completion;
  return only after successful commit. Failure rolls back row and event together.
  Never modify EditorialDecision/RewriteJob/diagnostic job/claim/receipt or flags;
  do not enqueue classifications just because the policy was configured.

**TDD and verification:**

- [ ] Behavioral RED using migrated SQL and actual missing/stale configuration
  behavior, not absent import alone. A temporary deliberately unsafe in-test CAS
  seam may reproduce the stale overwrite; remove it once the real service exists.
  Preserve actual command/native RED; no invented result after interruption.
- [ ] Migrated read missing/legacy/corrupt; create/reopen; both providers; exact
  DTO/false permissions/deep copy; complete invalid-input matrix and alias/byte
  bounds; no-op/enable-toggle/content-change/restored-content version semantics.
- [ ] Stale/null/malformed ETag, dirty and raw-active transaction refusal with
  unchanged caller state; actual two-connection stale-update/create arbitration;
  event count/metadata/cycle uniqueness, injected storage failure atomic rollback.
  PostgreSQL-only lock/concurrency cases explicitly skip locally and run in the
  strict opt-in PG harness, with a bounded thread/event timeout and no busy loops.
- [ ] Reuse test_editorial_admission.py migrated store/ingest fixtures where
  appropriate. Configure/disable/change an admitted diagnostic binding: fresh
  resolver/factory/runner blocks stale work before injected provider construction.
  Existing REJECT/source decisions remain unchanged, RewriteJob count remains0,
  rewrite calls0; no config operation itself creates jobs or decrypts credentials.
- [ ] Target new service + admission/factory/runner regressions. Ruff0.17 full
  existing backend lint command, changed format/compile/YAML/diff checks. Freeze
  three files; ONE full backend gate from backend cwd/explicit Telethon1.45.
  Root actual strict WindowsPG new-file verification on fresh UUID schemas after
  ownership check, frozen hashes before/after, native evidence and independent
  scoped review. No unchanged Docker/UI/recovery gate repetition.
- [ ] Self-review/report exact commands/raw/native/hashes/limits; commit only
  owned three files plus own report, no push. Controller resolves review/CI and
  proceeds to separate authenticated operator API/UI, never automatic activation.

Deferred: dedicated operator authentication/API/UI, actual live model benchmark/
qualification and guarded PASS propagation. This internal service is not a public
configuration feature yet, not proof of model availability or PHASE1 completion.
