# Protected editorial settings in the existing navy UI

Status: prepared; implementation waits for acceptance of operator API Task1.
This is integration of approved persistent editorial configuration, not a new
design, public identity system, AI model qualification or deployment activation.

## Context and choice

Use the existing Settings / Модерация category, current Panel/Notice/form
styles and App dirty-page guard. DEMO remains exactly its accepted eight-section
interface and never mounts or calls the protected operator panel. A separate
settings page/navigation redesign would change the approved visual contract;
reusing the illustration reviewer token would improperly expand its authority.
Choose a small live-only EditorialPolicySettings component and a strict client
for the accepted /api/settings/editorial-policy GET/PUT contract instead.

The human approved autonomous execution of this configuration workflow. Preserve
their manual settings and drafts; do not ask for repeated implementation choices
or provision a real operator secret. The default-disabled503 is an honest server
configuration requirement, not permission to reuse any master/provider key.

## Authentication and transport

Operator token is a separately issued32–128 ASCII alphanumeric/underscore/hyphen
bearer, entered in a masked password field with autocomplete disabled. It stays
in React memory only: never local/session storage, cookie, query/hash, logs,
analytics, screenshots/traces containing real keys, or persisted form data.
Only an explicit connect/load button makes a GET; typing, opening Settings and
DEMO make no policy request. Disconnect/unmount/mode switch clears the token,
snapshot and draft and aborts pending reads/writes. Before discarding a dirty
draft by disconnect/reload, require an explicit in-panel discard confirmation;
cancel leaves draft unchanged. Category/page navigation preserves the panel and
draft while hidden, matching existing visited-page behavior.

Protected requests use same-origin /api routing. Accept VITE_API_BASE_URL only
when its resolved origin equals window.location.origin; reject credentials,
query/hash and unexpected path prefixes rather than send an operator token to
another host. Local Vite proxy and existing production reverse proxy already
support /api. No cross-origin cookie or new CORS/auth architecture is introduced.
Use cache:no-store, credentials:omit, redirect:error, referrerPolicy:no-referrer,
AbortSignal and Authorization header only. Bound response stream300000bytes;
strict UTF8/JSON/exact DTO. Reuse the existing bounded stream implementation
through a small shared helper, preserving illustration reviewer error behavior.
Do not duplicate the whole protected file/auth or streaming logic.

## Policy and authority

Display configured/enabled/provider/model, protected entity IDs and aliases,
opaque policy_version/etag, diagnostic-only and unqualified status. All returned
real_model_qualified/execution_authorized/rewrite_allowed must be false and
diagnostic_only true; malformed/extra/contradictory DTO never populates a trusted
form or produces a success notice. Missing policy is configured=false,enabled=false,
provider/model/version/etag=null,entities=[] and permits create-only nullETag.

Edit diagnostic enabled, OPENAI/OPENROUTER, pinned model and entity rows with
individual exact-value alias controls. Use textareas for entity IDs/aliases so
previously valid embedded newlines are not silently stripped by text inputs or
split/join serialization. Never trim/normalize/drop existing Unicode values.
Allow0–64entities,1–16aliases per entity, nonblank ID<=128codepoints/alias<=255;
model<=255, exact lowerhex64ETag and canonical entitiesUTF8<=262144bytes.
Server remains authoritative for provider/model/alias ambiguity and byte rules;
do not duplicate Unicode NFKC/casefold policy with an incompatible JS approximation.
OpenRouter classification requires a pinned :free model, not openrouter/free or
another dynamic openrouter/* router. No model catalog/availability claim or AI
call from this form. No actor/version/permission input.

PUT supplies the original displayed expected_etag and exactly enabled/provider/
model/protected_entities; never auto-reload/auto-retry/last-write-wins. Accept only
strict DTO success after server commit and confirm returned editable values
match the submitted semantic values (entity/alias order may be canonicalized).
Set saved snapshot/draft from that verified response. No-op is valid but is not
an activation. A409 keeps the unsaved draft, blocks stale save and offers explicit
reload with discard confirmation;422 shows static validation error and preserves
draft;401 drops authenticated authority,503 explains unavailable server/storage.
Network/aborted/invalid success body after PUT means acknowledgement unconfirmed,
not definitely rolled back. Preserve the draft and offer explicit reload; never
claim success or blindly retry. Reading current server state does not prove our
ambiguous request caused it.

Use one request generation/AbortController and an immediate in-flight ref to
fence double click, token edit/disconnect/unmount and late/out-of-order responses.
Changing the credential invalidates old authority and cancels requests; do not
silently overwrite the user's dirty draft. Freeze editable controls during a PUT;
every new request or context change invalidates older completions.

Saving enabled=true configures diagnostics only. The mandatory EditorialGate,
REJECT zero-rewrite invariant, protected negative content, source/fact/media/
review rights, qualification/worker flags and publication permission are unchanged.

## Dirty state and visuals

Settings owns editorialDirty and ORs it with existing settings/provider dirty
state before its single markDirty('settings',...) call. Child receives a stable
onDirtyChange callback, never competes for that App key. Keep live panel mounted
inside a hidden wrapper on category switches; never mount it in DEMO. Existing
provider-key replacement/settings values are not reset or rewritten.
Use existing navy panels, typography, buttons, responsive field styles and
Russian accessible labels, status/alert and visible loading/disabled explanations.
No global layout/colors/assets/navigation changes; no new fake-save controls.

## Evidence and rollout

Task1: behavioral RTL RED -> strict transport/component regression -> all Vitest/
format/typecheck-build -> independent task review. Task2: actual isolated migrated
API fixture and real browser GET/PUT/CAS/reload/privacy/dirty/DEMO/narrow/axe flow,
existing browser regressions plus all eight DEMO screenshots compared to accepted
baseline; exact CI includes that dedicated fixture, not mocked successful saves.
Only synthetic temporary files/SQL/credentials and zero provider/publication calls.
Default/unprovisioned endpoint and actual model/Telegram acceptance remain pending.
Optional api-only persistent Compose secret mount is a separate integration;
this task does not generate a token or change operational containers.
