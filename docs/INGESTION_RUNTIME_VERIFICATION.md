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

## Pending

Durable donor polling, bounded replay/edit recovery, configurable mapping filters,
encrypted session factory, actual Telethon RPC verification/history and provider
authorization remain separate increments. Real publication remains disabled.
