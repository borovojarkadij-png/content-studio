# Task 1 — bounded authorization and encrypted provisioning

Date: 2026-10-13. Base: `d7c580a8108a7523bcc5eff6a4d1c68c60e908aa`.
Repository/branch verified before work: origin
`https://github.com/borovojarkadij-png/content-studio.git`, `codex/dark-navy-ui`.
The historical placeholder remote was observed but never used.

## Scope and interfaces

Owned implementation: `backend/src/newsflow/providers/telegram_login.py`,
`backend/src/newsflow/services/telegram_login.py`,
`backend/tests/test_telegram_login.py`, and this report only.
No CLI, API, UI, Compose, schema, dependency, existing provider/parser, worker,
rights, queue, publication or real secret/session changes. No pushes or live calls.
Controller's unrelated documentation/evidence edits were preserved.

Implemented the exact named public interfaces from task-1-brief.md:
`TelegramLoginError`, frozen private-repr `AuthorizedTelegramSession`,
`TelethonLoginAdapter(api_id, api_hash, client_factory=None).authorize(...)`,
frozen private-repr `ProvisioningRequest`, and
`SessionProvisioningService(session_factory, *, master_key_loader, login_adapter)`
with `preflight(account_name, actor_id, expected_user_id=None)` and
`provision(request, *, phone, read_code, read_password)` returning only account ID.

The wrapper validates the existing shared credentials without discovering files.
Client construction occurs only inside authorize after validated phone; service
preflight completes before that construction. A fresh in-memory StringSession,
zero retries/reconnect/flood sleep, disabled updates and isolated disabled logger
are supplied to the client factory. One send-code, one code sign-in, at most one
password sign-in; verified authorized=true, typed nonbot User/positive signed64
identity/exact canonical phone, and SDK-parsed 256-byte authorization key.
Every awaited RPC receives wait_for(15); disconnect receives wait_for(3), always
in finally. EOF/Ctrl-C/cancellation preserve abort and store nothing; RPC and
cleanup errors expose fixed private messages with suppressed exception context.
Manual callback duration has no RPC deadline.

Preflight validates trimmed name/no control or format characters, strict IDs,
existing key/cipher, existing metadata, and captures the stable-key fingerprint
and exact row snapshot. Its transaction closes before input/RPC. Requests are
ephemeral, service-bound, identity-based, frozen and single-use capabilities;
an abandoned request is weakly referenced and contains no master key/session.
Provision revalidates the returned identity/session and key fingerprint, encrypts,
and uses create-only INSERT or exact snapshot conditional UPDATE with rowcount=1.
Different-name user identity and uniqueness conflicts fail without retry.
DISCONNECTED remains the saved status. Account mutation and one minimal
TelegramSessionProvisioned audit event commit in one transaction.

## TDD and actual command outcomes

Runtime: Python 3.12.10 at
`C:/Users/borov/AppData/Local/Programs/Python/Python312/python.exe`.
Every pytest command below ran from the repository's `backend` directory with
this explicit prefix (global Telethon 1.44 was never used):

```powershell
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; sys.exit(pytest.main(ARGS))"
```

`ARGS` was the literal Python list shown below, not an environment variable.
Inspection also printed Telethon `1.45.0` and its resolved path
`D:/Codex-Recovery/content-studio-20261008/telethon-145/telethon/__init__.py`.

1. `['tests/test_telegram_login.py','-q']`: native exit 1, **1 failed**.
   Meaningful first RED: successful durable-encryption/reopen/audit scenario
   reached actual service scaffold and failed at its explicit provisioning
   refusal, rather than collection/import. The service/cipher/SQL were real;
   initial unwritten authorization interface was then replaced by the actual
   adapter with only synthetic RPC substitution before implementation.
2. `['tests/test_telegram_login.py','-q','--tb=short']`: native exit 1,
   **69 failed, 4 passed**. Fixture defect: hand-split fake StringSession had
   incorrect serialized length. Corrected the literal using offline SDK format;
   this is not claimed as meaningful RED.
