# Data flow

## Telegram

1. Telethon receives a donor message and persists immutable source identity.
2. Technical filters reject disallowed media, links, advertising and malformed data.
3. Exact duplicates are rejected before any classification cost.
4. `EditorialGate` records `PASS`, `REJECT`, or `MANUAL_REVIEW` with reasons.
5. Only `PASS` may create rewrite work through a transactional outbox.
6. Rewrite validates facts and creates a candidate publication.
7. Scheduler applies limits, TTL, timezone, quiet hours and locks.
8. Moderator approves; publication revalidates current hard constraints before send.

## YouTube (historical contract — out of scope)

URL import → metadata/transcript when available → shared content analysis →
editorial decision → channel matching → editable schedule plan. No live YouTube
transport is implemented. The user excluded YouTube from the entire current
Content Studio deliverable on 2026-10-08; this flow is historical context, not
a remaining task or permission to implement it.
