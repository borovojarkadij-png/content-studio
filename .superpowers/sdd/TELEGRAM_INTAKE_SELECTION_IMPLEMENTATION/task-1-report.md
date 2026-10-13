# Task 1 implementation report — 2026-10-13

Status: DONE. Implemented the isolated, unused deterministic intake comparison kernel against BASE 639bef0db2b79da2c576581f12de8b980e44a0f3.

## Owned files and scope

- NEW backend/src/newsflow/domain/intake_selection.py: four frozen/slotted contracts, exact bounded validation and revalidation, TOP_SCORE/RANDOM/HYBRID selection, explicit fractional carry, ordered decisions, canonical normalized audit digest.
- NEW backend/tests/test_intake_selection.py: 127 parametrized cases with literal expected picks; no production ranking/digest helper generates expectations.
- NEW .superpowers/sdd/TELEGRAM_INTAKE_SELECTION_IMPLEMENTATION/task-1-report.md: this report.

Read task-1-brief.md, full design, plan Global Constraints, progress ledger, implementer-prompt.md, TDD SKILL.md and writing-good-tests.md, and verification-before-completion SKILL.md before implementation. Discovered test/tool paths before use. No repository AGENTS.md was discovered by rg.

No existing source/test/export/caller/worker/API/UI/config/provider/DB file changed by this writer. Existing unrelated root-owned document changes remain untouched. No helpers, subagents or reviewers spawned. No push. Branch codex/dark-navy-ui and origin https://github.com/borovojarkadij-png/content-studio.git verified before commit.

Selection produces comparison evidence only. No editorial, rewrite or publication authority is present. This does not implement durable ranked ingestion, membership/source/policy fencing, transactional carry persistence, target mix, operational activation, model qualification or PHASE completion. Root owns independent review, packaged network-none smoke and CI.

## TDD sequence and results

All native exits below were captured immediately from $LASTEXITCODE and returned by the command tool; failed logs were retained, never overwritten by successful retries.

| Evidence file | Native exit | Actual result |
| --- | --- | --- |
| 01-import-red.log | 1 | 1 failed: find_spec returned None. Importability RED only; no collection error. |
| 02-behavior-red.log | 1 | 1 failed: real selector stub returned (), expected literal (10,9,8,7,3). Behavioral RED before ranking implementation. |
| 03-digest-reference.log | 1 | Independent reference command had PowerShell quoting error: SyntaxError, unterminated string literal. Not a product/test failure. Retained. |
| 04-digest-reference.log | 0 | Corrected stdin reference hashed literal canonical JSON to a96e4cd576b14e49d805b09ea4174093493a03dfd3ffa568512da412ee8e3a4d, without importing production code. |
| 05-contract-red.log | 1 | 124 failed, 3 passed against the minimal stub, before validation/ranking/digest implementation. |
| 06-kernel-green.log | 0 | 127 passed in 0.11s. |
| 07-ruff-version.log | 0 | ruff 0.17.0. |
| 08-ruff-format.log | 0 | 2 files reformatted. |
| 09-final-tests.log | 0 | 300 passed in 0.91s: 127 new + 173 existing targeted guards. No warnings/skips/noise. |
| 10-ruff-check.log | 1 | I001 import order; PYI041 internal validator float/int annotation. Both corrected; public contracts retained exactly. |
| 11-ruff-format-check.log | 0 | 2 files already formatted. |
| 12-compile-static.log | 0 | Python 3.12 compilation of both files; AST imports exactly dataclasses/hashlib/json/math. |
| 13-final-kernel-tests.log | 0 | Final frozen source: 127 passed in 0.12s, pristine. |
| 14-final-ruff-check.log | 0 | All checks passed! |
| 15-final-ruff-format-check.log | 0 | 2 files already formatted. |
| 16-final-compile-static.log | 0 | Final frozen source: both files compiled; AST import allow-list passes. |
| 17-source-diff-check.log | 0 | Staged source/test diff whitespace check clean (empty output). |

Evidence/TEMP/TMP/basetemp/compiled bytecode all under freshly created D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/. pytest cache disabled and PYTHONDONTWRITEBYTECODE=1. Logs are external evidence, not source ownership or committed artifacts.

After importability RED, created only minimal dataclass declarations and a zero-selection stub. Removed the temporary find_spec assertion once behavior tests imported the real module. Added literal behavioral expectations, ran behavioral RED, then added the full contract tests and ran their RED before implementing validation/ranking/digest. No expected pick is derived with production code.

Existing targeted suites ran once, not the whole backend. Only import ordering and the private helper annotation changed after that 300-test run; the 127 new tests and all static checks were rerun afterward. No test weakened or skip introduced. No actual provider, Telegram, credential, rewrite or publication calls.

## Exact verification commands

