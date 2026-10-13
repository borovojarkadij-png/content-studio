# Task 1 implementation report — 2026-10-13

Status: DONE. Base: `87e5189a39b09847c1655cecdb64317b8942008d`.
Branch verified: `codex/dark-navy-ui`. Origin verified:
`https://github.com/borovojarkadij-png/content-studio.git`.
No push was performed. The implementation commit contains exactly the four new
assigned source/test files and this report; the controller owns the other dirty
documentation and progress files.

## Implemented contract

- `backend/src/newsflow/domain/hype.py`: frozen eleven-field components and
  weights with the exact approved defaults; finite exact numeric validation;
  explicit coverage; weighted mean over known enabled components; honest
  INSUFFICIENT_EVIDENCE/READY; boundary revalidation by reconstruction; explicit
  aware-time freshness decay; saturating donor-relative velocity mapping.
- `backend/src/newsflow/domain/donor_performance.py`: frozen validated adjacent
  observation windows and frozen per-metric performance results; explicit tuple
  bound2000 and integer minimum1..200; every window reconstructed/revalidated
  before exclusion; canonical observation/publication conflict detection across
  target and all samples; exact replay deduplication by independent message;
  account/donor/current/nonprior/future exclusions; inclusive25% comparable age
  and duration using timedelta arithmetic; closest-age/closest-duration/latest-end/
  latest-start selection; independently counted per-metric medians; reset/missing/
  cold-start/zero-baseline honesty; finite ratio guard.
- `backend/tests/test_hype.py` and `backend/tests/test_donor_performance.py`:
  101 focused cases covering hand-derived arithmetic, donor-size fairness,
  interval rather than lifetime rates, median arithmetic, coverage and all default
  shares, no rounding, seven unavailable components remaining None, boundaries,
  duplicate/repeat independence, order-independent selection, per-metric missing/
  reset behavior, zero median and target, conflicts including excluded samples,
  aware timestamps, frozen/forged objects, malformed numerics and input bounds.

The pure modules import only standard library and the accepted engagement domain.
No SDK, SQL, service, UI, settings, collector, candidate ordering, approval, job,
usage, outbox or publication code was changed. Ranking grants no authority:
REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0 remains
the existing requirement; this task neither invokes nor modifies that path.
No Telegram/AI/network request, credentials or operational data were used.

## Runtime and retained raw evidence

Fresh evidence directory:
`D:/Codex-Recovery/content-studio-20261008/telegram-hype-task1-20261013`.
Actual versions (`11-versions.log`): Python3.12.10 Windows64, pytest8.4.2,
Telethon1.45.0 loaded from the explicitly supplied recovery SDK directory,
Ruff0.17.0. Native version-command exits were both0.

All pytest runs used backend cwd and this exact Python launcher, with test-path
arguments as recorded below. The supplied SDK path was set at sys.path0 before
pytest import and appears nowhere in the source/tests.

```powershell
$env:PYTHONPYCACHEPREFIX='D:/Codex-Recovery/content-studio-20261008/telegram-hype-task1-20261013/pycache'
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['-q','tests/test_hype.py','tests/test_donor_performance.py','-o','cache_dir=D:/Codex-Recovery/content-studio-20261008/telegram-hype-task1-20261013/pytest-cache']))"
```

Each launch piped combined output through `Tee-Object -FilePath <log>`;
immediately captured `$LASTEXITCODE` in `$taskExit`, appended
`NATIVE_EXIT=$taskExit` to the same log, and returned that native exit.

| Raw log | Actual result |
| --- | --- |
| `01-red.log` | 69 failed,11 passed in0.54s; native1; no import/collection error |
| `02-green.log` | 80 passed in0.14s; native0 |
| `03-format.log` | Four files reformatted; native0 |
| `04-focused-regression.log` | 178 passed in1.31s; native0 |
| `05-ruff-check.log` | Two C408 findings in test helper dict construction; native1 |
| `06-format-final.log` | One file reformatted,three unchanged; native0 |
| `07-final-focused.log` | 101 passed in0.17s; native0 |
| `08-ruff-final.log` | All checks passed; native0 |
| `09-format-check.log` | Four files already formatted; native0 |
| `10-compile.log` | No compiler diagnostics; native0 |
| `11-versions.log` | Versions and Telethon actual import path; native0 each |
| `12-self-review-source.log` | Full staged source diff reviewed; native0 |
| `13-frozen-hashes.json` | Four SHA256 hashes below |
| `14-staged-diff-check.log` | Exact five-path staged whitespace check; native0 before commit |
| `15-commit.log` | Exact five-path implementation commit receipt |
| `16-source-freeze.log` | Working/index byte SHA256 equality for all four frozen files; native0 |

