# Telegram album observation / fail-closed checkpoint

## Implemented boundary

Read-only `album_window` exists in TelegramProvider, Telethon adapter, encrypted
current-session factory and FakeTelegramProvider. One explicit ID request spans
at most 100 IDs around a validated anchor; existing request/session/user/peer
guards and deadline apply. Missing IDs remain missing, unrelated messages are
not members, sparse member IDs are retained, and captions/media types are kept
in immutable message order. Identical duplicates are folded; conflicting,
foreign, malformed or over-ten-member groups fail closed.

Album identity is the canonical decimal representation of a signed 64-bit
Telegram `long`, not a presumed positive number. Observation explicitly returns
`membership_complete=false` and `rewrite_allowed=false`: a bounded history
window does not prove that all members have arrived or survived deletion.

An individual grouped photo caption must not bypass the group's video/ad/link
constraints. Deterministic filters now return `ALBUM_NORMALIZATION_REQUIRED`
after cheaper unsuitable-content checks. Ingress retains every observed grouped
member, including captionless/video members, as technical rejection without an
editorial decision or rewrite. An old album job cannot bypass via legacy/missing
candidate state; per-output review/planning/media technical guards also reject
unverified groups. Actual review API no longer offers approval for such drafts,
and POST approval returns 409 without changing state or creating jobs.

This is **not complete album ingestion/publication**. Durable group manifests,
membership confirmation/deletion tracking, combined revision identity and
grouped media download/publication remain pending. Do not remove the gate merely
because a window contains two or more photos, ten adjacent IDs, or a quiet delay.

## Verification

2026-10-08: test-first normalization/adapter/ingress/legacy-worker/API failures
reproduced and fixed. Full backend 500 PASS; focused rewrite/API/provider/filter
gate 76 PASS, compile/lint/format and isolated migration round-trip PASS. A test
expecting BLOCKED_TECHNICAL for an absent candidate was corrected to the existing
SUPERSEDED terminal behavior; it still proves zero provider construction and a
false shared technical permission. No ignored database was used or reset.

Actual Windows Docker acceptance is IN PROGRESS, session 23498:
`verify-persistence.ps1 -Project newsflow-verification-albumguards20261008
-ApiPort 18017 -WebPort 15190 -ProductionPort 18097 -CrashRecovery -IngestionGuard`.
Extended create-only fixture checks photo/video group members retain source and
produce zero editorial/rewrite while cursor/partial fan-out recover. Do not mark
it VERIFIED until completion and packaged PostgreSQL drift have actually passed.
Never reseed retained fixtures. Operational network flags remain disabled.

## Primary protocol references

- [Telegram message/grouped_id and protected content](https://core.telegram.org/constructor/message)
- [Telegram long type](https://core.telegram.org/type/long)
- [Telethon read-only get_messages contract](https://docs.telethon.dev/en/stable/modules/client.html)
