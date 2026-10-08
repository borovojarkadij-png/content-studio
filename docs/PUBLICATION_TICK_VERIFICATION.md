# Bounded opt-in publication processing

2026-10-08: publication admission/tick seam implemented, not main-loop wired yet.

DurablePublicationRunner.enqueue_due scans at most 16 eligible due reservations
per call (validated maximum 64), excludes expired/future/non-PLANNED items and
ANY existing send-intent history. Every selected item still passes fresh preflight.
An unsupported/stale item creates no intent and cannot prevent admission of later
items. Returned cyclic ID cursor preserves fair scanning between worker iterations.
This cursor is an optimization, not durable state: resetting it does not lose
plans/jobs; PostgreSQL owns all intent, nonce, attempt, receipt and recovery state.

run_publication_tick refuses absent key/credentials before database/network setup,
does nothing when disabled, admits a bounded batch and executes at most one
persisted job. ConfiguredTelegramPublisher chooses text/photo by bound asset;
there is no fallback to another media type after a failure. Future/expired slots,
terminal/uncertain send history and current rejects never become new sends.

Evidence: seven missing-tick tests RED, then GREEN; 14 final tick tests PASS.
Actual encrypted factory + real SQL + synthetic TL network cover both media types,
stable nonce/receipt, zero database access when disabled, missing prerequisites,
stale-first-item fairness/wrap, invalid cursor/limit and unknown-result zero-resend.
Full backend 717 PASS (15953), Ruff/targeted format/compile PASS. No schema change.
Windows Docker packaging is currently blocked by host disk-full/Docker unable to
start; no actual sending enabled, no operational environment or secrets changed.

Next: main-loop opt-in flag defaults 0, offline main-loop regressions and honest
UI wording about server worker versus public send actions, then synthetic packaged
acceptance when Docker is writable. Verified difference reconciliation and real
authorization remain pending; never make a timeout into proof of non-delivery.
