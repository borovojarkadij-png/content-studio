# Telegram first-login verification checkpoint — 2026-10-13

Scope: Telegram-only Content Studio, origin
`https://github.com/borovojarkadij-png/content-studio.git`,
branch `codex/dark-navy-ui`. Accepted dark-navy frontend unchanged.

## Reviewed producer contract

Task1 source `bb30b9642ad156689b72bbf98860c3be024aa53f` adds a separate bounded
Telethon authorization adapter and atomic encrypted-session producer. Existing
read-only provider, workers, account API and schema are unchanged. The producer
does not enable polling or publication, replace an existing session, generate a
master key, or mark a newly provisioned account HEALTHY.

Reported actual focused100PASS and covering160PASS used Telethon1.45.0, actual
SQLAlchemy/SQLite/cipher and independent provider reopen with fake Telegram RPC.
Source/three-module frozen hashes and complete report were checked by controller.
Fresh independent task review: spec compliant, task quality Approved, no findings.
Source missing-provisioning, abort and child-SDK-logger privacy failures were
retained separately from corrected test-fixture failures. No duplicated suite
execution was requested solely for review.

This is not PostgreSQL concurrency, packaged CLI, human login or live encrypted
restart acceptance. Those conclusions cannot be inferred from SQLite/fake RPC.

## Task2 and controller gates

Historical Task2 checkpoint (superseded by completed source/runtime below):
Task2 was in progress under `TELEGRAM_LOGIN_IMPLEMENTATION.md`: default-disabled
interactive CLI, masked prompts, explicit configured/migrated PostgreSQL checks,
private errors, migrated create-only PostgreSQL regressions and operator guide.
It must preserve REJECTfalse/zero-rewrite invariants, all existing CI checks and
the separate Windows backup job. Combined full backend is run once after this
source increment, not repeatedly for unchanged Task1.

Interim focused CLI/core/PG collection:153PASS/11PG-onlySKIP without the explicit
synthetic URL. No migrated PostgreSQL proof is claimed from this result. Writer
corrected a terminal/capture test-fixture setup error before these results;
static/full/self-review/frozen source review remain in progress.

Task2 source now committed `f30fb73256c92cfd68f811ef611a213c399db339`, only five
implementation/test/doc/workflow paths plus its report. Actual final static
Ruff0.17/format3/compile/YAML exactappend native0, one full backend3186PASS/
26PG-onlySKIP514.98s/native0. Controller read complete retained output and matched
all six frozen owned hashes. Full log SHA256
`DB9DE9D3F2B6F75D991185A0CB112484E4EF2543A4DDD2732667791A7E476F26`.
At that earlier checkpoint, fresh independent Task2 spec+quality review was in
progress. No new actualPG or
container gate claimed before review; no same-source full suite rerun.

Controller actual Windows PostgreSQL/package gates now PASS on reviewed
`f30fb73256c92cfd68f811ef611a213c399db339`; details below. Real human
authorization/restart remains pending, not inferred from these synthetic gates.

Prepared controller-only helpers in
`D:/Codex-Recovery/content-studio-20261008/telegram-login-acceptance-20261013a/`:

- `verify-postgres.ps1`, parser PASS, SHA256
  `46730DD56BE3543799B428F52478D61B9583A03E12B2D3DB42BF05910FC114AF`.
  Checks exact source/container/ownership/sole volume/loopback binding, create-only
  namespace growth, unchanged public relations/input hashes, actual no-skip JUnit.
- `verify-package.ps1`, parser PASS, SHA256
  `A6969C415328EC26D5F3AE9CA1D14831369FDA664065EA1879AF0F22DBCE88BE`.
  Builds reviewed source with immutable revision/owner labels, then actual
  default/help/malformed/enabled-nonTTY CLI cases with network none, read-only
  root, no volumes/secrets and private fixed status. Failed commands must have
  nonzero exit; only default2/help0 are contract-specific exact exit values.

