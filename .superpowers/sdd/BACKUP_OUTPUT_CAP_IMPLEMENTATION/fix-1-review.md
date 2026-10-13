**First overflow-inspect-backup fails before the owned PID/trace is recorded** — **ADDRESSED** for the demonstrated first-launch mechanism. `backend/tests/test_windows_backup_restore.py:36–40` adds exact `--ready` handling before configuration access; `:145–166` invokes the compiled executable with a 30-second bound and asserts native exit 0, exact byte response `SHIM_READY`, and empty stderr before timed cases.

**Readiness behavior coverage** — **PASS**. `backend/tests/test_windows_backup_restore.py:170–195` exercises the actual executable without `BACKUP_FAKE_DIR`, asserts the exact response/native exit, and rejects unexpected fixture files. No validation helper was introduced; direct strict assertions refuse malformed responses.

**Existing boundaries preserved** — **PASS**. The immutable fix diff contains only additions to the test module and report; all prior 97 cases remain. The overflow cases retain `TimeoutSeconds=1`, elapsed `<8s`, owned PID termination, unrelated process survival, private errors, required trace/start markers, forbidden blocked-writer completion, no later database commands, destination absence, source snapshots, and sentinel assertions (`backend/tests/test_windows_backup_restore.py:385–432`). Production files are outside the fix diff.

**Evidence verification** — **PASS**. Retained CI `38338368307` artifact confirms `1 failed, 96 passed`, with only config/status/sentinel files in the first overflow fixture. Disposable experiment logs confirm injected 1,800ms first-launch delay produces the missing-PID failure; bounded readiness records native 0/exact response/empty stderr in 1.875s, followed by target GREEN and eight-case GREEN. The retained cold fixture has its entered marker without completion. Report `task-1-report.md:172–199` correctly distinguishes this causal experiment from the unproven historical CLR/OS/AV hypothesis.

**Covering checks verified without rerunning suites** — **PASS**. Retained correction logs show 15 focused passes/native 0 and 98 full passes/native 0; full JUnit records 98 tests, zero failures/errors/skips. Fixture and behavior receipts contain exact readiness responses. Eight overflow fixtures retain expected PIDs, traces, private failure statuses, and blocked completion absence. Ruff, formatting, compile, three PowerShell parsers, and diff checks each record native 0.

**New breakage in the fix diff** — **None**.

**Out-of-scope observations** — **None**.

**Spec compliance and quality** — **PASS**. Narrow, bounded, asserted test-harness correction; no retry or weakened deadline/assertion. Readiness does not guarantee arbitrary later scheduling within one second, as the report explicitly acknowledges.

**Fix round** — **All findings addressed, no new Critical/Important breakage**. Review remained read-only; no checkout/index/HEAD mutation or test rerun.
