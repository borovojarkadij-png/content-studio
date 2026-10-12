# SDD ledger — plan: docs/EDITORIAL_DURABLE_ADMISSION_IMPLEMENTATION.md

BASE:1d00655e7722ea615f23a35f860800b01d1d1bff.
Task1: in_progress, sole writer /root/editorial_admission, gpt-6.1-sol/high,
fresh no-history dispatch, no helpers. Adapter increment6dd3517 independently
accepted; root checked frozen native evidence and pushed reviewed source/docs
to authorized origin/branch at1d00655. Root owns state/CI/actual Windows PG.

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

Root actual Windows PG final02:1 FAIL/87 PASS/60.67s/exit1. Sole failure is
overlength model fixture expecting IntegrityError while PG VARCHAR255 rejects
earlier with DataError/StringDataRightTruncation. Production guard intact;
same writer owns narrow dialect-aware test correction. Original native log
editorial-admission-root-pg-20261012b.log retained on D:. Full02 source gate
continues; test-only amendment must be separately covered and reported, no
false frozen-hash equivalence or unchanged full-suite repetition.

Root corrected strict Windows PG88 PASS/62.03s/exit0, amended testA17D hash
independently matched; all production hashes unchanged. Exact owned synthetic
PG restart/double read-only reopen PASS,176 fresh schemas/116 QUEUED+2 terminal
jobs/all nine table snapshots unchanged. Original failing log retained. Root
report EDITORIAL_DURABLE_ADMISSION_VERIFICATION_20261012.md carries exact IDs,
hashes/limits; no provider calls or operational activation. Full02/review pending.

Task 1: complete (commits1d00655..88ce234, review clean).
Independent /root/editorial_admission_review read full2095-line package and
approved spec/quality, no findings. Root matched all7 frozen hashes and original
full02 native log/hash2301 PASS/6 explicit old PG-only SKIP/396.76s/exit0;
amended test separately88 SQLite/88 actualPG PASS. Existing skip coverage/new
exact remote CI remains a separately recorded gate, not inferred acceptance.
No source/provider/runtime permission promoted beyond canonical enqueue.
Original RED process history/report provenance is being clarified by same
writer without rerunning tests/source; root will retain that explicit boundary.

Root resolved chronology boundary: report-only0d142f1 retains original native
RED output excerpts/chunk IDs/exits, explicitly transcribed from worker tool
history rather than fabricated standalone logs. Original standalone RED logs
were not retained; root checked the actual completed GREEN logs/hashes directly.
No source/test changes or reruns. Exact new CI still pending after reviewed push.
