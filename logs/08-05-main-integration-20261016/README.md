# 08-05 / main integration

Merge main `93884ba457a390739c653f978cf340774904e9e7` into PR #4 head
`2c03b208670466301203be05b9bd0fc2182f3d87`. Common base:
`d8219f5a867e2a1bb2ed22c86f0437367617da06`. Both histories are retained.

## Resolution

| Area | Integrated behavior |
| --- | --- |
| VDD input | Main's anchored behavior tables and companion context; 08-05 semantic/execution metadata separation; each source keeps its own byte hash. |
| V3 | Bounded parallel and split transport, path grounding and validated cache reuse compose with selective per-obligation repair and offline fixture reuse. Worker output/schema paths are request-specific. Split peers retain the full frozen domain, so successful siblings are reusable while unknown IDs remain rejected. |
| Plan scope | Remove the unconditional Toolchain-only instruction from the generic worker. Frozen sources and declared owners determine scope, including Phase plans. |
| V4 | Bounded empty-response retry, exact supported/invented partition checks, source-gap repair limits and published-repair restrictions remain active. |
| Publication | Bind final recall to published obligations. Preserve an older root witness and use a plan-hash-keyed binding for current recall across resume, V1 reuse and V3/handoff repair. |
| Quick Dev | Preserve .NET static admission through pytest, worker failure records, materialized-test reuse, exact assertion mapping and actual-production-progress gates. |
| Q8 | Recheck each slice's frozen roots and snapshot tuple. Compose declared plan evidence deltas and unrelated-slice reuse with production/test/fixture boundaries. Whole-plan roots remain independently checked. |
| Snapshot hashing | Preserve Windows long-path support and .NET output exclusions limited to real project roots. |
| Skill-input | Acceptance transport exclusions are limited to the authority's target_plan; other plans remain candidate inputs. |
| Test cleanup | Restore temporary test edits using original bytes to preserve bound CRLF fixtures. |

Authority: Accepted ADR-0041 (compiler/Quick Dev ownership), ADR-0058
(evidence ownership and exact budget transition), ADR-0060 (Skill-input).

## Verification

- VDD package validator: passed.
- VDD: 424 passed, plus 58 subtests.
- Affected Quick Dev: 79 passed, including native staged lifecycle and coverage.
- Skill-input / Acceptance consumer regression: 116 passed; one Windows-only
  junction test deselected because this environment has no cmd/mklink.
- Final selected total: 619 passed; zero selected cases skipped.
- All 16 Git conflicts resolved; 25 paths overlapped between the branches.
- 17,349 existing 08-05 plan/evidence entries preserve their original Git entry.
- 668 Phase/runtime/test entries match main exactly. No unexpected edits outside
  the overlap and explicit integration files. Manual Python parsing and
  whitespace checks pass. See merge-audit.json for source hashes.

Native stdout/stderr, JUnit XML, command argv, process exits and durations are
stored alongside this report. The environment is Linux/Python 3 with a local
py -3 compatibility launcher, not Windows-native execution. No live model
calls, 340-node replay, full slice replay or formal Acceptance run was performed.

## Baseline limitations

The eleven failures found in broader Quick Dev testing were reproduced on the
exact original PR parent and on this merge. These concern legacy v1 Skill-input
fixtures, historical helpers assuming a .git directory, stale process-mocking
seams, a forbidden-entry compiler fixture, and an old pinned Matrix fixture.
They are retained as failures, not disabled or reported as passes.

The ten original budget replay tests pass on the parent. Five reject the merged
Q8 owner's changed bytes, as required by their exact adapter pins. The pins were
not loosened: historic budget-transition proofs cannot automatically validate
this new implementation. See parent-baseline.* and merge-baseline-comparison.*.

Historical Acceptance remains bound to its original candidate. This merge does
not declare new formal Acceptance or implementation completion. C3 remains OPEN;
authorizes=[]. No historical receipt or failure was rewritten.
