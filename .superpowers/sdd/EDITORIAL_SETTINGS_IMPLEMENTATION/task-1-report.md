# Task 1 implementation evidence

Base: `3d34b40bccd0b7bdeac2692c3a52bacc1e108ac0`, branch `codex/dark-navy-ui`, origin `https://github.com/borovojarkadij-png/content-studio.git`. Node v24.19.0 / npm 11.17.0, native Windows PowerShell. Existing root-owned `docs/CURRENT_STATE.md` modification preserved. No AGENTS.md found in repository or checked ancestor locations. Synthetic credentials/responses only; no runtime, provider, SQL, Docker, release or qualification activity.

## TDD RED

Command (frontend cwd): `npm test -- src/App.test.tsx -t 'opens the live editorial policy'`.
Native exit 1; Vitest 5.0.1; 1 failed, 15 filtered/skipped, 1 file failed, duration 1.46s.
Actual failure: `TestingLibraryElementError: Unable to find an accessible element with the role "region" and name "Редакционная политика"`, `src/App.test.tsx:36:19`. Actual App opened live Settings / Модерация. This is the expected absent-feature behavioral failure, with no absent import and no component mock. Full native output retained in task tool transcript.

## Implemented scope

- `boundedResponse.ts`: transport-independent bounded stream reader. It cancels/releases the reader on success/error/overflow and now cancels an outstanding read on AbortSignal (a behavioral RED found that the old loop waited forever for a pending chunk). No environment, auth or storage access. Illustration wraps only shared boundary failures in its existing private `ReviewApiError`; existing DTOs, signatures, limits, UTF8 checks and review behavior remain intact.
- `editorialPolicyApi.ts`: explicit same-origin `/api/settings/editorial-policy` GET/PUT; separate validated operator token; root-only VITE base, including rejection of empty query/hash delimiters; no-store/omit/error/no-referrer/signal and header-only bearer. Strict bounded UTF8/JSON, exact nested DTO keys, fixed false authority, missing/configured cross-fields, codepoint/entity/alias/model/canonical-byte limits and exact nullable ETag. Unicode ambiguity remains server-owned. Accepted legacy U+FEFF/nonblank NUL/newlines are preserved exactly, with backend-compatible blank checking and no trimming/normalization. PUT constructs only the five allowed fields and verifies returned editable values, allowing entity/alias order changes. All public errors are static; locally rejected requests are distinguished from unconfirmed PUT acknowledgements.
- `EditorialPolicySettings.tsx`: live-only Russian accessible region, masked memory-only operator input with autocomplete off, explicit load/disconnect, exact-value entity/individual-alias textareas, pinned provider/model, diagnostic checkbox, read-only version/ETag and explicit false qualification/execution/rewrite/publication note. Creation requires valid empty GET. One generation/controller/in-flight ref fences duplicates, edited credentials, disconnect, unmount, mode changes and late responses. Editable policy fields freeze during requests. 409 blocks stale saves; 401 invalidates authenticated authority; 422 and 503 preserve the draft with honest notices. Network/invalid/contradictory PUT acknowledgements remain unconfirmed and require explicit reload. Dirty reload/disconnect requires in-panel discard/cancel. Verified saves set canonical saved/draft and clear only editorial dirty.
- `workspaces.tsx`: only the live Moderation panel integration and existing Settings dirty OR. The stable React state setter is passed as callback; Settings retains the single `markDirty('settings',...)` owner. Panel remains mounted hidden across categories; App's existing visited/mode keys handle page persistence and mode clearing. DEMO never mounts the panel. Existing provider values/drafts are independent. Existing accepted styles/classes are reused without CSS/layout/assets/navigation changes.
- Tests use real App/panel/client/stream code and replace only external fetch responses with synthetic fixtures. App coverage includes all eight DEMO screens with zero network IO, live hidden navigation, both directions of provider/editorial dirty ownership, mode discard of a pending PUT, and late completion rejection.

