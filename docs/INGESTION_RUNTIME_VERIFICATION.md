# Telegram ingestion runtime verification

## Editorial/source safety checkpoint — 2026-10-08

Durable ingress defaults to **unknown**, not fabricated neutral classification.
Unknown/invalid sentiment or framing produces `MANUAL_REVIEW`, disables rewrite
and persists immutable text for the moderation inbox. Trusted explicit annotations
remain an internal domain contract, not a public permission to auto-classify text.
The current deterministic gate applies policy to annotations; it is **not** an
implemented or qualified semantic text classifier. Live automation must not
declare unclassified source material neutral or bypass this boundary.

Editorially rejected and unclassified source observations are retained, with no
rewrite job/candidate/rewrite-request event. An `incoming_post.created` or
`content_revision.created` event is an observation, not an AI instruction.

Known-source edits are persisted even when technical filters or mapping exact
dedup reject them. Otherwise the old approved revision misleadingly remains
current. Regression tests reproduced that bypass before the fix. Existing
downstream source-freshness checks now see the newer blocked revision and fence
old rewrite/review/planning paths. Cheap technical rejection and exact dedup
still precede editorial evaluation; this increment makes no AI/network calls.

Local verification: targeted regressions passed; full backend gate recorded in
CURRENT_STATE. Fake/classification fixtures explicitly annotate synthetic allowed
content; test defaults no longer manufacture a PASS. No live Telegram acceptance
or automatic model qualification is claimed.

## Durable polling checkpoint — 2026-10-08

New-message history has a persistent per-donor high-water mark, 60-second lease,
fresh locked ownership checks and bounded 1–100-message pages. Network history is
outside DB transactions. Each configured mapping commits before progress advances;
a crash between mapping commits replays the same message without duplicating
rewrite jobs. Only canonical account/channel identities and strictly increasing
bounded provider results are accepted. FloodWait/cooldown and retry delays persist.

Current mapping intake uses a stable identity/mapping hash bucket (not an exact
quota guarantee); zero percent performs no editorial/rewrite work. Current output,
delay, priority and media intent are read within the ingestion transaction. Target
mix percentages are still configuration, not yet a realized planner quota.

Actual Windows Docker Desktop procedure completed:

```powershell
./scripts/verify-persistence.ps1 -Project newsflow-verification-ingestion20261008 -ApiPort 18011 -WebPort 15184 -ProductionPort 18091 -CrashRecovery -IngestionGuard
```

Build/dev+production startup/migrations/health/IP-change proxy recovery,
Redis/worker restart, PostgreSQL SIGKILL and Redis loss passed. The ingestion probe
retained a partial mapping commit and unadvanced cursor through actual down/up;
expired owner was fenced, missing fan-out recovered, REJECT and MANUAL_REVIEW
remained non-rewriteable and history survived another worker restart. Actual
PostgreSQL schema drift check passed. Isolated stack stopped with volumes/history
retained. Never rerun its seed. No Telegram/AI network call or publication occurred.

## Read-only Telethon execution

The adapter now performs `connect` + `is_user_authorized`, not merely a local
session-presence check. It never calls start/sign_in/send_code or publication.
History is bounded/ascending, verifies returned chat identity, uses no hidden
FloodWait sleep/retry and has a 15-second RPC deadline plus 3-second disconnect
bound. Unsupported document media is not relabelled as text. Contract tests use
an injected async client; this is NOT live authorization evidence.

The factory decrypts the current PostgreSQL session with the existing stable key.
Session refresh is encrypted/persisted with compare-and-swap protection before a
history request and after success; concurrent manual replacement is not overwritten.
Health releases its DB lock before the RPC/refresh callback and rechecks concurrent
cooldown after it. Regressions reproduced both the lock and lost-cooldown hazards.

An explicitly opt-in worker polls at most four eligible configured donors per
tick. Default `NEWSFLOW_TELEGRAM_INGESTION_ENABLED=0` remains unchanged operationally.
Unclassified text remains manual review, not automatically neutral. The optional
`compose.telegram.yaml` mounts ONLY a separately provisioned Telegram JSON secret;
it is not required by the default or synthetic verification stack and does not
generate credentials. JSON contract: `api_id` positive signed-32-bit integer,
`api_hash` 32 hex characters. Duplicate fields/invalid/oversized input fail without
echoing values. Host source: `NEWSFLOW_TELEGRAM_CREDENTIALS_SOURCE`; runtime mount:
`/run/secrets/telegram_credentials`. No actual credential file was provisioned.

Primary adapter documentation: [Telethon client methods and bounded history](https://docs.telethon.dev/en/stable/modules/client.html),
[authorization methods](https://docs.telethon.dev/en/stable/quick-references/client-reference.html).

## Remaining limitations / external prerequisites

- Recent polling now rereads the latest 50 donor messages on subsequent polls.
  It detects edits inside this bounded window without resetting the new-message
  cursor. Older edits and deletions outside/inside the window are NOT fully
  recovered; complete Telegram update-difference recovery remains pending.
- StringSession stores authorization, not the entity/access-hash cache. A numeric
  donor absent from the client's resolvable entity cache can fail; persistent
  donor resolution/access-hash wiring is still required. Never label that success.
- Configurable mapping-specific domain/media/ad policy persistence, real text
  classification/manual review mutation and full album/media ingestion are pending.
- External Telegram api_id/api_hash, explicit authorization/session provisioning
  and live restart verification are missing. No user action is requested one-by-one.
- Live AI qualification remains blocked by usable credentials; synthetic fixtures
  do not qualify operational models. Real publication remains disabled.

## Source observation checkpoint — 2026-10-08

Revisions retain source media type, album ID and UTC update timestamp. Existing
migrated rows receive `unknown` media and NULL time, not invented metadata.
Media-only edits create new revisions. Older or missing timestamps cannot replace
a known timestamped source. Conflicting payloads at an equal timestamp invalidate
the old revision and require manual review, including a packet without an edit
flag. Rejected edits create no rewrite for their new revision. Album identifiers
are preserved; this is not yet full album batching/download/publication.

Backend 414 tests, lint/compile/format and isolated migration upgrade/check/
downgrade/base/re-upgrade/check PASS. Populated metadata downgrade refuses loss.
Windows Docker acceptance PASS in `newsflow-verification-source-observation20261008`
(ports 18012/15185/18092; CrashRecovery + IngestionGuard): baseline persistence,
partial fan-out recovery, then same-caption video/album/timestamp edit persisted
through another real down/up. Old revision stayed stale, no editorial/rewrite was
created for the technical rejection. PostgreSQL drift passed; fixture stopped
with volumes/history retained. The missing-edit-flag regression was added/fixed
after the fixture image build and passed locally; latest operational rebuild and
next CI package it separately. No live providers or publication were exercised.

A separate guarded script `docker_telegram_health_probe.py` also passed on actual
fixture PostgreSQL: health released its row before an injected authorization RPC,
encrypted session refresh committed through a separate transaction, concurrent
120-second FloodWait survived the returned success, disconnect completed. A
2-second lock timeout makes a reintroduced deadlock fail promptly. This is actual
DB concurrency plus injected RPC, **not** actual Telegram login.
