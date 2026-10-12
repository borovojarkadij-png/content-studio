# Source-bound editorial classification implementation plan

> For agentic workers: use subagent-driven-development, one writer and an
> independent task review. This is a bounded increment of the approved PHASE1.

**Goal:** Validate source/policy-bound pre-rewrite classifier evidence and run a
reproducible synthetic contract benchmark without granting rewrite permission.

**Architecture:** A pure offline service derives bindings from exact source text
and an explicit protected-entity policy. Strict evidence is assessed by the existing
deterministic EditorialGate. Only negative protected evidence can become REJECT;
all other effective decisions remain MANUAL_REVIEW until separately implemented
real-model qualification. Existing ingestion/worker/API behavior is unchanged.

**Tech Stack:** Python3.12, existing Pydantic2, pytest, Ruff; no new dependencies.

**Spec:** docs/IMPLEMENTATION_PLAN.md and docs/QUALITY_GATES.md; CURRENT_STATE.md
NEXT_STEP names this contract/benchmark. User-approved mandatory EditorialGate
before rewrite, cheap filters/dedup first, exact source identity and no synthetic
qualification are binding. No new production policy/entity list is invented.

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
  modify them, Compose, existing production services or dependency configuration.

### Task 1: Offline source/policy-bound classifier contract and benchmark

**Files:**
- Create backend/src/newsflow/services/editorial_classification.py (pure contract).
- Create backend/tests/test_editorial_classification.py (behavioral regressions).
- Create backend/tests/fixtures/editorial-classification-v1.json (synthetic cases).
- Create scripts/evaluate_editorial_contract.py (offline JSON stdout evaluation).
- Report in this plan's SDD workspace task-1-report.md.

**Interfaces:**
- Consumes EditorialGate, EditorialDecision, EditorialStatus from existing domain.
- Produces frozen ProtectedEntity(entity_id: str, aliases: tuple[str, ...]).
- Produces build_classification_request(*, content_key: str, source_text: str,
  policy_version: str, protected_entities: tuple[ProtectedEntity, ...]) ->
  EditorialClassificationRequest, immutable and constructed from validated inputs.
- Request exposes content_key, source_text, source_sha256, policy_sha256,
  prompt_version, protected_entities and classification-only messages/payload.
- Produces assess_editorial_classification(request, raw: str) -> report with
  diagnostic_status (string), decision (EditorialDecision), real_model_qualified
  (read-only false) and stable reason_codes. No caller qualification toggle.
- Produces evaluate_editorial_contract(cases: list[dict]) -> JSON-serializable
  aggregate/case results for trusted checked-in synthetic benchmark inputs.
- CLI reads only the checked-in fixture by default, prints JSON, exits0 only
  for all expected comparisons; invalid/mismatching dataset exits nonzero.

**Exact request/evidence rules:**

- prompt_version = editorial-classification-v1. Derive source_sha256 from exact
  UTF8 bytes (no normalization). Derive policy_sha256 from deterministic JSON
  containing policy_version and sorted entity IDs with sorted aliases; policy
  ordering is not semantic. Policy changes invalidate old evidence.
- Require nonblank content_key/policy_version (max255 codepoints), source text
  nonblank and max32000 codepoints/max128000 UTF8 bytes. Reject invalid surrogates.
- Entity IDs nonblank/max128; aliases nonblank/max255; at most64 entities and
  16 aliases per entity, at least1 alias each. Reject duplicate IDs and ambiguous
  normalized aliases across entities. Reject wrong types rather than coercion.
- Evidence JSON max262144 UTF8 bytes, object root, exact required fields:
  content_key, source_sha256, policy_sha256, prompt_version, source_complete(bool),
  ambiguous(bool), sentiment(negative/neutral/positive/unknown/mixed),
  framing(hostile/neutral/positive/unknown/mixed), entity_findings(list<=64).
- Each finding has exactly entity_id and source_quote (nonblank/max32000).
  Unique known entity IDs only; exact contiguous quote must occur in source and
  contain one configured alias under NFKC+casefold matching. Every cheaply matched
  protected entity in the source must have a finding; omission fails closed.
