# Explicit Telegram first-login implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development task-by-task. Steps use checkbox syntax.

**Goal:** Give the operator a guarded interactive first-session producer for
the existing TelegramAccount, with encrypted durable storage and atomic audit.

**Architecture:** Separate opt-in login adapter, two-stage snapshot/CAS service,
and local interactive CLI. Existing read-only providers, APIs, workers, schema
and accepted dark-navy UI remain unchanged. No browser login endpoint.

**Tech Stack:** Python3.12, Telethon1.x/current tested1.45, SQLAlchemy/Alembic,
PostgreSQL+psycopg, existing Fernet SessionCipher; pytest/fake RPC.

**Spec:** docs/TELEGRAM_ONBOARDING_DESIGN_20261013.md

## Global Constraints

Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
codex/dark-navy-ui. No merge/force/push by implementers. No subagents/helpers.
No real login/credential discovery/key generation/session replacement/real sends.
Never log phone/code/password/API hash/key/plaintext/ciphertext/session repr.
REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
No schema/dependency/Compose/API/worker/frontend changes in these tasks.
Existing saved sessions and unrelated account state must never be overwritten.
CLI disabled by default; enabled requires explicit flags, TTY, configured
PostgreSQL+psycopg, migrated schema and existing separately supplied secrets.
Every RPC deadline15seconds; disconnect3seconds; no application resend/retry.
Existing health probe, not login persistence, determines later HEALTHY status.
Actual human Telegram/2FA and encrypted restart remain separately pending.

---

### Task 1: Bounded authorization adapter and atomic session provisioning

**Files:**
- Create backend/src/newsflow/providers/telegram_login.py.
- Create backend/src/newsflow/services/telegram_login.py.
- Create backend/tests/test_telegram_login.py.
- Own task-1-report.md in this plan's SDD workspace.

**Interfaces:**
Provider module defines TelegramLoginError(RuntimeError), a frozen
AuthorizedTelegramSession(telegram_user_id:int, phone:str, string_session:str)
with secret-safe repr, and TelethonLoginAdapter(api_id, api_hash,
client_factory=None). Its async authorize(phone, *, read_code, read_password)
returns that verified result. Callbacks are zero-argument masked-input readers;
their operator-paced duration is not an RPC deadline.
Service module defines SessionProvisioningService(session_factory, *,
master_key_loader, login_adapter), frozen private-safe ProvisioningRequest,
preflight(account_name, actor_id, expected_user_id=None)->ProvisioningRequest,
and async provision(request, *, phone, read_code, read_password)->int accountID.
Task2 CLI consumes these exact public names/signatures. Do not expose session
material through a CLI result or persist serialized requests.

- [ ] Read spec, TelegramAccount/OutboxEventModel, SessionCipher, existing shared
  load_telegram_credentials/_validate_credentials and read-only provider.
  Write a successful encrypted-row/reopen/audit test before implementation:
  ```python
  request = service.preflight("synthetic-login", 29, expected_user_id=1001)
  account_id = asyncio.run(service.provision(
      request, phone="+15550001001", read_code=lambda: "12345",
      read_password=lambda: "synthetic-only-password"))
  with factory() as session:
      account = session.get(TelegramAccount, account_id)
      assert account.telegram_user_id == 1001
      assert account.health_status == "DISCONNECTED"
      assert account.encrypted_session != literal_valid_fake_string_session
      assert SessionCipher(SYNTHETIC_KEY).decrypt(account.encrypted_session) == literal_valid_fake_string_session
      assert session.scalar(select(func.count()).select_from(OutboxEventModel)) == 1
  ```
  Use actual service/DB/cipher, fake only RPC. Run and retain meaningful RED,
  not a collection/import-only error. A minimal interface scaffold raising
  TelegramLoginError permits a causal missing durable behavior assertion.