Owned files: the eight frontend paths in the task brief plus this report. Root-owned docs, backend, CI, Compose, package/dependency files, operational containers and real credentials were not changed or staged. No push/merge/PR.

## Native verification and retained evidence

All npm commands below ran from `frontend` in native Windows PowerShell. Complete raw logs from `targeted-01` onward are retained under:

`D:/Codex-Recovery/content-studio-20261008/editorial-settings-task1-ui-20261013-0133/`

Later runs used `COMMAND 2>&1 | Tee-Object -FilePath LOG; $taskNative = $LASTEXITCODE; "NATIVE_EXIT=$taskNative" | Tee-Object -FilePath LOG -Append; exit $taskNative`. `targeted-01.log` and `typecheck-01.log` contain raw output, but their native exit was emitted to the task transcript, not appended to their files. Initial RED and initial API/extraction run were transcript-only; no retrospective original log is claimed.

| Command / log | Native result | Evidence / diagnosis |
| --- | --- | --- |
| `npm test -- src/App.test.tsx -t 'opens the live editorial policy'` (transcript) | 1 | Required actual App behavioral RED: absent named region; 1 failed / 15 filtered. |
| `npm test -- src/editorialPolicyApi.test.ts` (transcript) | 1 | Expected absent module during test-first preparation; no tests collected. This is NOT claimed as the behavioral RED. |
| `npm test -- src/editorialPolicyApi.test.ts src/illustrationReviewApi.test.ts` (transcript) | 0 | First API/extraction GREEN, 70/70, 2 files. |
| `npm test -- src/EditorialPolicySettings.test.tsx` (transcript) | 1 | Expected absent component module during test-first preparation; no tests collected. This is NOT claimed as the behavioral RED. |
| `npm test -- src/EditorialPolicySettings.test.tsx src/App.test.tsx src/editorialPolicyApi.test.ts src/illustrationReviewApi.test.ts` / `targeted-01.log` | 1 | 96 passed / 1 failed. Test incorrectly read input `.disabled`, which excludes inherited fieldset disabling. Changed assertion to observable `:disabled`, preserving actual control freeze. |
| `npx tsc --noEmit` / `typecheck-01.log` | 1 | Unsupported brief example `ByRoleOptions.exact` and zero-argument spy tuple inference. Omitted unsupported option (string name is exact by default) and typed the fetch boundary normally. No casts/suppression for these failures. |
| `npm test -- src/editorialPolicyApi.test.ts -t 'pending response\|NUL'` / `targeted-02-red.log` | 1 | 2 failed / 58 filtered: pending reader abort timed out at 5000ms; valid legacy Unicode/NUL incorrectly rejected. Fixed shared abort cancellation and exact string validation without modifying values. |
| Same four-file targeted command / `targeted-03.log` | 0 | 108/108, 4 files. |
| `npx tsc --noEmit` / `typecheck-02.log` | 0 | No diagnostics. |
| `npm test -- src/EditorialPolicySettings.test.tsx -t 'locally invalid'` / `targeted-04-red.log` | 1 | 1 failed / 11 filtered: a local invalid model incorrectly produced an ambiguous-save lock. Local validation is now distinct; user can correct and save without discarding. |
| `npm test -- src/App.test.tsx -t 'editorial drafts\|eight DEMO'` / `targeted-05.log` | 1 | 1 failed / 1 passed / 16 filtered: test used a longer nonexistent mode-confirm button label. Corrected to existing `Переключить и сбросить`; production App unchanged. |
| Same four-file targeted command / `targeted-06.log` | 0 | 114/114, 4 files. |
| `npm test -- src/App.test.tsx src/EditorialPolicySettings.test.tsx src/editorialPolicyApi.test.ts src/illustrationReviewApi.test.ts src/IllustrationReviewPanel.test.tsx` / `targeted-07.log` | 0 | 129/129, 5 files, including existing reviewer panel/API. |
| `npm test -- src/editorialPolicyApi.test.ts -t 'unsafe base'` / `targeted-08-red.log` | 1 | 2 failed / 7 passed / 53 filtered: URL normalizes empty query/hash away. Reject their original delimiters before token transmission. |
| Same five-file targeted command / `targeted-09.log` | 0 | Final targeted GREEN: 131/131, 5 files, 2.86s. |
| `git diff --check --` followed by all eight owned paths | 0 | No whitespace errors. Git warned that tracked LF files may become CRLF on a later Git touch. |
| `npx prettier --write` followed by all eight owned paths (frontend-relative) | 0 | Formatting only owned paths; performed before final source freeze. |