The `04` pytest arguments inserted these two existing paths before `-o`:
`tests/test_engagement_rates.py`, `tests/test_telegram_engagement.py`.
Thus it ran90 then-current new cases plus88 existing math/provider cases,
once for unchanged engagement regression. Later default-share test additions
were covered by the final101-case focused run. No warnings or failures appeared
in either passing regression/final test output. No full backend run was performed:
the controller runs the combined backend gate after Task2.

Actual Ruff invocations, from workspace root, used the following four literal
paths, not guessed globs:

```powershell
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format backend/src/newsflow/domain/hype.py backend/src/newsflow/domain/donor_performance.py backend/tests/test_hype.py backend/tests/test_donor_performance.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check backend/src/newsflow/domain/hype.py backend/src/newsflow/domain/donor_performance.py backend/tests/test_hype.py backend/tests/test_donor_performance.py
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check backend/src/newsflow/domain/hype.py backend/src/newsflow/domain/donor_performance.py backend/tests/test_hype.py backend/tests/test_donor_performance.py
python -m compileall -q backend/src/newsflow/domain/hype.py backend/src/newsflow/domain/donor_performance.py backend/tests/test_hype.py backend/tests/test_donor_performance.py
```

Compile used the same external PYTHONPYCACHEPREFIX as pytest. Log output/native
exits used the wrapper described above. The final lint correction replaced the
two test-helper `dict(keyword=...)` constructions with equivalent literals via
apply_patch. It did not change the production implementation.

## Causal TDD evidence

Tests were written first along with declaration-only/inert API scaffolding, so
the RED exercised public functions instead of failing collection. RED assertions:

- Weighted100 and0 at weights1 and3 returned `(None,0,INSUFFICIENT_EVIDENCE)`;
  the independent expected result was `(25,1,READY)`.
- Freshness at0/30/60minutes returned None instead of100/50/25.
- A target400 increment over10minutes against five200-increment intervals
  returned unknown rather than expected20/minute,relative2,independent count5.
- Invalid numeric/policy/frozen/window inputs failed their expected-raise checks
  because the scaffold lacked validation.

RED had69 causal failures and11 incidental passes: unknown ratio and exclusions
matched the inert unknown result. GREEN implemented the formulas/validation and
all80 initial cases passed. Self-review then strengthened cases for default
weight evidence shares, independent age/duration boundaries, best-window reset
selection, datetime extremes, forged excluded observations and minimum200.
No production behavior was added after GREEN; the later work was test coverage,
formatting, and test-helper lint corrections.

## Self-review, corrections and freeze

Reviewed both complete source files and the complete staged test diff against
the approved brief/design. Corrected two initial just-outside boundary fixture
pairs whose arithmetic actually remained inside the allowed interval. Final
fixtures isolate an end-age violation at duration10 and a duration violation
at end-age20; inclusive boundary fixtures also isolate both dimensions. There
was no production defect or scope change resulting from self-review.

Read-only discovery found no applicable repository AGENTS.md. The assigned brief,
full linked design, implementer prompt and TDD/verification instructions were read.
No helpers, subagents or reviewers were dispatched. All source/test/report edits
used apply_patch; Ruff formatting was the mechanical formatting step.

Frozen SHA256 of the four final working files, identical to their staged LF bytes:

| Path | SHA256 |
| --- | --- |
| `backend/src/newsflow/domain/hype.py` | `A7D45A1B9436E3DF9845C4E6224E3F94E66A9E550C7E9B4FABF5047E00A320E4` |
| `backend/src/newsflow/domain/donor_performance.py` | `B6CDBEDD33C7130366423F836645232715BC3F582BB54A09F591531F2F877A49` |
| `backend/tests/test_hype.py` | `AD643C76D518BAFB1F2810A42649B1F97588328346A38A8366BBF3CD98374E13` |
| `backend/tests/test_donor_performance.py` | `69A822B2C7D3EAF6A8148AFC1E51102DB37A3CC0EAB93D468AA7B1ED4CF0251C` |

Git warned that future Git checkout operations may convert working LF to CRLF;
the staged source bytes remained LF. No broad staging or unrelated file change
was performed. Final staging explicitly checks the exact five owned paths,
then `git diff --cached --check` must return native0 before `git commit`.

Concerns: none outstanding for the pure Task1 contract. SQL projection,
cross-task review, PostgreSQL and combined backend/authority gates remain the
controller's subsequent scope and are not claimed as verified here.