Workspace cwd for non-pytest commands:
C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2

Pytest cwd:
C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend

These environment assignments preceded every Python run:

    $env:TEMP='D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a'
    $env:TMP=$env:TEMP
    $env:PYTHONDONTWRITEBYTECODE='1'

TEMP/TMP also preceded every Ruff run. The fresh evidence directory was created before the first RED:

    New-Item -ItemType Directory -Path D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a -ErrorAction Stop | Out-Null

Every native command below used *> with the absolute evidence path matching its log table entry. Immediately afterward the command block captured $nativeExit=$LASTEXITCODE, read the log using Get-Content, printed "NATIVE_EXIT=$nativeExit", then exit $nativeExit. For 05 only the last 25 log lines were displayed; its full 95,473-byte output was preserved.

01, exact Python command and output target:

    python -c "import sys; assert sys.version_info[:2] == (3, 12); sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_intake_selection.py', '-q', '-p', 'no:cacheprovider', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/pytest-import-red']))" *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/01-import-red.log

02:

    python -c "import sys; assert sys.version_info[:2] == (3, 12); sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_intake_selection.py', '-q', '-p', 'no:cacheprovider', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/pytest-behavior-red']))" *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/02-behavior-red.log

03, the failed quoting attempt, retained verbatim:

    python -c "import hashlib; raw = '{\"algorithm_version\":\"intake-selection-v1\",\"candidates\":[{\"candidate_id\":1,\"eligible\":true,\"revision_sha256\":\"' + 'b'*64 + '\",\"score\":50.0}],\"carry\":0,\"policy\":{\"intake_percent\":100,\"minimum_score\":0.0,\"mode\":\"HYBRID\"},\"window_key\":\"' + 'a'*64 + '\"}'; print(raw); print(hashlib.sha256(raw.encode('utf-8')).hexdigest())" *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/03-digest-reference.log

04, corrected independent literal-payload reference:

    @'
    import hashlib
    raw = '{"algorithm_version":"intake-selection-v1","candidates":[{"candidate_id":1,"eligible":true,"revision_sha256":"' + 'b'*64 + '","score":50.0}],"carry":0,"policy":{"intake_percent":100,"minimum_score":0.0,"mode":"HYBRID"},"window_key":"' + 'a'*64 + '"}'
    print(raw)
    print(hashlib.sha256(raw.encode('utf-8')).hexdigest())
    '@ | python - *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/04-digest-reference.log

05:

    python -c "import sys; assert sys.version_info[:2] == (3, 12); sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_intake_selection.py', '-q', '-p', 'no:cacheprovider', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/pytest-contract-red']))" *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/05-contract-red.log

06:

    python -c "import sys; assert sys.version_info[:2] == (3, 12); sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_intake_selection.py', '-q', '-p', 'no:cacheprovider', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/pytest-green']))" *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/06-kernel-green.log

07:

    & D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe --version *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/07-ruff-version.log

08:

    & D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py --no-cache *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/08-ruff-format.log

09 (new module + targeted existing suites exactly once):

    python -c "import sys; assert sys.version_info[:2] == (3, 12); sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_intake_selection.py', 'tests/test_hype.py', 'tests/test_engagement_rates.py', 'tests/test_engagement_sampling.py', 'tests/test_mapping_technical_filters.py', 'tests/test_editorial_gate.py', 'tests/test_durable_ingestion_workflow.py', 'tests/test_durable_rewrite_runner.py::test_free_factory_never_calls_network_for_stale_reject', 'tests/test_durable_rewrite_runner.py::test_stale_editorial_reject_blocks_claimed_job_without_constructing_provider', '-q', '-p', 'no:cacheprovider', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/pytest-final']))" *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/09-final-tests.log

10:

    & D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py --no-cache *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/10-ruff-check.log

11:

    & D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py --no-cache *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/11-ruff-format-check.log

12:

    @'
    import ast
    from pathlib import Path
    import py_compile
    import sys
    assert sys.version_info[:2] == (3, 12)
    paths = ['backend/src/newsflow/domain/intake_selection.py', 'backend/tests/test_intake_selection.py']
    for index, path in enumerate(paths):
        py_compile.compile(path, cfile=f'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/compiled-{index}.pyc', doraise=True)
    tree = ast.parse(Path(paths[0]).read_text(encoding='utf-8'))
    imports = sorted(node.module if isinstance(node, ast.ImportFrom) else alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in (node.names if isinstance(node, ast.Import) else [None]))
    assert imports == ['dataclasses', 'hashlib', 'json', 'math'], imports
    print('Python 3.12 compile: 2 files OK')
    print('Kernel AST import allow-list: dataclasses, hashlib, json, math; no stateful dependency')
    '@ | python - *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/12-compile-static.log