## Frozen source and one full frontend verification

All eight source/test files were frozen after final formatting/targeted GREEN and before the following full commands. Root was notified before these runs. Manifest: `frozen-source-sha256.txt` in the recovery directory. No code/test generation split or changes between these full verification runs and the owned commit.

| Path | Working-file SHA256 |
| --- | --- |
| frontend/src/boundedResponse.ts | 4f7ee3832f7a9dba30d2db6149808914551d5e7c6679777a22df61da795d1f0e |
| frontend/src/illustrationReviewApi.ts | 4762c4a16623b74134dbbcbe861eff06fb5a4b07e1e72ae4955871ac85ff99dc |
| frontend/src/editorialPolicyApi.ts | 9977fbfa15c2662738adf411e16a1045fcbc9f09d9fe166c3fc5898503b752dd |
| frontend/src/editorialPolicyApi.test.ts | deefe655f7a866f07ce1ba1a20b8c3e9894c0db0858bb77e2bd71c72e38277c6 |
| frontend/src/EditorialPolicySettings.tsx | 1b818c2b0c0e27cb3d4e572f601ae122f847ae0074e156f9adbab50163c42472 |
| frontend/src/EditorialPolicySettings.test.tsx | b316bde88d2d83ffac930ba5d4ed3f5cd0d1072f3e2fcfe6a9cc007aaccf3a6c |
| frontend/src/workspaces.tsx | b0081b3e30c8d9c71a7f0a259ef40122e430118cc041a6f4e9216778d287b84b |
| frontend/src/App.test.tsx | bdec2ab0773dfabc6cd089f5c4b90897843652adf1c5a41023542ffa4c534596 |

| Final full command | Native result | Raw log / output |
| --- | --- | --- |
| `npm test` | 0 | `full-vitest.log`: 21 files passed, 325/325 tests passed, 3.63s, no warnings or skipped tests. |
| `npm run format:check` | 0 | `full-format-check.log`: all matched frontend/e2e files use Prettier style. |
| `npm run build` | 0 | `full-build.log`: TypeScript noEmit passed; Vite 8.2.2 transformed 44 modules, built in 217ms. CSS39.06kB/gzip9.53kB; JS402.96kB/gzip112.76kB. No warnings. |

The three independent final checks were dispatched together against the same frozen source. Full frontend suite/format/build each ran once. No backend full suite, old Docker/browser recovery gates or production services ran.

## Self-review / limitations

Read the complete owned diff and checked the brief against implementation. Extraction touches only the old stream wrapper and its import; existing reviewer API/panel regression suites pass. Settings has one App dirty owner with a stable child callback; tests prove saving either form does not clear the other form's dirty draft. All server-authority flags fail closed, error bodies are never read into notices, save acknowledgements must match submitted editable values, and stale generations cannot populate trusted form/success state. No optimistic save or automatic retry is present.

The new panel is a focused but verbose form (400 lines after formatting); existing `workspaces.tsx` and `App.test.tsx` are already large. No unrelated restructuring was introduced. Row controls operate on controlled current array positions without sorting/reordering; exact submitted strings and alias multiplicity are preserved.

Task1 verification is source/RTL/transport evidence only. Actual isolated migrated API persistence, real browser privacy/dirty/narrow/axe flows, and comparison of all eight DEMO screenshots with the accepted baseline remain Task2, after root's independent spec/quality review. Default503/provisioning, real model qualification, worker/rewrite/publication permissions and optional api-only Compose secret integration remain pending and outside this commit. No runtime/qualification/release acceptance is claimed.
