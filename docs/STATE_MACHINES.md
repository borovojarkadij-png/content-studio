# State machines

| Entity | States |
| --- | --- |
| IncomingPost | RECEIVED → TECHNICAL_REJECTED \| DEDUPLICATED \| EDITORIAL_PENDING → EDITORIAL_REJECTED \| MANUAL_REVIEW \| ELIGIBLE |
| RewriteJob | NOT_CREATED → DISPATCHED → RUNNING → SUCCEEDED \| FAILED \| BLOCKED |
| Publication | DRAFT → SCHEDULED → PENDING_APPROVAL → APPROVED → PUBLISHING → PUBLISHED; terminal CANCELLED/EXPIRED/BLOCKED/FAILED |
| ScheduleSlot | AVAILABLE → RESERVED → LOCKED \| RELEASED |

Only domain services transition these states. Each significant transition emits an
AuditEvent and, when background work is needed, a transactional OutboxEvent.
