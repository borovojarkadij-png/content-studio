# SDD ledger — plan: docs/BACKUP_OUTPUT_CAP_IMPLEMENTATION.md

Spec: docs/BACKUP_OUTPUT_CAP_DESIGN_20261013.md, fully read/self-reviewed.
Prepared only. No source writer dispatched while sampling Task3 full/source
acceptance is active. Current source SHA427E7A147A8B1062C5EBEA3CBB49D44FF95A597509554E2324794F4BE27BF40F.
Root actual-helper causal resource RED: capacity2,097,152 >1,048,576; oversized
output rejected, native1, zero child/Docker/network/credential/data mutation.
Original evidence retained in D:/Codex-Recovery/content-studio-20261008/backup-output-cap-20261013a/.

## Preflight shared-interface and self-consistency scan

| Tasks/interfaces | Produced and consumed contract | Finding |
| --- | --- | --- |
| 1 / existing backup and restore callers | Same Get-BackupNativeText arguments, strict text return/private exception | No entrypoint signature/format/caller edit needed |
| 1 / existing Invoke-BackupNative | Non-expandable output Stream, existing finite timeout and owned-child kill | Overflow can fault drain before child exit; retain timeout rather than promise instant termination |
| 1 / own regression module | Real helper resource assertion plus native shim entrypoint refusal | Boundary replacement only in isolated PowerShell test; native test separately proves private caller failure/no downstream writes |
| 1 / own file list | Two files and own report, exact-limit/Unicode/overflow/privacy/lifecycle cases | No dependency/CI/migration/frontend edits; complete83existing contracts retained |

Ruling: use a single narrow correction under the user's autonomous bug-fix
authority, without requesting intermediate design approval — confirmed deferred
resource defect, no operational side effect or architecture change; cost if
wrong: isolated two-file fix can be revised without modifying user data.
Ruling: destination capacity, not whole-process RSS or immediate cancellation,
is the bound — fixed .NET pipe/task buffers and existing finite lifecycle are
outside this narrow defect; cost if wrong: overflow may wait for the existing
deadline, not unbounded memory or real data writes.
Ruling: retain this plan's scratch/evidence through ongoing PHASE, rather than
delete on local completion — human requires resumable state/reports; cost: small
scratch/docs storage. No production data or volume cleanup authorized.

Spec coverage/self-review: causal resource RED, bounded destination, exactlimit,
UTF8valid/invalid, public privacy, native refusal/no later operations, timeout/
ownedchild, old contracts, static checks, immutable scoped review and root probe
all mapped to Task1. Placeholder scan has no matches. Same existing PowerShell
signatures throughout. No source changes during current sampling full run.

NEXT: complete sampling source/runtime/integration acceptance; freeze BASE,
dispatch Task1 sole fresh standard implementer with own17line brief/report.
