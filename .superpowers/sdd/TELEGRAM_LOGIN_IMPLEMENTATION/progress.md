# SDD ledger — plan: docs/TELEGRAM_LOGIN_IMPLEMENTATION.md

Prepared next independent approved TelegramAccount onboarding increment; not
dispatched while Windows backup Task2 solewriter/review is active. Main fully
read saved spec/plan, provider/session/model/migration/isolation interfaces,
NewsFlow migration/security/runtime guidance and SDD/TDD/writing-good-tests.
Current human explicitly requests autonomous implementation, no questions/pauses.

| Preflight | Producer/consumer boundary | Finding/ruling |
| --- | --- | --- |
| Task1 internal | Adapter RPC -> verified result | In-memory only; typed bounded user/phone/authkey/session validation; no real network tests |
| Task1 internal | Preflight snapshot -> transactional persistence | No transaction spans input/RPC; full metadata CAS and key fingerprint recheck; no saved-session replacement |
| Task1 internal | Account row -> outbox | Existing event table, atomic commit/rollback, no secret payload or schema change |
| Task1/Task2 | Public service types -> CLI | Exact preflight/provision signatures; interactive guard precedes runtime setup; constructor is not client construction |
| Task1/Task2 | Unit DB -> PostgreSQL proof | Fake only RPC; real cipher/store/reopen; UUID migrated PG later, no SQLite-as-PG acceptance |
| Task2 internal | Arguments/TTY -> secret/config/DB | Default/help/malformed/nonTTY zero runtime IO; explicit PostgreSQL and current migration heads |
| Task2 internal | Masked human input -> async RPC | getpass warning fails closed, one code/password attempt, cancellation privately exits |
| Task2/root | Source/CLI -> packaged/live | Root actual synthetic Docker and exact CI after review; human login separately pending |

Ruling: proceed within already approved Telegram onboarding/autonomous scope
without another design-confirmation question — human explicitly forbids such
pauses and the CLI closes an existing missing session producer — cost if wrong:
isolated opt-in adapter/CLI can be reworked; no live credentials/UI activation.
Ruling: separate explicit interactive CLI from read-only ingestion/provider —
prevents accidental worker login prompts and an unauthenticated browser endpoint —
cost if wrong: later protected UI integration remains separate work.
Ruling: execute one full backend gate after combined Task2 deliverable, focused
new and covering regressions after Task1 — unchanged expensive suites do not
gain evidence from duplicate runs — cost if wrong: full regression discovery is
delayed until CLI integration but before release/push acceptance.
Ruling: no actual remote auth during autonomous run; source/fake/migrated PG/
network-none package smoke continue independently of missing human code/2FA —
cost if wrong: live session usability cannot be claimed until explicit gate.

BASEd7c580a8108a7523bcc5eff6a4d1c68c60e908aa; brief89lines read, generated final
blankline removed before root staged diffcheck/commit. Solewriter
/root/telegram_login_provisioning,gpt-6.1-sol/high/forknone/nohelpers active.
Root d7c580a actual authorized pushnative0/exactref; CI38323820316 tenexecutions
inprogress covers backup source only, not this new login source. No re-dispatch.
Ruling: independent login implementation proceeds after clean backup task reviews
while exact backup CI runs — no overlapping writer/files/runtime activation —
cost if wrong: CI findings are resolved before release, not inferred away.

Prepared Task2 plan clarification before brief/dispatch: argparse failure must
not echo unknown/invalid argv (could contain a phone/secret); fixed failure status
and negative subprocess case required. This implements existing private-output
spec, not a new CLI option/source scope. Task1 brief/interfaces unchanged.

Task2 preflight correction before brief/dispatch: actual existing PostgreSQL CI
uses NEWSFLOW_UNATTENDED_POSTGRES_URL and an explicit file list, not the prepared
generic TEST_POSTGRES_URL name. Task2 consumes that actual opt-in and appends
only its new PG file to the existing invocation; all other steps unchanged.
Ruling: wire the new migrated contracts into the existing strict CI namespace
consumer rather than leaving them always skipped on hosted jobs — cost if wrong:
scoped one-line workflow correction/new synthetic schemas, no production target
or check weakening. Task1 source/interfaces/ownership unchanged.

Task1 writerDONEbb30b9642ad156689b72bbf98860c3be024aa53f; complete report read.
Actual reported final100focused/160covering/Telethon1.45/native0/staticPASS;
causal missing provisioning/EOF and SDK child-logger privacy failures retained,
test-only fixture failures distinguished. Root three source hashes+report hash
match freeze; complete d7c580a..bb30b96 package1commit/56701bytes. Fresh scoped
/root/telegram_login_provisioning_review,gpt-6.1-sol/high/forknone/nohelpers,
read-only active. No sourcecaller/CLI/live integration yet. Fullbackend deferred
to combined Task2, no same-source suite rerun. Task2 prepared75linebrief read,
not dispatched until Task1 clean spec+quality review.

Task 1: complete (commits d7c580a..bb30b96, review clean).
Fresh review speccompliant/qualityApproved/no Critical/Important/Minor findings;
verbatim task-1-review.md retained. Cannot-verify items are explicitly allocated
to Task2/controller migrated PG, packaged smoke, combined full backend and
human-only live acceptance; not defects or claimed completed runtime gates.
Task2 BASEbb30b9642ad156689b72bbf98860c3be024aa53f, prepared75linebrief read;
sole fresh implementer dispatch next, no duplicate Task1 tests/source work.

