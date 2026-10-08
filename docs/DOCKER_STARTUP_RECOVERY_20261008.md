# Windows Docker engine startup recovery — 2026-10-08

Docker Desktop 4.91.0 (239619) was installed but stopped. Normal startup failed
before Linux Engine readiness on a stale `Docker/run/sailor-ingest.sock`: Windows
error 1920 during rename to `.stale`. The bounded normal CLI stop also failed.
Read-only reparse-point inspection reproduced error 1920. This matches reported
[Docker issue 554](https://github.com/docker/desktop-feedback/issues/554) and
[related issue 692](https://github.com/docker/desktop-feedback/issues/692).
The reports describe a workaround, not a proven permanent vendor/kernel fix.

## Narrow recovery actually performed

Initial inventory had no Desktop/backend processes. After failed normal stop,
stopped only explicit task-started Docker process IDs with executable paths
validated under `C:/Program Files/Docker/`. Confirmed Desktop/backend absent
before moving runtime directories. Validated physical non-reparse-point absolute
directories and refused unexpected files/subdirectories/nonzero content.
Docker/run held four zero-byte socket endpoints; docker-secrets-engine held only
zero-byte engine.sock. Native PowerShell moves preserved both directories:

- `C:/Users/borov/AppData/Local/Docker/run.recovery-20261008-942db362`.
- `C:/Users/borov/AppData/Local/docker-secrets-engine.recovery-20261008-942db362`.

Created fresh empty original runtime directories, verified installed Desktop's
Authenticode signature (Valid) and launched with hidden window style. No deletion,
factory reset, installer/update/EULA acceptance, prune, WSL unregister or VHDX/
volume/configuration/credential modification. Old runtime entries remain preserved.

## Actual verification

- `docker version`: Linux Engine **29.8.0**, API 1.56, Desktop 4.91.0,
  linux/amd64, WSL2 kernel 6.18.33.2-microsoft-standard-WSL2.
- `wsl --list --verbose`: docker-desktop Running, version 2; Ubuntu Stopped.
- `docker info`: real ServerVersion 29.8.0, linux, overlayfs.
- Existing cached official redis:7-alpine successfully ran in a unique disposable
  container with `--pull never --network none --read-only`, no volumes, entrypoint
  `redis-server --version`: Redis 7.4.11, exit 0. Probe auto-removed, no persistent
  data attached. No image pull or live provider request.
- Existing inventory remains readable. Operational newsflow containers are exited
  (255); this is not application health/deployment proof. No operational compose
  up/down, migration, queue, session or publication action during this recovery.

Engine availability is verified. **Fresh current-source Windows stack build,
health, migrations, persistence/recovery acceptance are NOT VERIFIED.** Previous
missing-pipe blocker is now historical; higher gates are not promoted from daemon
readiness. This workaround may be needed again after Desktop shutdown.

## Next step

Run existing create-only isolated Windows verification procedures with retained
target/configuration guards. Do not reuse/reseed old fixtures or operational
queues. Live Telegram/AI authorization remains separate; the user will provide
credentials and explicitly designated test-channel destinations. No live send
performed or destination inferred from donor links.