- [ ] Implement adapter: credential validation without discovery; fresh
  in-memory StringSession, request_retries=0/connection_retries=0,
  auto_reconnect=False/flood_sleep_threshold=0/receive_updates=False,
  private quiet non-propagating logger. No start()/QR/bot/login loop.
  Connect/send_code_request once, one code sign_in, SessionPasswordNeededError
  allows one password sign_in. Bind phone_code_hash privately, never echo.
  Validate phone +[1-9][0-9]{4,14}, code4–8digits, password1–1024chars.
  Wrap each awaited RPC in asyncio.wait_for(timeout=15); disconnect with3s
  in finally, including failure/abort; preserve primary failure privately.
  Authorized true/get_me positive non-bool signed64 ID/nonbot/canonicalphone
  exact match, then SDK StringSession1–4096characters with auth_key256bytes.
  Fixed private TelegramLoginError for malformed/RPC/FloodWait/timeout; no
  underlying exception chain leaks through public errors. EOF/KeyboardInterrupt/
  CancelledError do not save anything or repeat remote actions.
- [ ] Implement preflight before RPC: trimmed accountname1–100/no control or
  format characters; actor/expected IDs positive signed64/nonbool. Load existing
  master key and initialize SessionCipher without generating anything. Capture
  stable key fingerprint, metadata id/name/user/empty-session/health/cooldown
  in request, close transaction. Reject existing nonempty session, nonDISCONNECTED,
  any cooldown, expected identity mismatch before client construction/RPC.
- [ ] Provision validates request and phone, calls adapter once, validates
  returned identity/session again at persistence boundary. Recheck same master
  key fingerprint after RPC; encrypt only with matching supplied key. In one
  transaction, verify different-name user-ID conflict, create-only new account
  or update existing metadata with conditional SQL matching the exact captured
  id/name/user/session/health/cooldown snapshot. Rowcount must1; uniqueness
  conflict means private failure, no overwrite/retry. Retain DISCONNECTED.
  Flush account and insert existing OutboxEventModel event_type
  TelegramSessionProvisioned, aggregate_key telegram-session:{actor_id}:{account_id},
  idempotency_key telegram-session-provision:{fresh_uuid_hex}. Commit atomically.
  Any encryption/SQL/audit/commit failure rolls back DB; remote sign-in is not
  reversible and never triggers automatic logout/revoke.
- [ ] Extend real-service regressions for one-code/2FA, credential/client config,
  malformed phone/code/password/session/user/bot, mismatched expected/userphone,
  invalid/expired code/FloodWait, every RPC timeout, disconnect failure/timeout,
  abort, key-change, existing provisioned before0RPC, compatible metadata fill,
  independent writer rename/health/session/CAS conflict, different-name ID,
  concurrent creation and audit/commit/encryption rollback. With seeded REJECT
  and immutable source, assert unchanged and all rewrite/classification/semantic/
  publication/usage rows absent; no real AI/send calls permitted by fake.
  Prove reopen through real ConfiguredTelegramProvider/fake authorized RPC,
  not just a standalone cipher check. Don't weaken existing provider invariants.
- [ ] Run focused new file, covering provider/session/health/configuration
  regressions once, Ruff0.17 check/format/compile/diff. Full backend is deferred
  until Task2's combined deliverable, not duplicated after every edit.
- [ ] Freeze exact owned hashes; complete report with commands/RED/GREEN/
  native statuses/limitations/self-review; commit only owned source/tests/report.
  Root fresh spec+quality review/fixloop before Task2; no push/live call.

### Task 2: Explicit interactive CLI, migrated integration and operator procedure

**Files:**
- Create backend/src/newsflow/telegram_login.py.
- Create backend/tests/test_telegram_login_cli.py.
- Create backend/tests/test_telegram_login_postgres.py.
- Create docs/TELEGRAM_LOGIN.md.
- Own task-2-report.md in this plan's SDD workspace.

