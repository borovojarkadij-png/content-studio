# Bounded editorial model evaluation implementation plan

> Execute with subagent-driven-development, one writer then independent scoped
> review. Start only after the diagnostic history increment is accepted.

**Goal:** Produce a reproducible, bounded diagnostic model-evaluation report from
actual classifier responses, without granting model qualification or permissions.

**Architecture:** A pure orchestration service validates a frozen synthetic labeled
dataset, calls one already accepted pinned classifier, and independently assesses
its actual evidence. A default-no-network CLI explicitly opts into bounded calls.
No database, worker, registry, settings or application behavior changes.

**Tech stack:** Existing Python, accepted OpenAI/free-only OpenRouter classifiers,
strict JSON parser, pytest and existing CI lint/full backend gate.

**Spec:** Approved PHASE1 actual model benchmark/report requirement,
QUALITY_GATES.md, EDITORIAL_LIVE_ACCEPTANCE_20261012.md and accepted classification
contract/adapters. Existing SYNTHETIC_CONTRACT benchmark remains unchanged.

## Global Constraints

- Telegram Content Studio only; preserve the accepted UI/design.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force-push, PR or push by workers.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify real models or activate automatic approval.
- No real keys, sessions, provider calls, publication or operational SQL in tests.
- Never generate/rotate a key, read real env files or print credentials.
- Evaluation reports are untrusted evidence until independently reviewed; no
  result or report field may activate a release, editorial PASS or publication.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN, CI evidence and live acceptance.
- No schema, settings, worker, transport, prompt, frontend or Compose changes.

## Decision and boundaries

Do not reuse the synthetic contract's supplied evidence as a model response.
That dataset deliberately contains fabricated binding mutations, useful for
parser regressions but not evidence of real classifier accuracy. Use a separate
small labeled synthetic-source dataset without supplied model evidence.

Alternatives: report existing synthetic contract as model accuracy (invalid);
run a full unrestricted production corpus (unsafe/expensive); bounded separate
fixture + pinned classifier + honest partial report (selected). This is a
verification seam within the approved benchmark requirement, not a new product
subsystem. Rollback removes only evaluator/CLI/tests; no data migration.

### Task 1: Strict labeled dataset, bounded evaluator and safe opt-in CLI

**Files:**
- Create backend/src/newsflow/services/editorial_model_evaluation.py.
- Create backend/tests/fixtures/editorial-model-v1.json.
- Create backend/tests/test_editorial_model_evaluation.py.
- Create scripts/evaluate_editorial_model.py.
- Modify .github/workflows/ci.yml only to append the new script to the existing
  backend Ruff check command. Never execute live evaluation in CI.
- Report in this plan's SDD workspace task-1-report.md.

**Interface:**

```python
def evaluate_editorial_model(
    dataset, *, classifier, max_calls: int, budget_seconds: int, clock=None
) -> dict: ...
```

- No environment, file, SQL, worker, credential or transport construction in
  this service. clock defaults to time.monotonic; tests inject a finite clock.
- Validate the entire dataset before any classify call. Exact dict keys
  benchmark_version, synthetic, cases; version editorial-model-v1; synthetic is
  exact True; 1..24 cases. Each case exact keys id/content_key/source_text/
  policy_version/protected_entities/expected_diagnostic_status. Use the existing
  immutable request/ProtectedEntity validation. IDs unique nonblank ASCII
  [A-Za-z0-9][A-Za-z0-9._-]{0,127}; content keys unique. Expected status exactly
  PASS, REJECT or MANUAL_REVIEW, no supplied evidence or action permission.
- max_calls exact int1..24 and budget_seconds exact int1..300, never bool.
  Validate classifier exact accepted OpenAIEditorialClassifier or
  FreeOpenRouterEditorialClassifier, pinned provider/model/prompt identity and
  free-only constraints before calls; do not accept arbitrary verdict objects.
- Capture immutable request/provider/model/prompt/dataset identities before
  execution; compare classifier identity before and after every call. Count
  each attempted classify invocation before calling it. One call per case,
  no retry, repair, rewrite, fallback, dynamic model or cross-provider change.
- Reassess classifier.last_evidence_json using the accepted assessor and original
  request. Do not trust the returned report or echoed hashes as authentication.
  Typed configuration/response/provider failures produce stable static outcome
  codes, never exception text; configuration errors stop the remaining run.
  Invalid/missing evidence cannot match an expected PASS/REJECT by fabrication.
- Validate finite nonnegative monotonic clock before/after calls; backward or
  invalid readings terminate visibly. Stop BEFORE the next call when the call
  cap or elapsed budget is exhausted. Existing bounded transport may finish
  its one in-flight call up to30 seconds beyond the orchestration deadline;
  document this accurately, no invented strict wall-clock cancellation.
