# Backup text destination capacity — verification

Source `21d24d3fb39b40654c5f78cef80e4df600bfcbcd`, branch
`codex/dark-navy-ui`, origin `borovojarkadij-png/content-studio`.

## Outcome and scope

The real PowerShell helper now allocates a non-expandable 1,048,576-byte
destination before native output is read, initially length zero. Strict UTF-8,
existing final size guard, native lifecycle and private errors are unchanged.
Only the helper and Windows contract module changed, plus the writer report.
This closes the previously confirmed allocation defect, not whole-process RSS,
instant overflow cancellation or full-application backup coverage.

## Actual checks

| Check | Actual result |
| --- | --- |
| Committed regression before fix | Causal FAIL: rejected output but capacity2,097,152 exceeded1,048,576; native1 |
| Focused helper/native boundary contracts | 14PASS,83deselected,10.10s, native0 |
| Complete Windows PS7 contract module | 97PASS,0SKIP,44.35s, native0; JUnit97/0FAIL/0ERROR/0SKIP |
| Ruff0.17, formatting, compile, three PowerShell parsers, diff check | Native0 |
| Fresh scoped independent review | Spec compliant; quality Approved; no Critical/Important/Minor |
| Root original unchanged resource probe | PASS/native0; peak1,048,576; overflow rejected; source unchanged; child/Docker calls0 |
| Final increment review | Spec compliant; quality Approved; no Critical/Important/Minor; all text callers/lifecycle/receipts inspected |
| Exact newer GitHub Windows97 contract generation | Pending; earlier sampling generation Windows83 is not this gate |

Tests exercise empty/exact-limit ASCII/exact-limit multibyte/malformed UTF-8,
one-byte and chunked overflow. Actual synthetic native backup/restore entrypoints
reject oversized inspect/version text before any pg_dump/createdb/pg_restore.
Blocked writers terminate within the existing deadline, only the owned child is
stopped, an unrelated process survives, and original sentinel/destination
absence remain unchanged. No operational Docker, database, provider or key call.

The retained intermediate focused failure was Windows'32,767-character
environment limit from huge pytest parameter IDs, not suppressed assertions:
short explicit IDs fixed setup/teardown and all cases were rerun successfully.

## Evidence identity

Writer evidence:
`D:/Codex-Recovery/content-studio-20261008/backup-output-cap-task1-20261013a/`.
Root original probe:
`D:/Codex-Recovery/content-studio-20261008/backup-output-cap-20261013a/`.

| File | SHA256 |
| --- | --- |
| scripts/postgres-backup-common.ps1 | 2C79B0BC2AE32D10D2E8E6B4981FF6483D2BD5328AD9758DEF51CA9F646EB9C3 |
| backend/tests/test_windows_backup_restore.py | 426297CB861524235AC660E72ED232844224402ACD47094DFF636087B4944C99 |
| 04-full.log | E12D9FF9B8255B5ADB1D9393BCCE3EB6BAD145AC83538A67CDB45CC2068AB183 |
| 04-full.xml | 8DFED93468DA256E0E95C4868C2EE22A34392F1CAF3865D0E0CDAC81DD852875 |
| probe-backup-text-cap.ps1 | C471C666D0BA604527B1940A8F340EA94375F1EF70AB1E8AF321809984FB4E65 |
| 02-resource-cap-green.log | 49C5D18C2B905DC84004CAC886B17647AA6C30186D904E4F3F78250C3B7D6700 |

## Limits and next step

REJECT→rewrite_allowed=false→no new RewriteJob→rewrite calls0 is unchanged;
this fix grants no editorial/publication authority. Accepted UI and real data
are unchanged. No repeated full backend, actual Docker backup or live test was
needed. Finish final increment review, checkpoint and guarded push to the same
branch, then inspect actual exact-generation Windows97 and all existing checks.
PHASE1 and live Telegram/model qualification remain incomplete.
