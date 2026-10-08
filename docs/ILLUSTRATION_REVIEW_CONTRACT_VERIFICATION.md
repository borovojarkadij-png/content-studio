# Human illustration review contract — 2026-10-08

## Scope and boundary

Implemented the next approved offline domain increment, not a new publication
permission. `domain/illustration_relevance.py` has no database, network, AI,
filesystem, API or worker dependency. Existing library publication preflight
continues to reject with `ILLUSTRATION_RELEVANCE_APPROVAL_NOT_IMPLEMENTED`.

An immutable binding includes exact candidate, output channel, mapping, content
key, source revision/text hash, rewrite output/text hash and asset identity/bytes/
metadata hashes. Source/channel/draft/photo/provenance changes invalidate review.
The future canonical SQL resolver, not a browser or provider, must construct
these values from current guarded records and decoded bytes. Asset metadata
must cover origin, storage, MIME, license and attribution. This increment does
not claim that resolver or durable review storage exists yet.

Human evidence requires an explicit enum verdict, positive reviewer identity,
bounded nonempty rationale, aware timestamp and boolean acknowledgment that the
photo is an **illustration**, not a photograph of the described event. Absent,
raw/boolean/structurally similar model evidence, rejected/uncertain judgments,
missing acknowledgment, future review, changed bindings or any revocation never
grant use. IDs/hashes/keys/timestamps are strict and revalidated at assessment.
Values are frozen; there is no JSON-to-approval coercion.

The narrow `allowed` result is not authentication, fact preservation, model
qualification, editorial/source/technical/rights readiness or permission to
publish. A future authenticated durable writer must establish reviewer identity,
resolve canonical bindings, audit immutable decisions and revalidate all hard
gates. No public override, operational flag, model release or actual send added.
Human review remains separate from an eventual benchmarked visual-semantic
verifier; synthetic judgments cannot qualify a real model.

## Verification

- Test-first RED: first two real domain behavior tests fail because the approved
  module is missing (ordinary test failures, not collection failure); minimal
  implementation then passes all **107** initial strict contract cases.
- Final combined contract / actual PowerShell refusal / existing migrated media
  status / publication-preflight regressions: **146 PASS /6.11s**. This retains
  the current hard library publication block; no provider or publication calls.
- Exact CI-context Ruff initially reports import sorting and intentional naive
  datetime fixture construction. Import ordering fixed; naive fixtures now use
  `NOW.replace(tzinfo=None)` without disabling datetime rules. Fresh exact Ruff,
  changed-file format and D: bytecode compile: PASS.
- Explicit fresh D: isolated migration upgrade/check/downgrade/base/upgrade/check:
  PASS, no drift. No new schema/migration or operational database touched.
- Fresh frontend **205 PASS**, format and TypeScript/Vite build PASS. No frontend
  code changed; preceding final real browser **33 PASS** is historical UI proof,
  not a fresh browser run for this domain-only increment.
- Required independent read-only review found one Important DST-fold defect:
  aware local comparisons can ignore `fold` on a shared timezone object. Actual
  New York 2030-11-03 01:30 fold=1 accepted against fold=0 reproduced RED;
  UTC normalization and conversion-error refusal corrected it. The added test
  checks exact 05:30/06:30 UTC instants, future rejection and reverse acceptance.
  Follow-up read-only review confirms finding resolved, no remaining actionable
  issues in the correction. Reviewer ran no tests or live calls.
- Initial full backend **1511 PASS /175.91s**, before the review correction.
  Final post-correction full isolated Telethon 1.45 backend **1512 PASS /172.51s**,
  completed session 19438. Fresh exact Ruff and D: compile PASS after correction.
  Do not substitute the initial count for this final corrective proof.

## Observed CI startup failure and safe test harness correction

Exact source `d29d6f0` CI **37792513344**, backend job **113363336650**, records
**1 failed /1402 passed /221.11s**: `/usr/bin/pwsh` produces no stdout/stderr
before the test's 20-second subprocess deadline. The actual script has its
mixed-family refusals before fixture writes or Docker. The same unchanged
source on docs HEAD `008eef6`, CI **37792828642**, backend **113364454003**,
subsequently passes, including all eight workflow jobs (fresh `gh` inspection).
A cold runtime/host scheduling delay is the supported
timing hypothesis, not proof of a script refusal defect or Docker failure.

The test harness now uses a noninteractive process with telemetry opt-out and
a still-hard **60-second** deadline covering PowerShell/.NET startup. Timeout
still fails: no retry, xfail, ignored error or removed assertion. It copies
the exact script into an owned isolated test root and installs a PowerShell
Docker trap, so a missing guard cannot invoke a real daemon or write operational
fixtures. Both mixed channel-sync/publication and admission/channel-sync cases
must return the exact expected refusal, never invoke Docker and create no
artifact directory. Actual Windows execution: **11 PASS /2.61s**, before the
combined confirmation above. Original source workflow subsequently finished
FAILED solely on this backend test; its other seven jobs, including both Docker
variants, succeeded. Corrective Linux CI remains pending until the new exact
checkpoint runs; the original failure stays recorded as failed.

No real Telegram/AI/media network calls, authorization/rights/key changes,
operational queues or Docker storage modifications. Current Windows Docker
and live authorization/provider acceptance remain independently **NOT VERIFIED /
BLOCKED BY ENVIRONMENT**. PHASE 1 is not complete.

## Next increment

Create the read-only guarded canonical illustration-binding resolver and actual
migrated regression tests: clean session, exact current candidate/mapping/source/
approved channel draft, current technical/editorial gates, selected successful
library acquisition and validated asset bytes/rights. Hash metadata canonically;
revalidate after byte reads and refuse any stale or contradictory relation.
Never trust client hashes, inferred topic relevance or old selected-job success.
Then add durable audited human review storage/workflow separately. Keep current
publication hold until the complete durable boundary is integrated and verified.