- Return only bounded JSON-safe metadata: evaluation_kind MODEL_DIAGNOSTIC,
  benchmark_version, canonical dataset_sha256, prompt_version, provider/model,
  max_calls/budget_seconds, attempted_count/completed_count/matched_count,
  mismatched_count, completion_status COMPLETE/CALL_BUDGET_EXHAUSTED/
  TIME_BUDGET_EXHAUSTED/CONFIGURATION_FAILED/CLOCK_INVALID, and cases containing
  only id/expected_diagnostic_status/actual_diagnostic_status/matched/error_code.
  An error outcome has null actual status and matched=false, never a verdict.
  Unattempted cases are omitted and reported by total case_count separately.
- Always include real_model_qualified=false, qualification_granted=false,
  execution_authorized=false, rewrite_allowed=false, rewrite_calls=0 and
  transport_attestation=UNATTESTED. Both real and injected transport reports
  remain unqualified until independent provenance/dataset/results review.
  Never return source text, aliases, raw evidence, provider error, credentials,
  claims, internal hashes other than the public canonical dataset digest.
- Do not invent a token-price/cost/invoice field. Existing durable diagnostics
  remain the independent usage-history source; this evaluator is accuracy and
  conformance evidence, not a cost ledger or release registry.

**Fixture:**

Exactly24 clear synthetic cases, independently specified labels (not generated
from actual responses), distributed across Russian, Ukrainian and English.
Include protected neutral/positive/negative/hostile, negative unprotected,
mixed/unknown/ambiguous, incomplete-context and prompt-injection-as-source
examples. Use fictional entities/owned synthetic text, no real donor corpus,
keys, URLs to operational destinations or asserted actual-world accusations.
Fixture labels are reviewable test labels, not a human-approved qualification
dataset; a green simulated run never promotes them or the real model.

**CLI:**

```text
python scripts/evaluate_editorial_model.py --allow-provider-calls
    --provider OPENAI --model explicit-model --max-calls 3 --budget-seconds 90
```

- Default dataset is the checked-in model fixture. An explicit --dataset path
  is read-only, bounded262144 bytes and parsed by existing strict JSON parser.
- Without explicit --allow-provider-calls return static JSON error/native2,
  attempted_count0 and all permission/qualification fields false; do not read
  credentials or construct a classifier. No implicit environment autoactivation.
- Only explicit provider OPENAI/OPENROUTER and pinned --model. Credential comes
  from process-local NEWSFLOW_EDITORIAL_EVAL_API_KEY only, never command-line
  argument/file/catalog/DB. Missing/malformed value yields static JSON/native2
  before network. Do not write env/key files, create keys or print values.
- A complete all-matching run exits0, completed mismatches/provider failures or
  partial run exits1, invalid input/configuration before execution exits2.
  Emit one bounded sanitized JSON report to stdout. Argument errors must not
  echo unknown argument values or secrets; help contains only public names.
  Unexpected exceptions must not print traceback/private text or fake success:
  native1/static EVALUATION_INTERRUPTED and attempted_count=null (unknown),
  never claim attempted_count0 after an unobserved partial execution.

**TDD and verification:**

- [ ] Behavioral RED using accepted classifier with injected counted transport
  and a real immutable request: misleading returned report cannot substitute for
  actual evidence; expected mismatch/count/false qualification asserted. Temporary
  in-test empty seam allowed, not an absent import as the sole RED evidence.
- [ ] Both accepted adapters with synthetic HTTP responses; all24 fixture labels
  evaluated against explicitly injected evidence, exact pinned model and prompt,
  no rewrite method, no SQL/settings/worker mutation. This proves harness behavior
  only, never real model accuracy. Keep original RED/native logs.
- [ ] Invalid final dataset case prevents all earlier calls; duplicate/extra/
  Unicode/bool/wrong type/model/prompt inputs; fabricated report, stale/missing/
  malformed evidence and changed identity; refusal/unavailable/config failure.
- [ ] Cap1 and time boundary prevent a second call, no hidden retry; clock NaN/
  infinity/backward handling, partial counts and unattempted case accounting;
  exact stdout schema cannot leak supplied secret/source/error markers.
- [ ] CLI no-flag/no-credential/malformed dataset/unknown argument are zero-call
  subprocess tests. In-process explicit opt-in tests monkeypatch only classifier
  transport and fake environment credential, never live network or actual keys.
- [ ] Target new evaluator/accepted classifier contract/adapters. Ruff0.17,
  changed formatting/compile/script CLI/YAML/diff checks. Freeze then one complete
  backend suite with Telethon1.45. Root checks raw logs/frozen hashes and safe
  no-flag CLI independently; no schema/PG/UI/Docker recovery rerun needed.
- [ ] Self-review, original RED/GREEN/native results/hashes/limitations, exact
  owned-file/report commit only, no push. Independent scoped review follows.

Deferred: actual secret-backed model run, independently reviewed dataset and
release qualification, protected policy editor, guarded PASS propagation and
post-rewrite semantic benchmark. This task does not satisfy those gates or
complete PHASE1. Missing live credentials never becomes a passing model result.
