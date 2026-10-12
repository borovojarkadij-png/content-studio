# Protected editorial Settings implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development. One writer at a time, behavioral
> TDD and independent spec/quality review after each task.

**Goal:** Make accepted persistent editorial policy editable safely through the
existing live Settings / Модерация, without changing the navy DEMO design.

**Architecture:** Strict bounded same-origin client and small memory-only
authenticated panel. Settings remains the single App dirty-state owner. Separate
actual migrated API browser fixture proves persistence/CAS without real secrets.

**Tech Stack:** Existing React/TypeScript/Vitest/RTL/Playwright/FastAPI/SQLAlchemy.
No dependency/schema or production configuration changes.

**Spec:** EDITORIAL_SETTINGS_DESIGN_20261013.md and accepted operator API contract.

## Global Constraints

- Telegram Content Studio only; preserve the accepted UI/design.
- Only origin https://github.com/borovojarkadij-png/content-studio.git and branch
  codex/dark-navy-ui; no merge, force-push, PR or worker push.
- REJECT -> rewrite_allowed=false -> no new RewriteJob -> rewrite calls=0.
- Synthetic verdicts never qualify real models or activate automatic approval.
- No real keys/sessions/provider calls/publications/operational SQL in tests.
- Never discover/create/rotate a real key or change runtime authorizations.
- Root owns CURRENT_STATE/IMPLEMENTATION_PLAN, CI evidence and acceptance docs.
- DEMO does not mount/call the protected policy panel. No global navy/layout/
  navigation redesign or unrelated provider-key workflow changes.
- No model qualification, provider catalog calls, worker activation or publication
  authority from saving policy. Default-disabled503 must not be faked as success.

### Task 1: Strict policy client and existing live Settings integration

**Files:**
- Create frontend/src/boundedResponse.ts: shared stream bound/cancel only.
- Modify frontend/src/illustrationReviewApi.ts only to use shared stream reader,
  preserving its public DTO/error behavior and all existing tests.
- Create frontend/src/editorialPolicyApi.ts and editorialPolicyApi.test.ts.
- Create frontend/src/EditorialPolicySettings.tsx and EditorialPolicySettings.test.tsx.
- Modify frontend/src/workspaces.tsx only live Moderation integration/dirty OR.
- Modify frontend/src/App.test.tsx only integration/dirty/DEMO regressions.
- Own SDD task-1-report.md, no other docs/CI/backend/Compose/style changes.

**Interfaces:**

```typescript
type ProtectedEntity = { entity_id: string; aliases: string[] };
type EditorialPolicy = {
  configured: boolean; enabled: boolean; provider: 'OPENAI'|'OPENROUTER'|null;
  model: string|null; policy_version: string|null; etag: string|null;
  protected_entities: ProtectedEntity[]; diagnostic_only: true;
  real_model_qualified: false; execution_authorized: false; rewrite_allowed: false;
};
type EditorialPolicyChange = {
  enabled: boolean; provider: 'OPENAI'|'OPENROUTER'; model: string;
  protected_entities: ProtectedEntity[]; expected_etag: string|null;
};
readEditorialPolicy(token: string, signal: AbortSignal): Promise<EditorialPolicy>;
writeEditorialPolicy(token: string, change: EditorialPolicyChange,
  signal: AbortSignal): Promise<EditorialPolicy>;
EditorialPolicySettings({onDirtyChange}: {onDirtyChange: (dirty:boolean)=>void});
```

- [ ] Behavioral RTL RED renders actual App live Settings/Модерация and expects
  a labelled «Редакционная политика» region and masked «Токен оператора» field,
  no policy request before explicit «Загрузить редакционную политику». Run RED,
  preserve native/log; no absent-import-only RED or canned component.

```tsx
render(<App initialDemo={false} />);
await user.click(screen.getByRole('button', {name: 'Настройки', exact: true}));
await user.click(screen.getByRole('button', {name: 'Модерация', exact: true}));
expect(screen.getByRole('region', {name: 'Редакционная политика'})).toBeTruthy();
expect(screen.getByLabelText('Токен оператора').getAttribute('type')).toBe('password');
expect(policyRequests).toEqual([]); // collect actual fetch path calls, other API separately
```
- [ ] Shared reader factors existing stream logic, no environment/storage/auth
  access. Retain cancellation/release/UTF8/error behavior of illustration client;
  map shared boundary errors to each client's fixed private public error type.
- [ ] GET/PUT exact /api/settings/editorial-policy; validate token before fetch,
  same-origin explicit /api proxy routing and reject foreign/credentialed/query/
  hash/prefix VITE base before token transmission. no-store/omit/redirect:error/
  no-referrer/signal, header-only token. Read <=300000bytes, strict UTF8+JSON+
  exact key/nested DTO/cross-field bounds and all fixed false permissions.
- [ ] Client rejects malformed success without trusting server text; static
  401/409/422/503/network messages never echo token/body/error. PUT only exact
  request fields/original nullableETag, no caller actor/version/permissions.
  Confirm acknowledged returned editable values equal submitted values allowing
  canonical entity/alias order; never accept contradictory200 as a save.
