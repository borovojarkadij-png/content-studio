# OpenAI rewrite and natural tabloid style — 2026-10-07

## Implemented

- Server-only OpenAI Responses adapter using strict `text.format` JSON Schema,
  selected saved model, `store=false`, separate developer/source messages and no
  tools. Contract follows [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
- Maximum response 256 KiB, maximum source/result 32,000 characters and output
  budget 4,096 tokens. Socket timeout is at most 15 seconds; incremental reads
  enforce a 30-second deadline between reads. A stalled read can extend that
  deadline by at most one socket timeout. No hidden adapter retries or redirects.
- Authentication/model errors are terminal configuration failures; transient
  network/rate-limit failures use the runner's persisted bounded retry budget.
  Refused/incomplete/malformed/duplicate-key JSON is terminal, never AI-repaired.
  Exception tracebacks omit private provider errors and credentials.
- Factory decrypts only saved encrypted server-side OpenAI settings after runner
  editorial/source checks. It reads the channel's current style once per attempt.
  Model selection currently comes from the shared OpenAI Settings entry; every
  output still has its own rewrite job, call, draft and review state.
- `NEWSFLOW_REWRITE_ENABLED=0` is the safe default. Exactly `1` enables at most
  one durable OpenAI job per timer tick; a stable mounted cipher is required.
  Ambiguous flag values fail closed. This flag NEVER enables Telegram delivery.
  Operational stack remains disabled and has no provider credentials configured.
- Known input/cached/output tokens and style/model are persisted per job attempt,
  including a response subsequently rejected by the fact guard. Unknown price
  stays NULL, not zero. Explicit `TokenPrices` can estimate USD per million tokens;
  tariffs are not guessed or hard-coded. Factory tariff configuration/UI is pending.
  Unknown network outcomes/crashes do not yield reliable usage or exactly-once billing.
- Per-channel `NEUTRAL` / `TABLOID` style is constrained in PostgreSQL. Planner
  buttons «Обычный стиль» / «В стиле жёлтой прессы» save through actual GET/PUT API,
  preserve selection after failed writes, survive reload and do not trigger calls.
  Tabloid instructions request lively natural words without invented sensations,
  allegations, changed polarity or facts. Existing drafts remain unchanged.
- Style never bypasses `EditorialGate`, fact anchors or mandatory PENDING review.
  No claim that synthetic tests measure actual literary quality or full semantics.

## Verification

- TDD: missing adapter/factory/worker/style API/button failed before implementation;
  duplicate JSON and local HTTP redirect credential-forwarding regression failed
  before fixes. Redirect test uses a local synthetic HTTP server, not real secrets.
- Backend full gate: **207 passed**, lint and compile passed.
- Frontend: **26 units**, format/typecheck/build passed, production npm audit zero
  vulnerabilities. **19 browser E2E** passed, including actual migrated API style
  persistence/reload, WCAG AA and responsive desktop/mobile planner screenshots.
- Isolated migration/drift regression and guarded style downgrade passed.
  Actual operational PostgreSQL drift check passed after migration deployment.
- Runtime, live provider execution and current CI evidence are recorded separately
  in CURRENT_STATE.md and DOCKER_VERIFICATION.md; local unit PASS is not live PASS.
- Windows isolated Docker acceptance `newsflow-verification-openai20261007`
  (18006 / 15179 / 18086) passed: actual migrated PostgreSQL, encrypted settings,
  TABLOID factory prompt, structured synthetic HTTP response, persisted attempt
  usage and PENDING draft survived worker restart/expired claim recovery.
  The default network worker remained disabled; no OpenAI/Telegram network call.
- Authorized live-key smoke could not begin: the current local `апи.txt` has no
  supported `sk-...` key candidate under UTF-8, UTF-16LE or UTF-16BE. File contents
  were not printed, modified or persisted. This blocks live verification only.

Screenshots: `.artifacts/ui-dark-navy/live-planner-1440x900.png` and
`.artifacts/ui-dark-navy/live-planner-390x844.png`; all eight DEMO sections remain
under `.artifacts/ui-dark-navy/`. The live style panel appears only for an actual
configured output channel, not an invented operational channel.

## Remaining

Bounded free-only OpenRouter execution was subsequently connected to the opt-in
daemon; see OPENROUTER_REWRITE_VERIFICATION.md for its independent evidence.
Provider-compatible
model discovery does not guarantee that every returned model supports rewriting
and strict Responses schema. Unsupported selection fails visibly, not via a paid
fallback. Usage dashboard/rate configuration/cache, semantic fact verification,
guarded automatic approval, Telethon ingestion/delivery and internet-image
acquisition remain pending. PHASE 1 is NOT complete.
