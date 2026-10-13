### Strengths

- Strict validation precedes digesting and selection, including excluded rows, empty windows, duplicate IDs, exact types, signed64 bounds, and the 1000-candidate limit (`backend/src/newsflow/domain/intake_selection.py:89`).
- Canonical input ordering and the specified JSON representation bind all candidate evidence, policy, carry, window and algorithm version (`backend/src/newsflow/domain/intake_selection.py:110`).
- TOP_SCORE, RANDOM and HYBRID implement the specified ordering, tie handling, quota arithmetic, stage reasons and carry preservation (`backend/src/newsflow/domain/intake_selection.py:136`).
- Tests exercise literal expected selections, replay/permutations, exclusions, unknown scores, threshold equality, fractional carry, digest sensitivity, immutability and invalid inputs. Expectations are independent of production ranking helpers.
- The module remains disconnected and side-effect-free. Its contracts contain no rewrite/publication permission or executable job.

### Issues

#### Critical

None found.

#### Important

None found.

#### Minor

None found.

### Spec compliance and verification

**Compliant for this increment.** Reviewed the complete immutable `639bef0..920c099` change, design, implementation plan, writer report, prior review and progress ledger. The change introduces only the kernel, its tests and writer report.

Independently checked:

- Retained targeted test output: **300 passed**; final frozen kernel output: **127 passed**.
- Final Ruff, formatting, compilation/import allow-list and whitespace evidence.
- Kernel/test hashes match the writer freeze and package receipt. Neither file differs between reviewed source, package HEAD `4544143e05d7c8435d934c620e960c2e746bbad2`, and current checkout.
- All **326** package receipt input hashes match current files; smoke-script hash also matches.
- Unchanged Dockerfile installs the package. Build evidence identifies image `sha256:d4862c940b11d71c5403b1267f72ec8d48dc977b12134bc2a2f6a8edec07dbcb`; receipt records build/smoke native exits **0/0**.
- Smoke script and PASS output cover three literal modes, permutation equality, independent-process replay, exclusion reasons and fractional carry. Execution uses network none, read-only root filesystem, bounded temporary storage, no mounted user volumes or supplied secrets.

No suites were rerun and no files, index, HEAD or branch state were changed.

### Recommendations

Carry this approval into the controller’s increment checkpoint. Keep durable membership freezing, source/policy fencing, transactional carry, deduplication, restart guarantees and target-mix integration explicitly outstanding.

`selected=true` remains comparison evidence. Future integration must preserve **REJECT → rewrite_allowed=false → no new RewriteJob → rewrite calls 0**. Package smoke does not establish durable ingress or whole-branch release readiness.

### Assessment

**Quality: Approved.**
**Ready to merge this scoped increment: Yes, from this review’s perspective.**

The implementation matches the specified bounded deterministic contract, and retained verification is consistent with the reviewed and packaged source. This verdict covers the pure intake-selection increment only; exact CI and the later whole-branch release review remain separate gates.
