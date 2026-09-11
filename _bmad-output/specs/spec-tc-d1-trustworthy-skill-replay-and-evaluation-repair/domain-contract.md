# TC-D1 Domain Contract

## Terms

- **Target Package:** the exact repository-contained supported Skill package requested and proven to be inspected.
- **Validator Capability:** bounded validation behavior plus every trusted validator and Semantic Dependency identity that affects it.
- **Stable Package / Candidate Package:** immutable, independently identifiable comparison subjects; the Candidate contains the relevant real change.
- **Probe:** an independently materialized valid or invalid package executed to prove validator discrimination.
- **Replay Matrix / Matrix Case:** the closed six-case comparison and one independently executable scenario within it.
- **Consumer:** a currently declared caller of package validation. The **Consumer Manifest** is its complete version-bound set frozen before review.
- **Prior Route / Candidate Route:** validation behavior before candidate enablement and the behavior under evaluation.
- **Prior Behavior Baseline:** Prior Route identity plus expected verdict and diagnostic category for every rollback fixture.
- **Replay Result:** a current, non-authorizing conclusion derived from identities and real execution.
- **Exact Cover:** bidirectional coverage from every Atomic Obligation to assertions, selectors, commands, witnesses, and runtime evidence.
- **Current Snapshot:** every current input that determines a Replay Result.
- **Semantic Reproduction:** equality of terminal verdict, diagnostic categories, Exact Cover, and required identity/evidence relationships from the same pinned inputs.
- **Trust Approval:** an explicitly authorized, candidate-external binding of Validator Capability content, Semantic Dependencies, support policy, and scope before evaluation.

## Semantic Dependency Closure

The closure includes every executable, data artifact, policy, configuration value, and environment representation that can affect target selection, verdict, diagnostic category, or evidence validity. Probe reachability neither defines nor narrows this closure. Discovery and fixed-point algorithms are deferred to Architecture; implementations may not choose a smaller product boundary.

## Probe Oracle

The detached positive Probe must pass. The detached negative Probe must fail for its declared defect and expected diagnostic category. Import errors, missing dependencies, timeout, non-start, or other infrastructure failures are infrastructure failures, never successful negative validation. Each Probe independently binds input, actual target, command, result, and output evidence; the Matrix invalid-package case does not substitute for this oracle.

## Route Transition Contract

| Transition | Preconditions | Required call | Postcondition |
| --- | --- | --- | --- |
| enable | Candidate identity and applicable approvals are current and bound | Real Consumer invokes Candidate Route | Candidate behavior and evidence are observed. |
| disable | Candidate was enabled; no approved applicability omission | Real Consumer invokes Prior Route | Prior Route identity and Prior Behavior Baseline verdict/category are reproduced for every applicable fixture. |
| rollback | Candidate route is disabled or failed; rollback fixture is applicable | Real Consumer invokes Prior Route, not merely a state setter | Same Prior Route identity, verdict, and diagnostic category are observed; rejection/error/configuration-only changes do not qualify. |
| re-enable | Candidate remains approved and current; any exception is pre-approved and bound | Real Consumer invokes Candidate Route | Candidate Route is actually called and its current result is captured. |

An applicability exception must be approved and bound before execution; implementations cannot skip a transition themselves.

## Stable Eligibility

Stable represents source-supported existing behavior, with a verifiable provenance reference and immutable identity bound before the run. Architecture chooses the concrete commit/package binding. A temporary package constructed for this run cannot qualify merely because it differs from Candidate. Stable eligibility does not create a new quality baseline or Acceptance authority; Candidate must contain the real change under evaluation and both subjects execute with all invariants enforced.

## Target and Validator Invariants

- Supported targets are existing repository-contained Toolchain Skill packages. VDD and Acceptance are the irreducible minimum; candidate policy cannot remove them.
- Successful evidence proves effective target reads. A target identity beside a command that inspected something else is invalid.
- The Validator Capability source remains inside its approved root and cannot be selected or substituted by the candidate.
- Validator trust binds content and the complete Semantic Dependency closure. Version text is descriptive only.
- Any jointly changed validator, descriptor, dependency, support policy, or scope requires a new matching independent Trust Approval and makes prior approval-bound results stale.
- Positive and negative Probes bind input, target, command outcome, and output. Prefilled, inferred, or always-success outcomes fail.

## Historical and Seed Invariants

- Freeze tracked membership, repository-relative paths, and content identity for the historical 08-01 directory and all pre-repair tracked 08-05 files. Do not remove, rename, or change them.
- Preserve the original machine-bound command as native historical fact, without treating it as current execution authority or portability proof.
- A current equivalent replay creates new process evidence and states the equivalence boundary.
- Preserve exactly one of each seed: `candidate-baseline-contamination`, `self-hosted-knowledge-read-set-collision`, and `toolchain-policy-architecture-index-gap`.
- Each seed binds native evidence, identity, applicability, missing labels, and a counterexample or explicit absence, and uses only `anchor_candidate`, `challenge_candidate`, or `non_baseline_exploratory_candidate`.
- Seeds remain non-authorizing candidates and cannot become baselines or evaluation-set members within TC-D1.

## Matrix Contract

| Case | Required semantic distinction |
| --- | --- |
| Valid package | Handles a valid package under its declared contract. |
| Invalid package | Rejects an independently malformed package for its intended defect. |
| Historical compatibility | States machine-bound historical limits without authority promotion. |
| Dirty baseline | Detects and prevents candidate identity contamination. |
| Knowledge read-set collision | Detects the collision without self-reference. |
| Closed-policy architecture-index gap | Fails until the required policy/index relationship is satisfied. |

Every case owns a distinct fixture or state transition, frozen expectation, two subject executions, and separate observations. Distinct hashes alone do not prove a meaningful comparison. Unaffected cases demonstrate preserved behavior. `expected-difference` is valid only when frozen for that case and all execution and evidence gates pass; it cannot approve a regression. Missing identity or execution, timeout, infrastructure failure, stale input, undeclared diagnostics, copied expected output, evidence reuse, relabeling, or wrong-target execution invalidates the aggregate.

## Consumer and Rollback Contract

- Freeze a non-empty Consumer Manifest and check it against the current repository call surface. It includes VDD package validation, Acceptance package validation, and the workflow-model-routing terminal observation at minimum.
- Bind each Consumer's actual interface, input, command, output, result, and dependencies. A success path cannot make a required route check unreachable.
- Exercise enable, disable, rollback, and re-enable through every applicable Consumer. Any approved non-applicability must be explicit and bound before execution.
- Rollback executes the same Prior Route identity and reproduces the Prior Behavior Baseline verdict and diagnostic category for every fixture. Configuration state alone is insufficient.
- Preserve historical and failed-candidate evidence; new evidence is append-only and isolated between subjects, probes, cases, Consumers, and route stages.

## Result and Snapshot Contract

- Terminal categories are `pass`, `comparison-failed`, `invalid-input`, `identity-invalid`, `evidence-invalid`, `stale`, `execution-failed`, and `timed-out`; a case may also report `expected-difference` under the Matrix rules.
- Serialized aliases may be versioned but cannot merge a failure into success or silently reinterpret these categories.
- The Current Snapshot binds the current Git baseline and Skill-input v2 selection/content plus all result-determining code, fixtures, contracts, Consumers, tests, targets, validators, dependencies, sources, and evidence.
- Reconstruct exact original input identities before producing fresh replay evidence. Timestamps and process IDs may vary only when they cannot affect selection, observation, diagnostics, evidence validity, or authority.
- Until a versioned portable-field exclusion policy is approved, unexplained differences in bound inputs fail. Policy changes make dependent results stale.