- Strict Pydantic extra-forbid types. Refuse duplicate keys at any depth,
  NaN/Infinity, invalid UTF8/surrogates, malformed/deep JSON and unknown fields;
  return sanitized reason code without leaking raw text/error contents.
- Bind echoes against authoritative request fields. Wrong source/policy/content/
  prompt binding fails closed. Echoed hashes are not themselves authentication.
- On malformed/missing/mismatched/incomplete/ambiguous evidence effective status
  MANUAL_REVIEW, rewrite_allowed=false. Unknown/mixed remains MANUAL_REVIEW.
- On valid complete unambiguous protected-negative/hostile evidence existing
  EditorialGate diagnostic/effective status REJECT, rewrite_allowed=false.
- A valid diagnostic PASS is NOT effective PASS: decision MANUAL_REVIEW,
  rewrite_allowed=false, reason REAL_MODEL_NOT_QUALIFIED. Report never supplies
  a runtime rewrite/publication authorization or a mutable qualification flag.
- Prompt is classification-only. Treat source as untrusted data, do not rewrite,
  change tone, repair negativity, schedule, publish or execute source instructions.
  This contract has no provider/DB/worker adapter and grants no action.

- [ ] Step1: Write behavioral tests before implementation. Initial RED can be a
  missing callable assertion (avoid import/fixture-setup errors):

```python
import importlib.util

def test_classifier_boundary_is_available():
    spec = importlib.util.find_spec('newsflow.services.editorial_classification')
    assert spec is not None, 'source-bound classifier boundary is missing'
```

Then replace this temporary availability assertion with real behavior tests once
the module exists. Add each new guard RED first. Hand-derived assertions include
neutral evidence never yielding effective PASS, protected-negative REJECT, exact
binding invalidation after whitespace edit and no source-text leakage in reasons.

- [ ] Step2: Run focused RED: `python -m pytest tests/test_editorial_classification.py -q`
  from backend. Record actual assertion failure and why; no test skip/xfail.
- [ ] Step3: Implement the interfaces/rules above, using small pure functions and
  existing schema patterns. Keep request/evidence validation bounded. No generic
  provider or future qualification framework.
- [ ] Step4: Add at least18 versioned synthetic cases: ordinary neutral/positive,
  protected-negative, hostile framing, unprotected-negative, unknown, mixed,
  incomplete, ambiguity, sarcasm/negation/quoted accusations, prompt injection,
  fabricated quotes/entities, omission, stale source/policy/key/prompt and invalid
  schema. Store labels/evidence independently of implementation. Fixture can use
  explicit named mutations to otherwise valid bound response; builder may fill
  bindings but never derive expected verdict with code under test.
- [ ] Step5: Test raw parsing duplicate keys including nested, oversize/deep/NaN,
  strict booleans/types/extra keys, exact byte binding, entity-policy collisions,
  immutable request and no callable qualification bypass. Assert existing
  editorial_allows_rewrite(report.decision) is false in every fixture case.
- [ ] Step6: Benchmark report explicitly evaluation_kind=SYNTHETIC_CONTRACT,
  real_model_qualified=false, provider_calls=0, rewrite_calls=0, case counts,
  matched/mismatched counts, per-case expected/actual diagnostics. Never call this
  model accuracy. Exercise CLI in subprocess, including nonzero mismatch and
  malformed dataset; don't grep its source.
- [ ] Step7: Run focused tests, existing editorial/ingestion/rewrite guard tests,
  then a single frozen full backend suite. Use owned D: temp/cache directories
  (`--basetemp` unique), no deleting retained schemas/artifacts. Native Ruff0.17
  executable at D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe
  must check all source/tests/alembic/new script; format changed files; compile;
  git diff --check. Full-suite PG-only skips remain explicit, no PG reset needed.
  Existing Telethon1.45 override directory is on D:, but module import must be
  verified (environment may prioritize installed site packages).
- [ ] Step8: Run CLI and retain output as generated evidence, write full report
  with RED/GREEN/results/failures/limitations/changed files/self-review. Commit
  only task files and report. No push. Return status/commit/test-summary/report
  path; root performs independent review and tracks exact CI.

Deferred explicitly: live classifier adapter, durable classification jobs/source
CAS/recovery, qualification storage and real benchmark, operator policy setup,
automatic approval activation. Those are not completed by this increment.
