# SDD ledger — plan: docs/BACKUP_RESTORE_IMPLEMENTATION.md

BASEcf3892987f78b36856996b92fe6eb06a44bce540, exactauthorizedbranch/origin,
no current sourcewriter. Root read entire spec/plan and skills/references.

| Preflight | Producer/consumer boundary | Result |
| --- | --- | --- |
| Task1 internal | Backup native bytes -> bundle | New files only, exit and archive validation before manifest; no PS encoding |
| Task1 internal | Manifest/hash -> restore | Strict version/source/size/hash/archive provenance, trusted private own backup only |
| Task1 internal | Exact target -> DB creation | Full inspected owned ID/project/service/role/source; new target DB only, no overwrite/drop |
| Task1 internal | Helper -> entrypoints | Shared bounds/private errors/binary streams; no business/API/Compose changes |
| Task1 internal | Fake child -> regressions | Real pwsh/native shim/argv/files/exit; original behavioral failure, no fake missing-interface RED |
| Task1 internal | Source tests -> runtime claim | Only contract until rootactual owned Docker copy/SQL/drift gate afterreview |
| Task pairs | Sole Task1 -> root acceptance | One sourcewriter, root only docs/CI/new isolated DB afterreview |

Ruling: implement approved backup/restore as create-only new database recovery,
not destructive in-place restore — user scope authorizes backup/restore, but no
irreversible production action — cost if wrong: users require separately
reviewed cutover procedure; original data is preserved.
Ruling: PowerShell7 for binary-safe .NET ArgumentList/streams — installed
runtime/test harness supports it; WindowsPS5.1 text pipelines are unsafe for
binary archives — cost if wrong: documented PowerShell7 prerequisite, no new
application dependency or silent corrupt backup.
Ruling: include this independent originally requested workflow after operator
gate — existing scripts visibly lack native checks/target/path safeguards,
release policy names restore proof — cost if wrong: scoped script/docs rework,
no architecture/UI/provider change. No midtask human confirmation needed.

Task1 brief68lines, sourcewriter not yet dispatched; root owns full Docker
copy acceptance and final exact CI. Previouscf38929 pushnative0/exactref,
CI38321414003 queued/inprogress, no success inferred.

Task1 active solewriter /root/windows_backup_restore, BASEcf3892987f78,
gpt-6.1-sol/high/forknone/nohelpers; no duplicate dispatch after compaction.
Reported current57 native-shim contracts PASS20.78s, final freeze/report pending.
Original behavioralRED2FAIL0.80s/native0 falsely returned by old scripts is
retained. Writer moved its exact empty backend/backups/newsflow.sql (SHA256
E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855)
to D:/Codex-Recovery/content-studio-20261008/backup-restore-task1-20261013-red/
legacy-dot-source-newsflow.sql; no file deletion. Child cwd now unique tmp.
PowerShell parser/duplicate Get-Command candidates diagnosed/fixed by writer;
root source review and actual Docker copy acceptance remain pending.

Task1 writerDONE7861c4ae71a2ddaec40b8f76ec98453e57d0e037 + reportad06bf0;
root read complete report including final77PASS28.93s/native0/noSKIP and all
development failures. All five working-file SHA256 match frozen report. Actual
retained native entrypoint receipt files75 plus separate dot-source cases, not
invented77 native executions. Review packagecf38929..ad06bf0 has2commits/69067bytes.
Fresh scoped /root/windows_backup_restore_review,gpt-6.1-sol/high/forknone,
nohelpers/read-only, spec+quality review active. Root acceptance helper parsed
clean; not executed before review. Engine29.8/Linux healthy; no restart/reset.

Current predecessor exactcf38929 CI38321414003 completedSUCCESS/all9SUCCESS;
root actual backend2950/15SKIP, PG831/3nonapplicableSKIP+5, frontend334/33+1+3,
all recovery native logs and actual new benchmark24matches/0calls/unqualified
inspected. See EDITORIAL_CI_ACCEPTANCE_20261013.md. Does not cover Task1 source.

Task2 added as separate hosted Windows regression consumer, not dispatched
before Task1 review/runtime acceptance. Root full spec/plan addition self-reviewed.

| Additional preflight | Producer/consumer boundary | Result |
| --- | --- | --- |
| Task1/Task2 | Windows contracts -> hosted job | Same actual scripts/shim, no production test changes, required prerequisites/atleastoneexecuted check |
| Task1/Task2 | Operator docs -> continuous verification section | Task2 appends CI scope, not rewriting Task1 recovery trust contract |
| Task2 internal | Native pytest -> JUnit/artifact | Immediate native exit retained; all-SKIP not PASS; always synthetic-only evidence |
| Task2 internal | New Windows job -> existing workflow | Existing nine jobs/triggers/permissions unchanged, no secrets/real daemon |
| Task2/root | Source review -> exact hosted CI | No local result presented as hosted PASS; authorized root push and exact job tracking |

Ruling: add isolated Windows contract CI job after paired-script runtime proof
because Ubuntu's explicit module SKIP cannot prevent future Windows regressions —
cost if wrong: one bounded extra hosted job and scoped workflow/docs rework;
no production activation, credentials, architecture or existing gate weakening.

