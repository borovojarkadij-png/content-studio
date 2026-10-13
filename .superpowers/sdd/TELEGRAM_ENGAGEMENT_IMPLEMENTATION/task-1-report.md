# Task 1 implementer report — 2026-10-13

Status: DONE. Base: `0bc8ebd77ec985d43e5e3a349697d6ea7fe8c21b`, branch `codex/dark-navy-ui`.

## Implementation and contracts

- `backend/src/newsflow/domain/engagement.py`: SDK-independent frozen observation, strict canonical signed-range source identities, exact nullable signed64 counts, aware UTC-normalized timestamps and publication-before-observation validation; immutable velocity/reset and acceleration results. Acceleration divides adjacent velocity change by the actual interval midpoint distance, including unequal intervals. No hidden clock or baseline.
- `backend/src/newsflow/providers/telegram_engagement.py`: separate provider protocol, exact seeded deterministic fake, bounded real-SDK reaction aggregation and read helper. Observation is also importable from this module. Fake API is `seed_observation(observation)`; keys include the exact UTC observation timestamp and complete identity; unseeded requests fail, conflicting seeds fail.
- Existing `telegram.py`: one new delegating method only (7 added lines). Existing `telegram_provider_factory.py`: one new delegating method including request validation before `_adapter` (8 added lines).
- `backend/tests/test_telegram_engagement.py`, `backend/tests/test_engagement_rates.py`: 88 synthetic contract/behavior cases. Existing Client is extended only in tests; aggregate fixtures use actual Telethon 1.45 `MessageReactions`/`ReactionCount`/`ReactionEmoji`.

The new read path validates supplied identity/time before constructing any client, requires the provisioned expected user ID, then reuses existing `_run`, `_channel_id`, `_input_channel`. The existing authenticated deadline/FloodWait/session-refresh/finally-disconnect machinery is unchanged. Exactly one `get_messages(peer, ids=message_id)` follows peer resolution; actual raw source ID/chat/date/counters are validated before returning. `date`, not `edit_date`, supplies publication time. Missing counts and absent/partial reaction aggregates remain `None`; complete empty results and explicit zeros remain zero. Reaction vectors are bounded to 100 actual SDK count objects; malformed/overflow counts fail.

Existing TelegramMessage/FakeTelegramProvider/content protocol, accepted frontend, source revisions, Editorial behavior and rewrite path are unchanged. No real credentials, login, Telegram/AI network RPC, sends, live activation, operational queues/volumes, Docker restart, PG mutation, push/PR/merge or main change was performed. Synthetic reads only use injected clients; the factory test uses temporary SQLite and a synthetic encryption key/session. Controller-owned progress/current-state/evidence files were left untouched.

## Exact verification commands and retained raw logs

All Python commands below ran with working directory `C:/Users/borov/Documents/Codex/2026-09-08/files-pasted-by-the-user-software-2/backend` using `C:/Users/borov/AppData/Local/Programs/Python/Python312/python.exe`. Every pytest invocation inserted the SDK directory before importing pytest; the product and tests contain no developer SDK path. The RED/GREEN/focused/covering logs that print Telethon confirm `1.45.0` from `D:/Codex-Recovery/content-studio-20261008/telethon-145/telethon/__init__.py`.

Each test command was executed using this PowerShell capture wrapper, replacing LOG and PYTHON_CODE with the literal values below:

```powershell
$taskLog = 'LOG'; python -c "PYTHON_CODE" *> $taskLog; $taskExit = $LASTEXITCODE; Get-Content $taskLog; Write-Output "NATIVE_EXIT=$taskExit"
```

For longer outputs `Get-Content` used `-Tail 8`, `-Tail 10` or `-Tail 50`; the raw files retain the full output. The covering process yielded a session and was polled to completion; native exit was captured as 0, not inferred from an incomplete progress line.

1. Causal RED, before any product implementation:

```text
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('Telethon', telethon.__version__, telethon.__file__); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_engagement.py', '-q']))"
```

Log: `D:/Codex-Recovery/content-studio-20261008/engagement-task1-red-20261013-01.log`. Native exit **1**, **1 failed**. Existing `fetch_message` succeeded, then `assert callable(getattr(provider, 'fetch_engagement', None)), 'Missing engagement reader'` failed. This is the requested missing behavior assertion, not a collection/import/setup failure. That same test subsequently passed, also proving changing raw views from 100 to 200 leaves content equality unchanged.

2. Broader contracts RED:

```text
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_engagement.py', 'tests/test_engagement_rates.py', '-q']))"
```

First log: `D:/Codex-Recovery/content-studio-20261008/engagement-task1-contract-red-20261013-01.log`. Native exit **2**, **1 collection error**: synthetic `UnauthorizedError(None)` omitted the real SDK required `message` parameter. Corrected the fixture to `UnauthorizedError(None, 'synthetic')`; no product change was involved. This run is **not** counted as causal RED proof.

Corrected log: `D:/Codex-Recovery/content-studio-20261008/engagement-task1-contract-red-20261013-02.log`. Native exit **1**, **86 failed**, before implementation. Collection succeeded and the missing engagement method/domain feature caused the failures.

3. First GREEN:

```text
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('Telethon', telethon.__version__, telethon.__file__); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_engagement.py', 'tests/test_engagement_rates.py', '-q']))"
```

Log: `D:/Codex-Recovery/content-studio-20261008/engagement-task1-green-20261013-01.log`. Native exit **0**, **86 passed in 0.39s**.

4. Type-contract RED before correcting the two unvalidated-object branches:

```text
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_engagement.py', 'tests/test_engagement_rates.py', '-q', '-k', 'unvalidated_object_type']))"
```

