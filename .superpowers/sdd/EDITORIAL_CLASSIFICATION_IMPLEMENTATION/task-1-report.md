# Task 1: offline editorial classification contract

Base: `03f0e8e0d7f1fdeee622248c2ac6372adcd502a0`; repository `https://github.com/borovojarkadij-png/content-studio.git`, branch `codex/dark-navy-ui`.

Implemented the pure source/policy-bound request, strict evidence assessment, synthetic benchmark and offline CLI. No runtime integration, provider calls, rewrite calls, dependency changes, DB changes, worker changes, Compose changes or publication actions were introduced. All decisions returned by assessment deny rewriting. A diagnostic PASS becomes effective MANUAL_REVIEW with REAL_MODEL_NOT_QUALIFIED; valid protected-negative/hostile evidence remains REJECT. The report's qualification property is read-only false, and the assessment accepts no qualification argument.

## Changed files

- `backend/src/newsflow/services/editorial_classification.py`
- `backend/tests/test_editorial_classification.py`
- `backend/tests/fixtures/editorial-classification-v1.json`
- `scripts/evaluate_editorial_contract.py`
- This report, explicitly force-tracked.

Root-owned state/plan/CI files were excluded from the worker commit.

## Contract and narrow choices

- Source hashes use exact UTF-8. Policy hashes use compact deterministic JSON containing the exact policy version, entity IDs sorted lexically, and each entity's aliases sorted lexically. Whitespace/normalization edits to the source and policy edits invalidate old evidence. Alias/entity ordering does not change policy hashes.
- Request/entity objects are frozen dataclasses with strict manual input validation. Derived hashes/prompt version cannot be supplied to their public constructor. Messages/payload return fresh serialized data; editing a returned message cannot mutate the request.
- Evidence uses strict Pydantic extra-forbid schemas. Parsing rejects duplicate keys at every depth, nonfinite JSON constants, invalid UTF-8/lone surrogates including escaped object keys, malformed JSON, excess bytes and nesting deeper than 32. Root/finding types and limits are checked before semantic validation.
- Findings must identify unique known entities and provide exact contiguous source quotes with an NFKC+casefold alias. Source matching uses conservative normalized substring matching; it intentionally does not infer semantic entity identity or remove ambiguous substring matches. Missing findings fail closed.
- Unknown/mixed sentiment or framing stays MANUAL_REVIEW even when another field is negative/hostile. Invalid evidence diagnostics are MANUAL_REVIEW and contain only stable reason codes; raw evidence/source/error text is not retained in reports.
- The trusted fixture evaluator fills binding echoes and applies explicit named stale-source/policy/key/prompt mutations. Evidence and expected labels are stored independently in the checked-in JSON. Duplicate case IDs, unknown case fields/mutations, empty datasets and invalid request policies are refused as DATASET_INVALID.
- The CLI defaults to only the checked-in fixture, accepts an explicit local `--dataset` for reproducible negative checks, bounds input reads to 262145 bytes, and exits 0/1/2 for complete matches/mismatches/invalid datasets respectively. It has no provider adapter.

## TDD evidence

Read the complete TDD skill and its writing-good-tests reference, and the requested NewsFlow AI Evals skill. The latter guided independent versioned synthetic labels, deterministic schema/support checks, and explicit separation from real-model quality/qualification.

All Python runs used Python 3.12.10, Pydantic 2.13.5, and owned D: bytecode/cache/temp paths. No skip/xfail was added to the new tests. Initial availability assertions were replaced by behavior tests once the module existed.

Commands were run from `backend` unless otherwise stated. Common environment/cache settings:

```powershell
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/editorial-task1-pycache'
# Each pytest command also supplied:
-o cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-task1-pytest-cache
```

1. `python -m pytest tests/test_editorial_classification.py -q --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-red01`: **1 failed**, expected assertion `source-bound classifier boundary is missing` (module absent). This first command also set PYTHONPATH to the existing D: Telethon override; the full run later verified the import explicitly instead of relying on that environment setting.
2. `python -m pytest tests/test_editorial_classification.py -q --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-red02`: **25 failed** at the missing boundary assertion. These tests described request byte binding, policy ordering/collisions, strict invalid inputs, limits and immutable prompt data before implementation.
3. Implemented the request boundary. `python -m pytest tests/test_editorial_classification.py -q --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-green01`: **25 passed**.
4. Added evidence/gate/parser tests first. `python -m pytest tests/test_editorial_classification.py -q --tb=short --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-red03`: **57 failed, 24 passed, 4 errors**. Failures were the deliberately missing assessment callable. The four errors arose from enormous automatic parametrization IDs for oversize raw input cases; shortened those test IDs before proceeding. This run is not counted as clean RED evidence.
5. `python -m pytest tests/test_editorial_classification.py -q --tb=line --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-red04`: clean **59 failed, 24 passed**, every new assessment check failed at the missing callable assertion, with no setup errors. Request checks remained green; the temporary availability test had been removed. RED phases establish missing interfaces; they do not claim independent mutation testing of every implemented guard.
6. Implemented assessment/parser. `python -m pytest tests/test_editorial_classification.py -q --tb=short --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-green02`: **83 passed**.
7. Added benchmark and subprocess CLI tests first. `python -m pytest tests/test_editorial_classification.py -q --tb=line --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-red05`: **8 failed, 83 passed**, expected assertions for missing fixture/evaluator callable/CLI.
8. Added the independent 24-case JSON fixture, evaluator and CLI. `python -m pytest tests/test_editorial_classification.py -q --tb=short --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-green03`: **91 passed**.
9. Added four further checks of the already implemented boundary: accepted maximum valid limits, direct-constructor forged-hash refusal, direct existing rewrite-gate denial for every fixture report, and invalid dataset IDs/fields/mutations. No production behavior changed for these checks. Final new test count: **95**.

