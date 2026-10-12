Require reload after ambiguous HTTP PUT failures — ADDRESSED. `frontend/src/EditorialPolicySettings.tsx:114` now classifies unexpected PUT statuses, including 500/502/504, as unconfirmed and sets the save block. Documented 401/409/422/503 and local validation retain their existing handling.

Check: `frontend/src/editorialPolicyApi.ts:195` now returns a static unconfirmed-save message for unexpected PUT HTTP failures without exposing response data.

Check: New panel tests verify retained dirty drafts, blocked repeat saves, discard/cancel reload behavior, and use of the refreshed ETag (`frontend/src/EditorialPolicySettings.test.tsx:133`). Actual App tests verify navigation persistence and the dirty mode-switch guard (`frontend/src/App.test.tsx:28`).

Check: Read the fix report through EOF and inspected the fix diff. Controller-confirmed evidence covers nine behavioral RED failures, 106 passing tests, native-zero format/typecheck/build, and matching eight-file hashes. No tests rerun; the original 325-test result applies only to the previous generation.

New breakage in the fix diff: None.

Out-of-scope observations: None.

Cannot verify: Task2 browser, API/SQL persistence, accessibility, and visual acceptance remain pending.

Fix round: All findings addressed; no new Critical/Important breakage.

Spec compliance: Approved within Task1 scope. Task quality: Approved.
