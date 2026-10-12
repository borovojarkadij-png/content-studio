# Durable diagnostic classifier execution implementation plan

> Execute with subagent-driven-development: one writer, then independent scoped
> review. Begin only after canonical durable admission is independently accepted.

**Goal:** Execute already admitted diagnostic requests with committed attempt
budgets, leases, canonical pre/post-call validation and durable audit evidence.
No diagnostic result can approve a post, create a rewrite or publish anything.

**Architecture:** Extend the accepted classifier adapter with a read-only bounded
raw-evidence receipt. A separate injectable durable runner uses the accepted SQL
admission resolver, closes each SQL session before external calls and persists
one append-only attempt receipt plus outbox/job transition transactionally.
No configuration API, credential factory or worker-loop activation is included.

**Spec:** Approved Telegram PHASE1; docs/IMPLEMENTATION_PLAN.md NEXT_STEP,
docs/EDITORIAL_DURABLE_ADMISSION_IMPLEMENTATION.md and docs/QUALITY_GATES.md.

## Global Constraints

- Telegram Content Studio only; preserve the accepted UI/design.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force-push, PR or push by workers.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify real models or activate automatic approval.
- No real keys, sessions, provider calls, publication or operational SQL in tests.
- No runner-owned database locks or active session/transaction during provider construction/IO.
- Keep source/editorial/review/fact/technical/sync/session/publication constraints.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN, CI tracking and actual Windows PG.
- No main-loop/settings/API/UI/Compose/dependency changes or old-row resubmission.

## Decision

This increment executes diagnostics, not an approval path. Even a well-formed
diagnostic PASS remains effective MANUAL_REVIEW with rewrite permission false.
Do not mutate editorial_decisions, existing rewrite jobs, candidates or outputs.
The fresh canonical checks and immutable request hashes bind a receipt to its
historical request; they do not claim permanent freshness after commit or the
later shared locking needed to propagate a qualified real-model PASS.

One bounded attempt receipt combines outcome/evidence and observed usage rather
than inventing a second billing system. A separate immutable claim-history row
proves an older token really owned an attempt after the job has been reclaimed;
the caller's claim object alone is not authority for a late charge receipt.
Missing usage is unknown, never zero.
External exactly-once AI execution is not promised: a crash after a call but
before a receipt may require another call, bounded by two committed attempts.

### Task 1: Leased diagnostic execution and append-only attempt receipts

**Files:**
- Modify backend/src/newsflow/providers/editorial_classifier.py narrowly for
  read-only last_evidence_json, without changing classify's return contract.
- Modify backend/src/newsflow/persistence/models.py for claim and receipt models.
- Create one additive backend/alembic/versions migration from actual head.
- Create backend/src/newsflow/services/durable_editorial_runner.py.
- Create backend/tests/test_durable_editorial_runner.py.
- Create backend/tests/test_editorial_attempt_migration.py.
- Extend backend/tests/test_editorial_classifier_adapters.py for receipt reset.
- Append only the new runner test file to the existing strict migrated PG CI list.
- Report in this plan's SDD workspace task-1-report.md.

**Adapter receipt:**

_EditorialClassifier.last_evidence_json -> str | None is read-only, reset before
every attempt, including rejected request/configuration paths. Set it only after
successful returned-model validation and canonical bounded serialization of the
actual transport JSON, before assessing it. Do not fabricate evidence from the
report, retain previous-attempt output, expose a key or perform repair calls.
Invalid schema/binding evidence may be retained as diagnostic data, never as
authorization. Existing typed errors/usage/strict free-model identity stay intact.

**Attempt persistence:**

EditorialClassificationClaimModel / editorial_classification_claims:
id PK, classification_job_id FK RESTRICT, attempt int1..2,
claim_token str36 unique, created_at aware UTC, Unique(classification_job_id,attempt).
Append-only UPDATE/DELETE-refusal triggers. Commit it atomically with each job
claim. A reclaimed job never destroys the old token's provenance. No source,
policy, permission, usage or response fields are duplicated into this table.

