# Explicit first Telegram authorization — scoped onboarding increment

This closes the approved TelegramAccount/encrypted-session onboarding gap. The
existing Accounts API creates metadata with empty encrypted_session; the real
provider deliberately cannot start/sign_in/send_code. Users currently have no
implemented first-session producer. Existing eight-screen styling stays unchanged.
No live authorization is attempted during autonomous implementation.

## Decision and boundaries

Use a local interactive CLI first, not an unauthenticated browser login endpoint
or a general plaintext StringSession importer. Keep current read-only ingestion
and publication adapters unchanged; login lives in a separate adapter/service.
The console is a trusted local operator boundary, not a replacement for a later
protected browser authorization flow. Actual code/2FA remains a manual live gate.

`python -m newsflow.telegram_login` is disabled unless --enable-login is present.
Help/default/malformed requests cause no DB, key-file, provider construction or
network access. Enabled execution requires real interactive stdin/stderr TTYs,
explicit --account-name and positive --actor-id; optional --expected-user-id is
strict positive signed64. DATABASE_URL, the existing NEWSFLOW_MASTER_KEY_FILE and
NEWSFLOW_TELEGRAM_CREDENTIALS_FILE are already provisioned by the operator. No
credential discovery, fallback key, generation, rotation or plaintext-session file.
Validate configuration/key and inspect metadata before any Telegram IO.
CLI requires configured PostgreSQL+psycopg, not a silently created local SQLite
database. Schema must already be migrated; login never runs migrations itself.

Phone, code and optional 2FA password are read with masked getpass only, never
command parameters, normal echoed input, URL, browser storage, logs or outbox.
Phone is canonical + followed by5–15digits/firstdigit1–9; one code4–8digits; 2FA
password nonempty and <=1024characters. Abort/EOF/cancellation never stores data.
One explicit send_code_request, one code sign_in, at most one password sign_in;
no application resend/retry/sleep/login loop, bot-token/QR/join/send/rights APIs.
FloodWait yields a fixed private error, not automatic repeated requests.

Fresh in-memory Telethon StringSession only, no filesystem session backend.
Use explicit api_id/api_hash validation already shared by provider factory. Client
retries/reconnect/flood sleep disabled, updates disabled, quiet non-propagating
logger. Every awaited RPC has15second deadline; disconnect3seconds in finally.
Manual masked input is operator-paced, not claimed to have a process deadline.
RPC convenience methods may have SDK-internal behavior within those deadlines;
one top-level invocation is not an attested actual network-call count.
Verify authorized state and actual get_me: positive non-bool user id, non-bot,
canonical phone equals requested phone, expected identity when supplied. Require
a valid StringSession of1–4096characters before persistence; no fabricated success
result. Require its SDK auth_key to be present/256bytes, not just a nonempty string.

## Create-only durable result

Preflight name is trimmed1–100characters/no controls. Refuse an existing provisioned
account before client construction. An existing same-name empty-session record
may be provisioned only in DISCONNECTED/no-cooldown state; its immutable user id
becomes the expected identity. Capture id/name/user/empty session/health/cooldown,
close the DB transaction before interactive input or RPC, and CAS-revalidate that
exact snapshot after authorization. A different-name record with the authenticated
user id is a conflict, never a relabel/replacement. Concurrent creation/rename/
provision/health changes fail closed without overwriting or retrying.

For a new name, create one TelegramAccount using the verified user id and encrypted
StringSession. For compatible pre-created metadata, fill empty encrypted_session
only with conditional SQL/CAS (row-lock alone is not SQLite concurrency proof).
Retain DISCONNECTED until existing separate health probe confirms the session;
do not claim ingestion/authorization/permissions/publication runtime is active.
In the same transaction append one existing OutboxEventModel:
event_type=TelegramSessionProvisioned,
aggregate_key=telegram-session:{actor_id}:{account_id},
idempotency_key=telegram-session-provision:{fresh_uuid_hex}.
No phone/userid/plaintext/ciphertext/password/code/key in that event. Failure of
encryption/SQL/audit/commit leaves the prior DB unchanged, no false success. A
successful remote sign-in cannot be rolled back by a failed SQL commit; document
that limitation without automatic logout or revocation. Never replace a saved
session automatically. Stable external master-file custody remains the operator's
responsibility; CLI rechecks the same key before final persistence.

CLI output is fixed status and internal account id only. Exceptions are sanitized;
no traceback/native provider text/credential/session repr. Underlying exception
chaining must not expose secrets through CLI logs. Stored ciphertext is read by
the existing ConfiguredTelegramProvider and survives an independent SQL reopen
with the same separately supplied cipher; no production worker opt-in changes.

## Verification

TDD against actual service/CLI/database/cipher with fake only at Telegram RPC and
interactive terminal boundaries. Use real Telethon typed fixtures/StringSession
format where the contract needs it; no real credentials, live sessions or calls.
Cover successful one-code/2FA paths, wrong user/phone/bot, invalid/expired code,
FloodWait, malformed response/session, per-RPC timeout/disconnect, EOF/Ctrl-C,
nonTTY/default/missing-secret zeroIO, fixed private output, wrong/stale key,
pre-existing and concurrent metadata/session conflicts, encryption/DB/audit
rollback and repeat refusal before another code request. Assert immutable source/
REJECTfalse plus zero rewrite/publication/diagnostic/semantic jobs and provider
calls independently of session storage. Integration consumer must actually reopen
the encrypted row through ConfiguredTelegramProvider with a fake authorized RPC,
not merely decrypt a standalone string. Add migrated PostgreSQL CAS/audit cases
on a separately owned UUID namespace before runtime acceptance. Packaged default/
help/refusal smoke has network disabled; actual human login/restart is pending.

## Primary API references

Telethon's [client reference](https://docs.telethon.dev/en/stable/modules/client.html)
distinguishes connection timeout from awaited-request deadlines and documents
retry/update controls. Its [session guide](https://docs.telethon.dev/en/stable/concepts/sessions.html)
describes in-memory StringSession credentials as sensitive authorization material.
These were inspected while preparing the bounded adapter; tests must exercise
our own control and persistence contracts, not merely assert upstream constants.

This is a prepared next independent increment, not implementation, approval of a
real login, PHASE1 completion, or permission to access unrelated credentials.