- [ ] Panel follows spec exact-value entity/individual-alias textareas, pinned
  provider/model, diagnostic checkbox, readonly version/ETag and clear false
  qualification/execution note. Missing-policy creation only after valid GET.
  No schema duplication for Unicode ambiguity; no trim/normalize/drop aliases.
- [ ] One request generation/controller/in-flight ref; explicit token load,
  masked memory-only token, edit invalidates auth/aborts without losing dirty
  draft, disconnect/unmount/mode clears. Late old responses never change state.
  Freeze controls during PUT. Duplicate click sends once, not optimistic save.
- [ ]409 keeps draft, prevents stale overwrite; explicit reload/disconnect dirty
  discard-confirm/cancel.422 preserves draft.401 invalidates auth;503 honest.
  Ambiguous PUT failure keeps draft/unconfirmed status and explicit reload, no
  fake rollback/success or automatic retry. Successful verified response sets
  canonical saved/draft and clears only this panel's dirty state.
- [ ] Settings keeps live panel mounted hidden across category/page changes and
  owns editorialDirty OR existingdirty. Stable callback, single markDirty key.
  DEMO never mounts/calls panel; existing default eight-screen visual unchanged.
- [ ] Target transport/stream/reviewer/panel/App tests: malformed/extra/true
  authority/oversized/chunked/invalidUTF8/abort/foreignbase, requests/provenance,
  null create/noop/update/conflict/corrupt/503, nonASCII/newline exact values,
  >64entities/>16aliases/empty/oversize fields, model :free/notrouter, repeated
  click/stale GET/stale PUT/credential edit/mode/unmount/navigation/dirty guard,
  provider draft independence/DEMO zero-policyIO. Tests assert observable behavior.
- [ ] Freeze owned hashes; ONE full frontend Vitest, format:check and build;
  existing illustration API regressions after helper extraction. No backend
  full or old Docker recovery rerun. Exact commands/native/counts/RED/hash/
  warnings/limitations/self-review in own report; commit owned paths/report only.
  Root fresh task review before Task2, no claim actual browser persistence yet.

### Task 2: Actual protected browser acceptance and CI evidence

**Files:**
- Create scripts/ui_editorial_fixture_api.py.
- Create frontend/playwright.editorial.config.ts.
- Create frontend/e2e-editorial/policy.spec.ts.
- Modify frontend/package.json only include e2e-editorial in format paths.
- Modify .github/workflows/ci.yml only add protected editorial browser run/
  always-upload evidence and standalone fixture lint; preserve all prior checks.
- Own SDD task-2-report.md. Root owns screenshots inspection/report/state/docs.

**Interfaces:** Task1 exports/types/Settings controls; actual app GET/PUT accepted
operator API and service. Fixture loopback5193, Vite5192, reuseExistingServer:false,
dedicated testDir./e2e-editorial,1worker/0retries, .artifacts/editorial-policy-ui
report/test-results and screenshots. Synthetic token
synthetic-browser-only-operator-token-0001, actor29; never operational secrets.

- [ ] Create-only TemporaryDirectory SQLite/schema Alembic target, clear/replace
  all consulted operator/reviewer/master credential env before app import/use;
  synthetic dedicated file only. Existing configured_session_factory points only
  at this URL; dispose/reset finally. No global host credential/model lookup.
  Do not copy the entire illustration/media fixture; this fixture only needs
  policy and isolated SQL counts. Fixture-only evidence endpoint proves real
  policy/audit actor/ETag/outbox count/rewrite+diagnostic+publication jobs0.
- [ ] Run a browser behavior RED against existing Task1 before the missing
  fixture/contract behavior is implemented where practical; never fake RED as
  server startup/import failure. Actual GET/PUT/state/evidence assertions are
  required even when Task1 already makes the happy path GREEN.
- [ ] Browser real save/reload/create/disable/model/aliases/noop; independent
  second API actor/request creates stale ETag so panel409 retains exact draft,
  cancel discard retains it, explicit reload obtains actual new policy. Count
  audit metadata actor and no duplicate events; no providers or real sends.
- [ ] Validate invalid token/private401, masked memory-only/no URL/cookie/storage
  secrets, pending cancellation/duplicate/dirty mode change and unrelated AI-key
  draft preservation, DEMO zero-policyrequests. Narrow390px/keyboard/axe checks,
  no horizontaloverflow/console errors. Fixture data remains synthetic.
- [ ] Run existing33 main browser + protected illustration browser regression
  and new protected editorial flow; preserve exact native/counts/logs. Save new
  live screenshots .artifacts/editorial-policy-ui/ and all8 DEMO sections under
  .artifacts/ui-dark-navy/. Root visually compares against accepted navy baseline.
- [ ] Full frontend Vitest/format:check/build, Ruff0.17 fixture lint/compile,
  exact CI/YAML check. No backend full or old Docker restart rerun unless an
  actual backend defect is found. Final report native/hash/screenshots/all
  failures/limits; owned commit, root review/push/exactCI. No auto deployment.

Deferred separate integration: api-only persistent operator-secret Compose mount
without generation; actual fixed-model benchmark/qualification and live authorized
test Telegram. UI config does not resolve these external prerequisites.
