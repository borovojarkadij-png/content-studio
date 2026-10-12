# Windows Docker startup recovery — 2026-10-12

Repository origin borovojarkadij-png/content-studio, branch codex/dark-navy-ui,
application source5fa89952afac22b438f26381eef8a5f7471c6cdb unchanged.
Normal engine check failed: missing dockerDesktopLinuxEngine pipe. Desktop had
no running processes. Normal `docker desktop start --timeout 45` launched the
installed Desktop but backend crashed before WSL startup on the retained
`sailor-ingest.sock` rename/error1920, matching the previously documented failure.

Only explicit task-started process IDs were stopped after validating executable
paths under C:/Program Files/Docker; one parent exited during the stop sequence,
so its later Stop-Process reported already absent. No unrelated processes were
stopped. The normal detached stop subsequently reported Stopping Docker Desktop;
Desktop/backend absence was checked again before filesystem changes.

Validated both physical absolute directories, rejected redirected parents and
unexpected/nonzero/subdirectory content. Docker/run held exactly the four known
zero-byte socket endpoints; docker-secrets-engine held only zero-byte engine.sock.
Native PowerShell moved these runtime-only directories, without deletion, to:

- C:/Users/borov/AppData/Local/Docker/run.recovery-20261012-8d87c822
- C:/Users/borov/AppData/Local/docker-secrets-engine.recovery-20261012-8d87c822

Fresh empty original directories created; installed Desktop executable signature
Valid was required before hidden launch. Previous recovery copies remain intact.
No factory reset/update/prune, volumes/VHDX/WSL distribution/configuration/secrets
or application data modified. This workaround is not a permanent vendor fix.

Fresh `docker version`/`docker info`: real Linux Engine29.8.0/API1.56,
Desktop4.91.0, WSL2 kernel6.18.33.2. No containers were running automatically.
The retained explicitly owned20261009c fixture was validated against its exact
original seven images, mounts, environment, secrets and volume labels, then
started with pinned IDs, --no-build/--pull never. No operational stack started.
Migrations/health passed; two independent original SQL/photo/review/encrypted
snapshot reopens passed with real RPC0. Entire command exit0. Original runtime
SHA2569de0045ca2fe24c0ab8f0187e759cbc6b6421e76b71b9cbd17c3057a76176e6a
unchanged. Native evidenceD:/Codex-Recovery/content-studio-20261008/windows-reopen-20261012c.log.
This is actual October12 retained-state runtime proof, not a new full build or
repetition of the October9 crash procedure. No real Telegram/AI/publication
activation or PHASE completion implied. Continue CURRENT_STATE NEXT_STEP.

## Follow-up at the October12/13 session boundary

On resume, Desktop/WSL and the Linux-engine pipe were absent. Installed signed
Desktop launched hidden as PID15432, but the same sailor-ingest.sock/error1920
recurred before the engine started. Normal `docker desktop stop --timeout20`
terminated native1 with a context deadline; this was not a successful normal stop.
Only task-started PID15432 was stopped after executable/start-time checks; its
children exited, and all Desktop/backend processes were confirmed absent.

Physical parent paths and the exact zero-byte socket-only directory contents
were validated again. Runtime-only directories were preserved, without deletion:

- C:/Users/borov/AppData/Local/Docker/run.recovery-20261012b-08a23384
- C:/Users/borov/AppData/Local/docker-secrets-engine.recovery-20261012b-08a23384

Fresh empty runtime directories and hidden launch of the Valid-signature Desktop
as PID30548 restored actual Linux Engine29.8.0/API1.56, Desktop4.91.0 and the same
WSL2 kernel. No reset/update/prune, VHDX/volume/secret/configuration changes or
operational stack launch. The exact owned unattended PostgreSQL container
4c1a4120ba72394b2851fe9916eddb48572feb9c70c5cd1a3167d7401b941b5e was validated
against its ownership nonce, original sole volume and loopback5432 binding before
starting only that container. PostgreSQL reports interrupted-system recovery and
data-directory fsync. PostgreSQL completed recovery and pg_isready reports
accepting connections; the retained1697 UUID namespaces/maxOID1294081 match the
pre-stop baseline exactly. No schema reset or reseed. The new history-reader
tests now use only newly generated synthetic namespaces on this recovered DB.
