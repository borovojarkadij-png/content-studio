# Whole-branch commercial review checkpoint

Reviewed range: `be730b8621827b85125bc53a3dce7f6eb235e9af` → `7af4324cac284b8bd3085eecb80e14c166149ccc` on `codex/dark-navy-ui`.

Package: `review-be730b8..7af4324.diff`, 3,369,484 bytes, 120 commits, 412 changed files, 73,345 insertions / 443 deletions. HEAD matched the requested head and the checkout was clean at review. This is the full-branch checkpoint, not a substituted Task 1–4 review and not PHASE 1 completion.

Verdict: **continued development is appropriate, with the four Important findings below corrected before relying on these boundaries for operational use. Release readiness is not established.** No Critical finding was verified in the inspected paths. Accepted Task 1–4 work is not revoked wholesale; the findings concern older cross-task paths in the complete range.

## Strengths

- The production ingress and rewrite paths have substantive defenses beyond a stored PASS bit. `domain/durable_ingestion.py`, `domain/sql_editorial.py` and `services/durable_rewrite_runner.py` reapply the editorial constraint, retain hostile source edits, reserve exact mapping fingerprints transactionally and fence provider completion with source/current-policy checks. The ordinary-ingress reject/unclassified fan-out regression in `backend/tests/test_mapping_fanout_dedup.py:154` checks zero new jobs, zero rewrite-request events and a provider factory that must not run. The migration exception is finding I-1 below.
- Publication has a conservative uncertain-outcome boundary: SENDING is committed before transport; unknown outcomes are quarantined; exact direct-response observations can reconcile without another send. Current source, approved draft, facts, mapping filters, rights, destination identity and request binding are checked independently. `backend/tests/test_publication_observation_recovery.py:46` exercises actual injected storage failures after send, while the historical-ack test at `:92` distinguishes recording an already delivered message from authorizing a new send.
- Human illustration approval has a separate server-derived principal, strict request fields, canonical source/draft/asset binding, exact operation replay, append-only review/revocation history and atomic outbox audit. Client hashes are assertions to compare, not authentication. The SQL migration fences UPDATE/DELETE, SQLite replacement and PostgreSQL TRUNCATE; downgrade refuses populated history. The current consumer selects the newest review only and retains all independent publication gates.
- Snapshot compatibility is explicit: strict v1 reading remains, v2 carries the illustration review/binding, and the original-source digest path remains separate. The final photo transport verifies immutable byte SHA-256 and invokes its execution guard after upload, directly before send. `backend/tests/test_illustration_publication.py:109` covers exact labeled library publication; `:156` covers changes during upload. These are synthetic contract checks, not live-send qualification.
- The protected UI checks the complete response shape, exact source/draft/photo hashes and strong validator; the masked bearer stays in component memory. Request generations, aborts, explicit same-operation retry and eligibility-independent latest-review/revocation cover useful real failure cases. App mode selection mounts the live and DEMO flows separately; no navy redesign is part of this checkpoint.
- Channel synchronization explicitly distinguishes a trusted new-donor baseline from legacy/gap recovery. Deletion-first application, retained quarantine/replay obligations and current-session binding are much stronger than a simple polling cursor. Unknown ingress classifications remain manual rather than being assumed neutral.
- The Task 4 corrections are present on merit: input ancestor/reparse checks precede fixture creation; retained startup pins all seven original image IDs and forbids build/pull. The dedicated controller validates exact config, secrets, mounts, project and volume identities. The crash helper observes the original full container ID exiting with 137 rather than treating a successful kill request as completed recovery.

## Issues

### Critical

None verified in the reviewed paths. This is not a claim that every changed line or every possible concurrent interleaving was exhaustively inspected.

### Important

#### I-1 / P2 — Legacy fan-out migration creates new rewrite jobs without the editorial hard gate

- **Location:** `backend/alembic/versions/e7d3a4f810bc_scope_rewrite_jobs_to_output_channels.py:61`, `:67`, `:113`–`:135` (especially insertion at `:117`).
- **What happens:** `_scope_legacy_jobs` selects every unscoped old job and every candidate for its content key. With two output IDs it marks the old job SUPERSEDED and unconditionally inserts a new DISPATCHED job plus `rewrite.requested` event for each output. It never reads the current editorial decision, `rewrite_allowed`, protected-entity constraints, or candidate state.
- **Concrete trigger:** upgrade a pre-scope database containing an old fan-out job and two retained candidates whose decision has since become REJECT / rewrite_allowed=false. The migration creates two fresh jobs despite the binding requirement `REJECT → rewrite_allowed=false → no new RewriteJob → rewrite calls=0`. Missing/manual decisions also pass this backfill. The present worker should block the eventual calls; that does not satisfy the separate no-new-job invariant.
- **Evidence:** the implementation is unconditional SQL, not dependent on a speculative provider result. `backend/tests/test_configuration_migration.py:116` seeds a two-output legacy case without any editorial decision and explicitly expects new dispatches at `:179`; it therefore does not verify the hard gate during upgrade. No migration was executed in this review.
- **Correction:** preserve legacy history and only create new output-scoped dispatches for currently eligible, explicitly passing source/candidate decisions. For reject/manual/missing/invalid decisions, retain blocked/superseded historical records without inserting work. Add populated-upgrade regressions for REJECT, manual, missing and hostile/corrupt PASS as well as the valid passing fan-out. Do not delete already retained audit history as a repair.

