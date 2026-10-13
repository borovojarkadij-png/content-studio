# SDD ledger — plan: docs/TELEGRAM_INTAKE_SELECTION_IMPLEMENTATION.md

## Preflight and scope

| Tasks/interface | Produced/consumed contract | Finding |
| --- | --- | --- |
| 1 / current intake/planner | New pure module only, no caller changes | Existing stablehash intake and targetmix gap remain; cannot claim wholefeature |
| 1 / future persisted window | Candidate/policy/carry/window/result identity | Caller must freeze source membership and commit carry; kernel alone grants no restart guarantee |
| 1 / new tests | Exact dataclass/function names, literal picks, normalized digest | Self-consistent; first importability RED distinguished from behavioral RED |
| 1 / existing guards | No editorial/rewrite/publication imports or jobs | Selection evidence never substitutes for current hardgate |

Ruling: proceed with autonomous scoped design/plan without intermediate approval
ceremonies — explicit approved architecture and human instruction to decide and
continue while asleep; cost if wrong: isolated unused kernel can be revised,
no operational policy or authority is changed.
Ruling: pure kernel first rather than planner-only or immediate ingest rewrite —
observed preAI/fanout/dedup lock integration deserves its own gate; cost if wrong:
one additional integration step, no false feature-completion claim.
Ruling: HYBRID uses80percent top/20percent deterministic exploration, ceil top;
unknown scores hold in all modes — requirement names modes but no exact split;
cost if wrong: explicit versioned algorithm/policy can be revised before caller
activation, small windows prefer top and coldstart may remain manually held.
Ruling: fractional intake carry is explicit input/output, not process-global —
small windows must not always floor to zero; cost if wrong: future durable caller
must atomically freeze/commit it, existing ingress stays unchanged now.
Ruling: preserve SDD workspace/reports through unfinished PHASE — human requests
recoverable exactstate; cost: small docs storage, no deletes/data operation.

Spec self-review: exact input/output signatures and algorithm/digest literals
consistent; original intake vs targetmix requirement retained. Scope decomposed
to one independently testable kernel. All validation/algorithm/reason/carry/digest
requirements mapped to Task1 cases; no placeholder matches. Only newtwofiles+
ownreport; rootdocs/evidence/CI. No fullbackend repeat for disconnected puremodule.

NEXT rootdesign/plan checkpoint, Task1 solewriter then independent scopedreview,
networknone actualpackage smoke/finalreview/exactCI. Backupcap bffda47 pushed
native0/exactremote ownerverified; newCI38338368307 active, no newCIclaim yet.
