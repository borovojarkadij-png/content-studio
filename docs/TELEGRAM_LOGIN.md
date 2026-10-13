# First Telegram authorization by an operator

The local interactive CLI provisions the first encrypted Telegram session. It is
disabled by default. This is an operator procedure; the Accounts screen still
creates metadata and does not provide a production Connect button. No successful
live login or qualified automatic approval is claimed by this implementation.

## Prerequisites

Use an approved account name and positive signed 64-bit operator actor ID. An
optional expected Telegram user ID must also be positive signed 64-bit. Existing
same-name metadata must have an empty session, DISCONNECTED health and no
cooldown; its recorded Telegram user ID binds the login. Saved sessions are never
replaced. A conflicting name or user, changed metadata or concurrent provisioning
fails closed. Re-running the CLI does not authorize replacement.

An operator must already have provisioned these settings and files:

- `DATABASE_URL`: explicit `postgresql+psycopg://...` with a database and role.
  The selected database must already be at the packaged Alembic head. The CLI
  only reads migration state and never creates/upgrades a database or schema.
- `NEWSFLOW_MASTER_KEY_FILE`: existing stable Fernet key file, maintained and
  backed up outside Git, separately from the database and session ciphertext.
  The same key is required to reopen sessions after restart. No key is generated,
  discovered, rotated or replaced. It is reloaded before persistence.
- `NEWSFLOW_TELEGRAM_CREDENTIALS_FILE`: existing JSON file containing exactly
  `api_id` (positive integer) and `api_hash` (32 hexadecimal characters), provided
  through the shared credential loader. Keep the application credentials private.
- Real interactive stdin and stderr terminals supporting masked `getpass`.
  Pipes, redirected input/error streams and unavailable masking fail closed.

Do not put a phone, login code, 2FA password or StringSession in arguments,
environment variables, shell history, URLs, logs or plaintext session files.

## Local command

From the `backend` directory in an installed environment with the above explicit
configuration:

```powershell
python -m newsflow.telegram_login --help
python -m newsflow.telegram_login
# LOGIN_DISABLED; exit 2. No database, key-file or Telegram access.

# Replace the example name and actor ID with the approved operator values.
python -m newsflow.telegram_login --enable-login --account-name "Approved account name" --actor-id 29
# If known, also supply: --expected-user-id 1001
```

The CLI checks configuration, the migration head, the master key and existing
account metadata before asking for a phone. Enter your own canonical phone
(`+` followed by 5–15 ASCII digits, first digit 1–9), your own received 4–8 digit
code, and your own nonempty 2FA password when requested (maximum 1024 characters).
All three use masked input. It makes one application code request, one code
sign-in and at most one password sign-in. There is no resend, retry or sleep
loop; FloodWait fails. Each awaited RPC has a 15-second deadline and disconnect
has a 3-second deadline. Human input is operator paced. SDK internals may perform
additional work within an RPC; the top-level count is not a network-call attestation.

## Docker Compose interactive option

From the repository root, use the approved Compose project/environment, with the
existing master-key secret mount and an already running, already migrated
PostgreSQL service. `--no-deps` deliberately does not run prerequisites. The
standard `compose.telegram.yaml` mounts credentials on the worker; for this
one-off API container supply the credential mount explicitly. The operator must
set `NEWSFLOW_TELEGRAM_CREDENTIALS_SOURCE` to the absolute existing external JSON
path first. The command contains paths only, never credential values:

```powershell
docker compose run --rm --no-deps --interactive --entrypoint python --volume "${env:NEWSFLOW_TELEGRAM_CREDENTIALS_SOURCE}:/run/secrets/telegram_credentials:ro" --env NEWSFLOW_TELEGRAM_CREDENTIALS_FILE=/run/secrets/telegram_credentials api -m newsflow.telegram_login --enable-login --account-name "Approved account name" --actor-id 29
```

Compose allocates a terminal automatically when launched from a terminal; do not
use `-T`, a pipeline or redirected stderr. Apply your approved `-p`, `--env-file`
and `-f` selections before `run` when your installation uses them. The API service
inherits `DATABASE_URL` and the separately provisioned master-key secret mount
from that configuration. Use only the intended installation and identity.

## Result, failures and subsequent manual gates

Success emits only `LOGIN_SAVED account_id=<internalID>` and exit 0. The verified
non-bot Telegram identity and valid in-memory StringSession are encrypted and
committed together with one `TelegramSessionProvisioned` outbox event. Its
aggregate is `telegram-session:<actorID>:<accountID>` and its fresh idempotency key
is `telegram-session-provision:<UUIDhex>`; it contains no phone, Telegram user ID,
code, password, key or session material. Health remains DISCONNECTED until the
separate existing health probe verifies the session. Saving a session does not
start ingestion or publication or grant channel permissions.

Malformed arguments and failures emit only `LOGIN_FAILED` and nonzero exit;
Ctrl-C/EOF/cancellation emit `LOGIN_CANCELLED` and nonzero exit. Native SDK/SQL/
configuration exception details and tracebacks are suppressed. Fixed prompts
identify the masked field. A failure or abort stores no account/session/audit
change from this attempt; concurrent writers retain their own changes. Database
rollback cannot undo an already successful remote Telegram sign-in. The CLI does
not automatically log out or revoke that remote authorization. If this happens,
review the remote session manually before deciding on a new explicit attempt.

After an approved human login, independently reopen the encrypted account after
restart with the same separately supplied key through the configured provider.
Then perform the separate health and test-channel permissions gates with an
authorized test channel. First authorization, encrypted restart, read permissions
and publication permissions are distinct manual/runtime checks. None of these
commands enables worker opt-ins, automatic approval or publication by itself.

## Synthetic verification

CLI and service tests use synthetic keys, typed RPC fixtures and isolated SQL.
`tests/test_telegram_login_postgres.py` runs only with the existing strict
`NEWSFLOW_UNATTENDED_POSTGRES_URL` fixture target. It creates a fresh UUID schema
per case, applies packaged migrations only there and retains the namespace;
it never reuses/drops/resets a public or operational schema. Without that explicit
URL, these PostgreSQL cases report SKIP. SQLite CLI boundary tests and those skips
are not PostgreSQL acceptance evidence. Live authorization and the independent
encrypted restart gate remain manual pending checks.
