### Task 1: Canonical durable diagnostic requests after exact dedup

**Files:**
- Modify backend/src/newsflow/persistence/models.py for the two new models and
  nullable fingerprint owner only.
- Create one additive backend/alembic/versions migration from actual current head.
- Create backend/src/newsflow/services/editorial_admission.py.
- Modify backend/src/newsflow/domain/durable_ingestion.py narrowly for reservation
  ownership and configured-mapping unknown-branch admission.
- Create backend/tests/test_editorial_admission.py.
- Create backend/tests/test_editorial_admission_migration.py.
- Modify .github/workflows/ci.yml only to append tests/test_editorial_admission.py
  to the existing migrated PostgreSQL vertical-slice pytest command.
- Report in this plan's SDD workspace task-1-report.md.

**Persistence contracts:**

- EditorialClassifierPolicyModel / editorial_classifier_policy:
  singleton id=1 constraint, enabled bool default/server false, provider
  OPENAI/OPENROUTER, model length1..255, policy_version length1..255,
  protected_entities JSON containing explicit entity_id/aliases objects.
  No secret, qualification, PASS or rewrite permission field.
- EditorialClassificationJobModel / editorial_classification_jobs:
  immutable binding columns content_key(255), source_revision_id FK RESTRICT,
  mapping_id FK RESTRICT, editorial_decision_id FK RESTRICT,
  source_sha256/policy_sha256/mapping_sha256(64), prompt_version(64),
  provider(16), model(255), idempotency_key(64 unique).
  state constrained QUEUED/RUNNING/REVIEW/REJECT/BLOCKED/FAILED;
  attempts0..2 default0, available_at/created_at aware UTC;
  optional claim_token(36)/lease_expires_at, last_error_code(64).
  RUNNING iff both lease fields nonnull; both null in all other states.
  Unique binding identity includes source revision, mapping, policy digest,
  mapping digest, provider, model and prompt. No rewrite permission field.
- MappingContentFingerprintModel gains nullable content_key(255). No guessed
  foreign key: legacy keys/prototype sources are retained safely.
- Additive upgrade preserves all old rows/default semantics. Downgrade of these
  additions is allowed only when new policy/job tables are empty; otherwise
  refuse explicitly before DDL, preserving history. Existing fingerprint owners
  may then be discarded only on an isolated copy; document that rollback limit.

**Service interfaces:**

- frozen EditorialAdmissionBinding: revision_id, mapping_id, decision_id,
  request: EditorialClassificationRequest, mapping_sha256, provider, model.
- resolve_editorial_admission(session, *, content_key: str, mapping_id: int)
  -> EditorialAdmissionBinding. Raises EditorialAdmissionBlocked with stable
  sanitized reason code; no raw source/policy/unknown model echo.
- enqueue_editorial_classification(session, *, content_key: str, mapping_id: int,
  now: datetime) -> EditorialClassificationJobModel | None. Caller owns transaction;
  no commit/rollback/session factory/network. Missing/disabled/invalid/stale/held
  binding returns None and never creates any job/outbox/fingerprint/decision.
  Do not swallow IntegrityError or unexpected storage failures; atomic caller
  rollback must preserve retryability. Repeated exact valid binding returns the
  original job, including terminal history, not reactivation.

**Canonical resolution and ordering:**

- Validate exact content_key str nonempty <=255 and mapping_id int>0 (not bool),
  aware finite datetime input before writes; accepted classification request
  validates source/policy bounds and aliases. Reject extra JSON policy fields,
  invalid JSON shapes/types, duplicate IDs/alias ambiguity; no default-neutral
  policy repair. Use accepted ProtectedEntity/request validation, not new rules.
- Resolve current enabled policy from DB each call (populate_existing), with
  bounded JSON serialization before reconstruction (<=262144 UTF8 bytes).
  Validate explicit provider/model; OPENROUTER must be a single bounded explicit
  :free ID, never dynamic openrouter/free/paid/fallback. No provider construction.
- Resolve real mapping -> donor -> account and output; source_revision() must
  resolve exactly one immutable revision using existing SQL identity expression,
  never split keys. Incoming account/channel strings must match mapped donor's
  actual numeric account/channel. Resolve the output's actual account too, but
  do not require donor/output accounts to be identical: existing configuration
  supports explicit cross-account mappings. Bind both ownership identities in
  mapping digest; missing/ambiguous/foreign source bindings fail closed.
- Current decision for exact content must be MANUAL_REVIEW with rewrite_allowed
  exactly false. REJECT, PASS, unknown/corrupt status, absent decision or any
  existing RewriteJob for the source fail closed. No decision is updated here.
- revision_is_latest()/existing deletion/sync guards must pass on fresh reads.
  Reconstruct original TelegramMessage from persisted media/links/timestamps;
  validate media metadata and current mapping_filter(intake=True).evaluate().
  Unknown/corrupt media, video/manual-video, album, visible/hidden YouTube,
  ads/forbidden links, sample exclusion, changed filters all block before enqueue.
