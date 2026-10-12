# Editorial classifier adapter implementation plan

> For agentic workers: use subagent-driven-development, one writer and an
> independent task review. Keep this increment separate from runtime admission.

**Goal:** Execute classification-only requests through the already implemented
bounded OpenAI/free-only OpenRouter transports without granting rewrite permission.

**Architecture:** Two small adapters wrap existing generate_json transports, pin
response model identity, and assess evidence using the accepted source/policy-bound
contract. They have no DB, worker, factory, endpoint or activation flag. Existing
ingestion stays unknown/MANUAL_REVIEW; a future durable job admission layer must
perform current filters/exact dedup/source/policy checks before invoking adapters.

**Tech Stack:** Python3.12, Pydantic2, existing urllib providers, pytest/Ruff0.17.

**Spec:** docs/IMPLEMENTATION_PLAN.md NEXT_STEP; accepted
docs/EDITORIAL_CLASSIFICATION_IMPLEMENTATION.md; docs/QUALITY_GATES.md.

## Global Constraints

- Telegram Content Studio only; no UI/design changes.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force push, PR or external writes by workers.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify a real model or activate automatic approval.
- No real credentials, Telegram sessions, AI calls, publication or operational SQL.
- No network calls or classification inside an ingestion database transaction.
- Keep existing source/review/fact/technical/sync/session/publication gates.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN and CI tracking; worker must not
  modify them, Compose, dependencies or existing runtime production services.

### Task 1: Classification-only provider adapters

**Files:**
- Create backend/src/newsflow/providers/editorial_classifier.py.
- Modify backend/src/newsflow/services/editorial_classification.py only to expose
  editorial_evidence_schema() -> dict returning a fresh strict evidence schema.
- Create backend/tests/test_editorial_classifier_adapters.py.
- Report in this plan's SDD workspace task-1-report.md.

**Interfaces:**
- OpenAIEditorialClassifier(*, api_key: str, model: str, opener=None).
- FreeOpenRouterEditorialClassifier(*, api_key: str, model: str, opener=None).
- Each exposes provider ('OPENAI'/'OPENROUTER'), model, prompt_version matching
  editorial-classification-v1; classify(request: EditorialClassificationRequest)
  -> EditorialClassificationReport. No qualification/rewrite/schedule/pub method.
- Read-only last_usage/last_response_model properties report only this attempt;
  reset on every call, including invalid local input (no stale previous result).
- editorial_evidence_schema() exposes existing _Evidence schema without aliasing
  shared mutable schema or duplicating the evidence definition.

**Required behavior:**

- Use existing OpenAIRewriteProvider.generate_json or
  StructuredFreeOpenRouterProvider.generate_json. NEVER invoke rewrite().
  No new URL, HTTP implementation, retry/fallback loop, key creation or settings.
- Source and policy payload must be the exact accepted request.payload;
  instructions come from request.messages[0]['content'], not source text.
  Schema = editorial_evidence_schema(), name = newsflow_editorial_classification.
  Request source remains original, never rewritten/repaired/truncated.
- Validate exact request type before IO. Serialized payload must fit existing
  shared transport bound131072 codepoints and explicit262144 UTF8 bytes;
  oversize fails before IO with ProviderConfigurationInvalid and stable code.
- OpenAI delegates existing model/key/timeout validation. OpenRouter uses only
  the single explicitly requested model, requires :free suffix, refuses dynamic
  openrouter/free and any paid/invalid/duplicate fallback before IO. No arbitrary
  fallback to an unqualified classifier model. Existing free-only transport
  require_parameters/allow_fallbacks=false/max_price0 must remain unchanged.
- Response model identity must match requested model. OPENAI exact comparison;
  OPENROUTER accepts only exact configured ID or the same ID without :free,
  matching the existing semantic-verifier identity convention. Missing, malformed,
  paid/different model fails with ProviderResponseInvalid and stable code.
  Do not expose unexpected response model text in errors/properties.
- Canonicalize returned object to bounded raw JSON with allow_nan=false and feed
  the strict accepted assess_editorial_classification(request, raw). Unknown
  fields, false hashes, fabricated/omitted quotes, incomplete/uncertain claims
  retain contract's false permission. Do not invent neutral/PASS on failures.
- Transport configuration/unavailable/refusal/schema/network errors retain
  existing typed exceptions, with no repair call/retry beyond existing bounded
  transport. Sanitized error text only, never raw source/key/response/body.
- last_usage can retain known validated usage for an actual attempted failed
  provider response, but never copy stale usage when no IO was attempted.
  last_response_model is populated only after validated identity. No API key
  accessible in report, exception, repr or public adapter attributes.
- Every returned report remains real_model_qualified=false and rewrite false.
  Adapter use is not qualification and not production ingestion integration.

- [ ] Step1: Write focused tests before implementation using real existing
  providers with injected HTTP opener/response objects at the network boundary.
  Use only synthetic credentials. Initial boundary check may assert missing
  callable without import-error; replace temporary existence check with real
  behavior once available. Example independent behavior assertion:

```python
report = classifier.classify(request)
assert report.decision.status.value == 'MANUAL_REVIEW'
assert report.decision.rewrite_allowed is False
assert report.real_model_qualified is False
assert editorial_allows_rewrite(report.decision) is False
```

- [ ] Step2: Run RED `python -m pytest tests/test_editorial_classifier_adapters.py -q`
  from backend, record actual expected failure; no skip/xfail.
- [ ] Step3: Implement adapters/public schema boundary only. Test actual emitted
  HTTP payloads via injected opener, exact unchanged source/policy bindings,
  structured schema, classification-only instructions and one attempted request
  for success. Install rewrite() tripwire in tests to prove it is never invoked.
- [ ] Step4: Test both providers: neutral diagnostic PASS/effective manual,
  protected-negative REJECT, stale hash/key/policy, invalid/uncertain evidence,
  response identity mismatch/missing/overlength, refusal/incomplete/malformed,
  timeouts/auth failures. Test no repair/second call after invalid response.
  OpenRouter paid/dynamic refusal must occur before opener calls. Inspect emitted
  free-only request constraints. Oversize request and invalid second call must
  fail before IO and clear prior usage/response identity. Constructor/repr and
  errors must not disclose synthetic credential or source sentinel. Test fresh
  schema mutation does not mutate subsequent schemas/request data.
- [ ] Step5: Run covering new adapters + accepted classification contract +
  existing structured provider/semantic-verifier tests. Run CLI benchmark again
  only as contract comparison, not model eval. Format changed files/native
  Ruff0.17 src/tests/alembic, compile, git diff --check. A single frozen full
  backend suite before commit, no unchanged frontend/PG/Docker repetition.
  Use owned unique D:/Codex-Recovery/content-studio-20261008/editorial-adapter-*
  temp/cache; explicit sys.path insertion for Telethon1.45 if needed. Do not
  delete retained resources; preserve failures and exact skip/exit counts.
- [ ] Step6: Self-review, full report with commands/RED/GREEN/frozen hashes/
  limitations. Commit only task files/report; no push. Root independently reviews.

Deferred: credential factory/settings selection, canonical durable admission and
dedup/filter/current-source CAS, leased jobs/recovery, model qualification and
real benchmark, runtime worker activation. This adapter must not be wired to
ingestion before those guards exist. All verification is injected HTTP/no live IO.
