# Fresh illustration publication evidence

Task 2 consumes the authenticated immutable review history introduced by Task 1.
It permits an exact current approved library illustration through the narrow
review gate. It does not assert that the image depicts the reported event,
qualify a model, activate a worker or bypass another publication constraint.
No operational credential or live Telegram send was used during implementation.

The consumer selects the newest REVIEW by canonical candidate identity, including
newer rejected or uncertain reviews. It never searches backward for an approval.
Any revocation of that review prevents its use. The current eleven-field binding
is resolved again from SQL, approved draft/source, rights and bounded decoded
image bytes. The strict existing domain assessment verifies human provenance,
verdict, explicit illustration acknowledgment, time, revocation and exact binding.
Repeated reads refuse intervening changes. Historical reads are never permission.

The immutable publication envelope includes optional `illustration_review_id`
and `illustration_binding`. Library digests include these values, complete final
caption and actual photo type. Original-source text/photo digests retain their
original tuple algorithm. Encrypted requests now use version 2 and require both
review fields explicitly. Version 1 accepts only its original exact schema and
maps the two absent fields to None. Both versions reject duplicate/unknown/bool
or inconsistent fields. A queued source request can therefore survive upgrade;
a library intent cannot acquire a different review identity on retry.

The final library caption contains `Иллюстрация.` followed by complete required
license credit. Its complete text and actual photo type pass mapping filters and
the Telegram UTF-16 caption limit. No fact or credit is truncated. All original
editorial/source/rewrite/fact/technical/rights/session/peer/sync gates remain.

The configured photo reader rechecks the exact current review and bounded photo
bytes before upload, rechecks after bytes, and verifies the canonical labeled
caption. The existing durable runner re-prepares immediately after upload and
before the send RPC, comparing the exact digest and encrypted snapshot. SQL
transactions close before upload/network work. A concurrent revocation or change
causes zero send RPCs. Unknown committed SENDING outcomes remain quarantined and
are never automatically resent; known non-delivery retries retain the original
review identity and require current evidence again.

Media diagnostics return `HUMAN_ILLUSTRATION_REVIEW_REQUIRED` for the narrow
library hold. Exact current approval clears only that diagnostic to null;
selection/preview permission and full publication readiness remain separate.
Existing Planner text explains this boundary without new review forms or sends.

Verification and concrete RED/GREEN evidence are recorded in
`.superpowers/sdd/ILLUSTRATION_REVIEW_IMPLEMENTATION/task-2-report.md`.
The new migrated library regressions join the existing create-only strict
PostgreSQL CI family. Independent review and actual Windows PostgreSQL/packaged
acceptance are owned by the parent task and must be recorded separately.

NEXT_STEP: protected reviewer controls in the existing MediaPreparation surface,
plus an owned library-review/immutable-snapshot Docker restart acceptance probe.
Live acceptance remains pending separately provisioned credentials and explicitly
designated test destinations. Operational channels are outside test scope.
