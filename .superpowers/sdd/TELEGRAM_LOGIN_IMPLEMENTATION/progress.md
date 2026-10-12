# SDD ledger — plan: docs/TELEGRAM_LOGIN_IMPLEMENTATION.md

Prepared next independent approved TelegramAccount onboarding increment; not
dispatched while Windows backup Task2 solewriter/review is active. Main fully
read saved spec/plan, provider/session/model/migration/isolation interfaces,
NewsFlow migration/security/runtime guidance and SDD/TDD/writing-good-tests.
Current human explicitly requests autonomous implementation, no questions/pauses.

| Preflight | Producer/consumer boundary | Finding/ruling |
| --- | --- | --- |
| Task1 internal | Adapter RPC -> verified result | In-memory only; typed bounded user/phone/authkey/session validation; no real network tests |
| Task1 internal | Preflight snapshot -> transactional persistence | No transaction spans input/RPC; full metadata CAS and key fingerprint recheck; no saved-session replacement |
| Task1 internal | Account row -> outbox | Existing event table, atomic commit/rollback, no secret payload or schema change |
| Task1/Task2 | Public service types -> CLI | Exact preflight/provision signatures; interactive guard precedes runtime setup; constructor is not client construction |
| Task1/Task2 | Unit DB -> PostgreSQL proof | Fake only RPC; real cipher/store/reopen; UUID migrated PG later, no SQLite-as-PG acceptance |
| Task2 internal | Arguments/TTY -> secret/config/DB | Default/help/malformed/nonTTY zero runtime IO; explicit PostgreSQL and current migration heads |
| Task2 internal | Masked human input -> async RPC | getpass warning fails closed, one code/password attempt, cancellation privately exits |
| Task2/root | Source/CLI -> packaged/live | Root actual synthetic Docker and exact CI after review; human login separately pending |

Ruling: proceed within already approved Telegram onboarding/autonomous scope
without another design-confirmation question — human explicitly forbids such
pauses and the CLI closes an existing missing session producer — cost if wrong:
isolated opt-in adapter/CLI can be reworked; no live credentials/UI activation.
Ruling: separate explicit interactive CLI from read-only ingestion/provider —
prevents accidental worker login prompts and an unauthenticated browser endpoint —
cost if wrong: later protected UI integration remains separate work.
Ruling: execute one full backend gate after combined Task2 deliverable, focused
new and covering regressions after Task1 — unchanged expensive suites do not
gain evidence from duplicate runs — cost if wrong: full regression discovery is
delayed until CLI integration but before release/push acceptance.
Ruling: no actual remote auth during autonomous run; source/fake/migrated PG/
network-none package smoke continue independently of missing human code/2FA —
cost if wrong: live session usability cannot be claimed until explicit gate.
