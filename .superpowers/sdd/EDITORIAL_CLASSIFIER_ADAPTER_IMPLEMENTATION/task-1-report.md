# Task 1 report: bounded editorial classifier adapters

## Scope and repository

- Base: `9bb6147ccb640a24311aad2a3f65303c463b3d97`; branch: `codex/dark-navy-ui`.
- Origin verified: `https://github.com/borovojarkadij-png/content-studio.git`.
- Initial worktree was clean. Root subsequently owns the dirty planning/state docs;
  none is included in this worker's staging or commit.
- Read the task brief, global constraints, TDD and its writing-good-tests reference,
  NewsFlow AI Evals, and verification-before-completion guidance. Re-read the
  updated brief authorizing the precise backend CI benchmark/report change.
- One writer; no helpers, reviewers, live AI/Telegram/key reads, settings,
  dependencies, Compose, ingestion/runtime services, push, or PR operations.

## Implementation

- Added `OpenAIEditorialClassifier` and `FreeOpenRouterEditorialClassifier`, using
  the existing providers' `generate_json` with injected HTTP test boundaries.
  Neither adapter exposes or calls rewrite, qualification, scheduling, or publishing.
- Added the fresh `editorial_evidence_schema()` accessor directly from `_Evidence`.
  The accepted evidence contract and prompt are otherwise unchanged.
- Exact request type and serialized 131072-codepoint / 262144-UTF8-byte limits
  precede IO. Source/policy payloads and accepted instructions are unchanged.
- OpenAI keeps existing configuration checks. OpenRouter accepts one explicit,
  syntactically bounded `:free` ID; dynamic routing, paid models, model lists, and
  duplicates are rejected before IO. Existing free transport constraints remain.
- Response identity is exact for OpenAI and exact or suffix-stripped for OpenRouter.
  Invalid identity never enters public response-model state. Per-attempt usage and
  identity are read-only and reset even for a locally invalid subsequent request.
- Canonical JSON uses sorted keys, compact separators, UTF8 bounds, and
  `allow_nan=False`, then the accepted strict assessment. Schema/binding/quote/
  completeness/uncertainty failures cannot grant rewrite permission. Deep parser
  recursion is translated to a sanitized typed failure at the adapter boundary.
- Backend CI now lints the accepted benchmark CLI, executes it after tests, and
  uploads `backend/editorial-contract-report.json` using the exact authorized
  artifact name and 14-day retention. Existing jobs/settings/checks are preserved.

## Test evidence and commands

All owned artifacts are retained under:
`D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/`.
Python is 3.12.10; native Ruff is 0.17.0; full/focused pytest use explicit
`sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145')`
and confirmed Telethon 1.45.0. No package installation or environment-file read.
For every Python command, `PYTHONPYCACHEPREFIX` points to the owned `pycache`.
Pytest cache is the owned `pytest-cache`; each temp directory is a unique owned
child. Existing artifacts were not removed or overwritten.

From `backend`, the initial RED command was:

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_editorial_classifier_adapters.py', '-q', '-o', 'cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/pytest-cache', '--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/red-tmp']))"
```

- `red.log`: **96 failed, 0 passed, 0 skipped; exit 1**, expected assertion failures
  for missing adapters/public schema. No import/collection error, skip, or xfail.
  Temporary existence assertions were removed after implementation.
- Same command with `green-tmp`: `green.log`, **96 passed, 0 failed, 0 skipped;
  exit 0**.
- Self-review identified deep JSON could escape the inherited parser as an untyped
  `RecursionError`. Added a test before the fix and ran:
  `python -m pytest tests/test_editorial_classifier_adapters.py -q -k deep_response
  -o cache_dir=.../pytest-cache`. `deep-red.log`: **2 failed, 96 deselected, exit 1**;
  the first 1100-level fixture was below pytest's recursion threshold, so the
  contract correctly returned manual review instead of the intended parser error.
  Corrected the fixture to 10000 levels; `deep-red-02.log`: **2 failed,
  96 deselected, exit 1**, reproducing the actual untyped recursion failure.
  The bounded adapter fix follows that expected failure.
- Focused regression command uses the same Python wrapper and `focused-tmp`:

```text
pytest.main(['tests/test_editorial_classifier_adapters.py',
 'tests/test_editorial_classification.py', 'tests/test_editorial_gate.py',
 'tests/test_openai_rewrite_provider.py', 'tests/test_openrouter_structured.py',
 'tests/test_openrouter_rewrite_provider.py', 'tests/test_semantic_provider.py',
 'tests/test_semantic_facts.py', '-q', '-o', 'cache_dir=.../pytest-cache',
 '--basetemp=.../focused-tmp'])
