# Corrected editorial candidate — exact CI evidence

Candidate cf3892987f78b36856996b92fe6eb06a44bce540,
run38321414003, authorized borovojarkadij-png/content-studio branch
codex/dark-navy-ui. This is new evidence after the original failed run38319840777;
the predecessor failure is not relabeled as success. Actual run completed
SUCCESS with all nine jobs SUCCESS. Backup/restore changes in progress are not in
this SHA; no acceptance of those newer bytes is inferred from this run.

Native downloads all exited0 into
D:/Codex-Recovery/content-studio-20261008/editorial-ci-38321414003-20261013a/.

| Completed affected gate | Actual result | Retained raw evidence SHA256 |
| --- | --- | --- |
| Backend115050122658 | 2950PASS/15explicitSKIP/581.14s; subsequent standalone fixture Ruff checks PASS | backend.log:5DB2B4E0EB8A5FE8BE2E856C67C6A502CC10BE94400941F41786C8B304986198 |
| Frontend115050122556 | 334units/21files; format/build;33main+1illustration+3editorial browser PASS | frontend.log:FDDBF8D7F6DF31F6624285B15F6AC43C881B4C42E8B53FC0DEB2C58A547A1588 |
| Channel sync115050122686 | Actual seed/pending/recover/concurrency and rewrite-wait/reopen PASS; real Telegram/AI/send0 | channel-sync.log:E220160704CBD18C57BB7ED311BA84F220A76F71E975281E936D30C7100FC9E3 |
| Full stack115050122723 | 1PASS/4explicitdeselected355.30s; Alembic drift clean | fullstack.log:54DD85555B6FA2344E35F6F7B23847248678EF3D4969070138B89BD0D54256E0 |
| Illustration restart115050122774 | 136PASS37.58s; packaged health/restart/finaldouble-reopen/drift PASS; real Telegram/AI0; liveacceptanceSKIP | illustration-restart.log:DF222DE9F543BC02B1653A1106887E14D36218BE3CFEEB58E6577F97EB18F195 |
| PostgreSQL115050122741 | Actual migrated831PASS/3explicitnonapplicableSKIP647.69s plus5concurrencyPASS6.73s | postgres-vertical.log:7206164C969B1CE7F10EBD5F147676FCD8C470A32CFCDB7D08162501E7D3E840 |
| Guarded admission115050122642 | Actual seed/pending/admit/reopen PASS; no provider execution/publications | guarded-admission.log:F1076035501A5DA4FA3D449FE0DACE2616D87FD9D51EF3E4986C2C25D29A30AE |
| OPENROUTER Docker115050122702 | Actual source/donor/filter/photo/publication recovery and final double reopen PASS; real IO0 | openrouter-persistence.log:5564AD6D40E55B963E7B52AE31D78DAA10E22A64C8F7608EF060BA63B2C29B0C |
| OPENAI Docker115050122745 | Actual source/donor/filter/photo/publication recovery and final double reopen PASS; real IO0 | openai-persistence.log:0252D9B8C5B90DBD7A4DE711CD626228C187CA1CB1305152613D1915EA9A6A36 |

Actual new benchmark artifact11779625544 downloaded native0 and parsed/asserted:
24cases/24matches/0mismatches, provider0/rewrite0, every rewrite permissionfalse,
real_model_qualified=false. JSON SHA256
318DE43F3C8C0DE9501B324A31B14C3390E6AFE6470A6913571393A0B9896E45.
This synthetic contract never qualifies a real model or authorizes automatic PASS.

Actual current editorial-policy-ui artifact11778354671 was separately downloaded
native0 and its embedded report ZIP inspected, not executed:
3expected/0unexpected/0flaky/0skip/oktrue. Report index SHA256
1CAF60AB841ED0B8A5B4C1CE9987516C16615305ED675EF537EAD276E15319C9.
SQL attachment shows actor29/four unique audit events, exact multiline aliases,
disabled synthetic policy, diagnostic-only/no authority, retained REJECTfalse and
all six execution counts0. Native action deprecation warnings remain recorded;
they are not hidden or treated as application failures.

Both provider Docker jobs have now completed SUCCESS; root downloaded their
actual native logs and inspected seed/recover/refusal/quota/reopen outcomes.
This is zero-network synthetic provider execution, not real provider acceptance.
Windows operator restart/down-up evidence is separate in
EDITORIAL_OPERATOR_RUNTIME_VERIFICATION_20261013.md; CI Linux is not Windows proof.
