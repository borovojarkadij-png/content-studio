# Durable Telegram engagement sampling — next approved-scope increment

## Outcome and current evidence

The approved automated planning/Hype scope needs real observations over time.
Accepted engagement contracts/history preserve aggregates separately from source
content, and donor-relative scoring is being implemented. Neither feature yet
collects observations in the running worker. Add bounded, restart-safe sampling
without admitting content, changing editorial decisions, or sending messages.
This document is design only until its own implementation/review gates execute.

Existing boundaries inspected: `worker.py` explicit opt-ins and bounded ticks;
`donor_ingestion_runner.py` committed leases/network outside transactions;
`source_revisions.py` deletion and synchronization quarantine;
`telegram_provider_factory.py` encrypted session/peer CAS and read-only delegate;
`telegram_engagement_history.py` incoming-row lock and caller-owned transaction.
TelegramMessage has source edit time, not guaranteed original publication time:
never relabel it or ingestion created_at as original publication time.

NewsFlow product-discovery/architecture-evolution/runtime-qa guide this small
new subsystem. The human's approved architecture, original1/5/10/20/30/60-minute
sampling requirement and explicit overnight autonomy supersede additional
intermediate approval ceremonies. Accepted UI stays unchanged.

## Options and selected boundary

Ephemeral timers lose progress at restart. A Redis-only schedule violates durable
truth. Reusing rewrite jobs conflates read-only metrics with content authority.
Choose one PostgreSQL sampling job per canonical incoming source, independent
from RewriteJob/publication/outbox authority, with a default-disabled worker seam.
Redis is unnecessary. Rollback is to disable that seam; historical observations
and completed/failed jobs are retained. Downgrade refuses retained job rows.

## Durable job contract

Add `TelegramEngagementSamplingJobModel` in existing models and one additive
migration following actual accepted head. Fields:

- incoming_post_id PK/RESTRICT FK; immutable source association;
- state QUEUED/RUNNING/SUCCEEDED/BLOCKED/FAILED;
- step exact int0..7;0 is initial discovery,1..6 are publication-age thresholds
  60,300,600,1200,1800,3600seconds;7 is completed;
- attempts exact int0..3 for the current step; a successful advance resets it;
- available_at aware UTC, created_at aware UTC, claim_token nullable canonical
  UUID, lease_expires_at nullable UTC; RUNNING requires token+lease;
- expected_user_id nullable signed64 positive and session_digest nullable64hex,
  present while RUNNING; no plaintext/session/credential storage;
- last_error_code nullable bounded private code, never raw exception text;
- missed_windows exact int0..6, accumulated only when scheduled thresholds were
  skipped; observation timestamps always remain their actual acquisition time.

QUEUED has no claim/session/lease fields and step0..6; RUNNING has all four
claim fields and step0..6/attempts1..3; SUCCEEDED has step7/attempts0 and no
claim fields. BLOCKED/FAILED retain step0..6 and attempts0..3, clear all claim
fields, and require a private error code. An error code is nullable or one of
WAIT_SYNC, WAIT_COOLDOWN, RETRY_PROVIDER, FLOOD_WAIT, SOURCE_UNAVAILABLE,
SESSION_UNAVAILABLE, INVALID_OBSERVATION, ATTEMPTS_EXHAUSTED, INVALID_SCHEDULE.
Expected user is nullable only outside RUNNING; token/digest are never repr/log
fields. All dates are stored UTC; naive restoration is internal SQLite-only.
Row-local time coherence: available_at>=created_at; RUNNING additionally requires
lease_expires_at>available_at, using actual timestamp ordering. The exact60-second
lease duration belongs to runner validation, not a SQL wall-clock assumption.

