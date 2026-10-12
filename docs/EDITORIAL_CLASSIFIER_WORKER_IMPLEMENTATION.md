# Diagnostic classifier credential factory and opt-in worker implementation plan

> Execute with subagent-driven-development, one writer followed by independent
> scoped review. Start only after diagnostic execution is independently accepted.

**Goal:** Make admitted diagnostic jobs executable through an explicit,
default-disabled worker using already encrypted provider credentials.

**Architecture:** Add a server-only classifier factory consuming the canonical
EditorialAdmissionBinding and existing RewriteProviderSettingModel credential.
Connect the accepted DurableEditorialRunner through one bounded worker tick and
strict opt-in main-loop flag. No editorial permission propagation or settings
mutation is included.

**Spec:** Approved Telegram PHASE1, docs/IMPLEMENTATION_PLAN.md,
docs/EDITORIAL_CLASSIFIER_EXECUTION_IMPLEMENTATION.md and docs/QUALITY_GATES.md.

## Global Constraints

- Telegram Content Studio only; preserve the accepted UI/design.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force-push, PR or push by workers.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify real models or activate automatic approval.
- No real keys, sessions, provider calls, publication or operational SQL in tests.
- Never generate/rotate a master key or persist/decrypt a credential in a report.
- No runner-owned SQL session/transaction during classifier transport IO.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN, CI and actual Windows acceptance.
- No policy seed/enablement, qualification, source reinterpretation, resubmission
  of historical rows, configuration API, UI, Compose or dependency changes.

## Decision

Reuse credentials, not rewrite-model policy: a diagnostic job's pinned provider
and model come from its immutable canonical binding. Do not use primary_model,
fallback_models, a live catalog or environment model override to retarget it.
Free-only OpenRouter remains a single pinned explicit :free model with existing
zero-price transport constraints, never a paid/dynamic/cross-provider fallback.

The flag only activates diagnostic execution. It cannot turn a diagnostic PASS
into editorial PASS, alter original/manual decisions, create rewrite jobs or
authorize publication. Current actual-model qualification remains pending.

### Task 1: Configured classifier factory and bounded opt-in worker

**Files:**
- Create backend/src/newsflow/services/editorial_classifier_factory.py.
- Modify backend/src/newsflow/worker.py narrowly for the new tick/flag.
- Create backend/tests/test_editorial_classifier_factory.py.
- Create backend/tests/test_editorial_worker.py.
- Modify the existing tracked .env.example only to document default-disabled
  execution; never read or edit the real .env as part of this task.
- Root-authorized narrow CI correction after full-suite termination: in
  .github/workflows/ci.yml change only unattended-postgres timeout-minutes10->20.
  Actual previous-source run38304194927 reached91% with continuous successful
  progress before the ten-minute job deadline; preserve all test commands,
  safety settings, failure propagation and all other job budgets.
- Report in this plan's SDD workspace task-1-report.md.

**Factory contract:**

```python
class ConfiguredEditorialClassifierFactory:
    def __init__(self, session_factory, *, cipher, opener=None): ...
    def __call__(self, binding: EditorialAdmissionBinding): ...
```

- Require exact EditorialAdmissionBinding, not an arbitrary object/dictionary.
- In a fresh SQL session, resolve_editorial_admission from binding's content key
  and mapping ID; compare the entire fresh immutable binding to the supplied one.
  Missing/disabled/stale/editorial/cheap-filter/ownership/fingerprint holds fail
  before loading/decrypting a credential or constructing a transport.
- Use the matching existing RewriteProviderSettingModel.encrypted_api_key only.
  Missing/empty or unreadable ciphertext is ProviderConfigurationInvalid with
  stable sanitized codes; no raw exception/ciphertext/source/key in messages.
  Handle the existing SessionDecryptionUnavailable and malformed-value errors
  narrowly. Unexpected storage errors propagate, never become fake success.
- Use the explicit injected stable cipher. Do not read environment/files,
  create a key/setting, repair a value, invoke a catalog or touch Telegram.
- Close the factory's SQL session before constructing OpenAIEditorialClassifier
  or FreeOpenRouterEditorialClassifier with exactly binding.model and opener.
  Construction has no network. The runner still performs its fresh post-factory,
  immediately pre-IO recheck; factory validation is not permanent authorization.