#### I-2 / P2 — Semantic verifier admission and execution omit the current technical filter

- **Location:** `backend/src/newsflow/services/semantic_verification.py:189`–`:192`; provider creation/call at `:104` / `:113`; caller `backend/src/newsflow/services/durable_semantic_runner.py:183`.
- **What happens:** `_binding` checks job, editorial status, pending draft, source freshness, fact anchors and qualified approval policy/release, but never invokes `output_technical_allowed` or the equivalent current mapping/source exclusion guard. Both durable enqueue and the pre-provider execution guard reuse this binding.
- **Concrete trigger:** a legitimate rewrite finishes into PENDING, then the operator excludes its source domain/media through the existing mapping-filter API. With VERIFIED policy, a new semantic job can still be admitted, and an already queued job still constructs/calls the verifier. The same gap affects retained legacy source-link/video exclusions where the text/source revision remains current.
- **Why it matters:** a cheap configured exclusion is meant to precede AI use. Auto-approval later calls the technical guard in `rewrite_outputs.py`, so publication remains blocked, but source/draft data has already been submitted and usage can already be incurred. Checking only at approval is too late.
- **Evidence:** `backend/tests/test_semantic_approval.py:157` tests editorial/source/facts/policy/release/provider changes but not technical-filter changes; the queued-reject test in `backend/tests/test_semantic_runner.py:41` likewise does not cover route policy. This is a statically traced production call path; no model or database action was used to demonstrate it.
- **Correction:** include the fresh shared technical eligibility check in the common semantic binding used by admission, pre-call and post-call validation, before provider construction. Add synthetic cases for filter change before admission, after queue/reopen and during verification; require zero factory/provider calls for the first two and no durable usable evidence/approval for the last. Preserve the existing committed attempt/history policy rather than resetting budgets.

#### I-3 / P2 — Custom blocked-domain policy can be bypassed by encoded or scheme-relative hosts

- **Location:** `backend/src/newsflow/domain/technical_filters.py:110` and `:122`–`:136`.
- **What happens:** the mandatory YouTube path canonicalizes the host with `unquote`, but the custom-domain path extracts only `http(s)://` URLs and compares a host without percent-decoding. Consequently the two checks disagree on the destination identity.
- **Reproduced without network or persistent state:** a `MappingTechnicalFilter` blocking `example.org`, evaluated against hidden destinations, returned:

  | Destination | Actual result |
  | --- | --- |
  | `https://example.org/news` | rejected / FORBIDDEN_LINK |
  | `https://%65xample.org/news` | accepted |
  | `//example.org/news` | accepted |
  | `https://youtube.com/news` | rejected / YOUTUBE_LINK |

  This was one pure `python -B -c` evaluation of the actual filter/dataclasses. It performed no SQL, filesystem writes, provider calls or publications. Percent-encoded ASCII hosts represent the same blocked destination in ordinary browser URL processing; scheme-relative destinations should at least fail closed rather than escape the policy.
- **Why it matters:** the shared filter is trusted at ingress, rewrite, review, planning and publication. Passing the same defective check repeatedly does not restore the operator's domain restriction. Existing tests cover Unicode/trailing-dot hostnames (`test_persisted_mapping_filters.py:222`) and a plain hidden `https://example.org` destination (`test_hidden_donor_links.py:173`), but not these equivalent forms.
- **Correction:** use one strict host extraction/canonicalization path for both mandatory and custom-domain checks, with encoded separators/control/invalid escapes refused. Apply it to visible and retained hidden destinations. Cover percent-encoded hostname letters, scheme-relative URLs, subdomains and malformed encoded authorities; retain the pre-classifier/no-job/no-provider guarantees.

#### I-4 / P2 — Planner reconciliation and media acquisition take the same row locks in reverse order