3. Same command after fixture repair, before implementation: native exit 1,
   **52 failed, 21 passed**. Causal missing adapter/durable behavior, missing
   preflight rejection, absent RPC/deadline handling. Some deadline scaffolding
   failures referenced missing asyncio; those are not claimed as causal proof.
4. Same command after adapter/service implementation: native exit 1,
   **1 failed, 72 passed**. Real bug: EOFError was sanitized rather than preserved
   as an operator abort. Fixed the exception handling without weakening the test.
5. Same command: native exit 0, **73 passed in 5.86s**.
6. Same command after rollback/invariant-tripwire test additions: native exit 1,
   **98 errors**. Test import misspelled the existing OpenRouter provider class;
   corrected from inspected source. Not meaningful production RED.
7. Same command after import repair: native exit 1, **78 failed, 20 passed,
   94 errors, 66 warnings**. Test-only issues: a socket tripwire also blocked
   Windows asyncio's own loopback socketpair; the seeded revision table is named
   incoming_post_revisions, not content_revisions. Allowed only internal loopback
   connect and corrected the invariant allowlist. No external call was attempted.
8. `['tests/test_telegram_login.py','-q','--tb=short','-x']`: native exit 0,
   **98 passed in 8.91s**.
9. `['tests/test_telegram_login.py','-q','--tb=short','-k','sdk_child_loggers']`:
   native exit 1, **1 failed, 99 deselected**. Meaningful RED discovered in source
   self-review: standard Logger.getChild bypassed the isolated parent and emitted
   a synthetic private log to root. Added isolated child handling in a private
   Logger subclass; no global logger reconfiguration or provider weakening.
10. `['tests/test_telegram_login.py','-q','--tb=short']`: native exit 0,
    **100 passed in 8.88s** after the logger fix.
11. Covering command, with the same explicit Telethon prefix and an extra printed
    resolved SDK version/path:
    `['tests/test_telegram_login.py','tests/test_telegram_provider_factory.py',
    'tests/test_session_cipher.py','tests/test_account_health.py',
    'tests/test_telegram_configuration_service.py','tests/test_telethon_rpc.py',
    'tests/test_telethon_adapter.py','-q','--tb=short']`:
    native exit 0, **160 passed in 11.48s**, no skips/warnings/failures.
12. Final focused command after strengthening test-only independent engine reopen
    and password-reader counts:
    `['tests/test_telegram_login.py','-q','--tb=short']`: native exit 0,
    **100 passed in 8.87s**, no skips/warnings/failures. No production edits after
    the covering pass.

Tests use real service/SQLAlchemy/file SQLite/SessionCipher/adapter. Only Telegram
RPC/terminal readers are substituted; targeted encryption/SQL/audit/commit fault
injection deliberately raises at those real boundaries to prove rollback.
Typed synthetic Telethon User and SentCode fixtures and a literal nonlive session
exercise the SDK serialization boundary. Timeout tests retain and assert actual
15/3 arguments while shortening waits around hanging synthetic RPC coroutines.
Consumer proof creates an independent Engine/sessionmaker and independently
supplied cipher, then actually verifies through existing ConfiguredTelegramProvider
using an authorized RPC fake; it does not stop at standalone decrypt assertions.

All SQLite store cases seed immutable synthetic source text and REJECT with
rewrite_allowed=false; teardown verifies both survive and every other job,
classification, semantic, publication, usage, media and rights table stays empty.
OpenAI/OpenRouter rewrite and external socket calls have failing test tripwires;
rewrite/external calls are zero. The RPC fake has no send/join/rights/AI methods.

Covered: one-code/2FA, credential/configuration rejection, invalid phone/code/
password/session/zero auth-key/ID/bot/phone/expected identity, invalid/expired code,
FloodWait, per-RPC deadline, cleanup failure/timeout, abort with cleanup failure,
key mismatch, preflight existing-session/health/cooldown refusal, compatible fill,
repeat refusal, independent rename/health/session/user/cooldown/delete conflict,
different-name identity, concurrent creation, copied/replayed/cross-service request,
and new/fill rollback at encryption/account SQL/audit/commit.

