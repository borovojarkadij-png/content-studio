# Task 1 — retained editorial diagnostic history

Status: DONE — implementation and both final gates complete; controller's
independent scoped review follows. Synthetic results never imply qualification.

Base: `65ed7f22e3d8cefc760210bb391c96f9d38a4267` on `codex/dark-navy-ui`,
origin `https://github.com/borovojarkadij-png/content-studio.git`.

## Implemented scope

The bounded SQL reader resolves one immutable source revision by SQL identity,
checks fresh canonical donor/output/account ownership, and reads only the exact
content/revision/mapping jobs in descending cursor order (`limit + 1`). It rejects
pending session state before SQL and validates decoded jobs, immutable claims,
receipts, fixed reason codes, usage, exact Decimal cost and UTC timestamps before
projecting the specified fields. Retained old/deleted/disabled/rejected history
remains readable with valid ownership. Every response stays diagnostic only with
execution/rewrite permission false and real-model qualification false.

The studio GET uses the existing request database session. Static private
404/422/503 errors do not echo binding, SQL, provider or source text; no configured
database or missing migration returns 503. Successful and handled error responses
carry `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.
No write/action route was introduced. CI only appends the new test path to the
existing strict synthetic PostgreSQL list; its inherited 20-minute budget remains.

Owned files (only these and this report may be committed):

- `backend/src/newsflow/services/editorial_history.py`
- `backend/src/newsflow/api/studio.py`
- `backend/tests/test_editorial_history.py`
- `.github/workflows/ci.yml`

Root-owned documentation, operational infrastructure, Docker, PostgreSQL startup
and remote CI evidence were preserved. Resume made no source changes.

## Honest original chronology and TDD evidence

Original writer was interrupted and its tool session was lost. Original logs are
retained at `D:/Codex-Recovery/content-studio-20261008/editorial-history-task1-20261012`.
They contain test output but do not retain exact command text or native exit
codes. Those unavailable details are not reconstructed below. The resuming writer
read these original outputs rather than rerunning completed RED/GREEN cycles.

- `01-red.log`: two setup failures (1.45s), `_IncludedRouter` lacked `.path`.
  This is explicitly **not** the behavioral RED requirement.
- `02-red.log`: valid behavioral HTTP RED, two failures (1.51s), real migrated
  canonical admission and injected runner REVIEW/REJECT receipts existed, but
  the temporary empty-reader seam returned `items=[]`; assertion was
  `assert len(payload["items"]) == 1`, actual `0 == 1`.
- `03-green.log`: both real receipt HTTP tests passed (1.29s).
- `04-expanded.log`: 50 passed, one test setup/assertion failure (22.33s).
  The stale-identity fixture's default commit expiration refreshed the object;
  `expire_on_commit=False` now preserves the intentionally stale identity.
- `05-boundaries-red.log`: 55 passed, four failures (24.13s), unhashable stored
  enums raised TypeError and an oversized positive ID overflowed SQLite.
  Explicit enum type checks and bounded SQL integer handling resolved them.
- `07-focused-green.log`: 192 passed, 5 PostgreSQL-only skips (78.01s).
- `11-reader-green.log`: 76 passed (34.66s).
- `12-consistency-red.log`: two expected failures (1.39s, 76 deselected): bool
  decision FK and QUEUED job with a terminal REVIEW receipt were accepted.
  Current code validates exact decision IDs and terminal state/receipt coherence.
- `15-final-focused.log`: output stops at 33%; no terminal summary or recoverable
  native exit. **It is not counted as a passing run.**
- `16-ruff.log`: `All checks passed!` (Ruff 0.17, src/tests/alembic per saved task
  context). `17-format-check.log`: `3 files already formatted`.
  `18-compile-yaml.log`: `Compile three files + YAML + inherited PostgreSQL20min
  budget PASS`. Native exit codes and original commands are unavailable.

The same interrupted Task 1 resumed after reading the exact brief, progress,
implementer prompt, resume/TDD/verification skills, scoped source/test/CI diffs,
original outputs, runner transitions and persistence constraints. It preserved all
existing work. No duplicate implementation, helper, reviewer, old full-suite run,
provider/network operation or Docker restart was introduced by the resuming writer.

## New native verification

All resumed test commands run from the repository's `backend` directory using
Python 3.12.10. Telethon is inserted into `sys.path` **before** import, using
`D:/Codex-Recovery/content-studio-20261008/telethon-145`; test execution asserts
`telethon.__version__ == '1.45.0'`. No dependency installation/change occurred.

Focused command (log `19-resumed-final-focused.log`):

```powershell
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon,pytest; print('Telethon',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; raise SystemExit(pytest.main(['tests/test_editorial_history.py','tests/test_durable_editorial_runner.py','tests/test_studio_overview.py','tests/test_moderation_inbox.py','-q']))" 2>&1 | Tee-Object -FilePath 'D:/Codex-Recovery/content-studio-20261008/editorial-history-task1-20261012/19-resumed-final-focused.log'; $taskExit = $LASTEXITCODE; "NATIVE_EXIT_CODE=$taskExit" | Tee-Object -FilePath 'D:/Codex-Recovery/content-studio-20261008/editorial-history-task1-20261012/19-resumed-final-focused.log' -Append; exit $taskExit
```

Result: `Telethon 1.45.0`; `211 passed, 5 skipped in 102.51s (0:01:42)`;
`NATIVE_EXIT_CODE=0`, confirmed by terminal tool exit 0. The five inherited runner
skips require PostgreSQL; the root's strict new-file PostgreSQL gate is separate.

Fresh scoped `git diff --check -- backend/src/newsflow/api/studio.py
.github/workflows/ci.yml` returned native exit 0. Git emitted only its existing
LF-to-CRLF checkout notices.

Four files froze after the focused result, before the full-backend and root
PostgreSQL gates. SHA256 of exact working-tree bytes:

| File | SHA256 |
| --- | --- |
| `backend/src/newsflow/services/editorial_history.py` | `1B1221D96D51F0783441FBFA57D3558C0F3074C5EE7BE28866AF81E3C999D2C9` |
| `backend/src/newsflow/api/studio.py` | `155A54D42A8DDF6271C942FBEF7168168B7F56693E0FCD611927DF1B84E9D5AD` |
| `backend/tests/test_editorial_history.py` | `853BB20F08601B530C659791CF94337FC3B03F459BE4EBAC4F7F3C3249D29D51` |
| `.github/workflows/ci.yml` | `25F2F59041B8D2C7EFBC1D42406B94625FB8270BA141A52B84215B022D3841F3` |

Sole full-backend command (log `20-frozen-full-backend.log`, same directory):

```powershell
python -c "import sys; sys.path.insert(0,'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon,pytest; print('Telethon',telethon.__version__,flush=True); assert telethon.__version__ == '1.45.0'; raise SystemExit(pytest.main(['tests','-q','-rs']))" 2>&1 | Tee-Object -FilePath 'D:/Codex-Recovery/content-studio-20261008/editorial-history-task1-20261012/20-frozen-full-backend.log'; $taskExit = $LASTEXITCODE; "NATIVE_EXIT_CODE=$taskExit" | Tee-Object -FilePath 'D:/Codex-Recovery/content-studio-20261008/editorial-history-task1-20261012/20-frozen-full-backend.log' -Append; exit $taskExit
```

Full result: `2643 passed, 11 skipped in 583.01s (0:09:43)`;
`NATIVE_EXIT_CODE=0`, confirmed by terminal tool exit 0 (session 76995).
No failures or warnings. This was the sole full backend run for this Task 1.
The exact skip summary was:

```text
SKIPPED [1] tests\test_durable_editorial_runner.py:805: Actual strict migrated PostgreSQL lock proof is root-owned
SKIPPED [4] tests\test_durable_editorial_runner.py:942: Actual strict migrated PostgreSQL finalizer row-lock proof is root-owned
SKIPPED [1] tests\test_illustration_review_storage.py:271: Real TRUNCATE requires the strict isolated PostgreSQL CI namespace
SKIPPED [2] tests\test_planner_media_postgres.py:76: Explicit isolated PostgreSQL concurrency opt-in not supplied
SKIPPED [3] tests\test_planner_media_postgres.py:248: Explicit isolated PostgreSQL concurrency opt-in not supplied
```

Full native log SHA256:
`096E6DD134E3B987AD631C546DD32214055CB50E37A83781530ACE3DAE0627D3`.
After both terminal gates, all four exact working-tree hashes were rechecked and
matched the frozen values above. No implementation file changed during either
gate. A fresh whole-tree `git diff --check` returned native exit 0; no whitespace
errors, only Git's existing LF-to-CRLF checkout notices. The staged commit is
limited to the four listed files and this force-tracked report; root-owned changes
are deliberately left in the working tree for the controller.

Root's independent strict Windows PostgreSQL new-file gate terminated successfully:
`78 passed in 58.03s`, no skips or warnings. The resuming writer directly read the
clean native log, which starts `Telethon 1.45.0`. Native exit 0 is parent terminal
tool evidence from session 99834 (`NATIVE_PYTEST_EXIT=0`); it is not a marker in
the raw log. Parent independently verified all four hashes unchanged pre/post.

Exact parent-reported pytest argument vector (root repository working directory,
same pre-import Telethon 1.45 insertion/assertion):

```python
pytest.main(['backend/tests/test_editorial_history.py', '-q', '-rs', '--basetemp', 'D:/Codex-Recovery/content-studio-20261008/editorial-history-root-pg-761a55dbcc5b47bab6da4008b28f6c89/tmp/pytest', '-o', 'cache_dir=D:/Codex-Recovery/content-studio-20261008/editorial-history-root-pg-761a55dbcc5b47bab6da4008b28f6c89/tmp/cache'])
```

Root set/restored process-local synthetic PostgreSQL URL, TMP, TEMP and
PYTHONDONTWRITEBYTECODE; there were no real credentials or operational SQL.
Retained namespace baseline was preserved; 78 fresh UUID test schemas were added
(`1697 / maxOID1294081` -> `1775 / maxOID1363793`). Root owns infrastructure and
its detailed verification report in
`docs/EDITORIAL_DIAGNOSTIC_HISTORY_VERIFICATION_20261013.md`.

Root raw log:
`D:/Codex-Recovery/content-studio-20261008/editorial-history-root-pg-761a55dbcc5b47bab6da4008b28f6c89/native.log`,
SHA256 `F3364E000DA27C9C52C269D9C4A99AAAEDD36DB0AD537ED77B96120869168F36`.
Focused log 19 SHA256 independently checked by parent:
`75A18BCCA7C430CD60D6A7BB7DA078791BE035F8A785F77E02A60CF77276E02A`.

## Self-review and limits

Self-review checked interface/type requirements, exact ownership and immutable
decision binding, fresh reads despite stale objects, bounded queries, fixed
projection, cost/null distinctions, state/lease and receipt consistency, private
errors, no SQL writes/commit/outbox mutation and no classifier/rewrite/decrypt or
worker work during read. Real runner fixtures establish diagnostic PASS remains
manual-only; REJECT creates zero RewriteJob rows and invokes zero rewrite calls.
Malformed-boundary tests corrupt decoded rows only, respecting migrated immutable
storage. Accounts/mappings have no invented `enabled` column: inactive fixtures
use DISCONNECTED accounts and mapping intake_percent 0.

The endpoint does not add Inbox presentation, a protected policy editor, a real
model benchmark, qualified PASS propagation, real provider qualification or
complete PHASE1. Synthetic test results never constitute qualification.

No implementation concerns found in self-review. The lost original command/native
exit evidence remains an explicit historical limitation; fresh focused/full native
exit 0 and the independent real PostgreSQL gate are retained. Commit subject:
`feat(editorial): expose bounded diagnostic history` (this report is included in
that commit; its SHA is reported separately to avoid a self-referential hash).