EditorialClassificationAttemptModel / editorial_classification_attempts:
id PK, claim_id unique FK RESTRICT to editorial_classification_claims,
outcome REVIEW/REJECT/BLOCKED/FAILED/RETRY/LOST_LEASE,
diagnostic_status nullable PASS/REJECT/MANUAL_REVIEW,
reason_codes nonnull JSON list of stable sanitized codes,
evidence_json nullable bounded string (<=262144 UTF8 bytes, runtime validated),
response_model nullable str255, usage_observed bool default/server false,
input_tokens/cached_tokens/output_tokens nullable integers,
estimated_cost_usd nullable Numeric(20,10), created_at aware UTC.
One receipt per immutable claim; no permission/qualification field.
DB constraints enforce bounded claim attempt/token and receipt status/outcome, nonnegative observed
counts and cached<=input, finite nonnegative known cost; unobserved usage requires
all token/cost fields NULL, observed usage requires all three token counts.
Sanitize/validate observed RewriteUsage before writes: exact integer counts not
bool, actual supported provider and bounded model, finite Decimal estimate or
None. Invalid usage remains unobserved with a stable reason, never coerced zero.
Install UPDATE/DELETE-refusal triggers for both append-only tables on SQLite/PG,
using existing migrated audit patterns. No policy/job/backfill/setting seeds.
Either populated table explicitly blocks downgrade before DDL; no operational
rollback/deletion. Upgrade preserves existing policies/jobs/fingerprints/history.

**Runner interfaces:**

```python
@dataclass(frozen=True, slots=True)
class EditorialClaim:
    job_id: int
    token: str
    attempt: int

class EditorialLeaseLost(PermissionError):
    pass

class DurableEditorialRunner:
    def __init__(self, session_factory, *, classifier_for_binding,
                 clock=lambda: datetime.now(UTC)): ...
    def claim_next(self, *, now: datetime, limit: int = 16) -> EditorialClaim | None: ...
    def execute(self, claim: EditorialClaim) -> str: ...
    def run_next(self, *, now: datetime) -> str: ...
```

Use the existing accepted EditorialAdmissionBinding and resolver, not caller
text/hash/report annotations. Stable returned states: IDLE, REVIEW, REJECT,
BLOCKED, FAILED, RETRY, LOST_LEASE. Reject malformed IDs/token/attempt/datetime/
limit before side effects; exact positive integers, canonical UUID token,
aware finite UTC times, limit1..100 (bool invalid). No raw exceptions in results,
logs, job.last_error_code, receipt reasons or outbox.

**Leases, gates and transactions:**

- Consider at most limit due QUEUED or expired RUNNING job IDs, ascending ID.
  Acquire the job FOR UPDATE/SKIP LOCKED; recheck eligibility after locking.
  No new opposite lock order with shared ingress/source/configuration writers.
  Terminal jobs and active leases are never reactivated or refunded.
- Fresh canonical resolver and exact immutable binding comparison must precede
  attempts/factory/IO. Compare revision/decision/mapping IDs, content key,
  source/policy/mapping digests, provider/model/prompt. Missing/disabled/changed
  policy, REJECT/PASS/nonmanual/current rewrite, duplicate/foreign fingerprint,
  stale/delete/sync/technical/ownership hold -> BLOCKED, no provider creation.
- Exhausted attempts -> FAILED with EDITORIAL_ATTEMPTS_EXHAUSTED. Otherwise
  commit RUNNING/random UUID token, attempts+1, lease now+60s and immutable claim
  history row atomically before returning. Faults roll back the whole claim.
- execute rechecks owned state/token/attempt/unexpired lease, then all canonical
  bindings; close SQL before factory. Validate classifier provider/model/prompt
  exactly, then revalidate in a new closed SQL session after construction and
  immediately before classify. Never call rewrite or repair.
- A RUNNING job without matching immutable claim history is not an authorized
  legacy claim. Fail closed without guessing/backfilling a token or invoking IO.
