# Commercial verification stages — Content Studio

Apply the NewsFlow runtime-QA and release-engineering evidence ladder to this
existing Telegram web/Compose application. Do not add Electron or a new project.
Implementation progress is distinct from release readiness.

| Stage | Required evidence before promotion |
| --- | --- |
| DEV increment | Actual failing regression for a new invariant/bug when applicable; minimal fix; relevant unit/contract tests; lint, format and type checks; documented outcome and remaining risks. |
| Integration | Actual migrated PostgreSQL/API/worker tests, stale decisions, duplicate delivery, concurrency, retry and source/review bindings. SQLite or mocks do not replace PostgreSQL/provider evidence. |
| TEST candidate | Exact commit SHA and CI run; full available backend/frontend gates; isolated synthetic browser flows, accessibility and narrow-screen checks; built Compose images identified by immutable digest. |
| Visual acceptance | Accepted existing screen references and current captures inspected together at the same viewport, section, mode and state. Check all eight sections for a UI milestone. DEMO data must remain explicitly separate from real API data. |
| RC runtime | Actual Windows Docker Desktop build/start/migrations/health; persistent data and stable encrypted sessions; down/up, Redis/worker/PostgreSQL recovery and durable unfinished-job recovery. Linux CI is supporting evidence, not Windows proof. |
| STABLE readiness | All mandatory gates PASS on the exact candidate; clean Windows first-run/deployment smoke; controlled required live acceptance; documented backup/restore, migration compatibility, rollback identity and known limitations. No automatic merge or production publication. |

For each gate retain expected/actual, command, platform/runtime, source SHA,
artifact/image identity, report and screenshot paths, PASS/FAIL/SKIP/BLOCKED,
root-cause evidence and subsequent re-verification. A source/package change
invalidates the affected candidate evidence; historical passes remain historical.
Required SKIP, pending, unavailable secrets or BLOCKED never become PASS.

Core acceptance retains `EDITORIAL_REJECT -> rewrite_allowed=false -> no new
RewriteJob -> rewrite calls=0` across API, worker, retry, stale tasks, manual
scheduling and publication. Preserve source/fact/per-channel review constraints,
video manual-only/discard, and pre-AI visible/hidden YouTube exclusions. Synthetic
semantic verdicts never qualify a real model for automatic approval.

Use isolated synthetic data. Never test on production queues, real sessions,
rights or publication destinations. Paid synthetic provider tests require existing
usable user-authorized credentials and bounded calls; do not expose secrets.
Diagnose and fix ordinary errors without disabling assertions or checks.

Current UI target: existing `.artifacts/ui-dark-navy/1440x900/01_overview.png`,
explicitly reaffirmed by the user on 2026-10-08. Preserve that design; refreshing
a stale preview is not a redesign. The fresh Overview capture under
`.artifacts/ui-dark-navy/preview-restored-20261008/` is a scoped preview check,
not a fresh eight-section visual acceptance or PHASE 1 completion.
