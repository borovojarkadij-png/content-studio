# Backup output cap — hosted generation and retained failure

Exact rootcheckpoint `bffda47235cbbda484485b26117f4ee72d7813f0`, authorized
branch push native0/exact remote verified. Run38338368307 is not accepted:
Windows job115103532885 endedFAIL,97cases/96PASS/1FAIL/0SKIP67.49s.
Eight other jobs SUCCESS and backend running at the latest retained snapshot;
no whole workflow success claim.

## Observed failure

`test_oversized_native_text_refuses_before_database_changes[overflow-inspect-backup]`
failed reading oversized.pid. Artifact11785736468/fixtures/
test_oversized_native_text_ref0 contains only config, sentinel and generic
private-error receipt; neither trace nor PID/start marker exists. This is the
module's first native-shim invocation after six helper-only cases. The following
seven native-overflow cases reached the shim and passed. Entry-point refusal,
private diagnostics and sentinel preservation were observed, but the missing
boundary evidence correctly makes this test FAIL.

The production deadline starts before Process.Start. Cold CLR/OS startup
contention exhausting the one-second budget is the leading hypothesis; generic
private errors do not prove the precise startup substage. Original writer's
readonly investigation proposes an asserted native --ready response before
short-deadline tests, followed by deterministic first-launch-delay reproduction.
No source change or timeout increase is accepted from diagnosis alone. A
disposable causal experiment proceeds first, followed by minimal reviewed fix.

Disposable causal experiment now actually completed, root fullreport inspected:
1,800ms injected firstlaunch before initialtrace reproduces identical missingPID
failure/native1. Exact asserted SHIM_READY response completed in1.875s outside
the timed entrypoint; same target1PASS/native0 and eightoverflow cases8PASS/
89deselected10.45s/native0. Every existing deadline/assertion remains unchanged;
checkout/index/HEAD untouched. Evidence/commands/copiedinputhashes in
`D:/Codex-Recovery/content-studio-20261008/backup-output-cap-startup-probe-20261013a/REPORT.md`.
This proves the startup mechanism under controlled delay, not the precise
historical host substage or all future OS scheduling. Repository fix4544143
implemented/retested/independently reviewed; exact newCI remains pending.

Every TimeoutSeconds1, <8s, owned-PID, unrelated-process, private-error,
no-downstream-DB and source/destination assertion must remain. No blind CI
rerun, skip, continue-on-error or production deadline weakening is authorized.

## Actual other job logs inspected

| Job | Actual result |
| --- | --- |
|115103532844 guarded admission|Encrypted fixture/configuration/job/outbox/media restart/reopen PASS; no provider execution/publication|
|115103532907 frontend|334unit/33main browser+1illustration+3editorial PASS; accepted design unchanged|
|115103532959 full-stack restart|Actual down/up/crash-boundary1PASS4deselected355.60s; migration drift clear|
|115103532972 channel sync|Rewrite-wait seed/pending/recover/repeated verify PASS; zero real Telegram/AI/send calls|
|115103533049 illustration|Authenticated create/review/execute/reopen PASS; live acceptance explicitlySKIP; realcalls0|
|115103533425 PostgreSQL vertical slice|892PASS3nonapplicableSKIP599.51s and5concurrencyPASS6.23s; negative SQL/legacy deadlock diagnostics expected by assertions|
|115103532957 OPENAI persistence|Synthetic ingestion/filter/photo/publication crash/down-up/repeated verify PASS; real calls0|
|115103533029 OPENROUTER persistence|Synthetic ingestion/filter/photo/publication crash/down-up/repeated verify PASS; real calls0|

## Evidence identity

Evidence:
`D:/Codex-Recovery/content-studio-20261008/backup-output-cap-ci-38338368307-20261013a/`.

| File | SHA256 |
| --- | --- |
|job-115103532885-api.log|8F0B75A6ED3043D620DD68E4722365B0AE3DB4B4570850922E3A4223FAA92335|
|artifact-11785736468/junit.xml|C6E08DFE044AC3149976AD352DD58222992B5B7FBA0F2B126D59C9C73674B5C7|
|artifact-11785736468/pytest.log|742834B6E663414BF6C606B7CD55CF566A6CDA0E642CF00EC47721AA632C0716|
|job-115103532844-api.log|4D164502E82B573EB467FA5232D0EACAB2E43505974ECBE6202CFE781A9DD559|
|job-115103532907-api.log|556C24D238044687063C8042D41C66F819DC0FEE9999046B99F91B6D49BB9115|
|job-115103532959-api.log|61AE238EF4D21FB007B0822DDBE2F86986C804B1CC5DC9DAB865804B7D5D5C4E|
|job-115103532972-api.log|6B93F8816D9F73AF18AA471E33D40D6C027E56448695594B9B70475560782C6A|
|job-115103533049-api.log|F8C75B343A3658F96C71F5607774CEC8F5A996EA0EDB26F50451545E8FF820AB|
|job-115103533425-api.log|EB2C1B3E8651A3B90D38A734370C015F7497CAAECB79A4A3C8FDB6B3108AA80F|
|job-115103532957-api.log|F26723C8938C42543D7573B3DD9F3AA57393853739311279685B15DB2429FF19|
|job-115103533029-api.log|D417057FFD54A82FCAD94114846E990D4F7DFB20D9F68D6EAC9214D38A12EEE3|

## New repository correction — local acceptance, hosted acceptance pending

Source4544143e05d7c8435d934c620e960c2e746bbad2 changes only the synthetic
shim readiness/session fixture and one native behavior test. Prior97cases/
deadlines/assertions unchanged; focused15PASS/full98PASS43.96s/native0,
JUnit98/0FAIL/0ERROR/0SKIP/static0. Fresh independent scoped re-review:
allfindingsADDRESSED/no new breakage/specPASS/qualityPASS. Exact new hosted
generation remains required; this does not relabel failed38338368307.

Correction evidence in
D:/Codex-Recovery/content-studio-20261008/backup-output-cap-readiness-fix-20261013a/.
04-full.log SHA7497A5EFD86962744169FA548EC67352182116F66E13194846C5E99155E596B9;
04-full.xml SHAD85B0DE94B85F1E34026F60FDAB6FFEE57703BEF22579010A00183791EAA5BEE.
Test hashAB743D5FFBC60F639DF7F32B0731ED4DF74E7C997DC41CFD733740EB096929E5;
unchanged production helper2C79B0BC2AE32D10D2E8E6B4981FF6483D2BD5328AD9758DEF51CA9F646EB9C3.

Exact local97PASS/source reviews/original resource probe remain valid for their
recorded environment, not a substitute for hosted acceptance. Sampling previous
2051990/run38337278244 all10SUCCESS remains a separate source generation.
PHASE1 and live/model qualification are incomplete.
