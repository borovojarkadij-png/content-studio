# Windows PostgreSQL backup and recovery copy

These commands save PostgreSQL business data to a new custom-format archive bundle
and restore a trusted bundle into a new, explicitly named database. PostgreSQL is
the business authority. This SQL workflow does not back up the entire application,
prove production recovery, activate workers, or complete a release.

## Prerequisites and private storage

Use PowerShell 7 (`pwsh`) and Docker Desktop, with the intended PostgreSQL container
already running. The current Compose image is PostgreSQL 16. Use a compatible
PostgreSQL major version for recovery; these scripts require the source and target
server major versions to match. The target container must have the same configured
`POSTGRES_DB` and `POSTGRES_USER` as the source bundle. It may have a different full
container ID and Compose project. No container is selected from the current
directory or ambient `POSTGRES_*` environment variables.

Store bundles in an existing private local directory with Windows ACLs restricted
to the operator and necessary administrators. The bundle inherits its parent's
ACLs; the scripts do not set ACLs, encrypt the archive, or protect a directory that
another local principal can modify concurrently. PostgreSQL dumps may include
sensitive rows even when particular fields are ciphertext. Use encrypted storage
and an independently protected off-device backup as appropriate to your recovery
policy. Do not place backups in source control, shared/public directories, or logs.

Preserve the stable application master key separately, along with required
operator/reviewer secrets, configuration, and media files. Record how those copies
match the database backup. Existing encrypted values remain ciphertext in the SQL
archive. Reading them after recovery requires the original key. Neither script
looks up, creates, rotates, embeds, or backs up a master key. Preserve keys securely
and separately from the SQL bundle.

## Explicit backup

Identify the intended container using your existing operational inventory. A
scoped read-only ID lookup can help, but confirm its result against that inventory:

```powershell
$containerId = docker ps --no-trunc --quiet --filter 'label=com.docker.compose.project=newsflow' --filter 'label=com.docker.compose.service=postgres'
if ($LASTEXITCODE -ne 0 -or @($containerId).Count -ne 1) { throw 'Resolve exactly one intended PostgreSQL container.' }
pwsh -NoProfile -File .\scripts\backup.ps1 `
  -ContainerId $containerId -ProjectName 'newsflow' `
  -Database 'newsflow' -User 'newsflow' `
  -Destination 'D:\Private Backups\newsflow-20261013-01' -TimeoutSeconds 120
if ($LASTEXITCODE -ne 0) { throw 'Backup failed; retain partial evidence and inspect privately.' }
```

Replace the example inventory, names, and private destination with your intended
values. `Destination` is a **new bundle directory**, not a SQL filename. Its parent
must exist. Existing files or directories are refused. Paths are resolved to
absolute local filesystem paths; Windows UNC/device paths, alternate data streams,
and reparse/symlink ancestors or files are refused. Paths containing spaces,
Unicode, brackets, and apostrophes are passed literally.

`ContainerId` must be the full 64-character lowercase hexadecimal ID. The running
container's ID, Compose project label, `postgres` service label, `POSTGRES_DB`, and
`POSTGRES_USER` must match the explicit inputs. Names accept 1–63 ASCII characters,
starting with a letter or underscore and continuing with letters, digits, or
underscores. The project accepts 1–63 lowercase letters, digits, underscores, or
hyphens and starts with a lowercase letter or digit. No SQL, shell fragments,
connection strings, or passwords are command parameters.

Successful backup prints `BACKUP_OK` and exits 0. The new directory contains only:

- `database.dump`: `pg_dump --format=custom --no-owner --no-privileges` bytes, never
  converted through PowerShell text encoding.
- `manifest.json`: strict version 1 schema with `format=postgresql-custom`,
  `archive=database.dump`, `sourceContainerId`, `sourceProject`, `sourceDatabase`,
  `sourceUser`, `postgresVersion`, lowercase SHA256 `sha256`, and positive integer
  `byteLength`. No passwords, keys, rows, media, or host session paths are included.

The manifest is written only after the native dump exits successfully and the
archive signature and native `pg_restore --list` validation succeed. A failed
backup exits nonzero and retains its newly created partial evidence without a
success manifest. Never treat a directory or partial archive alone as a backup.
Choose a different new destination for a later attempt; the script never removes
or overwrites an old bundle.

## Create-only restore

Restore only your own trusted backup. SHA256 and the manifest establish internal
consistency and detect accidental alteration; they do **not** authenticate origin.
An attacker who can replace both files can create matching metadata. A malicious
PostgreSQL archive can execute SQL during restore. `--list` validation establishes
archive readability, not SQL safety. Keep custody of the bundle and use an
isolated recovery environment with no live providers, Telegram sessions/sends,
workers, or production database credentials.

```powershell
# Resolve and confirm this ID separately for the intended recovery container.
$recoveryContainerId = docker ps --no-trunc --quiet --filter 'label=com.docker.compose.project=newsflow-recovery' --filter 'label=com.docker.compose.service=postgres'
if ($LASTEXITCODE -ne 0 -or @($recoveryContainerId).Count -ne 1) { throw 'Resolve exactly one intended recovery PostgreSQL container.' }
pwsh -NoProfile -File .\scripts\restore.ps1 `
  -Source 'D:\Private Backups\newsflow-20261013-01' `
  -ContainerId $recoveryContainerId -ProjectName 'newsflow-recovery' `
  -User 'newsflow' -TargetDatabase 'newsflow_recovered_20261013_01' `
  -TimeoutSeconds 120
