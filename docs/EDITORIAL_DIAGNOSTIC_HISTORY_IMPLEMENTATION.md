# Read-only editorial diagnostic history implementation plan

> Execute with subagent-driven-development: one writer, then independent scoped
> review. Start only after the encrypted classifier worker task is accepted.

**Goal:** Expose bounded, durable diagnostic history to the existing application
without exposing evidence/credentials or granting rewrite/publication permission.

**Architecture:** A new SQL read model projects existing immutable job, claim and
receipt tables. Add one GET route to the existing studio router; no new storage,
worker, settings, permission path or UI redesign.

**Tech stack:** Existing Python/SQLAlchemy/FastAPI/Alembic test harness.

**Spec:** Approved Telegram PHASE1 audit/history/observability requirements,
docs/IMPLEMENTATION_PLAN.md and accepted diagnostic execution/worker contracts.

## Global Constraints

- Telegram Content Studio only; preserve the accepted UI/design.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force-push, PR or push by workers.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify real models or activate automatic approval.
- No real keys, sessions, provider calls, publication or operational SQL in tests.
- Read-only diagnostics never enqueue, retry, recover, decrypt, approve or commit.
- Never expose source/evidence quotations, protected-entity aliases, captured
  links, claim tokens, request hashes, ciphertext, secrets or raw stored errors.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN, CI and actual Windows acceptance.
- No model/migration/worker/settings/Compose/dependency or frontend changes.

## Decision and boundary

History remains visible after policy disablement, source edit/deletion or terminal
editorial rejection, provided exact canonical source/mapping ownership is still
valid. This is historical evidence, not a fresh gate certificate. Do not invoke
the admission resolver to erase history merely because work is now blocked.
Never parse delimiter-separated content keys to infer account/channel ownership;
resolve the unique revision with the accepted SQL source_revision helper.

Alternatives considered: add raw receipts to every Inbox row (unbounded payload
and unnecessary sensitive evidence); expose a bounded separate read endpoint
(selected); expose controls with the read endpoint (rejected, different authority).
Rollback removes only the read route/service; no persisted row is modified.

### Task 1: Bounded SQL history projection and studio GET API

**Files:**
- Create backend/src/newsflow/services/editorial_history.py.
- Modify backend/src/newsflow/api/studio.py only for dependency/GET wiring.
- Create backend/tests/test_editorial_history.py.
- Modify .github/workflows/ci.yml only to append the new test file to the
  existing strict synthetic PostgreSQL list.
- Report in this plan's SDD workspace task-1-report.md.

**Interface:**

```python
class EditorialHistoryReader:
    def __init__(self, session): ...
    def read(self, content_key, mapping_id, *, limit=25, before_job_id=None): ...
```

- Require exact str content_key, nonblank valid UTF8, length1..255; exact positive
  int mapping_id and optional before_job_id; exact int limit1..25, never bool.
  Reject pending session.new/dirty/deleted before any SQL/autoflush.
- Resolve exactly one immutable source revision by SQL identity. Resolve mapping,
  donor, output and both account owners with fresh reads/populate_existing.
  Match source post.account/channel exactly to donor owner's canonical ID/channel;
  output may belong to another existing account. Missing/ambiguous/foreign
  relationships yield a fixed LookupError, never leak another binding's history.
  Disabled mappings/accounts, old/deleted revisions or disabled policy do not
  independently erase valid retained historical records.
- Query only exact content_key + source_revision_id + mapping_id jobs, descending
  ID and strict before_job_id cursor. Fetch at most limit+1 jobs; expose at most
  limit and next_before_job_id=last returned ID only when another row exists.
  Never scan all jobs, construct transports or infer a current qualification.
- Resolve each job's exact decision FK/content_key and immutable claims/receipts
  freshly. At most2 claims/one receipt per claim; inconsistent/malformed rows
  fail closed with static ValueError rather than silently truncating history.
- Project only this exact shape (null means genuinely unknown/not observed):

