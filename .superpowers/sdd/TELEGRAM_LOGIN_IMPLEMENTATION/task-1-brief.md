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
