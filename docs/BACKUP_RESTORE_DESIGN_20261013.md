# Windows PostgreSQL backup and create-only restore

This implements the already approved PHASE1 Windows backup/restore commands,
not a new storage architecture. PostgreSQL remains the sole business authority;
master/operator/reviewer files and media remain separately backed up. No UI,
business model, operational authorization or worker activation changes.

## Observed defect and scope

Existing backup.ps1 redirects pg_dump to a caller path without checking native
exit and can overwrite an existing backup. Existing restore.ps1 pipes text to
psql without ON_ERROR_STOP/native checking; an invalid or partial restore can
appear successful. Both depend on ambient POSTGRES_* rather than checking the
actual target. Actual script tests must demonstrate these defects before fix.

Replace only this paired workflow with an explicitly targeted, fail-closed
PostgreSQL custom-format archive and versioned manifest. PowerShell7 is required
for binary-safe .NET process argument/stream handling; no local Python dependency
for the user command. Existing Windows Docker Desktop is sufficient.

## Binding contract

- Backup accepts explicit full ContainerId (64 lowercase hex), ProjectName,
  Database, User, Destination; Destination is a new bundle directory, not a file.
  Never silently choose a Compose project, service, role or database from cwd/env.
- Before DB commands inspect the exact container: ID equal, running, labels
  com.docker.compose.project equal ProjectName and service=postgres. Database
  and User equal its POSTGRES_DB/POSTGRES_USER configuration. Do not print full
  inspect/env/private Docker diagnostics or secret data. Fixed public errors.
- Names are bounded ASCII PostgreSQL names; full ID and project are separately
  structurally checked, all external commands use argument arrays, never a
  string-built shell. No shell interpolation of caller SQL/path values.
- Backup bundle is create-only and contains database.dump and manifest.json.
  All existing destination files/directories and reparse/symlink ancestors are
  refused. Resolve absolute paths before writing; never overwrite/remove an old
  bundle. A failed dump leaves its newly created partial evidence, without a
  success manifest or success exit. No cleanup deletion of user paths.
- Archive bytes use pg_dump --format=custom --no-owner --no-privileges with
  binary-safe stdout to the new file. Check actual exit before manifest/success.
  Validate custom archive through pg_restore --list before acceptance, retain
  a SHA256 and byte size in a strict version1 manifest with source ID/project/
  database/user and PostgreSQL version. Do not include keys, URLs/passwords,
  source rows, host session paths or media contents in the manifest/logs.
- Restore accepts Source bundle plus exact ContainerId/ProjectName/User and
  explicit TargetDatabase. Verify structure, SHA256, positive length/archive
  list, source provenance/format and actual running target before DB creation.
  TargetDatabase must differ from source database, must not already exist, and
  must be explicitly named. No existing database overwrite/drop/--clean, no
  arbitrary SQL text restore, no master key generation or automatic migrations.
- Create the new DB once, then pg_restore --exit-on-error --no-owner
  --no-privileges into that copy. Every native failure exits nonzero with fixed
  public error; retain partial copy, never retry/drop/recreate/claim rollback.
  Existing encrypted rows remain ciphertext. The stable original key is needed
  separately to read them; SQL backup alone is not a complete application backup.
- Commands have bounded native execution (default120seconds, configurable
  1..1800seconds); timeout terminates only the command process created by the
  helper, never unrelated Docker/OS/container processes. No generic tree cleanup
  promise. Safely drain stdout/stderr; do not deadlock on either stream or expose
  private diagnostics. Binary bytes must not roundtrip through PS text encoding.
- Human docs explain bundle validation, private storage/ACLs, compatible PG
  major version, separately preserved master/secrets/media, create-only recovery,
  fail/partial-copy handling, post-restore migrations/drift/health checks on an
  isolated copy and forward-fix/rollback boundaries. No claim of production
  recovery, full backup or release completion from a SQL-only copy.

## Acceptance

Automated PowerShell contract tests execute actual scripts in a new subprocess
with a deterministic fake Docker executable (not real Docker), cover native
failure propagation, binary archive fidelity, nonzero dump/list/createdb/restore,
existing destination/target, bad digest/manifest, injection/reparse/foreign ID,
wrong labels/env/stopped/timeout and absence of destructive commands/secret logs.
Tests must assert meaningful child return codes plus durable files/command trace.
Real root gate uses only the exact owned Windows synthetic editorial fixture,
new bundle and new explicitly named DB. Original source DB/volumes/files stay
unchanged. Compare restored policy/outbox/REJECT/zerojob rows, run Alembic drift
read-only on the restored copy, and retain native statuses and hashes. No workers,
live sessions/AI calls/Telegram sends. Source review precedes actual runtime.

## Continuous Windows contract verification

Existing Ubuntu jobs explicitly skip the Windows native shim; their success is
not continuous Windows coverage. After Task1 source/runtime acceptance, add one
separate Windows-hosted GitHub job for this exact contract file. Keep all nine
existing gates unchanged. Preflight PowerShell7/native compiler, run real scripts
with the synthetic executable only, record JUnit/native terminal results and
always upload evidence. Missing prerequisites or zero executed test cases fail
the job; individual explicitly unsupported symlink cases remain honestly SKIP.
No real Docker daemon, credentials, sessions, server or paid provider is needed.
