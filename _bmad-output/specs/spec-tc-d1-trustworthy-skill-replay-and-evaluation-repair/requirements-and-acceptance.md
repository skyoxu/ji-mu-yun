# TC-D1 Requirements and Acceptance Contract

## Normative Requirement Coverage

| Capability | PRD coverage | Required acceptance outcome |
| --- | --- | --- |
| `CAP-1` | FR-1, FR-2 | Supported target rules and effective inspection identity are independently verified; missing, illegal, unsupported, escaping, and wrong targets cannot succeed. |
| `CAP-2` | FR-3, FR-4 | Validator source/content/dependency trust and real positive/negative discrimination are verified; substitution, drift, escape, incompatibility, self-approval, and always-success behavior fail. |
| `CAP-3` | FR-5, FR-6 | Historical bytes and native references remain intact; current replay is bounded; all three seed identities, classifications, provenance, limits, and non-authority are complete. |
| `CAP-4` | FR-7, FR-8 | Six distinct cases execute immutable Stable and Candidate subjects, preserve invariants, and reject missing, duplicate, copied, mislabeled, stale, or non-executed evidence. |
| `CAP-5` | FR-9, FR-10 | The full current Consumer set executes through real interfaces and observes enable, disable, behavioral rollback, and re-enable without evidence loss. |
| `CAP-6` | FR-11 | Every Atomic Obligation has bidirectional Exact Cover and a semantically matching fault or violation witness; all orphans fail. |
| `CAP-7` | FR-12 | A fresh checkout reconstructs the semantic result from pinned current inputs, and every result-determining change invalidates prior evidence. |
| `CAP-8` | FR-13 | Derived evidence declares an empty authorization set, foreign lifecycle publication fails, and only current independent review plus the proper lifecycle owner can advance Acceptance. |

## Cross-Cutting Requirements

- **NFR-1 Fail closed:** unknown, missing, stale, ambiguous, or unverifiable identity and execution facts prevent success.
- **NFR-2 Auditability:** every verdict traces to current source identity and real execution without assistant prose.
- **NFR-3 Reproducibility:** pinned inputs in a fresh checkout reproduce the semantic verdict and coverage result.
- **NFR-4 Evidence isolation:** subjects, Probes, Matrix Cases, Consumers, and rollback stages cannot share mutable state or evidence that creates false success.
- **NFR-5 Historical immutability:** frozen historical membership, paths, and bytes remain unchanged; repair and runtime evidence are appended under their declared boundaries.
- **NFR-6 Platform compatibility:** Windows is supported, platform-specific behavior is declared, and user-profile paths cannot act as current authority.
- **NFR-7 Bounded execution:** each external process and aggregate has bounded time/output and a deterministic terminal state; budget exhaustion is unsuccessful and never reduces coverage.

## Exact Cover Rules

- Decompose every FR consequence, NFR, guardrail, and retained historical sub-duty into independently decidable Atomic Obligations before implementation.
- Each behavioral obligation has its own observable fault witness. Each other obligation has a deterministic violation witness.
- Many-to-many evidence reuse is allowed only when every covered obligation is independently proven.
- Coverage is calculated from this rebuilt contract. Raw test count, evidence volume, and category labels do not establish coverage.
- Zero orphan requirements, assertions, selectors, commands, witnesses, or runtime evidence are allowed.

## Historical Acceptance Preservation

| IDs | Disposition retained by this package |
| --- | --- |
| A01-A02 | Preserve historical membership and bytes; use append-only repair paths. |
| A03-A04 | Retain repository-relative Windows validation and shared VDD/Acceptance package routes. |
| A05 | Narrow only the fixed source-root identity under the authority conditions; preserve bounded, non-escaping, non-self-substitutable selection. |
| A06-A07 | Retain complete provenance and all historical fail-closed cases; add wrong-target, always-success, and jointly drifted dependency witnesses. |
| A08 | Preserve native historical command and hashes without promoting authority. |
| A09-A11 | Preserve the three exact seed identities, reject missing/drifted evidence, and restrict them to approved non-baseline classifications. |
| A12 | Strengthen to two-sided execution, six distinct states, immutable identities, invariant checks, and non-regression comparison. |
| A13 | Preserve workflow-model-routing terminal execution as one Consumer observation. |
| A14 | Strengthen machine-verifiable empty authorization and reject all foreign lifecycle states. |
| A15 | Strengthen disable/rollback to all Consumers, four transitions, and restored Prior Behavior Baseline. |
| A16 | Preserve Phase/runtime/workspace/account/sandbox boundaries and all installed BMAD/GDS forbidden paths. |
| A17 | Preserve TC-E0/D2-D6 separation and prohibit promotion, Miner/Curator, autonomous change, ranking, and RL. |

`TC-D1-001` through `TC-D1-013` remain retained. Only the already-completed one-time directory creation and obsolete live Skill-input v1 design are superseded context; current Skill-input v2 behavior remains governed by ADR-0060.

## Success Measures

- **SM-1:** 100% of Atomic Obligations have bidirectional Exact Cover and required witnesses; zero orphans.
- **SM-2:** all adversarial target, validator, dependency, invalid-package, unexecuted-case, reused-evidence, skipped-Consumer, stale-input, and foreign-authority cases reject success.
- **SM-3:** all six Matrix Cases execute distinct inputs and both subjects; any missing execution fails the aggregate.
- **SM-4:** 100% of the non-empty Consumer Manifest completes every applicable route transition and observes the Prior Behavior Baseline after rollback without historical evidence loss.
- **SM-5:** each successful Replay Result independently verifies target, Validator Capability, dependencies, command, Probe, output, Consumer, snapshot, and non-authority bindings.
- **SM-6:** a fresh checkout and pinned inputs reproduce the terminal semantic verdict and Exact Cover.

Passing test count, evidence volume, added case labels, and reduced runtime are counter-metrics when obtained without unique semantic coverage, attributable identities, distinct inputs, required executions, or complete evidence capture.
