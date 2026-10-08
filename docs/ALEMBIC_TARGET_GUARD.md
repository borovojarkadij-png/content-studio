# Explicit migration target / incident

2026-10-08: a validation command set DATABASE_URL to an isolated D: path, then
called the plain Alembic CLI. Legacy env.py ignored that environment variable;
the ini default selected ignored backend/newsflow.db instead. Upgrade, downgrade
to base and re-upgrade executed there. This was an agent error, not an authorized
data reset. Operational Docker PostgreSQL and root newsflow.db were not targets.

Afterward, a read-only SQLite inspection found zero records in every business
table and one Alembic version record. There is no pre-command snapshot proving
previous contents, so absence of data loss cannot be claimed. The database must
not be reset or populated to conceal this incident.

Fix: ini has no default database. env.py requires an explicit configuration URL
or DATABASE_URL; the legacy sqlite:///newsflow.db fallback also requires an
environment target. Explicit programmatic isolated URLs remain authoritative.
GitHub migration validation supplies a dedicated migration-ci-isolated.db URL.

Actual subprocess regression RED: CLI unexpectedly migrated sentinel DB and
ignored explicit environment URL (2 failures). GREEN: both fixed; separate
programmatic URL isolation and four packaged-runtime migration tests pass.
Sentinel tests run only in temporary D: directories, never on user databases.

Use python -m newsflow.migrate for packaged upgrades. Any round-trip verification
must use a fresh isolated explicit URL and must never downgrade operational data.