- Same supported-provider/model/prompt identity as accepted adapters/runner;
  preserve actual per-attempt evidence/usage and typed error contracts.

**Worker contracts:**

```python
def editorial_classification_enabled(value: str) -> bool: ...

def run_editorial_classification_tick(
    session_factory, *, enabled: bool, cipher, now: datetime, opener=None
) -> str: ...
```

- Flag accepts exactly strings "0"/"1"; any other value (including bool) raises
  ValueError with static message identifying
  NEWSFLOW_EDITORIAL_CLASSIFICATION_ENABLED. No truthy coercion.
- Tick requires exact bool enabled. Disabled returns DISABLED before session,
  cipher/factory/runner construction or IO. Enabled without a cipher fails
  visibly, not as an empty installation. Delegate one runner.run_next(now=now)
  with ConfiguredEditorialClassifierFactory; no scanning old content/reseeding,
  ingestion transaction IO, batching loop, parallel IO or rewrite call.
- worker.main reads NEWSFLOW_EDITORIAL_CLASSIFICATION_ENABLED default "0".
  Include enabled diagnostics in the existing stable master-key loading guard.
  Run at most one diagnostic tick per existing loop iteration, honor stopped,
  preserve scheduler/ingestion/rewrite/semantic/media/publication behavior.
  Log only stable result or static interrupted/recovery marker, never exception
  text, source text, evidence, model output, credential or binding contents.
- Do not activate any runtime env, policy, credentials or live services. The
  environment template documents "0" and diagnostic-only/no-approval semantics.

**TDD and verification:**

- [ ] Start with a real migrated enabled-policy/queued-job fixture using fake
  encrypted credentials and an injected transport opener. A bounded tick must
  actually commit a diagnostic REVIEW attempt/history/outbox, retain original
  MANUAL_REVIEW/false, RewriteJob0 and rewrite calls0. Before implementation,
  execute to behavioral assertion RED, not import/collection failure.
- [ ] Factory tests cover OpenAI and single pinned free OpenRouter; primary and
  fallback rewrite settings deliberately differ and cannot retarget diagnostics.
  Verify exact JSON transport/model/zero-price guards with counted fake opener.
- [ ] Missing/stale/disabled/REJECT/PASS/source/sync/technical/duplicate bindings,
  wrong input type, unsupported model/provider and credential corruption fail
  without network; rejected-before-gate cases also decrypt/construct counts0.
  Independent committed changes in decrypt/factory callbacks are caught by the
  runner's post-factory recheck before classify. No SQL session spans opener IO.
- [ ] Disabled tick uses a throwing session factory/cipher/opener and performs
  no work. Enabled missing cipher, malformed flag/bool/now, idle state and
  recoverable typed provider failure remain explicit and bounded.
- [ ] Exercise actual worker.main once with controlled stop/Event/time seams:
  missing flag is off/no diagnostic cipher, explicit1 loads stable cipher and
  dispatches one bounded tick, early stopped skips it, exception logs sanitized;
  all other flags stay0. No real process/network/sleep or secret file in tests.
- [ ] Cover accepted runner/admission/adapters plus scheduler/rewrite/semantic
  main-loop regressions. Ruff0.17 src/tests/alembic, changed formatting,
  compilation, YAML/diff and one frozen complete backend suite with Telethon1.45.
  No schema/dependency migration or unchanged UI/Docker recovery rerun required.
- [ ] Self-review and report original RED/GREEN, native commands/counts/skips,
  exact frozen hashes and limitations. Commit only owned files/report; no push.
- [ ] After the already-running five-file frozen full suite terminates, apply
  only the authorized CI deadline correction, parse YAML and assert the new
  finite budget and unchanged PostgreSQL test commands. Preserve actual timeout
  as failed verification, not PASS; root tracks exact corrected new-source CI.
  No Python edits or second full-suite run for this configuration-only change.

Deferred: protected-policy settings API/UI and diagnostic history read model,
actual benchmark/qualification, qualified editorial PASS propagation and its
shared final-gate serialization. This task does not satisfy those deliverables
or complete PHASE1; live acceptance actions remain collected in the live report.
