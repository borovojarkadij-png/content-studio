# Owned illustration restart acceptance

The separate test-only launcher creates a retained synthetic Compose project. It
uses the packaged API and migrated PostgreSQL, persisted media/PostgreSQL volumes,
and two separate public deterministic fixture credentials. Reviewer credentials
are mounted only in API. Every network/provider worker flag is `0`. PostgreSQL
has no published host port. Existing sync, admission and unattended fixtures are
independent and must remain untouched.

Run from the repository on the authorized `codex/dark-navy-ui` branch:

```powershell
pwsh -NoProfile -File scripts/verify-illustration.ps1 -Mode preflight -Project newsflow-verification-illustration-win-20261009a
pwsh -NoProfile -File scripts/verify-illustration.ps1 -Project newsflow-verification-illustration-win-20261009a -ApiPort 18237 -WebPort 15394 -ProductionPort 18337
pwsh -NoProfile -File scripts/verify-illustration.ps1 -Mode verify -Project newsflow-verification-illustration-win-20261009a
```

The launcher repeats absence checks before any fixture writes. Ownership, exact
resolved config, complete database URL, disabled flags, ports, mounted files and
immutable image/mount/environment inventory are checked before every operation.
Both labeled resources and exact unlabeled names are refused. Existing ownership,
files, keys, rows and manifests are never overwritten or reseeded.

Before any fixture file or Docker command, conflicting inherited Compose,
database, credentials, ports or worker overrides are refused without changing
the operator's environment. Exact matching public fixture values are accepted;
alternate Compose files/profiles are refused. The two checked-in Compose source
files are pinned by normalized UTF-8 SHA-256 so redirected image/build/context,
Dockerfile or reviewer mounts cannot reach creation. Intentional Compose changes
require reviewed digest updates in this separate controller. Successful bounded
scoped Docker stderr is emitted to the transcript, including warnings.
Backend/frontend directories, their Dockerfiles and the bound standalone probe
must be existing physical checkout paths with no symlink/junction/reparse ancestor.
This check repeats before retained operations, not only initial creation.

Before down, crash or retained up, every original image ID must still exist and
every original Compose image/build tag must resolve to that exact ID. Retained
startup passes an in-memory Compose override containing only those recorded IDs,
with `--no-build --pull never`. Missing images or changed tag resolution refuse
before the operation; there is no build/pull recovery or manifest overwrite.

The first packaged HTTP flow proves bearer authentication, canonical presentation,
validator-bound bounded photo, review and audit persistence. It creates four
immutable encrypted publication snapshots. Revocation happens through HTTP;
stale draft and abandoned SENDING are isolated synthetic mutations. Fresh worker
processes reopen original IDs before and after down/up and an actual PostgreSQL
crash using the existing exact-container-ID exit-barrier helper. The configured
photo publisher receives a synthetic injected Telethon client. It records one
exact durable fake receipt; revoked/stale jobs are blocked and abandoned SENDING
is quarantined. No real client is initialized, no rewrite/provider call occurs,
and the additional rejected ingestion creates no rewrite job.

After publication, the approved candidate is PUBLISHED and current presentation
correctly returns 409; the original canonical binding, immutable review/audit,
encrypted snapshot, encrypted observation and exact original photo remain
readable and verified through SQL/storage reopen. Read-only `verify` executes
twice and issues no admission, fake transport or mutations.

Artifacts remain in `.artifacts/docker-verification/<exact-project>/`. The
create-only `runtime.json` records immutable image IDs, mounts and environment.
The media volume retains `illustration-original.json`,
`illustration-invalidated.json` and `illustration-result.json` with original row
identities and hashes. Preserve failed and partial resources and inspect them;
missing manifests are an explicit failure, never an instruction to recreate data.
The controller prints bounded policy failures without raw configuration values.
Docker Desktop may report an exact Windows drive bind using
`/run/desktop/mnt/host/<drive>/...` after recreation. The controller compares both
inventories using only that exact alias for its known owned bind sources and a
deterministic mount order. It retains every mount/image/environment field and
the original manifest bytes. Foreign drives, traversal, near misses, changed
permissions, destinations and mount types remain refusals. A bounded reason
code distinguishes environment, source graph, bind source and runtime mismatch
failures without exposing exception values.

The separate CI job runs Linux synthetic acceptance. This is not Windows proof.
Record host, commit, exact image IDs and transcript for an actual Windows run.
Credential-dependent live Telegram/AI/publication acceptance is always SKIP for
this procedure; it requires its own explicit authorization and environment.
