### Task 1: Implement the bounded deterministic intake kernel

**Files:** Create backend/src/newsflow/domain/intake_selection.py. Create backend/tests/test_intake_selection.py. Own report task-1-report.md only. Read spec for exact validation, fields, digest representation and algorithms; no other product edits.
**Consumes:** Frozen tuple of bounded candidate evidence, explicit window key/policy/carry, no outside state.
**Produces:** IntakeCandidate, IntakeSelectionPolicy, IntakeSelectionDecision, IntakeSelectionResult and select_intake_window signatures exactly as spec; decisions cannot authorize rewrite/publication.

- [ ] Read spec fully. First importability RED avoids collection errors from a nonexistent module:
```python
from importlib.util import find_spec
def test_ranked_intake_module_available():
    assert find_spec("newsflow.domain.intake_selection") is not None
```
  Retain native1, create minimal declarations/stub, then write concrete failing behavior before implementing ranking. Do not change existing namespace exports. Record which RED is importability versus actual failing selection behavior; remove the temporary discovery assertion once behavior tests import the real module.
- [ ] Establish desired API/real selector behavior with hand-derived picks:
```python
rows = tuple(IntakeCandidate(i, "b"*64, i) for i in range(1,11))
result = select_intake_window(rows, window_key="a"*64,
    policy=IntakeSelectionPolicy(50,"HYBRID"))
assert result.selected_ids == (10,9,8,7,3)
assert result.quota == 5
assert result.carry_out == 0
```
  TDD minimal declarations/stub permitted only after importability RED; retain behavioral FAIL before replacing stub with algorithm. RANDOM literal(8,3,7,2,1), TOP_SCORE literal(10,9,8,7,6);100rows30percent selects literal tuple100down71.
- [ ] Implement exact frozen/slots contracts, strict validation and bounded pure algorithm from spec. Stage top then random for HYBRID; reasons sorted by candidateID. Canonical digest normalizes valid numbers to float and includes excluded rows; no elapsed time or implicit policy/random seed. Do not add exports to existing files.
- [ ] Add regression cases for invalid inputs including excluded/empty validation; zero/full/empty/allblocked; unknown/highestexcluded/threshold equality; carry=0,30,60,90 across one-row30percent windows yields quota0,0,0,1 and carry30,60,90,20; 1000 accepted vs1001 rejected, no arbitrary iterable. Replay/permutations/ties/content/policy/window/carry/revision digest changes and immutable inputs/results. Test expected behavior with literals, no production helper mirrored expectations.
- [ ] Run new module tests to GREEN; run targeted existing domain hype/engagement/technical-filter/reject boundary suites once, not fullbackend for a disconnected pure module. Run Ruff0.17 check/format, compile, diff check. Use D: TEMP/TMP/basetemp, Python3.12 with existing Telethon1.45 overlay before pytest where needed. Retain RED/intermediate FAIL/native exits, pristine final output, no provider calls.
- [ ] Self-review/freeze newtwofile hashes; report exact commands/results/native exits/evidence/limits to own report, commit only two new files plus own report. Return DONE/commit/oneline tests/concerns/reportpath. Root independently reviews complete diff, runs packaged network-none smoke and checkpoints/exactCI without claiming durable integration or PHASE completion.