- Require exact mapping fingerprint SHA256(source_text.strip().casefold()) row
  with content_key == resolved exact revision key; absence, NULL owner or another
  owner blocks. Admission never creates/adopts a fingerprint to bypass dedup.
- Build accepted request from exact stored source and current policy; derive
  hashes internally. mapping_sha256 is deterministic canonical JSON of current
  mapping identity/donor/output/intake/target mix/eligibility/delay/priority/media
  policy and effective technical filter (sorted sets, actual advertising markers).
  No transient ORM cache/caller hash is authority. Job idempotency is SHA256 of
  canonical immutable binding including decision/revision IDs and all hashes,
  provider/model/prompt; text length never overflows key bounds.
- Enqueue job QUEUED/attempts0 and event editorial.classification.requested in
  same outer transaction. Outbox aggregate exact content key, idempotency
  editorial.classification.requested:<job idempotency hash>. No candidate,
  rewrite job, usage or publication outbox. Fresh repeated enqueue returns same
  job and exactly one event; persistence errors propagate, no blanket catch.

**Ingestion seam:**

- Change _reserve_exact_content(event, *, content_key) calls in both new ingress
  and existing passing fan-out; write owner with targeted ON CONFLICT DO NOTHING.
  Do not claim old conflict rows or change existing passing fan-out status/gates.
- After source persisted and current state set MANUAL_REVIEW, call enqueue only
  when _configured_mapping_id is a real positive mapping ID; use canonical stored
  inputs, not incoming annotations. Keep existing IngestionResult/status intact.
  No active/missing policy defaults, jobs from unconfigured prototypes, scan,
  credentials, factory, HTTP, actual classifier call or worker wiring.
- Earlier deterministic rejection, dedup, stale source, sync quarantine, REJECT
  and existing duplicate decision branches do not enqueue classification work.
  Exceptions in enqueue/outbox insertion roll back entire source+fingerprint+
  editorial+job unit; do not return success after failed persistence.

**TDD and verification:**

- Write tests before implementation; record actual behavioral RED/exit (missing
  symbols may use temporary assertion, no import/collection error/skip/xfail).
- Real mapped synthetic ingestion with enabled synthetic policy creates exact
  one QUEUED job/outbox, false editorial permission, RewriteJob0, rewrite calls0.
  Missing/disabled policy preserves old manual behavior with no new work.
- Regression for every guard above: protected REJECT/manual video/YT/ads/album/
  duplicates/stale/edit/deletion/sync, foreign donor/source account, missing output
  or its owner, valid explicit cross-account mapping, invalid policy,
  owner mismatch/legacy NULL, existing rewrite work, invalid caller/time/bounds.
  Actual duplicate different messages with same text create only first request.
- Fresh service resolution after retained-session cache then independent policy,
  filter/source/deletion change must block or yield different binding, never stale
  cached authority. Do not take DB locks in a new opposite order to ingestion.
  This is admission-only, not a claim of completed runtime TOCTOU fencing.
- File-backed migrated SQL reopen retains original job/idempotency/state/event;
  fault injection at classification job/outbox insertion proves whole ingress
  rollback and successful fresh retry (no poisoned dedup fingerprint).
- Admission test fixture follows existing NEWSFLOW_UNATTENDED_POSTGRES_URL
  opt-in: validate/create a fresh UUID namespace with unattended_postgres helper
  when supplied, otherwise a newly migrated isolated SQLite file. No public
  schema reuse/reset/DROP/cleanup or implicit live target. The same behavioral
  cases run on real PostgreSQL in existing CI; only append this file to that
  existing job's explicit pytest list, preserve permissions/timeouts/checks.
- Migration before/after sentinel proof retains legacy source/editorial/job/
  fingerprint rows with NULL owner; upgrade/check, empty downgrade/re-upgrade,
  populated downgrade refusal preserves both old and new data. Row constraints
  exercise invalid status/provider/lease/attempt/hash/idempotency identities.
- Covering tests include new admission/migration, durable ingestion workflow,
  SQL ingestion, technical/YT/source deletion/sync and accepted classifier/adapters.
  Native Ruff0.17 src/tests/alembic, changed format, compile, diff-check; one
  frozen full backend suite with explicit Telethon1.45 and unique D: artifact paths.
  YAML parse/command inspection for the narrow CI addition. No unchanged
  UI/recovery rebuilds. Root handles exact GitHub/actual Windows PostgreSQL
  and independent review; do not claim those as local PASS without execution.
- Self-review and detailed report with RED/GREEN/counts/commands/hashes/migration
  limit; commit only owned source/tests/migration/report, no push.

Deferred: lease executor, source/policy/mapping CAS before/after real IO, usage and
evidence persistence, real benchmark/qualification, configured protected entity
UI/API, propagation to approved editorial PASS/per-output rewrite jobs. None may
be inferred from queued diagnostic requests or synthetic tests.
