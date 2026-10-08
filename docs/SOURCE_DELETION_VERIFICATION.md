# Durable source deletion guard

2026-10-08; `codex/dark-navy-ui`, parent
`2d744c20bf5adcb2a5e770db505fb7e95459e3e7`, correct origin
`borovojarkadij-png/content-studio`. No operational database migration or provider
activation was performed.

## Implemented contract

Validated bounded channel differences persist permanent account/channel/message
tombstones, including unknown source identities. One transaction records the whole
deletion vector and exactly-once `source.deleted` outbox events. Replays retain
first observation time and monotonically increase observed pts; insertion races
retry the entire transaction at most three times. Lost lease guards fail before
writes. This is not delivery acknowledgement evidence.

Historical source revisions, editorial decisions, rewrite drafts/jobs and
publication receipts are never deleted or relabeled. Shared source freshness
checks query current tombstones, including in already-open sessions. Ingestion
rejects deleted identities before mapping filters/dedup/classification. Cached
editorial PASS cannot create a new per-channel rewrite. Existing workers, review,
media, scheduling and final publication guards consume shared freshness and
therefore reject deleted sources without AI/download/send side effects.

Already-observed exact publication receipts remain historical delivery truth:
crash recovery completes the original acknowledgement without another send even
when the source was subsequently deleted. Unknown deliveries are not inferred by
text/time and are not automatically retried.

Migration `d9a648fbcd37` adds only the tombstone table, no fabricated backfill.
Account/channel lengths, positive signed-32-bit message IDs and pts have database
constraints. Downgrade refuses any populated deletion history; restore or forward
fix is required rather than silently reviving deleted sources. Empty downgrade
is allowed without touching historical source rows.

## Verification evidence

- Missing boundary regressions: five RED, then GREEN; missing migration table RED.
- Targeted SQL/service/real HTTP/migration regressions: **22 PASS**. Replay before
  classifier, cached PASS, stale publication, stale/retry/expired rewrite, manual
  approval/planning, source download, last pre-send guard, cross-session freshness,
  exact-ack recovery, actual SQL outbox failure/whole-chunk rollback, lost lease,
  malformed account and naive observation tested with synthetic fixtures only.
- Initial expanded full gate: 800 PASS / one test-helper failure (receipt reader
  returns `(snapshot, observation)`, not an observation alone). Corrected to the
  actual contract; final fresh full rerun **801 PASS**, session 10602, exit 0.
- Exact CI Ruff, targeted format, compile PASS. Explicit isolated D: CLI Alembic
  upgrade/check/downgrade/base/re-upgrade/check PASS. Migration regression preserves
  original source and refuses populated rollback.
- No frontend changes; previous frontend evidence is historical, not a new gate.
- Windows Docker/PostgreSQL packaged deletion acceptance and real Telegram update
  ingestion: **NOT VERIFIED / BLOCKED BY ENVIRONMENT/AUTHORIZATION**. Local C: disk
  remains almost full; no deletion/prune/volume reset/key replacement workaround.

Next: leased durable channel-pts consumer, deletion-first fan-out, idempotent replay
after partial mappings, no pts advancement until the whole chunk is durable.
Missing baseline/TooLong/unknown update gaps must remain explicit and must never
silently reset to the latest message snapshot. No worker flag is enabled here.