Parser acceptance is not execution acceptance. Helpers refuse to overwrite
retained output and execute only after fresh clean Task2 review/source freeze.

## Actual migrated Windows PostgreSQL acceptance

Fresh Task2 review: spec compliant/task quality Approved, no blocking findings.
One test-only machine-specific SDK path Minor is retained for final whole-branch
triage in the plan ledger, not silently discarded.

Actual controller command after review:

```powershell
pwsh -NoProfile -File D:/Codex-Recovery/content-studio-20261008/telegram-login-acceptance-20261013a/verify-postgres.ps1 -ApprovedHead f30fb73256c92cfd68f811ef611a213c399db339
```

Final actual11PASS7.02s/native0, no warnings/errors/failures/skips. JUnit11/0/0/0
and all11 `synthetic_namespace` properties independently checked. Actual cases
cover migrated encrypted insert/outbox/provider reopen, six independent-writer
snapshot CAS conflicts, two identity/uniqueness races and two atomic audit
rollback paths. Every fixture retains immutable REJECTfalse and zero unrelated
jobs/usage/media/publication execution. Actual source hashes unchanged.

Initial controller preflight failed before pytest/schema creation because the
public-catalog diagnostic concatenated PostgreSQL internal `char` without an
explicit text cast. Corrected both read-only diagnostics to `::text`, retained
native1 log; no application/schema/source change. First actual execution then
passed11/native0 but reported11 JUnit xunit2/record_property warnings. Changed
the controller report format to supported `junit_family=legacy`, not warning
suppression, and reran the11 relevant cases in new UUID schemas/new output paths.
Both prior evidence sets remain intact; no source suite replay or old-schema
reuse/reset. Initial property reader looked for `schema` instead of the actual
`synthetic_namespace` attribute; corrected in-memory reader confirmed11, without
artifact mutation or another test run.

Namespace history: original2010/maxOID1560501 retained; first run adds11 to2021,
final clean-report run adds11 to2032/maxOID1578917. Both run receipts record all
new UUID identities. Original schemas remain, public relations unchanged,
same full container/namedvolume/ownership. Only synthetic schemas were created.

## Actual immutable packaged CLI acceptance

Reviewed application source built through existing backend/Dockerfile, native0.
141tracked package inputs were hashed before and after; unchanged. No dependency,
Dockerfile, UI or operational deployment modification.

- Tag `newsflow-verification-telegram-login:f30fb73256c9-20261013a`.
- Image `sha256:ce3d1ab80090d6f00841133ec11769b6229b1fd6f2611baa5126c22a89c21745`.
- Exact revision label `f30fb73256c92cfd68f811ef611a213c399db339` and owner
  `content-studio-login-package-v1` checked.
- Actual packaged Python3.12.15/Telethon1.45.0/SQLAlchemy2.1.4 inspected through
  a separate network-none/read-only version-only container, native0.

| Actual packaged CLI case | Exit | Result |
| --- | --- | --- |
| Default | 2 | exact LOGIN_DISABLED |
| Help | 0 | actual usage/enable-login help |
| Forbidden secret-bearing argument | 1 | exact LOGIN_FAILED, supplied value absent |
| Enabled invocation without terminal | 1 | exact LOGIN_FAILED |

All four run actual module in network-none/read-only containers, cap-dropALL,
no-new-privileges, no volumes or credentials. Master/credential paths deliberately
refer to nonexistent/unmounted files. No provider IO/session artifact/DB write
or real login/publication is possible through this gate. Package helper native0;
source HEAD and all141inputs remain identical. No operational container restarted.

## Retained actual evidence SHA256

Evidence root is the same D: directory above; no raw synthetic SQL/session
artifacts uploaded to Git. Full package receipt includes all141input hashes.