Log: `D:/Codex-Recovery/content-studio-20261008/engagement-task1-type-red-20261013-01.log`. Native exit **1**, **2 failed, 86 deselected**: `ValueError` where `TypeError` is appropriate for an unvalidated object. Changed those two branches to TypeError; included in the final GREEN below.

5. Final focused GREEN (same command as item 3): log `D:/Codex-Recovery/content-studio-20261008/engagement-task1-focused-20261013-01.log`. Native exit **0**, **88 passed in 0.52s**, no warnings/skips.

6. Covering regression, run once:

```text
python -c "import sys; sys.path.insert(0, 'D:/Codex-Recovery/content-studio-20261008/telethon-145'); import telethon; print('Telethon', telethon.__version__, telethon.__file__); import pytest; raise SystemExit(pytest.main(['tests/test_telegram_engagement.py', 'tests/test_engagement_rates.py', 'tests/test_telethon_rpc.py', 'tests/test_telegram_provider_factory.py', 'tests/test_fake_telegram_provider.py', 'tests/test_telegram_channel_checkpoint.py', 'tests/test_telegram_channel_difference.py', 'tests/test_telegram_peers.py', 'tests/test_telegram_photo_download.py', 'tests/test_telegram_video_download.py', 'tests/test_telegram_albums.py', 'tests/test_source_observations.py', 'tests/test_source_sync_guards.py', 'tests/test_source_sync_replay.py', 'tests/test_source_deletion_guards.py', 'tests/test_editorial_admission.py', 'tests/test_durable_rewrite_runner.py', '-q']))"
```

Log: `D:/Codex-Recovery/content-studio-20261008/engagement-task1-covering-20261013-01.log`. Native exit **0**, **453 passed in 38.58s**, no warnings/skips. The 453 includes the 88 new tests; these counts are not additive. Covers auth/session/peer CAS/factory, media/content equality, source observation/revision/replay/deletion fences, Editorial admission and durable rewrite guards. Full backend suite intentionally deferred to the single combined Task2 run.

7. Formatting, lint and compilation, with the exact file list:

```powershell
$taskFiles = @('src/newsflow/providers/telegram_engagement.py', 'src/newsflow/domain/engagement.py', 'tests/test_telegram_engagement.py', 'tests/test_engagement_rates.py', 'src/newsflow/providers/telegram.py', 'src/newsflow/services/telegram_provider_factory.py')
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format @taskFiles
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' --version
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' check @taskFiles
& 'D:/Codex-Recovery/content-studio-20261008/ruff-017-20261012/bin/ruff.exe' format --check @taskFiles
python -m compileall -q @taskFiles
```

Initial format log `D:/Codex-Recovery/content-studio-20261008/engagement-task1-format-20261013-01.log`: native exit **0**, 4 files reformatted, 2 unchanged. Initial lint/version log `D:/Codex-Recovery/content-studio-20261008/engagement-task1-ruff-20261013-01.log`: actual **ruff 0.17.0**, native exit **1**, three findings (two TRY004 invalid-object exception types and C408 test fixture dict). Fixed with the type-contract RED above and a literal test dictionary, no suppressions.

Final log `D:/Codex-Recovery/content-studio-20261008/engagement-task1-quality-20261013-01.log`: check native exit **0**, format-check native exit **0**, compile native exit **0**; `All checks passed!`, `6 files already formatted`. `git diff --check` for the two existing-file delegates also exited **0** (only the existing Windows Git LF/CRLF conversion warning, no whitespace errors).

## Self-review and limitations

Read the new domain/provider files and test behavior, and reviewed the existing-file diff: exactly one additive delegation each; existing _run/session/deadline/peer/content paths remain unchanged. Checked canonical/account/message bounds, unknown/reset/equal metrics, unequal midpoint math, bounded real SDK aggregate overflow, frozen results, date-vs-edit-date, pre-client rejection and post-read cleanup. Test doubles lack send/login/download/raw-RPC APIs, so any such unexpected operation would fail; reader tests also verify one exact message read and zero history calls. No outstanding correctness concerns identified.

Task1 does not implement persistence, scheduler, HypeScore or UI. No real-provider acceptance was attempted; controlled live acceptance remains separate. Docker and PostgreSQL were not touched. No full backend suite was run; controller owns the combined Task2 verification and independent review.

## Frozen owned source/test SHA256

Hashes are the verified final working-file bytes before commit, using PowerShell `Get-FileHash -Algorithm SHA256` (Git may normalize line endings in its blob representation):

| File | SHA256 |
| --- | --- |
| backend/src/newsflow/domain/engagement.py | F94C7DBC0015170864D99DC4E01FDAD0AFCAD7CF96BD96A63579EEBF88815327 |
| backend/src/newsflow/providers/telegram_engagement.py | 807AF9E2316E1315BC4ED335144B02DC09C23A65DFEDEAA15DB90F8635D18209 |
| backend/src/newsflow/providers/telegram.py | 233299D82E8855108A332654F3F07C073BC27AD08AA9E696280DE21C84467818 |
| backend/src/newsflow/services/telegram_provider_factory.py | CC059E181E75B032349F5C9BE8FBA6126EF6B3ACC3FC7015F4113B5E022C6BF9 |
| backend/tests/test_engagement_rates.py | BF7499E3CF60EFF4E5A963FBBDC5A33F55DCC1352F216BCE61415C1AD0F49449 |
| backend/tests/test_telegram_engagement.py | 5971A0D4ED091D268C25170918D1275D90DE4B2AA95525F000B1F0F191988659 |

Commit is restricted to these six files and this report. Report hash/commit identity are delivered to the controller after commit, avoiding a self-referential hash.
