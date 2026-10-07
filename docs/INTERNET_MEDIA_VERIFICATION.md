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

## Not yet implemented / not verified

Durable media acquisition jobs/leases/recovery and explicit opt-in worker/UI
wiring; automatic caption attribution at Telegram send; visual-semantic ranking,
cross-language query quality and video acquisition. This provider seam is not
yet an unattended media daemon. No paid service or real publication was tested.

Primary documentation consulted: [MediaWiki imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo/en),
[Commons API](https://commons.wikimedia.org/wiki/Commons:API/MediaWiki),
[reuse conditions](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).