| Evidence | SHA256 |
| --- | --- |
| Amended `verify-postgres.ps1` | `80D508F92192B8EAADF3DBE71AE84FE6E9A4B01C4D9ACB1DC1D4BF689DA9CC0E` |
| Initial preflight failure `postgres-acceptance.log` | `4D98A35CB0CEAD97278C48B30171E12C64DC0987829E97B7A22D3BB98711A27D` |
| First actual PG/warnings `postgres-acceptance-02.log` | `A13CF8B7BE776F6C2D94B19A2CB87D949F55BF77E32821BA8A3B83E61BDAB6C4` |
| Clean PG `postgres-acceptance-xunit1.log` | `50FDE14E05E3ECAC11C778FCDA6F45ED185A28052C0A595129DAEFA6758620A2` |
| Clean PG JUnit | `D7BED463B8B3217402BBBACD19C71D2C4341F884C3B3BED7245328930C67A8E2` |
| Clean PG pytest log | `52DAEB970A0420844CC17F9E512124AC950D83A828300FB0BB74E364E99A1D42` |
| Package receipt/build/smoke log | `CA3DB19ADD20F30C57E76EC73B80C01F67BFA0359CFA5FD0D1FE97BEA526520E` |
| Image build log | `D61AED8275EC4930A5984EF18D19C04A0C9D61EA2A17F75E1F65D982A5DE0A28` |
| Packaged versions | `31C32172A4F220B96FCDFE4B082372D6C88391EB296767E024FA526254CEC4EB` |

Authorized source push/exact hosted CI and final cross-task/whole-branch review
remain pending. Earlier backup d7c580a/all10SUCCESS does not cover this login
source. Actual human authorization, encrypted live restart and test rights remain
external; PHASE1 is not complete.

## Read-only runtime preflight

Docker Desktop Engine actually responds: Linux29.8.0/API1.56; no restart/reset
needed. C:11.71GiB/D:145.44GiB free at inspection. New logs/test files go to D:;
no volume/key/media cleanup or operational deployment.

Existing strictly synthetic PostgreSQL fixture:

- Project `newsflow-verification-unattended-win-20261008a`.
- Owner `content-studio-unattended-v1`, nonce `205b74d7765f4055b1209a90de6a2935`.
- Container `4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e`, running.
- Sole PostgreSQL volume
  `newsflow-verification-unattended-win-20261008a_postgres_data`.
- Port5432 bound only to127.0.0.1.
- Ownership manifest SHA256
  `9FE53C36D8820C758D321A88F5DA33A8190BAB2188DE6F398BFA2655B61DD8F7`.
- Read-only baseline2010UUID namespaces, maximum namespace OID1560501.

Later actual contracts create new UUID namespaces only through the existing
strict helper. No public-schema reuse, drop, reset, old-fixture reseed, production
queue changes, or real Telegram credentials. Root will record exact source/image
and namespace growth before claiming that gate.

## Current integrated-source and CI status

Evidence commit `6bc5adc255be3ab446568e80ddfb83ff7d69a331` was pushed with
native exit0 and independently matched to the authorized remote branch.
Exact CI run38326431585 completedSUCCESS/all10SUCCESS, not inherited from
predecessor CI; actual logs/artifacts verified in TELEGRAM_LOGIN_CI_20261013.md.
Fresh final cross-task review of the complete `d7c580a..6bc5adc` package:
Approved, no Critical/Important findings. Nonblocking machine-specific test
import path remains explicitly deferred; stale intermediate status prose is
now labeled historical. This is not the final historical PHASE branch review.

## Remaining external boundaries

Actual Telegram code/2FA/CAPTCHA is human-only; successful encrypted live-session
restart remains pending. Existing blocked AI credential selection is not retried;
no key discovery, new credentials or real model qualification. Consolidated
external actions remain in `EDITORIAL_LIVE_ACCEPTANCE_20261012.md`. Disabled
heartbeat stays disabled; no real channel sends or PHASE1 completion claim.