## Static verification

From repository root, all scoped paths are the three owned Python files above.

```powershell
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe --version
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe check backend/src/newsflow/providers/telegram_login.py backend/src/newsflow/services/telegram_login.py backend/tests/test_telegram_login.py
& D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe format --check backend/src/newsflow/providers/telegram_login.py backend/src/newsflow/services/telegram_login.py backend/tests/test_telegram_login.py
python -m compileall -q backend/src/newsflow/providers/telegram_login.py backend/src/newsflow/services/telegram_login.py backend/tests/test_telegram_login.py
git diff --check
```

Actual Ruff is 0.17.0. Initial lint/format native exit 1 identified import/dict/
format issues and deliberate private-boundary broad catches. Applied safe import
fixes, manually changed dict literals, narrowed credential/SDK/capability catches,
and documented privacy/primary-abort reasons for remaining BLE001 suppressions.
`ruff check --fix backend/tests/test_telegram_login.py --output-format concise`
initially exited 1 (5 fixed, 3 dict findings remained); formatter then exited 0.
Final check, format check (3 already formatted), compile and diff check each exit 0.
Diff check emitted existing unrelated controller-file CRLF notices only.
Final `git diff --cached --check` also exited 0; staged names/stat confirmed
exactly the two owned modules, test file and this report before commit.

## Frozen implementation hashes

SHA256 of working-file bytes after final tests/static checks:

| Owned path | SHA256 | Git blob |
| --- | --- | --- |
| backend/src/newsflow/providers/telegram_login.py | 3e2252fa3db69e22e4024f30d4a9f65b452d497dec79157405913bf7028b9d45 | dfb9b46840d02c02df9f0239c59be448be341252 |
| backend/src/newsflow/services/telegram_login.py | be44ebffe2418300d508c14d51e3dcfb1f8d5a923e491b0c80ceaf6be78dd9d7 | 8588e28398009defa7dd8ab2d9e6e088c6b6d288 |
| backend/tests/test_telegram_login.py | 322e58c4d42b007493ca2a5170421c3e5bcb2f36497a25e12dd985dd39bd6e5e | b2997dd9eafcbc6d3d1d84b3e176f34e5a79bf41 |

The report's own hash/commit is supplied to the controller externally to avoid
self-referential hashing. Its ignored path is force-added explicitly.

## Source self-review and limitations

Read the entire final owned source/tests and checked spec branch by branch:
client creation sequencing, validation at both boundaries, single attempt counts,
private repr/logging/error handling, primary abort preservation, key custody,
closed preflight transaction, create-only uniqueness, conditional SQL matching
every required snapshot field, audit payload minimality and atomic commit.
The realistic missing-encryption/INSERT/CAS/key-check/event/cleanup/private-logger
mutations are caught by independently derived effects or fault injection.
No helper/subagent/reviewer was invoked. Independent controller review remains.
Applied TDD/writing-good-tests and NewsFlow security/migrations/runtime guidance;
verification-before-completion was read before final evidence/commit review.

No remaining scoped production defect is known. Full backend testing is explicitly
deferred to Task 2's combined deliverable. Migrated PostgreSQL concurrency/audit,
packaged CLI no-network smoke, and manual real Telegram login/restart acceptance
are pending and are not claimed by SQLite/synthetic RPC tests. Existing separately
running backup CI validates its frozen backup code, not these new files.
Application-level invocation counts do not attest SDK internal network-call counts.
Manual input is operator-paced. A remote sign-in cannot be undone by SQL rollback;
this implementation never automatically logs out/revokes. Stable external key-file
custody remains an operator responsibility; the service rechecks the supplied key
immediately before encryption/persistence, not arbitrary future filesystem changes.
