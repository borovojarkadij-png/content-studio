# Docker startup recovery — 2026-10-09

At this turn's first check Linux Engine's named pipe was absent. Desktop and
backend processes were not running, and WSL distributions were stopped. Normal
launch of the signature-validated installed Desktop reproduced the same Ingest
socket rename error in the fresh backend log at 09:25:41 UTC. The bounded normal
`docker desktop stop --timeout 10` reported failure.

Only this turn's explicitly recorded Desktop/backend process IDs were stopped,
after verifying their executable paths under the Docker install and start times.
Both exact runtime directories were validated as physical directories containing
only expected zero-byte socket endpoints. Native PowerShell moves preserved them:

- `C:/Users/borov/AppData/Local/Docker/run.recovery-20261009-f0bd5a6b`
- `C:/Users/borov/AppData/Local/docker-secrets-engine.recovery-20261009-f0bd5a6b`

Fresh empty original directories were created and signature-validated Desktop
launched with hidden window style. Actual `docker info` returned **29.8.0 linux**.
No reset, reinstall, WSL unregister, prune, volume removal, operational settings,
authorization or credential changes occurred. Earlier recovery directories remain.
This is a recurring workaround, not a verified permanent fix.

No application containers were automatically running after recovery. Only retained
synthetic `newsflow-verification-unattended-win-20261008a-postgres-1` was started
after verifying exact project/service labels, postgres:16-alpine image, synthetic
database/user, loopback 5432 port and project-owned postgres_data volume. Its exact
ID is `4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e`;
actual `pg_isready` reports accepting connections. No fixture was reseeded and no
operational database migrated. New regression tests use create-only owned schemas.

Engine/fixture readiness is not proof of new application acceptance. This turn's
authenticated review PostgreSQL results are recorded separately when completed.
Previous full Windows restart acceptance stays historical; no new down/up or live
Telegram publication acceptance is inferred here. PHASE 1 remains incomplete.
