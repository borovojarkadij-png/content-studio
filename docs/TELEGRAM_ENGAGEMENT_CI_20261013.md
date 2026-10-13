# Engagement exact-generation CI — 2026-10-13

Authorized owner `borovojarkadij-png`, origin
`https://github.com/borovojarkadij-png/content-studio.git`, branch
`codex/dark-navy-ui`. Root reviewed acceptance commit
`87e5189a39b09847c1655cecdb64317b8942008d` pushed native0, exact remote verified
from predecessor6bc5adc; no force/merge/main/PR. Existing owner credential used
only in a restored process environment, no global auth switch or new key.
Push receipt retained in
`D:/Codex-Recovery/content-studio-20261008/telegram-engagement-acceptance-20261013a/push-receipt.json`.

Exact [Quality gate run38330110524](https://github.com/borovojarkadij-png/content-studio/actions/runs/38330110524)
is **IN PROGRESS** at the recorded checkpoint, head87e5189. No completed full
gate claimed. Root will inspect actual native logs/artifacts for this exact run;
earlier login/backup CI does not prove the newer source.

The original local combined full native1/2FAIL/3347PASS52SKIP remains retained.
Both historical fixture fixes were narrowly authorized and independently reviewed;
final targeted119PASS/26PG-onlySKIP plus actual owned WindowsPG26PASS/0SKIP and
packaged smoke prove those boundaries but do not replace final whole-suite CI.

Ten jobs are enabled without weakened checks. Frontend is unchanged and accepted
UI is not redesigned. Source integration review Approved/no findings is not
live authorization/model qualification or PHASE completion.

Root first attempted a completed Windows job's log through `gh run view --log`
while its parent run was still in progress; CLI refused with native1 and explicit
"logs will be available when it is complete". Original82byte diagnostic retained
as job-115077707092.log in the run's evidence directory. The controller helper
now waits for whole-run completion and writes distinct `-native.log` receipts,
never overwriting that failure or treating it as a source/test failure. Metadata
and already-available artifacts can still be read independently.

## Available new-run artifacts inspected while other jobs run

Actual Windows job115077707092 completedSUCCESS. Downloaded artifact11782324768
`windows-backup-contracts`,455812bytes: actual JUnit83tests/0FAIL/0ERROR/0SKIP,
elapsed61.102s; native pytest log83PASS61.11s. Excluding duplicated `current`
fixture aliases,81entrypoint files contain82JSON exit receipts (5intentional
successes/77intentional failures);45native receipt files contain112lines,
including11intentional nativeexit23 negatives. Native receipts are text
`operation exit=N`, not JSON despite .jsonl suffix; parser diagnostics exposed
that format and underscore-bearing pg_dump/pg_restore operation names. Actual
format was inspected and no result regenerated or test changed.

Actual frontend job115077707203 completedSUCCESS; new editorial-policy-ui
artifact11782980186,2204127bytes, downloaded and actual .last-run.json is
statuspassed/failedTests[]. This establishes that browser runner's result,
not a new reference comparison or full PHASE claim. Full native frontend log
waits parent run completion.

Evidence directory:
`D:/Codex-Recovery/content-studio-20261008/telegram-engagement-ci-38330110524-20261013a/`.

| Retained artifact file | SHA256 |
| --- | --- |
| artifact-11782324768/junit.xml | 138D8AAE741733039F9961BA8A86D88F81259D04E379544BBD21889C8160908A |
| artifact-11782324768/pytest.log | E4406E098763118ED02A1F8D8BDC240914D7A49BEC666CD311E4CEFAC6ACF10A |
| artifact-11782980186/test-results/.last-run.json | 91D1C43004802CD49950D78EB11C8FA7D05DA8FFFFE219A8B13B2F561BC00903 |

## Completed native job logs inspected — parent still running

Completed-job REST logs are available independently of the parent run. First
REST attempt refused terminal escape sequences (native1, diagnostic retained
as job-115077707092-native.log). Controller uses the CLI's explicit
`--allow-escape-sequences` only when writing raw evidence to files, not executing
or rendering log instructions. Corrected distinct `-api.log` downloads native0;
both earlier failures retained. No CI/test command or check was disabled.

Seven completed jobs SUCCESS and actual native logs checked:

- PostgreSQL115077707307:868PASS/3nonapplicableSKIP475.13s;5controlled lock-order
  regressions PASS4.75s. New engagement file present in exact invocation,26new
  cases now execute in CI as well as the root actualWindowsPG gate.
- Full-stack115077707102:1PASS/4deselected353.87s; nine stage boundaries,
  down/up/Redis-worker/PostgreSQL crash recovery and final migration drift PASS.
- Authenticated illustration115077707170:136PASS39.21s; packaged health,
  seed/invalidate/pending/execute/final, down/up/crash and two final reopens PASS;
  realTelegram/AI0, liveacceptanceSKIP explicit.
- Channel sync115077707115: persistence/recovery/rewrite-wait proof PASS,
  zero realTelegram/AI/send IO.
- Admission115077707099: seed/admit/reopen/persistence PASS, configuration,
  session/outbox/media/unfinished jobs preserved; no execution/publication.
- Frontend115077707203:334units/21files, format/build and33main+1illustration+
  3editorial browser tests PASS. Accepted UI unchanged, no fresh visual claim.
- Windows115077707092:83PASS61.11s/noSKIP as actual artifact above.

Hosted Node/punycode deprecation notices are retained, not suppressed or confused
with test failures. Whole backend and both provider restart families remain
in_progress; no whole-run PASS yet.

Subsequent completed provider logs independently downloaded/inspected:
115077707229 OPENROUTER and115077707302 OPENAI both SUCCESS. Actual encrypted
peer/session, media, donor resolution, account cooldown concurrency, ingestion
and edited-source recovery, persistent mapping filters, source photos and
publication seed/recover/quota/pending/two-final-reopen stages PASS. Redis/worker
restarts are present. Every stage reports zero realTelegram/AI/send calls;
retained stacks and live authorization SKIP are explicit. Only whole backend
remains in_progress, and its benchmark artifact is not available yet.

| Actual job API log | SHA256 |
| --- | --- |
| 115077707092 | 543C1E49288562FC6C1D1B4C31B5D90CB1722D5E72AF6C918D5E6BC32FAD7EFF |
| 115077707099 | 33AB35F4F8FA359F648000111B2769B9AF7B3A4DCEC07DEB24C442994F0E254E |
| 115077707102 | BBCDE90025FBED556EA0A7FB2D58300D45690CC4B9D60383EB730B3AC40BDE91 |
| 115077707115 | 9924ECDC5E73416754EA9BBA1466607A2785BC66BF9350747AF258179405BE58 |
| 115077707170 | 54FB85B71DC646421884438DFA35DDEDBCFC3AD436A3536314AF1B4B75D4B4CC |
| 115077707203 | CE56F73ACCFC3A394E7958439A5EC83349B28E5B2099DBB743994C580B2984AD |
| 115077707307 | D99904B2052F51A20EB6C287DDACE1BAB67CC652BF95C623D5B124483F476944 |
| 115077707229 | AD361F3C98E730EBE8EEDD4BD4B19C7799E1623429EEAA28878447567CA8398E |
| 115077707302 | F856F6648B385F55210393C1A306ED4BB94C4000FEF57C782F4F29EA1EAFD1A2 |

## Final exact-generation acceptance

Run38330110524/exacthead87e5189a39b09847c1655cecdb64317b8942008d is now
COMPLETED SUCCESS, all10jobsSUCCESS. Final backend115077706910 actual native
log:3266PASS/135explicitSKIP837.69s, backend/root browser-fixture lint PASS,
compile and fresh SQLite upgrade/downgrade/upgrade/alembic.check PASS/no drift.
This is corrected exact full-generation evidence, unlike the retained prior
local full2FAIL/3347PASS/52SKIP. Hosted Linux Windows/explicit-PG skips are not
misrepresented; actual independent Windows83 and PG868+5 execute those gates.

New artifact11782971919 `editorial-classification-contract`,1003archivebytes,
downloaded actual JSON independently checked:24cases/24matched/0mismatches,
provider_calls0/rewrite_calls0/real_model_qualifiedfalse, every case
editorial_allows_rewritefalse/actual.rewrite_allowedfalse. This synthetic
benchmark cannot qualify a real provider or allow automatic approval.
Actual artifact JSON SHA256
318DE43F3C8C0DE9501B324A31B14C3390E6AFE6470A6913571393A0B9896E45.
Backend rawlog SHA256
93C945DD49ED02CA417C9D970FC06D5570A682E3F1D366B70EAEE1057C0B955A.
Newer Hype source is not covered by this predecessor head; it requires its own
frozen full/source review/actualPG/new exactCI. PHASE remains incomplete.
