# SDD ledger — plan: docs/EDITORIAL_DURABLE_ADMISSION_IMPLEMENTATION.md

Task1: prepared, not dispatched. Depends on independent acceptance of the
classifier adapter increment. Root records BASE immediately before dispatch.

| Preflight | Producer/consumer boundary | Result |
| --- | --- | --- |
| Task1 internal | New exact reservation owner -> canonical admission | Owner written only after successful targeted reservation; NULL historical owners fail closed, no guessed backfill |
| Task1 internal | DB diagnostic policy -> accepted request validation | No missing-policy default, credential or qualification field; protected entities explicitly configured |
| Task1 internal | Canonical source/mapping/manual decision -> job/outbox | No input-text/hash authority; existing cheap filters, freshness and ownership checks precede writes |
| Task1 internal | Existing cross-account mappings -> canonical ownership | Source must match donor account; configured output may use another existing account, both identities bound |
| Task1 internal | Existing ingestion transaction -> enqueue | No network/commit/blanket IntegrityError catch, caller rollback preserves fingerprint retryability |
| Task1 internal | Additive migration -> historical rows/downgrade | No existing data reset; populated new tables block downgrade before DDL |
| Task1 internal | QUEUED diagnostic request -> future executor | Pending persistence is not completed delivery; pre/post-IO CAS, evidence/usage and real qualification remain explicit next increment |
| Task1 internal | Same admission fixture -> SQLite/strict PostgreSQL CI | Explicit environment opt-in creates only fresh validated UUID namespaces; one pytest-file append, no disabled checks |
| Task pairs | One implementation task; root documentation separate | No concurrent writers, no UI/provider/worker-loop edits |

Ruling: implement the approved canonical admission in a separate bounded
increment after adapters, with request persistence but no executable provider
path — avoids putting LLM IO inside ingress and preserves current manual gates
— cost if wrong: additive schema/service rework, no live charge or publication.
Ruling: add nullable exact fingerprint owner, never derive old ownership from
matching text — current table cannot prove which immutable source reserved it
— cost if wrong: old manual posts require explicit future safe backfill/resubmit,
not silent AI submissions or alteration of existing passing rewrite behavior.
Ruling: keep current checkout/branch, no new worktree/approval pause — explicit
user preference and accepted implementation scope — cost if wrong: reversible
source rework on the same non-main branch, no production changes.
Ruling: preserve this ledger through unfinished PHASE1, no finish/merge/cleanup
— final release acceptance remains outstanding — cost if wrong: retained docs.
Ruling: preserve explicit cross-account mappings rather than impose a new
same-account restriction — TelegramConfigurationService.create_mapping currently
validates both endpoints independently, no equality requirement — cost if wrong:
future admission must still fence each actual endpoint/owner, never guess identity.
Ruling: include new admission cases in the existing strict PostgreSQL job rather
than accept SQLite alone — same canonical fixture with create-only namespace
opt-in, no new service/permission or old test removal — cost if wrong: longer
verification time, bounded by the unchanged existing job timeout.