```python
{
    "content_key": content_key, "mapping_id": mapping_id,
    "diagnostic_only": True, "execution_authorized": False,
    "rewrite_allowed": False, "network_checked": False,
    "worker_enabled": None, "real_model_qualified": False,
    "items": [{
        "job_id": 1, "state": "REVIEW", "attempts": 1, "max_attempts": 2,
        "provider": "OPENAI", "model": "synthetic-explicit-model",
        "created_at": "2030-01-01T00:00:00+00:00",
        "available_at": "2030-01-01T00:00:00+00:00",
        "lease_expires_at": None, "reason_code": None,
        "receipts": [{
            "attempt": 1, "outcome": "REVIEW", "diagnostic_status": "PASS",
            "reason_codes": ["REAL_MODEL_NOT_QUALIFIED"],
            "usage_observed": False, "input_tokens": None,
            "cached_tokens": None, "output_tokens": None,
            "estimated_cost_usd": None,
            "created_at": "2030-01-01T00:00:00+00:00",
        }],
    }],
    "next_before_job_id": None,
}
```

The example's diagnostic PASS is not effective PASS. Actual receipt reason
codes come only from the accepted assessor/runner's fixed sanitized codes;
reject arbitrary stored strings instead of echoing them. Validate provider,
pinned model grammar, state/outcome/status, exact integer attempt/token counts,
lease/state consistency, observed/null usage consistency and finite nonnegative
Decimal cost. Preserve known estimated cost exactly as a decimal string, never
float/complete invoice; unknown cost stays null, not fabricated zero. Timestamps
are normalized UTC; SQLite's persisted naive UTC convention is allowed, not
caller-supplied clock authority. Never return raw evidence_json/response_model.

**API:**

```text
GET /api/studio/editorial-classification-history
    ?content_key=1%3A-1001234567890%3A7%3Arevision%3A1&mapping_id=1
    &limit=25&before_job_id=100
```

- Use existing database_session request scope; no configured DB/missing migration
  or SQL error is503 with static message, not an empty fake success.
- Canonical missing/foreign relation404; invalid request422; malformed stored
  history503. Never return raw exception text, request binding or source content.
- Private no-store and nosniff headers on successful and handled error responses.
  API only projects read history: no POST/PUT/DELETE/retry/approval route.

**TDD and gates:**

- [ ] Behavioral RED from migrated canonical admission + actual injected runner
  REVIEW/REJECT receipts; HTTP request must return real retained history, not404
  from an absent route/import/collection failure as the sole RED assertion.
  A temporary in-test empty reader seam is permitted to reach a real assertion.
- [ ] Cover exact response fields, zero rewrite/provider/decrypt/worker work and
  no SQL writes/commit/outbox mutation. Neutral diagnostic PASS stays manual-only;
  rejected, failed, retry and late LOST_LEASE histories never authorize work.
- [ ] Cover two attempts/one observed-cost plus one unknown receipt; exact Decimal
  JSON, zero known cost distinct from unknown, no sensitive fields/markers leak.
- [ ] Cover empty history, cursor pages/last-page, capped queries, wrong/bool/Unicode
  inputs, missing/foreign/cross-account mappings, colliding delimiter keys,
  invalid stored enum/reason/count/cost, dirty session and fresh committed updates
  despite a stale identity map. Rejected/old/deleted/disabled retained history
  remains readable only with correct ownership and always false permission.
- [ ] HTTP503 without DB/migration,404 ownership,422 invalid query, private headers,
  SQL errors sanitized and no raw provider/source/evidence data in exceptions.
- [ ] Target new reader + runner + existing overview/inbox API regressions; Ruff0.17
  src/tests/alembic, changed formatting, compile/YAML/diff. Freeze then one full
  backend suite with Telethon1.45. Root runs actual strict Windows PostgreSQL
  new-file tests after freeze; no old full/UI/Docker restart suite repeated.
- [ ] Self-review, report original RED/GREEN/native output/hashes/limitations;
  commit only owned files/report, no push. Independent scoped review follows.

Deferred: Inbox presentation of this endpoint, protected classifier policy editor,
real-model benchmark/qualification and qualified PASS propagation. This endpoint
does not implement those features or complete PHASE1.
