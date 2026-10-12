# Editorial diagnostic history verification — 2026-10-13

Status: IMPLEMENTATION ACCEPTED AFTER FIX1; EXACT FINAL-SOURCE CI PENDING.
Repository borovojarkadij-png/content-studio, branch codex/dark-navy-ui.
BASE65ed7f22e3d8cefc760210bb391c96f9d38a4267.
Requirements: EDITORIAL_DIAGNOSTIC_HISTORY_IMPLEMENTATION.md and its SDD brief.

## Scope

Bounded canonical SQL read model and one existing studio GET route for retained
diagnostic jobs/receipts. No mutation, retry, approval, provider construction,
decryption or publication. Historical diagnostic PASS remains unqualified and
always false rewrite/execution permission. No UI/schema/worker/settings changes.
Tests use migrated synthetic data and injected classifiers, not live providers.

## Interrupted-task evidence

The original writer's focused15 was interrupted without a terminal/native result;
it remains UNKNOWN, not PASS. Original01 test setup failures were not valid
behavioral RED. Original02 reached actual HTTP with migrated REVIEW/REJECT runner
receipts and failed because an empty reader returned zero retained items.
Raw logs remain under D:/Codex-Recovery/content-studio-20261008/
editorial-history-task1-20261012/. The same existing four-file implementation
was resumed by one replacement writer, without repeating completed increments.

Fresh focused19 completed native0:211PASS/5 explicit PG-only SKIP/102.51s.
Root inspected native summary and SHA256
75A18BCCA7C430CD60D6A7BB7DA078791BE035F8A785F77E02A60CF77276E02A.
These skips remain skips; a separate actual new-file PG run follows below.
The sole frozen full backend gate20 terminated native0:2643PASS/11 explicit
PG-only SKIP/583.01s, no warnings. Root read the actual terminal/native marker,
all skip reasons and hash, not only the writer's claim. Full log SHA256
096E6DD134E3B987AD631C546DD32214055CB50E37A83781530ACE3DAE0627D3.
Five durable-runner lock/finalizer cases, one illustration TRUNCATE control and
five planner/media concurrency cases require separate PG. Earlier actual exact
predecessor CI covers those unchanged controls; none is mislabeled local PASS.
Ruff0.17, changed three-file format, compile/YAML/retained20min budget PASS.

## Frozen bindings

Four hashes independently checked before and after the root PG gate:

- backend/src/newsflow/services/editorial_history.py:
  1B1221D96D51F0783441FBFA57D3558C0F3074C5EE7BE28866AF81E3C999D2C9
- backend/src/newsflow/api/studio.py:
  155A54D42A8DDF6271C942FBEF7168168B7F56693E0FCD611927DF1B84E9D5AD
- backend/tests/test_editorial_history.py:
  853BB20F08601B530C659791CF94337FC3B03F459BE4EBAC4F7F3C3249D29D51
- .github/workflows/ci.yml:
  25F2F59041B8D2C7EFBC1D42406B94625FB8270BA141A52B84215B022D3841F3

## Root actual Windows PostgreSQL

Desktop startup reproduced the stale sailor-ingest socket failure. Reversible
socket-only directory preservation restored actual Linux Engine29.8.0; see
DOCKER_STARTUP_RECOVERY_20261012.md. Exact retained synthetic PostgreSQL container
4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e, ownership nonce,
sole original volume and loopback5432 binding validated before starting only it.
Normal interrupted-system fsync/recovery completed. Pre-stop1697 UUID namespaces/
maxOID1294081 survived exactly; no reset/reseed/public migration or old-schema reuse.

Root native session99834:78PASS/58.03s/native0/no SKIP or warnings.
Only78 fresh UUID schemas created:1697/max1294081 ->1775/max1363793.
Explicit fake synthetic target supplied only through process-local environment;
TMP/TEMP/PYTHONDONTWRITEBYTECODE and target restored in finally.
Telethon1.45.0 asserted before pytest import. Exact new-file test invocation:

```text
pytest.main(['backend/tests/test_editorial_history.py','-q','-rs',
 '--basetemp', unique_tmp + '/pytest', '-o', 'cache_dir=' + unique_tmp + '/cache'])
```