- **Location:** `backend/src/newsflow/services/publication_planning.py:349`, `:359`, `:393`; opposite order in `backend/src/newsflow/services/internet_media.py:63`–`:86`.
- **What happens:** `_reconcile_stale_reservations` selects the planned-publication/candidate join with unrestricted `FOR UPDATE`, locking both rows, and subsequently requests the editorial row through `_is_currently_editorial_pass`. `InternetMediaAcquisition._binding` first locks rewrite job/editorial/draft and then requests that candidate with `FOR UPDATE`.
- **Concrete interleaving:** for a SCHEDULED candidate awaiting library media, a planner transaction holds candidate C; acquisition holds editorial E; planner waits for E; acquisition waits for C. The plan row does not serialize acquisition. The public plan-day route (`backend/src/newsflow/api/telegram.py:585`) can run concurrently with the worker, even when one worker executes its own stages sequentially.
- **Why it matters:** PostgreSQL must abort one transaction. This produces an avoidable planner error or leaves an already claimed media job to consume another limited attempt on lease recovery. The risk is liveness/reliability, not an asserted unauthorized publication.
- **Evidence/limit:** both lock orders were read directly; no PostgreSQL interleaving was executed under this read-only review. The examined planner/media tests cover stale state and provider-time changes but contain no independent-connection test for this pair of operations.
- **Correction:** establish one lock order across planner reconciliation and acquisition/approval, reloading and revalidating state after acquiring the required locks. Do not simply remove the editorial gate or add unbounded retry. Add a two-connection PostgreSQL regression that deliberately reaches this ordering and confirms completion without deadlock or burned acquisition budget.

### Minor / deferred ledger triage

1. **Existing color warning:** `.superpowers/sdd/ILLUSTRATION_REVIEW_IMPLEMENTATION/task-3-report.md:144` records simultaneous NO_COLOR/FORCE_COLOR behavior. Retain as nonblocking test-output hygiene. Resolve variable precedence in an isolated runner/environment change; it is not evidence of an application regression or reason to weaken tests.
2. **Nine older formatting differences:** `task-3-report.md:127`–`:130` records three older source areas and six older tests. The earlier Task 3 ruling was valid for that bounded increment, but “untouched by Task 3” does not mean “outside the whole branch.” Treat as accepted formatting debt, separately scoped from behavioral fixes. No repository-wide format PASS is claimed here; no formatter was run and the exact nine-file list was not independently regenerated.
3. **Actions runtime/runner warnings:** the ledger records old action-runtime fallback and upcoming ubuntu-latest transition notices; `.github/workflows/ci.yml:15` / `:19` / `:42` retains floating Ubuntu and older action major versions. Track a separate compatibility update with exact CI before any runner transition. These warnings do not invalidate current passing jobs, and this review does not independently verify the hosted-service announcement dates.

## Requirements and design rulings

- **REJECT / no new jobs / no calls:** ordinary production ingress and rewrite enforcement are strong; I-1 identifies the migration exception. No new ability to rewrite rejected text was introduced by the human illustration workflow.
- **Authentication:** dedicated server-owned reviewer ID and secret file, rejection of master-key reuse, strict API fields and memory-only bearer are coherent for the explicitly scoped single-reviewer local service. This is not general multi-user authorization. No credential was generated, exposed, changed or enabled during review.
- **Independent publication gates:** newest human image approval is narrow evidence; it does not waive editorial, source, draft, facts, current technical policy, rights, synchronization, clean-session or final byte checks. The inspected implementation preserves this separation, subject to the technical filtering findings above.
- **Source/sync/delivery history:** no blind channel-pts reset; current quarantine is enforced; replay rechecks source after ownership locks. Uncertain sends and exact receipt reconciliation are kept distinct. The immutable-review downgrade rule is appropriate.
- **Task 4 rulings:** separate fixture ownership, normalized Compose digests, redirected-input refusal and original-image retained startup are justified test boundaries. The corrected code addresses the prior findings; it does not certify older unrelated fixture controllers as having identical protections.
- **Scope:** Telegram only; YouTube remains excluded. Existing navy UI is preserved. Semantic deduplication, events/hype and operational workflows remain outstanding work, not silently counted as implemented.
- **Classifier distinction:** `backend/src/newsflow/domain/editorial.py:41` deliberately discards text and applies supplied annotations; donor polling supplies no qualified classification. Its default remains MANUAL_REVIEW / rewritefalse. Rewritten-draft semantic verification is a separate operation and does not fill the pre-rewrite classification gap.
- **Missing live acceptance:** synthetic fixtures do not qualify an actual model, real Telegram authorization/reconnect, authorized original-photo download, or live publication. Current documents appropriately mark those as pending. No phase-completion or operational deployment claim follows from this review.

## Coverage map and limits

The full-range package inventory and commit sequence were reviewed first, then risk-focused passes followed production contracts outside the illustration-only range. Counts below are **inventory**, not claims of reading every line in a category.

