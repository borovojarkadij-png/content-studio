# State machines

| Entity | States |
| --- | --- |
| IncomingPost | RECEIVED → TECHNICAL_REJECTED \| DEDUPLICATED \| EDITORIAL_PENDING → EDITORIAL_REJECTED \| MANUAL_REVIEW \| ELIGIBLE |
| RewriteJob | NOT_CREATED → DISPATCHED → RUNNING → SUCCEEDED \| RETRY \| FAILED \| FAILED_FACTS \| FAILED_SOURCE \| BLOCKED_EDITORIAL \| SUPERSEDED; RETRY or expired RUNNING → fresh fenced claim |
| SemanticVerificationJob | QUEUED → RUNNING → SUCCEEDED \| REVIEW \| BLOCKED \| FAILED; expired RUNNING → fresh fenced claim (maximum two committed attempts) |
| MediaAcquisitionJob | QUEUED → RUNNING → SUCCEEDED \| NO_MATCH \| BLOCKED \| FAILED; transient failure → delayed QUEUED; expired RUNNING → fresh fenced claim (maximum two attempts) |
| Publication | DRAFT → SCHEDULED → PENDING_APPROVAL → APPROVED → PUBLISHING → PUBLISHED; terminal CANCELLED/EXPIRED/BLOCKED/FAILED |
| ScheduleSlot | AVAILABLE → RESERVED → LOCKED \| RELEASED |

Only domain services should transition these states. Completed rewrite atomically
emits an OutboxEvent; retry/claim metadata remains in PostgreSQL. Full AuditEvent
history for all state changes remains pending (the table above includes intended
publication states, not proof of an implemented publication runner).

Rewrite budgets are committed when claiming, before possible external calls.
Old/expired tokens cannot store either success or error transitions. Success leaves
the per-output draft PENDING and the candidate AWAITING_REWRITE; approval remains
explicit and editorially guarded. Deterministic anchors are not semantic proof.