- After IO, a new transaction revalidates claim and fresh canonical binding.
  Ignore any permissive/forged classify return: assess only last_evidence_json
  with accepted assess_editorial_classification and the authoritative request.
  Valid effective REJECT -> diagnostic job REJECT; every other valid/uncertain
  report -> REVIEW, never PASS/SUCCEEDED/permission. Missing/ill-typed/oversized
  receipt -> terminal FAILED with stable code. Bounded but invalid schema,
  binding or uncertain evidence -> assessor's manual REVIEW, never repair retry.
- Binding invalidated during IO -> BLOCKED; receipt is quarantined diagnostic
  history only. Lost/expired/reclaimed lease -> LOST_LEASE, no job overwrite.
  Preserve known usage for the old committed attempt with its exact token even
  after lease loss only when immutable claim history confirms job/token/attempt;
  forged tokens cannot write late history. Do not transition the new owner or
  overwrite a prior receipt.
- ProviderUnavailable only: RETRY via same job QUEUED/available now+60s when
  attempt<2, otherwise FAILED. Configuration/response/unknown provider errors
  -> FAILED. Never automatic paid/free fallback beyond the pinned adapter.
- Receipt, owned job transition/lease release and event
  editorial.classification.attempted commit atomically. Event aggregate is exact
  content key; idempotency editorial.classification.attempted:<jobid>:<attempt>.
  Existing exact receipt/history returns unchanged, no duplicate event or call.
  Insertion/storage faults propagate; do not swallow unrelated IntegrityError.
  Crash leaves committed RUNNING budget/lease recoverable; no poisoned success.
- Do not hold SQL over external IO. No global worker flag, secret lookup or
  credential decryption here; factory injection is server-internal only.

**TDD / verification steps:**

- [ ] Write a migrated synthetic-ingress runner regression before implementation:
  an enabled policy creates the existing queued request; claim commits attempt1;
  fake classifier supplies exact bound neutral JSON; run ends REVIEW, original
  editorial stays MANUAL_REVIEW/false, RewriteJob0 and rewrite/provider calls0
  except the single intentionally counted synthetic classify invocation.
- [ ] Execute it to a real behavioral assertion RED, no import/collection error,
  skip/xfail or assertions that merely compare mocked return values.
- [ ] Implement the declared receipt/runner boundaries and minimal additive
  migration; run focused GREEN. Fake classify callbacks use independent committed
  source/policy/filter/editorial changes to prove actual pre/post fresh checks.
- [ ] Cover protected-negative, malformed/forged report, stale source/policy/
  mapping/owners, disabled policy, video/YT/ads/album/deletion/sync/dedup holds,
  factory identity/configuration failures, raw-secret exception sanitization,
  expired lease/reclaim/old result, original terminal replay, retry exhaustion,
  unknown vs known/invalid usage, job/claim/receipt/outbox insertion rollback and SQL
  reopen. Every blocked-before-IO case asserts factory/classify/rewrite counts0.
- [ ] Same runner fixture supports strict NEWSFLOW_UNATTENDED_POSTGRES_URL via
  create_postgres_namespace; otherwise migrated SQLite. Fresh UUID only, no DROP,
  public reset, retained-data mutation or cleanup. Actual independent PG writers
  prove two claimants cannot own one attempt; no sleep-based race probability.
- [ ] Migration sentinel/metadata/no-drift and populated downgrade refusal retain
  old/new rows. Direct SQL proves receipt UPDATE/DELETE refusal and bounds.
- [ ] Cover accepted admission/classifier/adapters and durable ingress/freshness
  files. Native Ruff0.17 src/tests/alembic, changed format, compile, YAML/diff check.
  One frozen full backend suite with explicit Telethon1.45 and unique D: paths.
  Root owns actual Windows PG and review/new exact CI; no duplicate full suite.
- [ ] Self-review, detailed report actual RED/GREEN/native commands/counts/skips/
  frozen hashes/limitations; commit only owned files/report, no push.

Deferred: actual model qualification/benchmark, protected-policy settings API/UI,
encrypted classifier factory, opt-in worker orchestration, qualified editorial
PASS propagation and per-output rewrite admission. No PHASE1 completion, live
call or automatic approval follows from this diagnostic runner.