13:

    python -c "import sys; assert sys.version_info[:2] == (3, 12); sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; assert telethon.__version__ == '1.45.0'; import pytest; raise SystemExit(pytest.main(['tests/test_intake_selection.py', '-q', '-p', 'no:cacheprovider', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/pytest-frozen']))" *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/13-final-kernel-tests.log

14:

    & D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py --no-cache *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/14-final-ruff-check.log

15:

    & D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py --no-cache *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/15-final-ruff-format-check.log

16 repeated the exact 12 script with cfile:

    cfile=f'D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/final-compiled-{index}.pyc'

and output redirect:

    '@ | python - *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/16-final-compile-static.log

17:

    git diff --cached --check -- backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py *> D:/Codex-Recovery/content-studio-20261008/intake-selection-task1-20261013a/17-source-diff-check.log

## Self-review and source freeze

Read the complete staged diff and the complete design again. Checked:

- Exact dataclass fields, frozen/slots inputs/results, no permission/job field.
- Type and field validation before digest/filter/ranking, including invalid excluded rows, empty windows, duplicate IDs and forged frozen-field mutation.
- Strict signed64 identity, bounded exact int/float scores and thresholds; bool/subclasses/nonfinite/huge int rejected without conversion overflow.
- Exact tuple and <=1000 bound before traversal; unknown scores excluded from pool in every mode.
- Threshold equality eligible; zero evidence differs from None.
- Quota/carry arithmetic cannot select beyond N with bounded carry; empty/blocked windows preserve carry.
- Descending score/ID tie order; deterministic ASCII SHA bytes/ID order; HYBRID ceil(4q/5), top stage first, remaining random picks without duplicates; sorted audit reasons.
- Digest uses exact payload keys/options, float normalization, all excluded rows, membership, window, policy, carry and version; permutations/replay stable.
- Literal expected tuples, independent canonical-payload literal hash, input preservation, output immutability.
- Only stdlib dataclasses/hashlib/json/math imports, no external/stateful operations or dependency.

Static source imports are exactly dataclasses, hashlib, json, math. Code is bounded by 1000 candidates and deterministic; no API/worker integration exists.

Frozen SHA256 working-file bytes (Get-FileHash -Algorithm SHA256, checked twice):

| File | SHA256 |
| --- | --- |
| backend/src/newsflow/domain/intake_selection.py | b94db8757c0b354503fa563c24b37ec43477da7ebd8bdb26cc20ca4c27dddb39 |
| backend/tests/test_intake_selection.py | 4ce4114da600663fce9d23af708292ee8ffa8ae64db2b989957bfeba2528ddb7 |

Source diff is 191 production lines + 512 test lines. Staged source/test with:

    git add -- backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py

Native exit 0. Git emitted the existing Windows LF-to-CRLF advisory for the two newly added files; source content remained unchanged, frozen hashes verified after staging. Native diff check exit 0; git diff --cached --name-only was empty before own staging. Root-owned document modifications are not staged by this writer.

Source writes stop at this report. The final ownership/freeze check, report staging, three-file commit and post-commit inspection follow without any further source edits. Commit identity and native result are returned in the required concise handoff.

Administrative commit correction: ordinary report staging

    git add -- .superpowers/sdd/TELEGRAM_INTAKE_SELECTION_IMPLEMENTATION/task-1-report.md

returned native 1 because .superpowers is ignored; the tool output preserved that diagnostic. The subsequent explicit-path commit attempt

    git commit -m "feat: add pure deterministic intake selection kernel" -- backend/src/newsflow/domain/intake_selection.py backend/tests/test_intake_selection.py .superpowers/sdd/TELEGRAM_INTAKE_SELECTION_IMPLEMENTATION/task-1-report.md

returned native 1 because the ignored report had not entered the index (19-owned-commit.log retained). No commit was created and source hashes stayed identical. Corrected staging uses -f for only the explicitly authorized own report:

    git add -f -- .superpowers/sdd/TELEGRAM_INTAKE_SELECTION_IMPLEMENTATION/task-1-report.md

Then the three-path index ownership, frozen hashes and staged whitespace are checked before retrying the same explicit-path commit. This report-only evidence correction makes no Python source/test changes. Final commit result is retained as 21-owned-commit.log and returned to root.

## Limitations and concerns

No correctness concern found in self-review. Pure kernel scope intentionally leaves durable ingestion and target-mix integration unfinished. Existing guards preserve REJECT -> rewrite_allowed=false -> no new RewriteJob, with stale REJECT execution blocked before provider construction/network. Tests use synthetic local evidence/SQLite only; no live service or model qualification is claimed. Full backend suite was intentionally not rerun for this disconnected module. Packaged network-none smoke, independent reviewers and exact CI remain root-owned verification.