unique_tmp is D:/Codex-Recovery/content-studio-20261008/
editorial-history-root-pg-761a55dbcc5b47bab6da4008b28f6c89/tmp.
Raw native.log in its parent directory, SHA256
F3364E000DA27C9C52C269D9C4A99AAAEDD36DB0AD537ED77B96120869168F36.
Four frozen hashes unchanged, PostgreSQL healthy. No actual Telegram/AI calls.

## Remaining gates

Writer commit fbb4c6e79c4521d5d1b6fc623e8376168b5028cc contains exactly four owned
source/test/CI files plus its force-tracked181-line report. Root read the final
report through EOF and verified the scoped commit. Complete BASE65ed..fbb package
generated for fresh /root/editorial_history_review. Independent review reports
spec issues/qualityNeedsFixes: FAILED/BLOCKED terminal receipts were not checked
against the final attempt/current job state. Root verified this against accepted
runner finalization; no plan conflict. Original writer resumes fix1 with a failing
regression, minimal reader/test amendment, covering new reader+runner tests and
root targeted actual PG. Original successful full2643 is retained, not claimed
as amended-source evidence. Scoped fix re-review follows; no second full suite.
Review provenance items outside diff are resolved by the root's original native
logs, frozen hashes, actualPG and exact origin/branch evidence above.

Fix1 behavioral RED is actually reproduced:4 expected failures/6 positive
controls PASS/78 deselected/3.76s/native1. The four corrupt decoded histories
(FAILED/BLOCKED each with QUEUED or a later attempt) failed to raise the required
static error. Original log21-review-terminal-red.log retained, SHA256
0BC63CE94D7B68067C8CA8B06294DE37802B4581E48AB2F50B73E04472F0B073.
The one-line reader amendment extends the existing terminal-outcome check;
covering reader+runner gate22 is running. Ruff0.17/format/compile/diff gates
23..26 native0, root inspected logs; only existing Git CRLF notices remain.
Fix covering22:213PASS/5 inherited PG-only skips/60.68s/native0/no warnings;
root raw log/hash CE01124F0C6F3F93C9481A5A5A2AE2667DC4AE4727DC55DB8B53E1F8DC64433B.
Root actual strict WindowsPG new-file `-k terminal_receipt`:
10PASS/78deselected/7.27s/native0/noSKIP/no warnings. Same validated exact
container/volume/loopback;10 fresh UUID schemas1775/max1363793 ->1785/max1372163.
Process environment restored finally; tmp under unique fix1 log directory.
Raw log D:/Codex-Recovery/content-studio-20261008/
editorial-history-fix1-root-pg-fc4e10c2abda49279a0fa03481fc0961/native.log,
SHA2564B1D82954578B40896DE0263A8548F5D35F7E39BB2628F719D5ED794D1CE6ACD.
Two amended files frozen before both gates and independently unchanged after:
service5C643A18BE9C6FDBD7A31D1414850DEFB13BCBA6E44BBE283305FC921EBF322B,
testsC619059A9F939A0CFECAB389D44A1AEF048696A0DDDD9717D4D0A8E3DC57EAAC.
Fixfae11e71d02027f8f33e80df62c5275ed83ffba7 contains only service/tests/appended
report; root read the appended107 lines EOF and verified the exact three files.
Complete FIX_BASEfbb..fae package15575bytes independently scoped re-reviewed:
findingADDRESSED, speccompliant/taskqualityApproved; no new Critical/Important/
Minor or outside observations. Root read full verdict and saved both original
review and scoped re-review, including the original Important rather than
erasing it. Local implementation accepted; exact final-source CI still pending,
not waived by review or prior65ed CI. Root documents/pushes this branch then
continues the prepared bounded model-evaluation increment. PHASE1 not complete.
Root documentation/push and exact new-source CI remain pending. Prior exact CI
38306240255/head65ed all9 SUCCESS proves the predecessor, not this later task.
PHASE1 remains unfinished. Live model benchmark/qualification, manual test
Telegram authorization and test destinations remain separate external actions;
independent implementation continues without enabling automation or real sends.
