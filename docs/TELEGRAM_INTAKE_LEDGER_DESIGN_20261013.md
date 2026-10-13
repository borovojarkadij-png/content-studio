# Durable Telegram intake comparison ledger

Scope: the next storage sub-increment of ranked pre-AI ingress. Persist the
already accepted pure kernel's comparison inputs/results and fractional carry.
Do not activate ranked ingestion, a new worker/API/UI or publication permission.
This is a necessary replay/audit seam, not completion of the automation feature.

## Context and choice

The kernel is verified independently and installed-package smoke passed.
Its caller currently owns membership and carry; losing either on restart would
make an eventual percentage quota unauditable. Existing ingress/fanout locks,
fingerprints and fresh editorial/source checks require a separate integration
gate. Options considered: process-local carry (not recoverable); append a result
without serial carry (concurrent windows can double-spend); a small transactional
comparison ledger (chosen). JSON snapshots avoid 1000 per-candidate SQL writes
while keeping total input/result size finite. They are comparison evidence,
not authentic source identity or current editorial/technical approval.

## Storage

Only two new tables, no existing business-row backfill or default activation.
Use existing SQLAlchemy/Alembic SQLite and PostgreSQL conventions.
Physical ledger id/stream_id/sequence/next_sequence types are BigInteger with
Integer SQLite variant (including autoincrement-compatible SQLite primary key)
to fulfill signed64 bounds on PostgreSQL. mapping_id retains the existing
Integer parent FK convention, carry fields Integer. Do not alter parent IDs.

`TelegramIntakeSelectionStreamModel`, table `telegram_intake_selection_streams`:

- id: Integer primary key, positive signed64.
- mapping_id: Integer FK channel_mappings.id, RESTRICT, positive signed64.
- policy_binding_sha256: exact lowercase64hex supplied by a future caller to
  bind its actual policy/configuration evidence; no value grants authority.
- policy_sha256: exact lowercase64hex of canonical ASCII JSON
  {algorithm_version:"intake-selection-v1",policy:{intake_percent,mode,
  minimum_score:float}}. Use sorted keys, separators(',',':'), ensure_ascii=True,
  allow_nan=False. This distinguishes selection settings within a binding.
- policy_payload: canonical policy object JSON, at most256 ASCII bytes.
- carry: exact stored integer0..99, initially0.
- next_sequence: integer1..9223372036854775807, initially1.
- created_at: required UTC-aware application time; portable year1..9999 DB
  bounds and strict SQLite26-character datetime representation, as sampling.
- Unique(mapping_id,policy_binding_sha256).

`TelegramIntakeSelectionWindowModel`, table `telegram_intake_selection_windows`:

- id: Integer primary key, positive signed64.
- stream_id: FK streams.id RESTRICT, positive signed64.
- sequence: integer1..9223372036854775806.
- window_key,input_sha256: exact lowercase64hex.
- algorithm_version: exact "intake-selection-v1".
- carry_in,carry_out: integers0..99.
- input_payload: canonical ASCII JSON object with exactly `policy` and
  `candidates`. Policy has the same three keys above. Candidates are sorted
  by candidate_id and each has exactly candidate_id/revision_sha256/score/
  eligible; known scores normalized to float. Maximum262144 ASCII bytes.
- result_payload: canonical ASCII JSON from dataclasses.asdict(kernel_result),
  maximum262144 ASCII bytes; tuple values naturally encode as JSON arrays.
- created_at: same time contract.
- Unique(stream_id,window_key) and Unique(stream_id,sequence).

Both tables have portable digest/length/integer range checks. SQLite additionally
rejects noninteger numeric fields, blob/text substitution and non-ASCII or
embedded-NUL text using typeof/byte-length equivalence. PostgreSQL digest regex
or portable replace check is strict; payload octet-length equals character
length. Snapshot semantic validity belongs to the bounded repository decoder,
not an SQL JSON expression pretending to enforce the kernel algorithm.

Alembic installs guards in both dialects: stream INSERT must be initialcarry0/
sequence1, reference an existing mapping and not replace an existing id or
unique binding; identity/policy/created_at are immutable; DELETE forbidden.
Stream UPDATE requires next_sequence=old+1 and a newly inserted corresponding
window with sequence=old next_sequence/carry_in=old carry/carry_out=new carry.
Window INSERT requires an existing stream at the exact sequence/carry, and
must not replace either primary/unique identity; all UPDATE including no-op
and DELETE forbidden. INSERT OR REPLACE must not erase either table's history.
PostgreSQL BEFORE TRUNCATE guards on both tables refuse whenever either ledger
table retains history, including CASCADE through a parent. Empty downgrade
serializes mapping→streams→windows via ACCESS EXCLUSIVE in PostgreSQL and a
zero-row stream UPDATE write lock in SQLite before checking either count.
No new triggers mutate existing mapping/source/editorial/job tables.

Migration id `c9d45e37f201`, predecessor `b8c34d26e190` (check current single
head before writing). Unsupported dialect fails visibly. Empty downgrade drops
only owned tables/triggers/functions; any retained stream/window aborts downgrade
before DDL. Forward fix is the rollback path after comparison history exists.
Existing data and REJECT/job/usage/outbox states survive upgrade/reopen/check.
Downgrade guarantees apply to this migration's own history, not atomicity of
an arbitrary multi-revision chain in SQLite. Actual evidence: empty ledger
downgrade to b8 commits successfully before a later populated sampling migration
refuses; the existing SQLite sampling test correctly expects b8. PostgreSQL
transactional DDL retains the initial version on later refusal; its regression
captures the exact before/after version. No env.py change or sampling preflight
is added to this ledger migration, and empty-ledger-only downgrade stays valid.

