# Donor video and visible YouTube exclusions — 2026-10-08

## User policy and implemented behavior

Telegram-only Content Studio. No YouTube ingestion, upload or publishing module.
The existing Connections media filter now has an explicit meaning:

- Video unchecked (default): discard before editorial classification or rewrite.
- Video checked: retain the source/caption, including captionless video, in
  MANUAL_REVIEW. No EditorialDecision, fingerprint, candidate or RewriteJob is
  created. Repeated delivery preserves one source; its normal source-created
  audit/outbox event is retained, never a rewrite-requested event.
- Visible YouTube URLs: mandatory deterministic rejection before editorial or
  AI, independent of configurable blocked domains. Includes short/subdomain/
  nocookie, bare/schemeless, encoded/IDNA hosts and sentence punctuation.
- Malformed visible URL parsing/IDNA: fixed INVALID_LINK rejection, not an
  exception or silently accepted default.
- Cached mapped, legacy-unmapped and missing-candidate tasks recheck the latest
  persisted source. Video/YouTube/invalid URL cannot construct a rewrite provider.
  Shared technical guards remain used by review/API, planning and publication.
- Inbox derives rewrite_allowed=false without changing a historical PASS.
  Technical manual hold is not falsely labeled EDITORIAL_REJECT.

No migration, historical deletion, operational flag, real credentials or real
provider call. Existing protected-source/editorial/fact/review gates remain.
REJECT still creates no new RewriteJob and performs zero rewrite calls; retained
historical jobs are not deleted to fabricate this assertion.

## Tests and actual defects

New tests: test_donor_automation_exclusions.py and test_telegram_video_download.py.
Policy initial 19 RED / 7 PASS; after implementation, two retention assertions
incorrectly expected no source-created audit event. Inspection confirmed the
ordinary source event is necessary; corrected assertion excludes rewrite work
while requiring that event. Targeted policy/filter gate then 46 PASS.

Independent skill-required source review found three reproducible issues:
sentence punctuation bypass, malformed URL exceptions in late guards, and Inbox
historical PASS incorrectly projected as rewrite-allowed. Regression 15 RED /
23 PASS; minimal shared fixed-verdict correction, 56 targeted PASS. Follow-up
found Unicode root-dot canonicalization (U+3002/U+FF0E/U+FF61); 6 RED then post-
IDNA trailing-dot normalization. Final video/policy/filter combined 135 PASS /
5.80s. Reviewer made no changes and ran no provider tests.

Frontend: 185 unit tests PASS; Prettier, TypeScript/Vite build PASS; production
dependency audit zero vulnerabilities. Actual FastAPI/current migrated isolated
DB + Vite browser suite: 32 PASS / 49.7s, including GET-only Connections controls,
WCAG AA and no horizontal overflow at 1440/390. Screenshots saved under
`.artifacts/ui-dark-navy/donor-exclusions-20261008/`; both manually inspected,
hint/control layout readable with no redesign. No operational database or demo/
real data mixing.

Exact Ruff source/tests/Alembic/scripts and changed-file format PASS, D: bytecode
compile PASS. Explicit isolated D: Alembic upgrade/check/downgrade/upgrade/check
PASS; no schema drift. Final full backend 1345 PASS /127.92s (45182).
Earlier snapshots: 1327 PASS /107.21s and
1339 PASS /124.41s, before the final six Unicode regressions.

## Bounded raw-video provider foundation

Fake/Telethon/current encrypted-session factory expose a read-only, account-
bound single-video download contract. Immutable DTO deliberately reports
media_validated=false and publication_allowed=false. Exact source identity,
caption/date/document metadata, protection, single-member ownership and MIME
must match before and after download. MP4 bytes are bounded to 16 MiB, chunks
64 KiB, RPC timeout to the existing bounded _run; incomplete/mutated streams
fail. This does not decode video, register an asset, or authorize automatic
rewrite/download/upload/publication. The user's manual/discard policy wins.

71 isolated video tests include actual locally installed Telethon 1.44.0 message
types and _DirectDownloadIter with only transport bytes substituted. Actual SDK
regressions exposed an extra empty EOF chunk for exact 64-KiB/16-MiB streams and
cleanup masking FloodWait/timeout before sender initialization. Correct ceiling
chunk limit and preservation of primary stream failures fixed all four RED.
Ordinary clean-stream close failures still fail; no hidden retries/login.
The public iterator documents bounded requests and explicit close:
[Telethon iter_download](https://docs.telethon.dev/en/stable/modules/client.html#telethon.client.downloads.DownloadMethods.iter_download).
Synthetic arbitrary bytes are not claimed playable or semantically verified.

## Remaining boundaries

Hidden Telegram text-URL entities/inline button destinations are NOT yet captured
in immutable source revisions. They are the exact next independent increment;
do not claim every hidden YouTube link is excluded. No redirect/network lookup
is performed. Full album membership remains unknown and blocks automation.

Manual-only video here means human inspection/retention, not a new one-click
video publishing feature. Windows Docker daemon remains unavailable (named pipe
missing), despite externally recovered healthy C: free space (~22.6 GB). No
daemon reset/start/deploy or operational configuration change occurred in this
increment. Current Windows runtime/persistence is NOT VERIFIED / BLOCKED BY
ENVIRONMENT; Linux CI is separate evidence. PHASE 1 is not complete.