**Interfaces:** Consumes reviewed Task1 interfaces exactly; no Task1 source edits
without controller routing. python -m newsflow.telegram_login exposes main(argv=None)
and CLI module guard. Existing PostgreSQL isolation helper
backend/tests/unattended_postgres.py creates fresh UUID schemas for explicit
synthetic NEWSFLOW_TEST_POSTGRES_URL only. Root owns actual Docker/image/PG gate.

- [ ] TDD actual CLI entrypoint/private IO. Default/help/malformed invocation
  touches no DB/keyfile/client/network. Default prints LOGIN_DISABLED/exit2;
  help exit0. Enabled requires --enable-login, --account-name, --actor-id,
  optional --expected-user-id, no phone/code/password/session arguments.
  Refuse nonTTY stdin/stderr before any configured runtime construction.
  Use getpass only; never fall back to echoed input if masking unavailable.
  On success print LOGIN_SAVED account_id=<internalID> only; failure fixed
  LOGIN_FAILED/nonzero; abort LOGIN_CANCELLED/nonzero; no traceback/provider
  exception/phone/session/DB URL in any output.
- [ ] Validate DATABASE_URL via sqlalchemy.make_url drivername exactly
  postgresql+psycopg/nonempty explicit database/role, no SQLite fallback;
  use configured_session_factory() only after validation. Verify DB migration
  current heads equal ScriptDirectory.from_config(runtime_migration_config()).get_heads()
  through read-only MigrationContext, never command.upgrade/check mutation.
  Missing/old/multiple/wrong heads fail before code request. Load existing
  NEWSFLOW_MASTER_KEY_FILE and NEWSFLOW_TELEGRAM_CREDENTIALS_FILE only, use shared
  loader, no guessed paths/new keys. Invoke service preflight before masked
  phone; perform async service provision once. Dispose only own created engine
  if applicable, don't clear other runtime caches or dump connection config.
- [ ] CLI tests execute real parsing/guard/service where practical, patch only
  interactive TTY/getpass and network/configured test boundary. Actual subprocess
  default/help/nonTTY sentinel files remain unchanged/no network (socket guard).
  Test parse/TTy/URL/prerequisite refusal before0RPC, Unicode account name,
  one-code/2FA success fixedoutput, GetPassWarning refusal, abort and sanitized
  secret-bearing SDK/SQL/config errors, no session artifacts/log leakage.
- [ ] Add explicit isolated migrated PostgreSQL cases using existing strict
  helper's create-only UUID schemas: new insert+outbox/encrypted reopen consumer,
  metadata CAS against independent writer, uniqueness race and audit rollback.
  Missing synthetic URL yields explicit PG-only SKIP, never SQLite-as-PG PASS.
  No public-schema reuse/drop/reset/new fixedschema. Root runs actual PG after
  source review and reports exact new namespaces; implementer does not touch
  operational Docker/old fixtures. Source REJECT/zero-execution invariants remain.
- [ ] Operator docs give actual guarded CLI commands from backend cwd and
  Docker Compose `run --rm --no-deps --entrypoint python api -m newsflow.telegram_login`
  interactive option with approved account/actor flags and operator-provisioned
  credential mounts. Explain default-off, prerequisite mounts/migrations/TTY,
  session/master-key separate custody, one attempt/no retry, no saved-session
  replacement, audit/state meaning, remote-login vs DB-rollback limit, own
  human code/2FA, test-channel permissions and separate encrypted restart gate.
  Do not claim a ready production UI connect button, live successful login or
  qualified autoapproval. Existing design/manual settings untouched.
- [ ] Focused CLI/core/PG collection tests, Ruff0.17/format/compile, then one
  full backend suite with explicit Telethon1.45 and synthetic-only defaults.
  Fix ordinary failures and rerun amended coverage; retain failures, no disabled
  checks. Report real pass/skip/native statuses; no frontend suite for no UI diff.
- [ ] Freeze owned hashes, self-review, complete report and owned commit. Root
  fresh task review, actual isolated migrated PG/packaged network-none default
  smoke/authorized push/exact CI follow; manual live login remains pending.