if ($LASTEXITCODE -ne 0) { throw 'Restore failed; retain any partial copy and investigate privately.' }
```

`Source` must contain exactly the two regular bundle files. Unknown/missing or
duplicate manifest keys, wrong JSON types/version, extra files, invalid provenance,
bad length/hash, or invalid archives fail closed. The script holds the archive's
read-only handle through hash verification, archive listing, and restore; Windows
writers/deleters cannot replace the validated bytes while that handle is held.
The manifest is limited to 64 KiB. Native textual responses are limited to 1 MiB.

The target must have a valid explicit name, differ from `sourceDatabase`, and not
already exist. The script validates the target container and compatible PostgreSQL
major version, checks the archive list, and checks target absence before `createdb`.
It creates the new copy once from `template0`, then invokes `pg_restore` with
`--exit-on-error --no-owner --no-privileges`. It never drops an existing database,
uses `--clean`, accepts arbitrary SQL text, or automatically migrates data.

Successful restore prints `RESTORE_OK` and exits 0. Every native failure exits
nonzero with a fixed public error. If creation or restore fails, a partial database
may remain. The script never retries, drops/recreates that copy, or claims rollback.
Retain the failed copy for private diagnosis. To retry after resolving the cause,
choose another unused target name. Concurrent creation of the target is handled by
`createdb` failing; an existing target is never overwritten.

Each native command has a finite deadline: default 120 seconds, configurable
`TimeoutSeconds` 1–1800. This is per command, not a single deadline for the entire
workflow. On timeout the helper terminates only its owned Docker CLI process.
It does not kill unrelated processes, process trees, containers, or server-side
commands. Server work may outlive a disconnected CLI; examine the isolated copy
privately before attempting further recovery. stdout and stderr drain concurrently;
native diagnostics and inspect environment contents are not printed publicly.

## Validate the isolated copy before cutover

Check the recovered schema, important row counts, policy/outbox/decision/job state,
and expected ciphertext. Run the project's migration drift check against the
explicit restored database using a private local configuration; inspect migration
requirements before applying any approved migrations to that copy. Run application
health and data access checks with the separately preserved original master key
and compatible media/configuration, while keeping integrations and workers off.
A successful SQL restore alone does not establish these application checks.

Keep the original database, volumes, bundles, keys, and media intact through
validation. Cutover and migration authorization are separate operational steps.
If validation fails, investigate and forward-fix on another isolated copy. A
schema downgrade or older application is not automatically a safe rollback:
preserve a known compatible application/schema/key/media set and confirm downgrade
support explicitly before relying on it.

The automated contract tests use a native synthetic Docker executable and actual
Windows PowerShell subprocesses. They never access Docker, providers, credentials,
or live data. Windows runtime recovery, release checks, and production recovery
acceptance require their own recorded evidence.
