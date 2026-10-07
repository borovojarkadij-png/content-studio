# Free-only OpenRouter rewrite — 2026-10-08

## Execution contract

The server-side encrypted-settings factory and opt-in durable worker now support
an explicit `NEWSFLOW_REWRITE_PROVIDER=OPENROUTER`. The alternative is `OPENAI`;
invalid values fail closed. A missing OpenRouter credential does not fall back to
OpenAI. `NEWSFLOW_REWRITE_ENABLED=0` remains the default and operational setting.
No rewrite flag enables Telegram publication.

Save a credential and ordered free models through existing provider Settings.
There must be 1–8 unique model IDs, each ending in `:free`, or `openrouter/free`.
The server validates the same bounded model contract before persisting settings.
This is a user-configured ordered list, not automatic discovery of every model.

The adapter posts to OpenRouter Chat Completions using strict JSON Schema,
`require_parameters=true`, zero prompt/completion/request price caps and no
upstream provider fallback. Only the explicitly configured free IDs are tried.
See [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
and [provider selection](https://openrouter.ai/docs/guides/routing/provider-selection).
These controls restrict routing; synthetic tests are not proof of external billing
or that every free model is available and supports the schema.

Rate limits, unavailable/unsupported models and transient connection failures
advance through that list under one shared 30-second deadline. Socket waits are
bounded by at most 10 seconds; a stalled read can extend the deadline by one wait.
The runner owns a 60-second lease and rechecks it before recording a result.
The existing persisted budget allows three job attempts by default, each bounded
by at most eight HTTP requests. Retries are persisted and delayed, not tight loops.

Authentication failures are terminal. Refusals, malformed/duplicate JSON,
truncation, unexpected positive reported cost and changed fact anchors are terminal:
no fallback to another model to repair them. Maximum response is 256 KiB;
source/result limits are 32,000 characters and output budget is 4,096 tokens.
Redirects are not followed with credentials. Raw provider errors/keys are not logged.

Known tokens, configured model ID, provider and channel style are saved per attempt.
Unknown cost stays NULL. The configured `openrouter/free` ID does not identify the
underlying routed model; there is no claim of complete billing reconciliation.
Unavailable responses without trustworthy usage do not manufacture zero usage.

Editorial and latest-source checks precede credential decryption and HTTP calls.
Every output has an independent job/draft. Both natural tabloid and neutral styles
use the same guards. Successful drafts remain PENDING manual review: token-anchor
equality does not establish semantic truth or permit unattended approval.

## Verification

- Missing factory/worker provider selection failed before implementation.
- Unsafe/unbounded settings acceptance failed before matching adapter validation.
- Full backend gate: 227 tests passed; lint, changed-file format and compile passed.
- Frontend gate: 26 units, format, typecheck/build and 19 Chromium E2E passed;
  production dependency audit reports zero vulnerabilities. Eight section screenshot
  sets and actual-API Planner screenshots were regenerated.
- Tests exercise ordered 429 failover, one overall deadline, authentication errors,
  free-only price/routing controls, invalid/truncated/refused/charged responses,
  independent per-channel styles/usage, zero calls for editorial rejection, no
  AI repair of changed facts and invalid provider selection before job claiming.
- Windows Docker and new Linux matrix evidence are recorded separately in
  CURRENT_STATE.md and DOCKER_VERIFICATION.md. No live OpenRouter request was made.
- Windows acceptance passed in `newsflow-verification-openrouter20261008`:
  encrypted synthetic credentials/style, actual 60-second abandoned lease,
  restart/fenced recovery, structured synthetic reply and PENDING usage/draft
  persistence. Down/up, PostgreSQL crash, Redis restart/loss and forced API-IP
  change passed too. Fixture stack stopped with volumes retained.
- Operational image rebuild, startup/health and actual PostgreSQL drift check
  passed; module is packaged and network rewriting is confirmed disabled.
- Full isolated migration upgrade/check/downgrade/upgrade/check passed.

## Remaining

No usable OpenRouter credential is provisioned; live provider behavior is pending.
The active worker remains network-disabled. Enabling requires an explicit local
configuration change and credential, not clicking the style button. UI-based worker
activation, per-channel provider/model overrides, semantic verification, guarded
automatic approval, billing/cache dashboard and actual Telegram transport remain
pending. PHASE 1 is not complete.
