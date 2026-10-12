# Editorial policy operator authentication

The protected `GET` and `PUT /api/settings/editorial-policy` routes use a
default-disabled, single-human operator credential. Without valid server-side
configuration they return 503 before obtaining storage. With valid configuration,
missing, malformed or wrong `Authorization: Bearer` credentials return 401.
Responses use `Cache-Control: no-store`; errors omit token values and file paths.
This boundary is scoped to the diagnostic policy routes, not every legacy API.

## Separate provisioning

Before opting in, an authorized human must separately provision an existing,
persistent regular secret file outside Git. Supply an independently generated
high-entropy token of 32–128 ASCII letters, digits, underscore or hyphen, optionally
followed by exactly one LF. CRLF, whitespace, Unicode, symlinks, Windows reparse
points, nonregular files and oversized files are refused. Do not reuse provider
keys, Telegram credentials or sessions, the encryption master key, or the
illustration reviewer credential. Use a separate file and independent token;
runtime refuses paths and inode aliases to the configured master/reviewer files,
but cannot establish independence of equal bytes in separate files.

Configure `NEWSFLOW_EDITORIAL_OPERATOR_ID` as the stable identity of the one
authorized human: decimal digits without leading zeros, in the inclusive range
1–9223372036854775807. Runtime validates the identity and token; Compose only
requires nonempty interpolation inputs. Successful `compose config` does not
validate the secret, authorize execution or prove a working mounted credential.
Neither Compose nor runtime generates or rotates credentials.

Protect the file and its parent directory with owner-controlled filesystem ACLs,
and permit only the intended API runtime to read it. The application does not
provision or enforce host ACLs. Keep the secret untracked and outside the checkout,
images, build contexts, logs, shell history and frontend assets. Keep the API on
localhost or behind an authenticated TLS termination boundary; never transmit
the bearer over a plaintext remote connection. Bearer possession represents the
configured human; this is not multiuser login or browser session management.
Trusted database administrators and process execution can bypass an application
authentication boundary.

Back up this persistent host file separately from encrypted SQL and separately
from the master key and reviewer credential. SQL backups do not contain or
restore this operator credential. Preserve owner ACLs during recovery.

## Optional Compose combinations

`compose.editorial-operator.yaml` mounts `editorial_operator` read-only at
`/run/secrets/editorial_operator` into `api` only and sets the existing runtime
variable `NEWSFLOW_EDITORIAL_OPERATOR_SECRET_FILE`. No worker, migration service,
frontend or Redis receives the mount or operator auth variables. The existing
master mount stays on API and worker; the reviewer override remains API only.
Default Compose has no operator credential dependency, even if operator source
and ID variables happen to be set in the invoking shell.

The following PowerShell commands are human deployment instructions after
separate provisioning and authorization; they were not executed by this task.
Replace the paths and identity with the intended deployment inputs. The deployment
env file must already exist and contain the application's ordinary configuration,
including `POSTGRES_PASSWORD`; keep operator bearer bytes out of that file.
`NEWSFLOW_MASTER_KEY_SOURCE` must separately refer to the deployment's existing
master file. `--env-file` controls interpolation and `NEWSFLOW_ENV_FILE` selects
the service env file so no implicit checkout `.env` is needed:

```powershell
$deploymentEnv = 'C:/NewsFlow-private/deployment.env'
$env:NEWSFLOW_ENV_FILE = $deploymentEnv
$env:NEWSFLOW_MASTER_KEY_SOURCE = 'C:/NewsFlow-private/master.key'
$env:NEWSFLOW_EDITORIAL_OPERATOR_SECRET_SOURCE = 'C:/NewsFlow-private/editorial-operator.token'
$env:NEWSFLOW_EDITORIAL_OPERATOR_ID = '29'
```

Development:

```powershell
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.dev.yaml -f compose.editorial-operator.yaml --profile dev config --quiet
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.dev.yaml -f compose.editorial-operator.yaml --profile dev up -d
```

Production:

```powershell
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.editorial-operator.yaml --profile production config --quiet
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.editorial-operator.yaml --profile production up -d
```

For reviewer coexistence, first separately provision its independent file and
positive signed 64-bit human identity, as described in
[illustration review authentication](ILLUSTRATION_REVIEW_AUTH.md), then set:

```powershell
$env:NEWSFLOW_ILLUSTRATION_REVIEW_SECRET_SOURCE = 'C:/NewsFlow-private/illustration-reviewer.token'
$env:NEWSFLOW_ILLUSTRATION_REVIEWER_ID = '17'
```

Development with both independent credentials:

```powershell
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.dev.yaml -f compose.editorial-operator.yaml -f compose.illustration-review.yaml --profile dev config --quiet
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.dev.yaml -f compose.editorial-operator.yaml -f compose.illustration-review.yaml --profile dev up -d
```

Production with both independent credentials:

```powershell
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.editorial-operator.yaml -f compose.illustration-review.yaml --profile production config --quiet
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.editorial-operator.yaml -f compose.illustration-review.yaml --profile production up -d
```

Missing or empty operator source or ID causes Compose configuration to fail.
Rendering configuration neither reads nor creates the referenced secret file.
Container startup requires the separately provisioned file to exist and runtime
authentication still validates its contents, type, inode and excluded aliases.

## Persistence and explicit rotation

API restart, image rebuild and stack down/up preserve the separately stored host
file; do not delete, regenerate or overwrite it during these operations. Restore
the same file and identity after recovery to retain the operator credential.
Configuration-only tests are not packaged restart/down-up acceptance evidence.

For authorized rotation, separately replace the host file with a new independent
credential, retain the ID for the same human, and distribute the bearer through
a trusted channel. The loader reopens its configured file on each request, so a
direct host-file deployment observes replacement and refuses the old bearer.
A container secret bind mount can retain the previous inode after atomic host
replacement. Recreate API using the same env file, profile and complete override
combination; restart alone is not a guarantee of rotation. For example:

```powershell
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.dev.yaml -f compose.editorial-operator.yaml --profile dev up -d --no-deps --force-recreate api
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.editorial-operator.yaml --profile production up -d --no-deps --force-recreate api
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.dev.yaml -f compose.editorial-operator.yaml -f compose.illustration-review.yaml --profile dev up -d --no-deps --force-recreate api
docker compose --env-file "$deploymentEnv" -f compose.yaml -f compose.editorial-operator.yaml -f compose.illustration-review.yaml --profile production up -d --no-deps --force-recreate api
```

Choose only the command matching the deployed combination. After rotation,
verify the new bearer authenticates and the old bearer returns 401 through the
intended localhost/TLS boundary without logging either bearer. A changed human
requires an explicit identity change and deliberate review of policy audit history.

Saving diagnostic policy does not disable the editorial admission gate, qualify
a real model, authorize execution, clear an existing rejection, create a rewrite
job or authorize publication. `REJECT` retains `rewrite_allowed=false` and zero
rewrite calls. Synthetic fixtures never establish model qualification or
execution authority. This configuration task provisions no operational credential,
session or provider and makes no publication or network send.