| Full-range category | Changed files | Review depth |
| --- | ---: | --- |
| Backend production source | 74 | Deep call-path review of ingress/editorial/rewrite, semantic admission/approval, synchronization, media/review and publication; selected supporting readers/configuration/provider code |
| Migrations | 33 | Inventory; full reads of rewrite fan-out, illustration immutable storage and media rights; existing base-migration diffs and explicit migration-target/runtime wiring; model constraints sampled |
| Backend tests | 120 | Relevant contract bodies and test inventories sampled to substantiate findings and safety claims; no suite rerun |
| Frontend source/unit files | 48 | Full protected reviewer panel/client; App mode mounting and selected planner/configuration lifecycle paths; reported unit evidence and test contracts sampled |
| Browser test files | 2 | Dedicated workflow coverage assessed from prior review/report and CI invocation; no new browser run or visual recapture |
| Scripts | 27 | Full corrected illustration controller, exact-ID crash helper, unattended ownership helper; illustration probe persistence/verification stages sampled; other families inventoried |
| Documentation | 80 | Current requirements/plan/current-state summaries, media semantics, SDD ledger and prior review/evidence reports; chronological evidence not all reread line by line |
| Other package/config/report files | 28 | Compose, proxy, workflow, package scripts, API assembly and report context; dependency-lock churn and all visual/style hunks not exhaustively audited |

Deep source pass details:

- Ingress/source: `domain/{editorial,sql_editorial,durable_ingestion,sql_ingestion,technical_filters}.py`; `services/{mapping_filters,source_revisions,source_deletions,donor_ingestion_runner,channel_baseline,channel_difference_runner,channel_sync_tick,source_sync_replay,account_health}.py`.
- Rewrite/semantic: `services/{durable_rewrite_runner,rewrite_outputs,publication_candidate_activation,durable_semantic_runner,semantic_verification,automatic_approval,rewrite_provider_settings}.py`; `providers/{openai_rewrite,openrouter_structured}.py`; current worker orchestration (the broad output was completed with focused call-path reads, not treated as an exhaustive worker-line proof).
- Media/illustration/publication: `services/{internet_media,source_photo,durable_media_runner,media_selection,media_job_read,illustration_binding,illustration_review,illustration_presentation,illustration_publication,publication_planning,publication_preflight,durable_publication_runner,publication_request_snapshot,publication_observations,telegram_publication_factory}.py`; dedicated API/auth and Telegram publication transport.
- Provider/configuration: full encrypted Telegram factory, selected actual Telethon lifecycle/history/identity methods, Commons bounded search/download/rights parser, settings API/redaction, studio usage aggregates; configuration mutation and route contracts sampled.
- Storage: populated migration fan-out; append-only illustration triggers and downgrade; media-mode/rights migration; source/rewrite/semantic model definitions and publication/media uniqueness/lease constraints. Remaining migrations were not all semantically proved.

Validation during review was limited to read-only file/diff/history checks and the pure filter evaluation documented in I-3. There were no source/index/HEAD mutations, helper reviewers, Docker commands, fixture writes, migrations, database access, real provider requests, publications or broad test reruns. The only written artifact is this report. Historical test totals and Windows restart success are identified as parent/implementer evidence, not new execution by this reviewer.

Exact CI `37924345507` for `7af4324` is tracked by the root agent. Its last supplied state during this review was all nine jobs in progress. This report does not substitute earlier green CI for that run or predict its result. Existing Windows proof remains useful synthetic evidence; latest operational deployment remains unverified.

## Recommended continuation

First perform **one combined correction wave for I-1 through I-4**, then a scoped independent re-review of the corrections and the targeted regressions. Keep runtime flags disabled, preserve rejected/manual history, original fixture manifests and accepted UI. Use isolated synthetic populated-migration and PostgreSQL concurrency tests; no operational migration or provider activation is needed to fix these findings.

After that, the next independent product increment should be a **source-bound pre-rewrite editorial-classification contract and offline qualification harness**: explicit protected entities/sentiment/framing and model/release provenance, cheap technical filtering and exact dedup before classification, canonical latest-source revalidation, unknown/error → MANUAL_REVIEW, and zero new rewrite jobs/calls for reject. Start with an injected default-disabled adapter and synthetic SQL-reopen regressions. Do not reuse the post-rewrite fact verifier as proof that this missing classifier already exists, and do not activate a real model without its separate qualification and authorization gate.

Ready to continue development: **yes, with the correction wave above**. Ready to merge/release or declare PHASE 1 complete: **no**; merge is outside authorization, four Important issues are open, exact current CI is separate, and classifier/dedup/events/hype plus real-model/live/operational acceptance remain independent release blockers.