Task2 solewriter /root/telegram_login_cli,gpt-6.1-sol/high/forknone/nohelpers
active at BASEbb30b96; root does not modify owned CLI/tests/operator doc/workflow.
Root preflight actual Docker29.8/Linux/API1.56 responsive; healthy engine needs
no restart/reset. Existing synthetic PostgreSQL manifest SHA9FE53C36...matches,
exact full container4c1a4120...running/project owner/sole namedvolume/loopback5432
checked; readonly baseline2010UUIDnamespaces/maxOID1560501. No reused schema or
operational data mutation. Actual new migrated cases await clean Task2 review.
Root package Dockerfile inspected, missing root .dockerignore diagnostic retained;
no file needed/created and no source build before reviewed source freeze.

Task2 interim153focusedPASS/11explicitPG-onlySKIP with no synthetic URL;
CLI/operator docs/11PG contracts and minimal CI append implemented. Initial
pytest capture stream fixture error corrected, not labeled causal product RED.
Writer performs static then one combined full backend/self-review/freeze/commit;
root actual PG and package remain pending review, not SQLite/skip-as-PG proof.

Root concrete unchanged integration check: compose.telegram.yaml supplies the
credential secret to worker only. Sent Task2 writer that operator API-login
procedure requires an explicit API-only operator override/mount, not assumed
inheritance. No tracked Compose edit/new credential required. Full backend
continues; docs-only clarification does not require duplicate source suite.
Controller actualPG/package helpers on D: parsed clean/hashfrozen, not executed
before Task2 review; see TELEGRAM_LOGIN_VERIFICATION_20261013.md.

Task2 writerDONEf30fb73256c92cfd68f811ef611a213c399db339. Complete report read;
root six frozen hashes match, actual retained full log3186PASS/26SKIP514.98s,
SHA DB9DE9D3F2B6F75D991185A0CB112484E4EF2543A4DDD2732667791A7E476F26.
Full diffbb30b96..f30fb73 onecommit48819bytes; fresh read-only scoped
/root/telegram_login_cli_review,gpt-6.1-sol/high/forknone/nohelpers active.
Root actual11PG/package wait for clean spec+quality; no unchanged-suite replay.
Doc append initially targeted an absent context twice, no file changed; corrected
to actual ledger ending. This was controller bookkeeping, not product/test failure.

Task2 fresh review speccompliant/qualityApproved/no Critical/Important findings;
verbatim task-2-review.md retained. ActualPG/package/push/exactCI are explicitly
controller gates executed next; human login/restart/rights remain external.
Task 2: minor (deferred): test_telegram_login_cli.py:299 subprocess guard injects
machine-specific D:/.../telethon-145 path; remove hidden dev-install selection.
Final whole-branch reviewer must triage; not silently discarded or a new fixloop.
Task 2: complete (commits bb30b96..f30fb73, source review clean, one deferred Minor).
NEXTcontroller: actual strict11migratedPG then immutable package network-none
smoke; no repeating153/3186suite and no live login/send/key discovery.

Root actual runtime f30fb73:11PG PASS7.02s/noSKIP/no warnings/native0;2010old
namespaces retained, first11cases2021 then correctedJUnitreport11cases2032,
public/sourceunchanged. Initial controller readonlySQL char-concat preflight
native1 fixed by explicittextcasts before tests; initial11JUnitxunit2 warnings
fixed by supportedlegacyreportfamily/newpaths, no source/test suppression.
Actual cleanJUnit11namespaceproperties and nine current source hashes matched.
Immutable packageimagece3d1ab80090.../141inputs native0; four actual network-none/
readonly/no-volume/no-credential CLIcases correct2/0/1/1 statuses/privatevalue
absent. Actual packagedPython3.12.15/Telethon1.45.0/SQLAlchemy2.1.4 native0.
See TELEGRAM_LOGIN_VERIFICATION_20261013.md for full IDs/hashes/failures/native
receipts. Root docs/authorizedpush/exactCI and final review next; live gatepending.

Root evidence6bc5adc255be3ab446568e80ddfb83ff7d69a331 pushnative0/exactremote.
ExactCI38326431585 in progress; predecessor CI not reused as current proof.
Generated raw review.diff had literal diff-context trailing whitespace when
staged; unstaged only that raw scratch artifact, preserved bytes unchanged,
remaining staged diffcheck0/commit0. No product/source/test change.
Final cross-task login review /root/telegram_login_integration_review,
gpt-6-astra/high/forknone/nohelpers: Approved/no Critical/Important, no reruns or
mutations; complete frozen179497byte d7c580a..6bc5adc package plus unchanged
integration dependencies read. Verbatim final-integration-review.md retained.
Final triage: machine-specific test path nonblocking, retained for whole-PHASE
triage; stale current-status/intermediate checkpoint prose Minor corrected by
controller documentation-only update. No fix wave/source change required.
Login increment integrated-source accepted; human/live, exactCI and historical
whole-PHASE branch gates remain separate. NEXT exactCI evidence, then approved
engagement observations/HypeScore work without revising accepted architecture.
ExactCI38326431585/6bc5adc completedSUCCESS/all10SUCCESS; actual ten raw logs
native0 downloaded/read, Windows83JUnit0SKIP/82entrypoint112native receipts,
new24case benchmark0calls/unqualified independently parsed. Backend3103/
109SKIP744.64s,PG842/3SKIP550.02s+5locks6.12s,frontend334/33+1+3 and full
recovery families PASS. See TELEGRAM_LOGIN_CI_20261013.md. Source/runtime/CI
login increment accepted, not human/live/PHASEwholebranch or STABLE approval.
