# Durable intake comparison ledger — verification record

Scope: Telegram-only, comparison evidence and fractional carry only. No ingress,
worker, UI or policy activation; selection never grants rewrite/publication.

## Source checkpoints

- Schema:9cc1be0d5bedf654023b76a3d247a43e6d6f7d10; scoped review Compliant/
  Approved/no findings. Local219PASS27explicitPGSKIP/static0.
- Repository:e2f9665580574c5d61ec642bd34bfdb1b73355cd; source frozen,
  independent concurrency review Compliant/Approved/no findings.
- Repository/kernel/schema focused:360PASS17explicitPGSKIP55.61s/native0.
- Related23-module regression:1014PASS33explicitSKIP242.31s/native0;
  original interrupted execution result recovered without repeating the run.
- Ruff0.17/format/compile/YAML-semantic-preservation/diff checks native0;
  all four repository/workflow hashes independently matched by root.

Both self-review defects have retained behavioral RED and corrected GREEN:
coherent load snapshot (1FAIL3PASS→4PASS) and initial-stream invalid retained
history (1FAIL9PASS→10PASS). New tests assert actual migrated storage or clearly
label isolated corruption fixtures; no public immutability bypass is claimed.
Fixtures retain source/REJECTfalse/zero rewritejobs/usage/outbox/provider calls.

## Actual Windows Docker runtime

The native gate executed exactly18cases without skips: seven schema,
ten repository/concurrency and one existing sampling populated-downgrade
version regression. Actual18PASS16.44s/native0/JUnit18/0FAIL/0ERROR/0SKIP.
Existing explicitly owned synthetic Windows Docker PostgreSQL fixture retained
all2082UUID namespaces and public catalog;18new UUID namespaces,2100total.

Installed unchanged-Dockerfile image:
`sha256:3fb1d00d3a02153ffa6734909389472291f79eb899808f12466eb310d941fff1`.
Build0/smoke0,331sourceinputs independently matched; networknone/readonly/
noVolumes/noSecrets. LiteralHYBRID, four30% quotas0,0,0,1/carry30,60,90,20,
rollback, fresh-process reopen/originalwindow replay/source/config/REJECTfalse/
zero jobs/provider/usage/outbox PASS. Alembic drift clear. No ingress authority.

Separate nonce-owned container
`d015cb3543f54274d2158590029870c973ad247554842a29948069a4fc2ddaf0`
with retained synthetic bind storage had THREE actual starts, native0/0/0:
COMMITTED_SELECTION(carry20,next5,4windows) → RECOVERED_AFTER_CONTAINER_START
(carry50,next6,5windows) → REOPEN_IDEMPOTENT(same exact state).
Old-window replay did not re-spend carry; source/config/public-test-cipher/
REJECTfalse/zero jobs/rewrite/provider/usage/outbox retained. This is not live
Telegram authorization or cryptographic session-decryption acceptance.
No operational container or volumes changed; fixture retained stopped.

Evidence/controllers:
`D:/Codex-Recovery/content-studio-20261008/intake-ledger-acceptance-20261013a/`

| File | SHA256 |
| --- | --- |
|postgres.log|1682816742693EDFF0657A39AB08ED3994BD07D7682D4E43F628BD4F3E4CA2C6|
|postgres-junit.xml|568F5AB930B8BDD965940D5F78FBEA2CB4DE823F2AB4E6282F3693E6DCB7F0C4|
|postgres-receipt.json|459A6A81E627D1B75835F69E05D7089BEF83FCF0B2BAE029AD27EF4322276032|
|package-smoke.log|C7A51988CF8A873404E4F632035C2A23EDB897FE609663AAB4A679A8FEF723DF|
|package-receipt.json|99156378E1220DEA4840E28B25B8527D92F7E5C72643A2948846DA32C1F6A700|
|packaged-ledger-smoke.py|E5EFD96F4FD49D093ED301BF71F3F46A37A5C75C3FA802099EF606921321D6DB|
|container-restart-ledger.py|7BFD51DB65DEAB170FD8A5572B12B86D4FCDBC52A41E8EC0560951A6E485DA94|

## Remaining release gates

Combined full backend completed at frozen e2f9665 (root execution29438):
4176PASS93explicitSKIP755.46s/native0, JUnit4269/0FAIL/0ERROR/93SKIP;
all332inputs independently matched. Fresh final increment review Compliant/Approved/no
Critical/Important/Minor; independently matched332PG/331package hashes,
all seven evidence hashes and three native restart logs. Exact new CI remains
pending, not replaced by the source/runtime review.

The full-run report retains78PytestWarnings, all the same harness incompatibility:
default xunit2 JUnit with record_property. This was diagnosed, not suppressed:
one-case warning-as-error RED native1; legacy JUnit with warnings-as-errors over
all78affected PG fixture cases gives native0/78explicitSKIP/0warnings. It is
report-format proof, not78business passes or a replacement for actual18PG proof.
Product/source/HEAD remained unchanged. Original full and controller preserved;
future JUnit invocations use legacy format. No giant unchanged full rerun.

| Additional evidence | SHA256 |
| --- | --- |
|backend.log|F5F01C0E50659B277C65CC60592CED46BD6B0713A4532831C9DA1449EF5EE345|
|backend-junit.xml|447A01377BBD13D77584FEC2923EC4D4CC66649B951BFA45B56AF1CE5D38ADCF|
|backend-receipt.json|0371FDECCD7EDDE731315AB89930AC2B29FB5960EB4970A25FC3200368D66746|
|container-restart-receipt.json|89A62708CFC05D89B51F6F7A416257D673DBF6377ED6F03B251F2DD07C72CBEE|
|junit-format-red.log|B68B1D1AFB58F2270F5B92A051465C730AF3129B91BACE3F43BBAEFBDA1319CD|
|junit-format-green.log|575B7BAF7C253881A170F234BE429BFCB6E1904E9BA376FF29B4941BC3B3AAFE|
|junit-format-receipt.json|598D5EABADF0307E16CE44C16D5146D5AA28FDF20A3E23224F450FA0E6485554|
Do not turn explicit SKIP or prior0950b33 all-ten-success CI into evidence for
this newer source generation. Executed runtime controllers refuse overwrites
or blind replay; no repeated nativePG/package/restart runs are needed.

Final deployment/live Telegram/real-model qualification and PHASE1 completion
remain unverified separately. No real credentials, sessions, working queues,
operational volumes, publications or accepted design were changed.
