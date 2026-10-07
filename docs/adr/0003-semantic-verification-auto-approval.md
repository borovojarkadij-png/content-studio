# ADR 0003: semantic evidence before automatic approval

Status: accepted implementation direction within the approved PHASE 1 plan.

## Context and decision

Numeric/name/link equality is not proof that a rewrite preserves meaning.
The next increment adds a provider-independent, strict semantic assessment
contract and PostgreSQL evidence, not a second rewrite/repair call. Checks must
cover support, negation, subject, attribution, certainty and omitted source claims.
Uncertainty, incomplete coverage, malformed evidence or provider errors leave the
draft pending. Existing explicit human approval remains a separate workflow.

Automatic approval is per output channel and defaults to MANUAL. VERIFIED mode
requires an active release for the exact verifier provider/model/prompt and
versioned benchmark, with a recorded evaluation-report digest. No HTTP endpoint
can register a release, supply a verdict or declare a model evaluated. Offline
fixtures prove the guards, not the semantic quality of a live model. No live model
will be qualified using fake results. Dynamic free routers cannot be qualified
without an identifiable underlying model; fallback must be qualified separately.

Evidence binds the immutable revision, exact source/draft SHA-256, channel,
verifier release and prompt version. Editorial/source/fact gates run before a
verification call and again before recording/using its result. The approval
transaction repeats every gate and activates only matching candidates. Scheduling
must invalidate automatic approvals when their evidence/release/policy is stale.
No verification, approval or configuration operation sends Telegram messages.

## Alternatives and consequences

- Anchors-only automatic approval: rejected; negation and attribution pass it.
- Always manual: remains the safe default, but does not satisfy unattended mode.
- Versioned evidence plus qualified verifier: selected; adds durable state and
  an explicit quality-release step. LLM verdicts remain probabilistic, not proof.

Schema changes are additive. Old drafts retain their manual approval semantics.
Downgrade refuses to discard evidence, qualified releases or automatic policies.
Durable leased verification execution/provider adapters are the follow-up after
the contract and approval boundary; synchronous test injection is not runtime QA.

## Verification

Synthetic adversarial cases include negation, changed subject, new/omitted facts,
uncertainty, injected instructions, incomplete evidence, stale revision/draft,
revoked release/policy, current editorial rejection and retry idempotency.
Migration checks use isolated databases only. Actual provider benchmark results
and live Telegram publication/recovery are tracked separately as pending.
