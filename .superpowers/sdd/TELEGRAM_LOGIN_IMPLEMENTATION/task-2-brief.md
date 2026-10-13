### Task 2: Explicit interactive CLI, migrated integration and operator procedure

**Files:**
- Create backend/src/newsflow/telegram_login.py.
- Create backend/tests/test_telegram_login_cli.py.
- Create backend/tests/test_telegram_login_postgres.py.
- Create docs/TELEGRAM_LOGIN.md.
- Modify .github/workflows/ci.yml, append the new PG test file to the existing
  unattended-postgres migrated test command only.
- Own task-2-report.md in this plan's SDD workspace.

**Interfaces:** Consumes reviewed Task1 interfaces exactly; no Task1 source edits
without controller routing. python -m newsflow.telegram_login exposes main(argv=None)
and CLI module guard. Existing PostgreSQL isolation helper
backend/tests/unattended_postgres.py creates fresh UUID schemas for explicit
synthetic NEWSFLOW_UNATTENDED_POSTGRES_URL only. Root owns actual Docker/image/PG gate.

- [ ] TDD actual CLI entrypoint/private IO. Default/help/malformed invocation
  touches no DB/keyfile/client/network. Default prints LOGIN_DISABLED/exit2;
  help exit0. Enabled requires --enable-login, --account-name, --actor-id,
  optional --expected-user-id, no phone/code/password/session arguments.
  Parser errors must emit only the fixed failure status, never echo supplied
  argv/invalid values; even a forbidden secret-bearing argument stays private.
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
  forbidden/invalid secret-bearing argv with no echoed argument values,
  one-code/2FA success fixedoutput, GetPassWarning refusal, abort and sanitized
  secret-bearing SDK/SQL/config errors, no session artifacts/log leakage.
- [ ] Add explicit isolated migrated PostgreSQL cases using existing strict
  helper's create-only UUID schemas: new insert+outbox/encrypted reopen consumer,
  metadata CAS against independent writer, uniqueness race and audit rollback.
  Missing synthetic URL yields explicit PG-only SKIP, never SQLite-as-PG PASS.
  No public-schema reuse/drop/reset/new fixedschema. Root runs actual PG after
  source review and reports exact new namespaces; implementer does not touch
  operational Docker/old fixtures. Source REJECT/zero-execution invariants remain.
- [ ] Append tests/test_telegram_login_postgres.py to the existing migrated
  unattended-postgres pytest invocation, using its existing
  NEWSFLOW_UNATTENDED_POSTGRES_URL and strict create_postgres_namespace helper.
  Preserve every other workflow job/step/env/command/trigger/permission and
  timeout, including the new Windows native gate. Validate parsed YAML plus
  scoped command delta; root exact hosted run must actually execute PG cases,
  not accept the normal no-PG backend skips as PostgreSQL proof.
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
