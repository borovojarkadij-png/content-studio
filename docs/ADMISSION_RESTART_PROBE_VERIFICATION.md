# Create-only guarded admission restart acceptance

2026-10-08; branch `codex/dark-navy-ui`; parent
`bdb66a9f4dda8afb360915ed7503ce0be61dd7e8`; correct origin
`borovojarkadij-png/content-studio`.

## Isolated fixture and contract

`scripts/docker_admission_probe.py` creates a version-1 fixture once: independent
synthetic account/encrypted non-session marker, donor, three outputs, original
source revisions, explicit source-photo mapping rights and synthetic verifier
release. 101 original sources each have three neutral historical drafts. Only
after retaining those drafts, 100 sources are rejected; old history is not erased
to falsify a zero-rewrite claim. This creates no operational model qualification.

Seven bounded windows per mode reach the late current source despite the 100
earlier rejects. Exactly one semantic job, one licensed-library job and one
original-photo job are retained QUEUED with attempts=0, no claims/assets/evidence.
The probe never executes a job or constructs a real provider. No rewrite,
classification, download, login, automatic approval or publication occurs.

Immutable manifest stores original SQL row vectors and ciphertext digest.
Separate create-only job manifest stores exact cross-table job identities; bool
IDs are invalid even though Python treats True==1. Independent read verification
checks original jobs/attempt budgets, exact binding modes/late IDs, encrypted
marker, historical rejection truth and absence of usage/evidence/assets. Repeated
pure admission is SQL-idempotent; CLI seed refuses existing files or SQL history,
and the job manifest is never overwritten. Corruption is an error, never empty
defaults followed by destructive reseeding.

CLI requires explicit probe opt-in, exact `newsflow_verification` PostgreSQL DB,
all seven network flags 0, supported mode and the separately mounted public
synthetic key, checked before database connection. Operational secrets/data are
not read into tests, regenerated or replaced. This proves only synthetic state,
not a real Telegram authorization.

## Actual offline evidence

- Missing probe RED -> GREEN; bool identity acceptance independently reproduced
  RED -> GREEN. 11 dedicated / **56 combined** admission/fairness regressions PASS.
- **Full backend 1068 PASS (82526)**, 94.80 seconds, D: temporary/cache outputs.
- Expanded exact CI Ruff, changed format and D: compile PASS.
- Explicit fresh D: migration upgrade/check/downgrade/base/re-upgrade/check PASS.
- PowerShell parser PASS; actual mixed-family and operational-project refusal
  before file/Docker operations PASS. Workflow YAML parsed with new job present.
- 351b137 CI 37757293108 and e46ee47 CI 37757580448 completed SUCCESS in all five
  jobs (actual gh list); bdb66a9 CI 37758555880 backend/frontend/dedicated sync
  SUCCESS, legacy Docker variants still in progress at inspection.

## New PostgreSQL/Compose procedure (execution pending)

Use a NEW isolated project, never an existing retained fixture:

```powershell
./scripts/verify-persistence.ps1 -Project newsflow-verification-admission-local `
  -CrashRecovery -AdmissionGuard
```

The existing foundation gate builds/migrates/dev+production/health/DNS/Redis/DB
storage first. This separate family then performs seed -> down/up -> original
pending verification -> bounded admission -> Redis/worker restart -> exact queued
verification -> down/up -> verification -> PostgreSQL SIGKILL/recovery -> exact
verification. No `down --volumes`, pruning, resync reset or operational activation.
AdmissionGuard refuses combination with other recovery families, especially
sticky global synchronization quarantine; no old fixtures are reset.

New dedicated Linux CI job `Synthetic guarded admission PostgreSQL restart` runs
that procedure. Actual execution remains pending the exact corrective commit.
Current Windows Docker is **NOT VERIFIED / BLOCKED BY ENVIRONMENT**; ~0.50 GB free
does not prove healthy storage/daemon. Linux success will not relabel Windows.

## Next

Inspect exact new CI, repair ordinary failures, and retain evidence by exact SHA.
Then add read-only per-draft semantic verification diagnostics to the real
Planner (jobs/budgets/manual/qualification/guard state), with strict API/UI DTO,
refresh/cancellation/DEMO separation and real isolated browser verification.
Do not add a classify/retry/qualify/send action or activate network flags.