```

`focused.log`: **259 passed, 0 failed, 0 skipped; exit 0** (98 adapter cases).
The tests use real transports and only injected HTTP responses, plus a rewrite
tripwire. Coverage includes exact emitted request/schema/free constraints,
neutral diagnostic PASS/effective MANUAL_REVIEW, protected-negative REJECT,
stale bindings, fabricated/missing quotes, strict/uncertain evidence, response
identity failures, refusals/incomplete/malformed/duplicate/non-object/nonfinite
responses, oversized bodies, timeout/network/auth/unavailable failures, state
reset after invalid input, both payload limits, constructor/model/key failures,
credential/source-safe exceptions/repr, fresh schema mutation, and deep JSON.

Verification commands from `backend`:

```powershell
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format src/newsflow/providers/editorial_classifier.py src/newsflow/services/editorial_classification.py tests/test_editorial_classifier_adapters.py --cache-dir D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/ruff-cache
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check src tests alembic ../scripts/evaluate_editorial_contract.py --cache-dir D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/ruff-cache
python -m compileall -q src tests ../scripts/evaluate_editorial_contract.py
python ../scripts/evaluate_editorial_contract.py > D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/editorial-contract-report.json
git diff --check
```

- Format: 2 files formatted initially; final run 3 unchanged, **exit 0**.
- `lint.log`: native Ruff **all checks passed, exit 0**.
- `compile.log`: no compile errors, **exit 0**.
- `editorial-contract-report.json`: **24/24 matched, 0 mismatched, exit 0**;
  `SYNTHETIC_CONTRACT`, model qualification false, provider/rewrite calls zero.
  This compares the existing contract fixture, not model accuracy.
- PyYAML 6.0.3 parsed the workflow and assertions checked benchmark command,
  step order after Test, upload path/name/retention, and CLI lint inclusion:
  **PASS, exit 0**. The root independently runs the GitHub workflow.
- `git diff --check`: **exit 0**; Git emits existing LF-to-CRLF advisory messages.

## Frozen full suite

Code, tests, workflow, accepted benchmark CLI, and fixture were frozen before the
single full backend run. SHA256 (`frozen-sha256.log`):

| Path | SHA256 |
| --- | --- |
| backend/src/newsflow/providers/editorial_classifier.py | 8E0DFB263FCF626E5EC750B138425563FB3B76552C067E0B404ED1F4DC91EDFD |
| backend/src/newsflow/services/editorial_classification.py | 7EBFD937A909F5175A5C60856D438F1B7AE35A72C9316EEB7696214CB8537A44 |
| backend/tests/test_editorial_classifier_adapters.py | D8E89EBA326CC870646B4999166B43F740C653A05E1B3D0F6BA3FC9A28948992 |
| .github/workflows/ci.yml | 5D0D8DA7785EE0AB0715C41D53D1FB5134642F22E70EF31DBEA90788718662DE |
| scripts/evaluate_editorial_contract.py | 1EB905AB821E7E093F5C0B4676DE123DC749C47E353946DE9B1F1664A8CD43F7 |
| backend/tests/fixtures/editorial-classification-v1.json | A1762093C7993CEA1F1CB2CCBF0D6ECC359D61B20D74554B30D277601F1C616C |

Full command (from `backend`):

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['-q', '-rs', '-o', 'cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/pytest-cache', '--basetemp=D:/Codex-Recovery/content-studio-20261008/editorial-adapter-20261012-1730/full-tmp']))"
```

`full.log`: **2182 passed, 0 failed, 6 skipped, exit 0**, 304.77 seconds.
The 98-test increase over the accepted 2084-test baseline is the new adapter suite.
All six skips remain explicit PostgreSQL-only checks:

- 1 at `tests/test_illustration_review_storage.py:271`: real TRUNCATE requires
  the strict isolated PostgreSQL CI namespace.
- 2 at `tests/test_planner_media_postgres.py:76`: explicit isolated PostgreSQL
  concurrency opt-in not supplied.
- 3 at `tests/test_planner_media_postgres.py:248`: same explicit concurrency opt-in.

No task code/test/workflow/benchmark file changed between freeze and completion.
Final SHA256 comparison, native format check, and staged diff checks passed.
The explicit-file commit contains only the three task Python files, the narrowly
authorized workflow change, and this force-tracked report. Root-owned planning/
state documents remain excluded. No push was performed.

## Self-review and limitations

- Reviewed exact scope and emitted payloads, bounded preflight, state clearing,
  private credential storage, identity pinning, typed sanitized errors, strict
  schema/evidence handling, and no rewrite/repair/retry/activation path.
- No changes to accepted request, evidence, assessment semantics, prompts,
  transport implementations, dependency versions, or runtime integration.
- No real model was evaluated or qualified. All returned reports still deny
  rewrite. Durable admission/current-source CAS/dedup/filter checks, model
  qualification, credential/settings factory, and worker activation remain deferred.
- No unchanged frontend, PostgreSQL, Docker, or Compose verification was repeated.
  The local accepted-contract baseline is 2084 passed / 6 PostgreSQL skips;
  this report does not claim those skipped checks were rerun here. Root tracks
  ongoing exact GitHub CI separately; this worker makes no current CI success claim.
- A preliminary attempt to read the updated brief from the backend directory had
  a harmless missing-path diagnostic; re-read succeeded from repository root.
  One orchestration call had JavaScript syntax failure before execution; it made
  no filesystem/test change, and the freeze/full commands were then run normally.
