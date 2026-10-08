# Guarded original-photo transport

2026-10-08, codex/dark-navy-ui; offline only, no runtime sending enabled.

## Implemented

TelethonPhotoPublisher shares the tested authorization, exact broadcast destination,
permission, nonce and last-moment guard path with text. ConfiguredTelegramPhotoPublisher
reads only a current successful source-photo acquisition selected for the exact
candidate, asset ID/hash/content key and rights. MediaJobReader performs bounded
PNG/JPEG decode/hash checks and repeated current-policy validation. Its database
transaction closes before immutable bytes reach upload_file.

Upload uses the original captured bytes, never a URL/forward or a text-only
fallback. Caption includes the attribution prepared by publication preflight and
is limited to 1024 UTF-16 units. Bound bytes are checked again against the
envelope SHA256 before upload. Only a real InputFile/InputFileBig handle is used
in InputMediaUploadedPhoto + SendMediaRequest with the persisted random_id.
No server-side schedule, Markdown, paid Stars or paid floodskip is requested.

The existing fresh runner guard executes after upload and immediately before the
send RPC. Editorial, source, review, session, rights or file changes therefore
cannot turn prepared media into permission to publish. Upload alone is not channel
publication; a rejected final guard can leave a temporary remote upload, but sends
zero channel requests. No actual uploads were made in these tests.

Confirmation requires the exact outgoing channel/nonce/caption update plus a
nonempty Photo acknowledgement. A text/empty/foreign response is not success.
This proves original bytes at our upload boundary, NOT byte-identical remote
media: Telegram may transform photos. Live visual/media acceptance remains pending.

## Evidence

- Eleven photo contract tests RED before implementation, then GREEN.
- Six configured photo/real-runner tests RED before factory implementation, then
  GREEN; two further durable timeout/rejected-queue regressions added.
- Full 703 backend tests PASS (session 55064), Ruff/targeted format/compile PASS.
  Combined source-photo/text transport targeted gate 52 PASS before the final two
  regressions. Real SQL/fake-network tests prove exact original upload/credit,
  committed SENDING/nonce, atomic receipt and no resend/reupload after timeout.
- Separate DB writer during upload changes editorial/rights/session/file; final
  guard blocks with zero sends. Known invalid/rejected queued source never connects
  or uploads; no synthetic results were promoted to operational records.
- No schema/frontend changes. Prior explicit D: migration round-trip/check and
  frontend 55 unit/23 browser/format/typecheck/build remain separate evidence.

## Limitations / next

Text/photo factories are explicitly injected, not wired to a publication runtime
flag or public send API. Opt-in worker/orchestration and verified update-difference
reconciliation are next. Library illustrations, albums/videos/deletion recovery,
live authorization and whole PHASE 1 acceptance remain incomplete.
Docker Desktop is unable to start after C: exhaustion/containerd read-only failure;
current packaged/operational acceptance is NOT VERIFIED / BLOCKED BY ENVIRONMENT.
Never delete/prune volumes or regenerate keys to work around it.

Contract sources: [sendMedia](https://core.telegram.org/method/messages.sendMedia),
[uploaded photo](https://core.telegram.org/constructor/inputMediaUploadedPhoto).