Task1 fix round1/5 starts, FIX_BASEad06bf0a278f3b9a1b54daf0c000eb44a627f9b5.
Fresh review specFAIL/qualityNeedsFixes: one Important real archive-list consumer
early stdin closure falsely fails; causal actual helper16MiB native prefix0 proof.
Verbatim review task-1-review.md. Originalwriter owns minimal fix/causalRED/
covering77file retest/reportappend/refreeze/ownedcommit then scoped re-review.
Root actual Docker acceptance withheld until clean source review.
Task1: minor (deferred): common.ps1:87–92 checks accepted native text<=1MiB
after unrestricted MemoryStream collection, not an allocation cap. Final
whole-branch reviewer must triage; not silently discarded or an expanded fixloop.

Task1 fix1 writerDONEe547e711fda45c1b95f74049cd5486c507d557e1/report6b96be1;
root complete fixappend read. CausalRED2FAIL/81deselected/native1; focused6PASS/
77deselected5.04s, covering83PASS33.77s/noSKIP/native0/staticnative0. Newfive
frozenhashes matched; retained nativeprefix/entrypoint receipts inspected.
Complete ad06bf0..6b96be1 scopedpackage2commits/24359bytes. Fresh independent
/root/windows_backup_restore_fix1_review,gpt-6.1-sol/high/forknone/nohelpers
active. No actual Docker copy before clean verdict; no duplicate fullsuite.

Task 1: fix round 1/5 (1 addressed, 0 open; commits ad06bf0..6b96be1).
Fresh windows_backup_restore_fix1_review specPASS/qualityPASS/no new breakage;
verbatim task-1-fix1-review.md. Deferred Minor remains for final review.
Source acceptance complete; root actual owned create-only Docker copy follows.

Task 1: complete (commits cf38929..6b96be1, review clean; Minor deferred).
Root actual Windows Docker entrypoints/newDBcopy/4.4MiB archive/exact SQL/cipher
decrypt/drift/sourceunchanged/externalkeyhashes/native0 PASS; report
docs/BACKUP_RESTORE_VERIFICATION_20261013.md. No original data replaced or live IO.
Task2 BASE6b96be1f3e994490a9f633b24c0f571c8b3861e0; brief43lines read.
Sole writer /root/windows_backup_contract_ci,gpt-6.1-sol/high/forknone/nohelpers
active; existing nine jobs unchanged, root source review/actual hosted CI follows.

Ruling: workflow currently has eight definitions and nine executions because
docker-persistence is a two-provider matrix; Task2 preserves every existing
definition byte-for-byte and adds one independent Windows execution — brief's
nine refers to executions — cost if wrong: documented CI-count wording only,
no removed check or widened source scope.

Task2 writerDONE81920abdda0068d3a94068cc2294ab77fbc2f5d2/report65c85d284cd0b3e197c0ce19dd6de8d624839694.
Root complete report read; actual retained JUnit83/0fail/0error/0skip and82
native entrypoint receipts checked; six frozen hashes match. Added consumer
83PASS34.08s/native0, allSKIP XML negativeexit1, no suite replay. Full package
6b96be1..65c85d2 contains2commits/21364bytes. Fresh independent scoped
/root/windows_backup_contract_ci_review,gpt-6.1-sol/high/forknone/nohelpers,
read-only active. Actual hosted job not yet run.

Task2 fresh speccompliant/qualityApproved/no findings; verbatim task-2-review.md.
Controller resolved current origin/branch and actual Windows recovery/REJECT
cross-task items through recorded exact owned Docker gate; hosted dependency/
exact CI remains explicitly pending. Root evidence commit and authorized push
follow; no predecessor CI presented as current source acceptance.

Task 2: complete (commits 6b96be1..65c85d2, review clean).
Root authorized d7c580a pushnative0/exactref; exactCI38323820316 started10jobs.
Actual Windows115057791858 SUCCESS, hosted pip/83PASS59.56s/0SKIP, downloaded
artifact11779563916/native0/JUnit+82uniqueentrypoint+112native receipts checked.
Uploader materialized24pytestcurrentaliases;17pairedreceipts SHAequaloriginals;
not extra executions. Reader diagnostics corrected, source/tests/artifact intact.
See BACKUP_RESTORE_CI_20261013.md; whole workflow still INPROGRESS, no release
claim. Deferred Minor remains for final whole-branch triage.

Exactd7c580a CI38323820316 terminalCOMPLETED SUCCESS/all10SUCCESS. Root downloaded
every new job rawlognative0/read actual results:backend2950/98SKIP940.30s,
PG831/3nonapplicableSKIP+5,frontend334/33+1+3,allsyntheticrecoveryfamilies0IO.
New artifact11779958155 independently JSONasserted24matched/0mismatch/calls0/
allpermissionsfalse/unqualified. Windows83/0SKIP artifact already accepted.
Report BACKUP_RESTORE_CI_20261013.md updated; no older/newer source substitution,
no rerun/disabledcheck/realprovider/operationaldata changes.