## Transactional repository

New `services/intake_selection_ledger.py`:

```python
@dataclass(frozen=True, slots=True)
class RecordedIntakeWindow:
    stream_id: int
    window_id: int
    sequence: int
    carry_in: int
    result: IntakeSelectionResult
    replayed: bool

class IntakeLedgerConflict(ValueError): ...
class IntakeLedgerCorrupt(ValueError): ...

class DurableIntakeSelectionLedger:
    def __init__(self, session: Session): ...
    def record_window(self, *, mapping_id: int, policy_binding_sha256: str,
        window_key: str, candidates: tuple[IntakeCandidate, ...],
        policy: IntakeSelectionPolicy, now: datetime) -> RecordedIntakeWindow: ...
    def load_window(self, *, mapping_id: int, policy_binding_sha256: str,
        window_key: str) -> RecordedIntakeWindow | None: ...
```

Caller must own an explicit active transaction with no pending/dirty/deleted
ORM objects; repository never begins/commits/rolls back the caller transaction
or performs a network operation. Reuse a clean flushed transaction, not a
session with unrelated pending work. Only SQLite/PostgreSQL supported.
Validate exact scalar types/digests/aware-time bounds and kernel inputs before
any SQL. Revalidate tampered frozen dataclasses through the public kernel.

Record locks the mapping first, then its existing stream, using populate_existing.
Missing mapping is ValueError. This serializes independent PostgreSQL sessions
and remains compatible with a future ingress caller already holding mapping;
no new lock may be taken from downstream publication/rewrite critical sections.
Create initial stream if absent; its policy payload/hash must match every call
for the same binding. Changed policy with reused binding is IntakeLedgerConflict.
Do not swallow unrelated IntegrityError; SQLite write-contention propagates for
caller transaction retry rather than fabricated success.

Before using carry, validate the stream's initial state or load/verify exactly
its previous sequence window and check carry_out against streamcarry. Every
stored payload is length/ASCII checked before JSON parsing; reject duplicate
object keys, nonfinite values, wrong/excess/missing keys, invalid exact types,
noncanonical serialization, >1000/duplicate candidate IDs, wrong policy/hash,
version/digest/result/carry/sequence linkage. Catch bounded malformed JSON/type/
recursion failures as IntakeLedgerCorrupt; do not turn corruption into defaults.
Recompute results with the accepted kernel and compare exact canonical result
JSON and input_sha256; never construct a trusted result from stored output alone.

For an existing window key, verify stored evidence using its original carry_in,
then require exact canonical requested inputs/policy; reorderings and numeric
int/float equivalents replay. Changed candidate revision/score/eligible/policy
raises IntakeLedgerConflict. Replay returns original ids/sequence/result with
replayed=True, changing no carry/history even if later windows exist.

For a new window, compute from the locked validated stream carry; insert window
and flush, then advance stream carry/sequence once and flush in the same caller
transaction. Return replayed=False. Empty/allblocked windows still get a durable
sequence while preserving carry. Sequence exhaustion fails before insertion.
Rollback leaves no stream/window/carry advancement. No partial commit is possible.
Load reads at most one stream and one window, validates strict binding/evidence,
returns replayed=True or None, never writes. Record uses a bounded number of
queries independent of candidate count (at most12 statements for first creation,
at most10 for existing stream excluding caller transaction setup). No history
scan, no per-candidate SQL, no Hype/provider work, no source/authenticity claim.

## Verification and later boundary

Task1 models/migration tests: behavioral RED, strict raw invalid inserts/updates,
immutability/replace/delete/carry linkage, guarded downgrade, old-row retention,
SQLite upgrade/check/downgrade-empty/re-upgrade/check. Task2 repository tests:
literal mode picks, fractional30% sequence, replay after reopen/later windows,
binding/input conflicts, rollback/fault between insert and advance, corruption
failclosed, 1000/1001, SQL query budget, missing/dirty/inactive transaction,
zero provider/jobs/usage/outbox and retained REJECT. PostgreSQL tests use existing
create-only UUID synthetic namespace helper; independent backend PIDs prove
same-window idempotency and different-window serial carry, no global monkeypatch
barrier/deadlock/sleeps. Record owns mapping→stream→window lock order.

Root performs one actual owned Windows PostgreSQL gate and installed Docker
reopen smoke after both scoped reviews, then final increment review/exact CI.
No repeated giant backend suite for each task; one covering/full checkpoint
after the repository task as proportionate, preserve every explicit SKIP.
No real Telegram/AI/publication, provider credentials or operational volumes.

Next integration must establish current source membership, exact owned dedup,
fresh policy/account/session and pre-AI holds for initial ingress AND fan-out;
it must revalidate selected evidence at editorial/rewrite/review/publication
boundaries. This ledger alone deliberately grants none of those permissions.
Targetmix/daily channel quota allocation remain separate. REJECT always means
rewrite_allowed=false, no new RewriteJob and zero rewrite provider calls.