## Frozen verification

After native formatting and self-review, the four implementation/test/fixture/script files were frozen before the combined regression and single full backend suite.

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' --version
# ruff 0.17.0
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format src/newsflow/services/editorial_classification.py tests/test_editorial_classification.py ../scripts/evaluate_editorial_contract.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check src tests alembic ../scripts/evaluate_editorial_contract.py
```

Native Ruff full scope: **PASS, All checks passed**. An earlier invocation from repository root with explicit `--config backend/pyproject.toml` produced 192 diagnostics because first-party resolution differed from the normal backend working directory; those existing files were not edited. A script-only unused noqa was removed. The correct backend-working-directory full check passes without changing lint rules or configuration.

```powershell
python -m pytest tests/test_editorial_classification.py tests/test_editorial_gate.py tests/test_durable_editorial.py tests/test_ingestion_service.py tests/test_ingestion_pipeline.py tests/test_durable_ingestion.py tests/test_durable_ingestion_workflow.py tests/test_rewrite_service.py tests/test_durable_rewrite_runner.py tests/test_rewrite_worker_policy.py tests/test_rewrite_candidate_activation.py -q --basetemp D:/Codex-Recovery/content-studio-20261008/editorial-task1-regression01 -o cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-task1-pytest-cache
```

Combined focused/editorial/ingestion/rewrite regression: **158 passed in 5.37s**.

The installed Telethon imports as 1.44.0 from system site-packages by default. Explicit `sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145')` verified **Telethon 1.45.0** imported from that D: directory before the single frozen full-suite run. No PostgreSQL/NEWSFLOW/DATABASE_URL opt-in environment variable was present in the worker shell.

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('Telethon', telethon.__version__, telethon.__file__); import pytest; sys.exit(pytest.main(['-q', '-rs', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/editorial-task1-full01', '-o', 'cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-task1-pytest-cache']))" 2>&1 | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-task1-full01.log
```

Single frozen full-suite result: **exit 0; 2084 passed, 6 skipped in 310.90s (0:05:10)**. Log retained at `D:/Codex-Recovery/content-studio-20261008/editorial-task1-full01.log`. Explicit skips (not passes):

- 1 at `tests/test_illustration_review_storage.py:271`: Real TRUNCATE requires the strict isolated PostgreSQL CI namespace.
- 2 at `tests/test_planner_media_postgres.py:76`: Explicit isolated PostgreSQL concurrency opt-in not supplied.
- 3 at `tests/test_planner_media_postgres.py:248`: Explicit isolated PostgreSQL concurrency opt-in not supplied.

No implementation/test/fixture/script file changed during or after this frozen run. Only this report was finalized afterwards.

From repository root:

```powershell
python -m compileall -q backend/src backend/tests backend/alembic scripts/evaluate_editorial_contract.py
python scripts/evaluate_editorial_contract.py | Tee-Object -FilePath D:/Codex-Recovery/content-studio-20261008/editorial-task1-benchmark.json
git diff --check
```

Compile: **PASS**. CLI: **exit 0, 24 matched, 0 mismatched**; `evaluation_kind=SYNTHETIC_CONTRACT`, `real_model_qualified=false`, `provider_calls=0`, `rewrite_calls=0`. Generated per-case JSON is retained at the D: path above. Each actual effective decision has rewrite_allowed=false, and the existing `editorial_allows_rewrite` denies every case, also exercised directly in tests. `git diff --check`: **PASS** (Git reported only root-owned docs LF/CRLF notices). Each of the four new task files was also checked with `git diff --check --no-index -- NUL <file>` before staging; all passed with LF/CRLF notices only. The explicit staged task files/report are checked again with `git diff --cached --check` immediately before commit.

Frozen SHA256 values:

- Service: `37EB0902604AFC573BD3028E0F0262F03EC7A5CE89104455CB7C9756D0FF6EFD`
- Tests: `F07C5AE387C2BD76B0F803DD934509F79F126CE27ABC955289D0A64D3F1AD317`
- Fixture: `A1762093C7993CEA1F1CB2CCBF0D6ECC359D61B20D74554B30D277601F1C616C`
- CLI: `1EB905AB821E7E093F5C0B4676DE123DC749C47E353946DE9B1F1664A8CD43F7`

## Self-review and limitations

Reviewed each brief rule against the implementation and real behavioral tests: strict types/required keys, duplicate/nested keys, malformed/deep/oversize/nonfinite/invalid Unicode evidence, exact source and policy binding, immutable authoritative request values, normalized alias collisions/matching, fabricated/omitted/duplicate findings, unknown/mixed/incomplete/ambiguous evidence, protected rejection, and the unconditional real-model qualification barrier. No data/provider/worker adapters or generic qualification framework were added. Caller inputs and raw validation errors do not appear in reason codes or reports.

The 24 synthetic comparisons establish deterministic contract behavior only. They are not model accuracy measurements, do not verify that a real model recognizes sarcasm/negation/accusations, and do not qualify a provider. Evidence echoes are integrity bindings, not authentication. Conservative alias matching can require review for incidental substring matches. Schema nesting is capped at 32 and evaluator datasets at 1000 cases; the CLI also applies the evidence byte limit to the local benchmark envelope. All are narrow, fail-closed choices.

Deferred: live classifier adapter; durable classification jobs/source CAS/recovery; qualification storage and real benchmark; operator policy setup; automatic approval activation. PostgreSQL opt-in scenarios are not run here, and no retained schemas, volumes, originals or artifacts were deleted. Root retains Docker/runtime validation, state/plan maintenance, independent review and CI tracking ownership.
