# Task 1 independent review

## Spec Compliance

- ✅ Spec compliant for the task-scoped diff `9bb6147ccb640a24311aad2a3f65303c463b3d97..6dd351763d0241183c8ea9e7061741a9d10f15c4`. Every requested implementation file and the authorized CI change are present; the only additional file is the requested implementation report.
- `backend/src/newsflow/providers/editorial_classifier.py:24`: the shared classification interface exposes provider/model/prompt identity and read-only attempt properties. The concrete constructors at lines 88–102 wrap the required existing transports, with one explicit OpenRouter model and no rewrite, qualification, scheduling, publication, factory, or ingestion integration.
- `backend/src/newsflow/providers/editorial_classifier.py:45`: both attempt properties are cleared before exact request-type validation; payload serialization and both requested bounds precede the transport call. At line 54, the accepted payload, accepted instructions, fresh evidence schema, and required schema name are passed unchanged to `generate_json`.
- `backend/src/newsflow/providers/editorial_classifier.py:68`: OpenAI requires exact response identity, and OpenRouter additionally permits only the configured ID with `:free` removed. Unexpected identity is neither interpolated into the error nor copied to the public response-model property.
- `backend/src/newsflow/providers/editorial_classifier.py:75`: returned evidence is canonicalized with `allow_nan=False`, bounded in UTF8 bytes, and passed to the accepted strict assessor. Serialization/parser recursion is converted to a sanitized typed failure. There is no repair or retry path in the adapter.
- `backend/src/newsflow/services/editorial_classification.py:171`: the sole contract change exposes a fresh schema directly from the authoritative `_Evidence` definition; evidence and assessment semantics are not duplicated or altered.
- `.github/workflows/ci.yml:27`: the existing lint command gains only the accepted CLI. Lines 30–37 execute the synthetic benchmark after Test and upload the specified backend report with the specified artifact name and 14-day retention. No existing check, dependency, permission, timeout, or job is removed or relaxed.
- `backend/tests/test_editorial_classifier_adapters.py:1`: the 414-line test module uses real existing transports with synthetic HTTP boundary responses, a rewrite tripwire, and independent decision/permission assertions. The inspected tests cover request/schema/free constraints, strict bindings/evidence, protected-negative rejection, response identity, refusal/incomplete/malformed/duplicate/nonfinite/deep responses, transport failures, state clearing, both payload bounds, configuration failures, sanitization, and schema freshness.
- ⚠️ Cannot verify from diff: actual GitHub workflow execution and artifact upload on this commit. The workflow code is correct; the controller owns exact CI execution/status.
- ⚠️ Cannot verify from diff: historical RED-before-implementation ordering, commit provenance, and whether frozen hashes were captured before the reported suite. The implementation report records commands, RED/GREEN results, hashes, and limitations; this review does not independently reconstruct history.
- ⚠️ Cannot verify from diff: end-to-end RewriteJob absence and preservation of all existing source/review/fact/technical/sync/session/publication gates. This task adds no runtime integration or changes to those gates, and its tests demonstrate false rewrite permission for returned reports. Controller-level integration evidence remains separate.
- ⚠️ Cannot verify from diff: live provider compatibility, model quality/qualification, durable admission/CAS/dedup, or activation. These are explicitly deferred; synthetic fixtures must not be treated as qualification or approval evidence.

## Strengths

- `backend/src/newsflow/providers/editorial_classifier.py:54`: composition reuses the bounded transports and keeps operation-specific policy in a small, shared adapter rather than duplicating HTTP behavior.
- `backend/src/newsflow/providers/editorial_classifier.py:46`: clearing state before local validation prevents a failed subsequent call from presenting the previous attempt's usage or identity.
- `backend/src/newsflow/providers/editorial_classifier.py:72`: identity validation occurs before public identity assignment, and its stable error code cannot disclose unexpected model text.
- `backend/src/newsflow/providers/editorial_classifier.py:85`: the accepted assessor remains the sole decision boundary. The adapter does not manufacture PASS or qualify a model.
- `backend/tests/test_editorial_classifier_adapters.py:1`: emitted HTTP payload assertions and injected failure cases test observable transport behavior, including one-call/no-repair guarantees, rather than replacing the provider implementation with mocks.

## Issues

### Critical (Must Fix)

- None found in the reviewed scope.

### Important (Should Fix)

- None found in the reviewed scope.

### Minor (Nice to Have)

- None identified that warrants a task change.

## Focused dependency and evidence checks

- Named risk: the adapter's `finally` usage copy could retain stale state or expose unvalidated response identity. Checked the unchanged constructor/generate/parse paths in `backend/src/newsflow/providers/openai_rewrite.py:83`, `:129`, `:185`, `:204` and `backend/src/newsflow/providers/openrouter_structured.py:26`, `:75`, `:141`. Both transports reset attempt state before work, validate usage into the immutable `RewriteUsage` type, and bind its model to the configured model. Adapter identity remains separately validated. No defect found.
- Named risk: inherited transport fallback or failure handling could create another classifier request, weaken free-only constraints, or leak response/source/credential text. The same focused transport inspection found that the single-model tuple limits OpenRouter to one attempt; `require_parameters=True`, `allow_fallbacks=False`, and all three zero-price constraints remain in its payload. Existing configuration/network/auth/schema failures use typed sanitized errors. The added adapter catches deep parser recursion without adding a second call.
- Named risk: the accepted request could permit source/prompt mutation that undermines the adapter's exact payload binding. Checked only the focused existing request-boundary tests in `backend/tests/test_editorial_classification.py:108`, `:124`, `:141`, and the existing permission tests at `:169`. They cover immutable requests/entities, fresh messages with source kept in untrusted data, bounded accepted source/policy inputs, non-forgeable constructor hashes, and effective false permission. Full request implementation was not reread.
- Read the submitted diff once. Its first tool rendering was truncated inside the OpenRouter constructor; reread only that missing constructor tail from the diff package. No changed implementation file was separately reread, no git command was run, and no checkout/index/branch mutation occurred.
- Inspected retained `full.log` tail: `2182 passed, 6 skipped in 304.77s`, with exactly the six documented PostgreSQL-only skips and no warning block. Inspected `focused.log` tail: `259 passed in 1.81s`; `lint.log`: `All checks passed!`; `compile.log`: no diagnostic text. These are retained execution evidence, not independently rerun verification.
- No test or suite was rerun: no specific untested doubt remained after the diff and focused dependency checks. Native Ruff/compile/YAML/24-case benchmark results are reported by the implementer; exact remote CI remains controller-owned.

## Assessment

**Task quality:** Approved.

**Reasoning:** The implementation is compact, shares transport behavior without expanding runtime scope, and preserves the strict accepted assessment boundary. The synthetic tests exercise the important request, identity, failure, and permission behavior; the inspected evidence supports the reported regression results within the documented PostgreSQL/live-provider limitations.
