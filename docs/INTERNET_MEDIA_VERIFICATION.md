# Free internet-image acquisition boundary

## Implemented

`CommonsImageProvider` queries Wikimedia Commons File namespace with bounded
topic words derived from source text; no API key, LLM, paid search or arbitrary
URL input. Search results are suggestions for **illustrations**, not evidence
that a photograph depicts the actual event. Russian terms are supported by the
query contract, but cross-language/semantic visual relevance is not verified.

Only explicit CC0 1.0 and CC-BY 3.0/4.0 metadata with a matching canonical license
URL, author/source attribution and no declared additional restrictions pass.
CC-BY-SA, NC/ND, unknown and generic public-domain declarations are not inferred
as permission. This is a conservative metadata filter, not legal clearance of
personality/trademark rights or proof that the uploader owns the image.

Downloads use HTTPS on the exact Wikimedia upload host/path, no redirects,
credentials, alternate ports or arbitrary query parameters. Imageinfo's known
UTM tracking is stripped. Metadata responses are limited to 512 KiB; photos to
16 MiB and 25 million pixels. Each network operation uses a 10-second socket
timeout and checked read deadline (a blocked read can take one additional socket
timeout). Pillow verifies and decodes single-frame PNG/JPEG, checks dimensions,
MIME and declared byte size, and rejects malformed/bomb/animated data.

`InternetMediaAcquisition` operates only on a currently reviewed READY/SCHEDULED
candidate in `LICENSED_LIBRARY` mode. It checks current job/editorial constraints,
latest source revision and manual/qualified automatic approval before searching
and after downloading. It does not rewrite, approve, schedule or publish.
Locks are released during external I/O. Changes in source/draft/editorial/policy
prevent registration. `REUSE_SOURCE` never silently searches or substitutes.

The service writes only its managed `internet/` directory under the existing
persistent media root. Filenames bind SHA-256 content and attribution; provider
titles cannot control paths. Staged bytes are fsynced and atomically linked
create-only; existing assets are never overwritten. The registry stores the
exact author/license/version/source credit, digest and topical tags. A crash
after file creation but before registration can leave a reusable unregistered
file; a crash during staging can leave an orphan staging file. No broad cleanup
is performed. Durable acquisition jobs/reconciliation are the next increment.

## Verification on 2026-10-08

- 32 new provider/acquisition tests PASS, including redirects/SSRF destinations,
  unsupported/mismatched licenses, metadata/mime/size/pixel bounds, malformed
  pictures/catalogs, immutable existing bytes, duplicate registration and
  editorial/source changes during download. Full backend: **346 PASS**, lint,
  format and compile PASS. Existing frontend gate remains 26 units / 19 browser
  tests PASS from the immediately preceding semantic-runtime checkpoint.
- Actual free live search `factory building` returned an eligible CC-BY 3.0 file
  (Commons page ID 12042189). Download of 2,643,989 bytes verified/decode PASS.
  Bytes remained in process memory: no operational media/state was changed.
  Paid AI calls and Telegram publications: **0**.
- Live metadata exposed two issues reproduced in failing tests and fixed:
  canonical license URLs omit a trailing slash; imageinfo adds UTM query fields.
- Semantic-runtime commit `59f4d4817dc248c191e489ec9f0d222661e994d6` CI run
  `37692242447` completed SUCCESS in all four jobs. This precedes this media change.

## Durable runtime increment

Migration `e93b0a4217d6` adds durable jobs with immutable candidate/binding digest,
two committed attempts maximum, 60-second recoverable leases and selected-asset
FK. Downgrade refuses populated history. Expired tokens cannot search, download,
register or select; registry and completion commit together. A final lease expiry
rolls back registration without claiming filesystem/DB distributed atomicity.
HTTP 429/5xx/connection failures get one persisted 30-second retry; malformed
metadata/photos and exhausted budgets fail terminally. NO_MATCH/BLOCKED/FAILED
do not repeatedly enqueue. `NEWSFLOW_INTERNET_MEDIA_ENABLED=0` is the default;
enabling it still does not authorize or execute Telegram publication.

GET `/api/telegram/publication-candidates/{id}/media-acquisition` is read-only:
state/attempts/history plus current `selected_allowed`, reason and qualified asset.
It never performs network calls. A historical SUCCEEDED row remains in history
after a reject, but stale/blocked/missing-byte assets are not offered as usable.

Latest local gate: **361 backend PASS**, lint/compile/format and isolated actual
upgrade/check/downgrade/base/re-upgrade/check PASS; 19 Chromium E2E passed again.
Additional tests cover expired owners, reject after enqueue, expiry during
download/disk-write, persisted bounded retries, atomic result rollback, downgrade
history protection and actual API queued/success/reject/missing-file projections.
Windows Docker media-job recovery **PASS** in `newsflow-verification-media20261008`
(ports 18010 / 15183 / 18090):

```powershell
./scripts/verify-persistence.ps1 -Project newsflow-verification-media20261008 -ApiPort 18010 -WebPort 15183 -ProductionPort 18090 -CrashRecovery -RewriteRecovery -SourceGuard -SemanticGuard -MediaGuard -RewriteProvider OPENROUTER
```

Actual build/startup/migrate/proxy-IP-change/Redis-loss/PostgreSQL-crash checks
passed. Rewrite and semantic expired-claim recovery passed, then an unfinished
media claim survived another real down/up. Attempt 2 fenced attempt 1 before
requests; injected synthetic photos were atomically registered/selected. Asset
bytes/hash/CC0 test provenance and job completion survived worker restart. Actual
GET status API reported usable success, then disabled selection after release
revocation; acquisition made zero requests after revocation. There were no live
AI/Telegram/media-provider calls in this drill. It uses a real decoded synthetic
PNG, not a Commons permission claim. Fixture volumes/history retained, stack stopped.
Current PostgreSQL drift checks passed there and on the rebuilt healthy operational
stack. Socket-rate retries/read API changes after the initial fixture image build
passed local regressions and were packaged operationally; CI tests latest images.
Provider-only commit 5faf7227 CI run 37692967241 passed all four jobs.

Remaining: explicit UI controls, automatic caption attribution at Telegram send,
visual-semantic ranking, cross-language query quality and video acquisition.
No paid service or real publication was tested.

Primary documentation consulted: [MediaWiki imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo/en),
[Commons API](https://commons.wikimedia.org/wiki/Commons:API/MediaWiki),
[reuse conditions](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).
