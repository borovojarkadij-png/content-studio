# Telegram ranked intake — deterministic decision kernel

## Context and decision

Approved Telegram requirements distinguish intake percentage from output donor
target mix, require RANDOM/TOP_SCORE/HYBRID(default), and prefer the best30of100
suitable posts over an arbitrary30. Current stable hash intake cannot do that.
See AUTOMATION_SELECTION_GAP_ANALYSIS_20261013.md for observed integration gaps.

This is an architectural seam, implemented in bounded independently reviewed
increments under the user's explicit autonomous implementation authority. Start
with a side-effect-free comparison kernel. Alternatives: change planner alone
(cannot recover already discarded ingress); replace durable ingress immediately
(mixes ranking algorithm, migration, locks and authority in one review); chosen
kernel first (independent deterministic acceptance, no operational activation).

This increment does NOT finish ranked ingestion, persist selection, change any
API/UI/default worker, consume target mix or qualify a model. The next durable
integration must own frozen membership, source/policy fencing, dedup, carry and
idempotency before calling this kernel. Existing intake stays unchanged meanwhile.

## Interface

Create `domain/intake_selection.py` using frozen/slots dataclasses and no new
dependency, clock, SQL, provider, filesystem, randomness or environment access.

`IntakeCandidate(candidate_id:int, revision_sha256:str, score:float|int|None,
eligible:bool=True)` describes frozen comparison evidence, not editorial PASS.
Strict positive signed64 IDs, unique per window; lowercase64hex revision digest;
score None or finite exact int/float in[0,100], bool never numeric; exactbool
eligibility. Invalid inputs fail the entire decision, including excluded rows.

`IntakeSelectionPolicy(intake_percent:int=100, mode:str="HYBRID",
minimum_score:float|int=0)` has exactint percent0..100, literal modes above,
finite exact int/float threshold0..100, bool rejected.

`select_intake_window(candidates:tuple[IntakeCandidate,...], *, window_key:str,
policy:IntakeSelectionPolicy|None=None, carry:int=0) -> IntakeSelectionResult`.
Exact tuple of at most1000 rows, exact dataclass input types, lowercase64hex
window key, exactint carry0..99. Validate before any early return. No arbitrary
iterable traversal, duplicate identity or silent coercion. An empty window is
valid, produces no picks and preserves carry.

Result: frozen/slots `IntakeSelectionResult` containing `algorithm_version`
("intake-selection-v1"), `input_sha256`, `selected_ids`tuple in selection order,
`decisions`tuple of frozen/slots `IntakeSelectionDecision(candidate_id,selected,
reason)` sorted by ID, `eligible_count`, `quota`, `carry_out`.
No rewrite_allowed/publication permission field or executable job is produced.

## Algorithm

1. Validate all inputs; sort candidates by ID for canonical input/audit order.
2. Ineligible rows get EXCLUDED regardless of score. Eligible None scores get
   UNKNOWN_SCORE; eligible known scores below threshold get BELOW_THRESHOLD.
   None is never zero. Only remaining known-score eligible rows form poolN.
3. `(quota,carry_out)=divmod(N*intake_percent+carry,100)`. No quota padding beyond
   N; no blocked/unknown row consumes carry. Caller must transactionally persist
   carry and freeze window membership; this kernel does not promise recovery.
4. TOP_SCORE: descending score, ID ascending ties, take quota; SELECTED_TOP.
5. RANDOM: ascending SHA256 ASCII bytes of
   `window_key + ":" + str(candidate_id) + ":" + revision_sha256`, then ID ties;
   take quota; SELECTED_RANDOM. This is deterministic exploration, not entropy.
6. HYBRID: take ceil(4*quota/5) from TOP_SCORE, then remaining quota from RANDOM
   among unselected pool rows; reasons retain respective stage. DefaultHYBRID.
7. Other pool rows get NOT_SELECTED; selected_ids lists top stage before random
   stage, regardless of decision audit order. No post selection score mutation.

Digest: SHA256 UTF-8 of `json.dumps(payload,sort_keys=True,separators=(",",":"),
ensure_ascii=True,allow_nan=False)`. Payload keys exactly `algorithm_version`,
`window_key`, `carry`, `policy`, `candidates`. Policy keys `intake_percent`,
`mode`, `minimum_score`; candidate keys `candidate_id`,`revision_sha256`,`score`,
`eligible`, sorted by ID. Normalize valid numeric score/threshold to float,
preserve None. Digest binds all rows including excluded evidence, current
policy/carry/revisions/window/version, not input permutation. It is audit
identity, not a signature, authorization or independently verified source truth.

## Verification and safety

TDD real kernel behaviors and hand-derived literal picks. TOP_SCORE100rows
score=id-1,30percent selects100..71; HYBRID tenrows score=id,50percent selects
10,9,8,7,3 for window"a"*64/revision"b"*64. Independently computed SHA ordering
is8,3,7,2,1,9,4,6,5,10, so RANDOM picks8,3,7,2,1. These expected IDs must be
literals, never computed by production helpers in tests.

Test permutations/replay/ties/zero/full/empty/one-row carry across windows,
excluded highestscore/unknown/belowthreshold, threshold equality, all invalid
types/bools/nonfinite/negative/ranges/duplicate IDs/hash/1001row exhaustion;
validate even empty/all-excluded. Test digest normalization/change sensitivity,
frozen result/input preservation. Import kernel in isolated network-disabled
package smoke later; no actual provider/Telegram/key/rewrite/publication calls.

No existing tests/gates weakened. Only new kernel/test and writer report are
sourcewriter ownership. Root owns docs/evidence/CI. Separate durable pre-AI
admission and planner target-mix integration remain explicitly unfinished.
REJECT→rewrite_allowed=false→no new RewriteJob→rewrite calls0 remains mandatory;
selected=true can never substitute for editorial/source/fact/media guards.
