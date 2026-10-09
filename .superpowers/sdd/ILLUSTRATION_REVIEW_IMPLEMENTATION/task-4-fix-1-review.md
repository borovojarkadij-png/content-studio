- **Reject redirected build and bind sources before creating the fixture.** — ADDRESSED. `scripts/illustration_restart_controller.py:344` checks backend/frontend directories, their Dockerfiles and the bound standalone probe with the existing ancestor-aware symlink/reparse guard at `:131`, exact resolved-path equality and existing file/directory type. `create()` invokes this before absence checks or any file write (`:277`); retained validation repeats it before Docker configuration/resource checks (`:370`). Restart/down, crash and retained up reach that validation before mutation (`:593`, `:600`, `:632`, `:688`). `backend/tests/test_illustration_restart_guards.py:599` covers six redirected targets across create/validate/restart/crash/retained-up, with actual Windows junctions, zero Docker commands, unchanged fixture bytes and untouched foreign sentinel.
- **Use the recorded immutable images for retained startup, or refuse changed image resolution before mutation.** — ADDRESSED. `scripts/illustration_restart_controller.py:599` requires the exact seven original services and well-formed recorded SHA-256 IDs, then inspects each ID and original explicit image/default project build tag and requires both results to match. Down invokes this before Compose down (`:595`); crash invokes it before the unchanged exact-ID helper (`:690`); retained up repeats it before startup (`:632`). The stdin override pins all seven services, including migrations, to original IDs and startup forbids builds and pulls (`:637`, `:641`, `:648`). `backend/tests/test_illustration_restart_guards.py:719` reproduces changed tag resolution while running containers still match, across all seven services and three operation boundaries; `:743` covers missing/mismatched original images; `:755` checks exact override IDs, no-build/pull-never and unchanged manifest/file bytes.

## New Breakage in the Fix Diff

- Critical: None.
- Important: None.
- Minor: None.

## Out-of-Scope Observations

- None newly raised. Unchanged whole-branch observations and previously documented acceptance limitations remain deferred; they do not extend this fix round.

## Checks and Evidence Boundaries

- Read the complete scoped re-review prompt, Task 4 brief, prior Important findings, appended fix report and supplied `review-bfba7ed..a6981f2.diff` once. Reviewed only fixes/new breakage in `bfba7ede98d775510abd5353f4182c68ceb60b18..a6981f26d52130331ba5bd5b0fe9bcb9acd9f712`, using focused current-file reads for guard ordering and line references.
- `task-4-report.md:244` names the three covering test files and records `152 passed in 27.79s`, session97753 exit0; the added refusal/startup regressions substantiate the reported scope. The report also names RED runs and lint/format/compile checks. These test results remain implementer-reported session evidence; raw pytest output is not part of this diff. No suite or focused test was rerun because code inspection raised no unanswered specific doubt.
- Read the final corrective section of `docs/ILLUSTRATION_RESTART_PARENT_20261009.md` and the complete native log `D:/Codex-Recovery/content-studio-20261008/task4-fix1-immutable-boundaries-20261009a.log`. The native log records health/restart PASS at `:93-94`, two final reopens with real Telegram/AI calls=0 at `:95-96`, health/crash PASS at `:137-138`, and two further final reopens with real calls=0 at `:139-140`. This independently supports successful retained Windows restart/crash/reopen; process10576 exit0 and the exact startup arguments are recorded by the parent/report, not printed as command lines in this native log.
- Read-only SHA-256 checks matched the frozen controller `0AF2EED48878A5007071956EB049D512703BA15DD24BD1654F4BF1BA1EF4E12D`, unchanged standalone probe `D917CEF2D8E7156D5DF7CE00EF006F637B8A1BD00C85E2F4D581EB4BB9483039`, and retained original runtime manifest `239FE7796C246CE1A5763F10E1897658C89868569A69D2AD5698623D0407CE34`.
- The fix changes only the controller, guard tests, dedicated procedure and implementer report. The production/probe/crash-helper behavior and existing REJECT/rewrite_allowed=false/no-new-jobs/zero-real-calls assertions are unchanged in this package. The earlier 1871 PASS/1 SKIP full suite remains historical; new exact CI remains pending and live acceptance remains SKIP.
- No helpers/subagents, Git commands, tests, Docker operations, fixture changes or source edits were performed. Only this review report was written.

## Verdict

**Fix round: All findings addressed, no new Critical/Important breakage.** Open findings: none.