Named state/step/attempt/lease/counter constraints, guarded immutable association
and delete refusal follow existing dialect conventions. No old data backfill or
source/history trigger weakening. Empty downgrade works; populated refusal
retains all rows/version. Existing strict migration-target protection applies.
Allowed transitions: QUEUED→QUEUED/RUNNING/BLOCKED/FAILED;
RUNNING→RUNNING/QUEUED/SUCCEEDED/BLOCKED/FAILED. Terminal rows never revive or
mutate. Initial INSERT is QUEUED/step0/attempts0/missed0. Immutable creation
time and association, step/missed counters never decrease. Attempts may reset
only when step advances, otherwise they never decrease. Enforce these retained
identity/terminal/counter rules in migration triggers as well as runner code;
SQLite INSERT OR REPLACE and PostgreSQL TRUNCATE cannot erase retained jobs.

## Admission and schedule

`TelegramEngagementSamplingRunner(session_factory, *, provider, clock)` owns
short transactions, not the provider's network lifetime.
`enqueue_window(*, now, after_id=0, limit=16)` returns frozen
`EngagementSamplingAdmission(cursor, queued_ids)`; canonical positive signed64
source IDs, cursor0allowed, exact limit1..16 and aware UTC clock required.
Scan at most16incoming IDs ordered ascending, wrap at0 when exhausted. Admit only
canonical existing sources created within the last60minutes, configured same
account/broadcast donor with at least one mapping, CONNECTED encrypted account,
no future cooldown, deletion or unresolved synchronization gap. Require an
existing content revision; never fabricate incoming posts. Existing job is
idempotent/no reset. Initial job is QUEUED/step0/attempts0/available_at=now.

Original publication time is learned only from the accepted provider response or
existing immutable engagement source. Initial observation may already be late;
that does not become a fabricated1-minute observation. After each successful
actual observation, select the first later threshold strictly greater than its
actual publication age. Skip elapsed intermediate thresholds, add their count
to missed_windows, and never make catch-up RPCs with historical observed_at.
If no later threshold exists, set SUCCEEDED/step7. Original date older than
60minutes therefore costs at most the single discovery observation, not six
fabricated historical probes. Overflowing schedule dates fail closed privately.

For old step s, count skipped threshold indices i with max(1,s+1)<=i<=6
and threshold[i]<=actual_age. The current scheduled step itself is fulfilled
by this successful acquisition even when late; discovery step0 fulfills none
of the six thresholds. Set next step to the first larger index whose threshold
is strictly greater than actual_age, or7. Thus discovery at age60seconds skips
index1 and schedules step2; step1 acquired at age61seconds skips none; step1
acquired at age601seconds skips indices2 and3 and schedules step4. No repeated
counting or decrement of missed_windows. Attempts reset only on advancement.

Pure schedule validation: a scheduled step1..6 cannot be fulfilled before its
own publication-age threshold; such input raises ValueError. Discovery0 has no
minimum age. Existing missed_windows must be exact0..6, and accumulated totals
above6 fail rather than clamp. Step7 is output-only, never an advance input.

## Claim, execution and recovery

`claim_next(*, now)` returns nullable frozen `EngagementSamplingClaim` with source
identity, step, token, expiry, expected user and hidden session digest.
Exact fields: incoming_post_id:int, account_id:str, donor_identifier:str,
message_id:int, step:int, token:str, lease_expires_at:datetime,
expected_user_id:int, session_digest:str (repr=False). Revalidate every claim,
including a forged frozen instance, before SQL/provider use. execute/run_next
return only IDLE, SAMPLED, SUCCEEDED, WAIT_SYNC, WAIT_COOLDOWN, RETRY_PROVIDER,
FLOOD_WAIT, BLOCKED, FAILED or STALE_CLAIM; no provider exception detail.
Due QUEUED jobs and expired RUNNING jobs are eligible; attempts3 is terminalFAILED
without another RPC. Resolve candidate ID without holding a job lock, then lock
incoming first, job second, account third, matching history's incoming-first
write order; SKIP LOCKED where supported. Revalidate canonical source/config/
mapping/deletion/sync/account/session/cooldown freshly. Temporary cooldown/sync
wait retains QUEUED with next available time and no new attempt. Permanent
missing/moved/deleted identity or invalid session yields BLOCKED; no automatic
reauthorization or terminal revival. A claim commits token/60-second lease,
current session digest/user and incremented attempt before external IO.

