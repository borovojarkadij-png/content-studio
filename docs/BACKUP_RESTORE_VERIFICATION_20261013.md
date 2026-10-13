# Windows PostgreSQL backup/restore verification — 2026-10-13

## Scope and result

PASS for the reviewed PostgreSQL-only create-only copy workflow on actual
Windows Docker Desktop, not whole-application backup, production recovery,
live Telegram authorization or release acceptance.

Branch: `codex/dark-navy-ui`; origin:
`https://github.com/borovojarkadij-png/content-studio.git`.
Reviewed source/report HEAD: `6b96be1f3e994490a9f633b24c0f571c8b3861e0`.
Source commits: `7861c4a` and `e547e71`; reports: `ad06bf0`, `6b96be1`.
Fresh initial review found an Important early-stdin-close defect; the original
writer reproduced it and fixed it. Fresh scoped re-review passed both spec
and quality, with no new breakage. Verbatim reviews and writer commands are
retained in this plan's `.superpowers/sdd/BACKUP_RESTORE_IMPLEMENTATION/`.

## Actual source and adversarial checks

Original scripts incorrectly returned success for native exit23; two causal
RED failures retained. Original guarded source: 77 Windows native contracts
passed. The amendment reproduced valid `pg_restore --list` consuming only a
prefix of a large archive: two causal RED failures. The bounded helper now
accepts only recognized closed-pipe errors after native exit0, only for archive
listing; restore remains strict. Six focused cases passed, then all 83 covering
Windows contracts passed in 33.77s, no SKIP, native0. Ruff0.17, format, Python
compilation, three PowerShell parsers and diff validation passed. Native shim
receipts, prefix bytes and owned-child timeout termination were independently
inspected; the controller did not repeat this same suite.

Deferred Minor: accepted text output is limited after collecting into a
MemoryStream, not with an allocation cap. This remains in the review ledger
for final whole-branch triage; it is not silently dropped.

## Actual Docker Desktop copy drill

Engine29.8.0/Linux/API1.56 responded; a healthy engine was not reset/restarted.
Ownership manifest, exact full IDs, project/service labels, image digest,
named volume, no host PostgreSQL port, no worker and three separately mounted
public synthetic secret hashes were checked before database mutation.

- Project: `newsflow-verification-editorial-win-20261013a`.
- PostgreSQL ID: `2ad14cabdc57f56cfa4281b4a1609a777658c30e960b872ee243106630588341`.
- API ID: `c2e5fe251fe1f25bd30eadb903ceadfaae5aa4263776e8cda8bfe66daccc45ae`.
- Backend image: `sha256:164171b35d2b8f19e21051cc0ab9015619f7f9a44ed2fe3253458957ce5f914e`.
- Source database: `newsflow_editorial_ci`; role: `newsflow_fixture`.
- New restored copy: `newsflow_restored_20261013a` (absence verified first).

The owned source initially had zero Telegram accounts, two synthetic outbox
rows, one REJECT/rewrite_allowed=false and six execution tables empty. The
controller created one DISCONNECTED synthetic account with an intentionally
non-Telegram four-MiB plaintext encrypted by the existing external public
synthetic master key. This makes a nontrivial 4,412,729-byte archive and exercises
the actual early-closing PostgreSQL16 archive-list consumer; no real session,
login, provider, worker or publication was involved.

Command (controller-only guarded helper outside product source):

```powershell
pwsh -NoProfile -File D:/Codex-Recovery/content-studio-20261008/newsflow-verification-editorial-win-20261013a/verify-backup-restore.ps1 -ApprovedHead 6b96be1f3e994490a9f633b24c0f571c8b3861e0
```

Actual terminal/native statuses: every inspected native step0; `BACKUP_OK`;
`RESTORE_OK: new database copy created.`; restored ciphertext decrypt0;
`No new upgrade operations detected.`/Alembic drift0; controller exit0.
The actual product entrypoints, not a substitute implementation, created
`database.dump`/strict version1 manifest and the new database.

Canonical SQL snapshots from the original and new copy matched byte-for-byte:
policy, two outbox rows, REJECT decision, synthetic account and exact ciphertext,
all six execution counts0. The restored ciphertext was independently decrypted
inside the pinned API image using the original separately mounted key. Source
after restore matched pre-backup state; three secret files and original
containers/volume remained unchanged/running. All evidence, archive, source
account and new copy are retained; no drop, clean, volume deletion or cutover.

## Evidence integrity

Evidence root:
`D:/Codex-Recovery/content-studio-20261008/newsflow-verification-editorial-win-20261013a/backup-restore-20261013a/`.

| Artifact | SHA256 |
| --- | --- |
| `bundle/database.dump` | `3094c46ece49e363a0e78d96c8e83754cc4153462cd011470337b2f3106ef4dc` |
| `acceptance.log` | `41ECC30E4C8652522654F29B939A390627DC1FF52309C093DAAC400038773688` |
| `source.json` and `restored.json` | `B2AEBDE7A6C38FA2D85813DBD90E53DA2F70AB941C2DD3FD9733C65602E23A1D` |
| `result.json` | `23E9E30F1F614C03489F2FF992241138A365F9E3EEC07E4F76D596A87560CE9B` |

Snapshots/archive contain only synthetic data; private evidence is not uploaded
as general workspace material. SHA confirms consistency, not archive
authenticity or permission to restore untrusted SQL.

## Remaining gates

New independent Windows hosted native-contract job passed83/0SKIP59.56s with
actual downloaded JUnit/native receipts on d7c580a; whole exact workflow now
completedSUCCESS/all10SUCCESS with actual logs/new artifacts independently
checked in BACKUP_RESTORE_CI_20261013.md. Previous cf38929 all-nine PASS does
not cover these scripts. Separate media/keys/full-app backup and operational cutover need
their own explicit procedure and proof. Real Telegram login/session restart,
test-output authorization and actual model benchmark/qualification remain
external gates. No synthetic result grants real autoapproval. PHASE1 remains
in progress; accepted UI and operational data were not changed.