`execute(claim)` rechecks ownership/current permission in a fresh short
transaction, closes it, samples `clock()` as actual observed_at, then invokes
exactly one `fetch_engagement` outside any DB transaction. Response is completely
reconstructed/validated and must match identity and exact requested timestamp.
The execution clock must be at least claim.lease_expires_at minus60seconds and
strictly before its expiry; backwards/pre-claim time or expired time is stale,
not permission to fetch/finalize. Resample actual clock after acquiring final
locks so time spent waiting for a row cannot extend a claim's authority.
No text rewrite/classifier/media/download/send/login/join RPC. Final transaction
locks incoming/job/account in the same order, rechecks token/unexpired lease,
session/user/config/health/source and original publication identity, then calls
accepted TelegramEngagementHistory.record() and advances the job atomically.
Lost/stale owners return STALE_CLAIM without storing or advancing. Legitimate
provider session refresh is conservative: changed ciphertext requires a fresh
claim, not assumed equivalence; unchanged adapter sessions are not rewritten.

`run_next(*, now)` claims at most one job and executes at most one provider call.
Persist TimeoutError/ConnectionError/OSError as QUEUED/RETRY_PROVIDER with30-second
delay; after third attempt FAILED. FloodWait persists account COOLDOWN and the
full required future delay (overflow fails privately), preserving an existing
longer cooldown; never retry early. SessionUnavailable sets SESSION_INVALID and
BLOCKED only if claim/session/user still match; stale errors cannot clobber newer
health. LookupError missing source and malformed/provider-conflict errors become
BLOCKED with bounded private codes. SQL interruption leaves committed lease for
restart recovery; no rollback of an unrelated caller or deletion of history.
No successful result or retry can change source text/revision/editorial/rewrite/
usage/outbox/publication state. REJECT remains rewritefalse/RewriteJob0/calls0.

## Default-disabled worker integration

Separate `services/telegram_engagement_tick.py` offers frozen
`EngagementSamplingTickResult(outcome,cursor,queued_ids)` and
`run_telegram_engagement_tick(session_factory, *, now, enabled=False, cipher=None,
provider=None, credentials_path=None, cursor=0, clock=...)`.
Exactbool enabled only; disabled returns without DB/credential/provider IO.
Enabled requires stable cipher; injected synthetic provider needs no credentials.
Otherwise reuse existing explicit Telegram credentials loader and configured
encrypted provider; never discover keys, login or create authorization.
One bounded admission window and one runner execution per tick.

Main uses exact0/1 `NEWSFLOW_TELEGRAM_ENGAGEMENT_ENABLED`, default0, includes
its cipher prerequisite and calls the seam after ingestion/sync work. Private
interruption logging only, no sessions/text/digest. No Compose flag is enabled,
no running worker is changed, and no unrelated opt-in is required or altered.
Current source quarantine and account verification remain mandatory.

## Verification / acceptance

Meaningful causal TDD followed by migrated synthetic SQLite and strict fresh
PostgreSQL tests: actual-time schedule and missed thresholds, originaldate versus
edit/ingestion time, duplicate admission, concurrent claim/expired lease, committed
attempt limits, out-of-order/stale/error finalization, session/user/config drift,
FloodWait/retry/health, missing/invalid counters and source/pub conflict, atomic
history+job rollback, restart/double reopen, downgrade refusal and no plaintext.
Instrument actual transaction ownership around the fake network operation;
no transaction may remain open during its callback. REJECT0jobs/0rewritecalls
tripwire throughout. No URL fallback/schema deletion/real account/AI/publication.
Append new PG tests once to existing CI, no checks removed. Root actual owned
WindowsPG and packaged synthetic restart acceptance after independent reviews;
one combined backend after source tasks, exact-generation CI and cross-task review.
Persistent user policy controls and candidate-consumer ranking still follow
separately; these observations do not constitute live qualification or PHASE finish.
