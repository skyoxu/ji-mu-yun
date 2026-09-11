---
title: TC-D1 Trustworthy Skill Replay and Evaluation Repair
status: final
created: 2026-09-11
updated: 2026-09-11
source: docs/know-tc-d1-rebuild.md
---

# PRD: TC-D1 Trustworthy Skill Replay and Evaluation Repair

## 0. Document Purpose

This PRD defines the product outcomes required to repair the existing TC-D1
Skill replay and evaluation capability. It is written for the Toolchain
Maintainer, Independent Reviewer, and Acceptance Operator. It groups functional
requirements by capability and leaves command, schema, hashing, fixture layout,
and orchestration design to the Spec and Architecture stages. Inferred decisions
are marked `[ASSUMPTION]` and indexed at the end.

## 1. Vision

TC-D1 provides a trustworthy answer to a narrow but consequential question:
did the repository validate the requested Skill package, with the intended
validator, against meaningful stable and candidate scenarios, and can another
operator reconstruct that conclusion from current evidence?

The repaired capability must make false success difficult. A successful replay
cannot be produced by validating another target, using an untrusted or
always-success validator, relabeling identical cases, copying expected values,
skipping consumers, or changing a rollback flag without restoring prior caller
behavior. When any required identity or execution fact is unknown, the result
remains unsuccessful and diagnostic.

TC-D1 remains one component in the wider Toolchain roadmap. It preserves prior
evidence and repairs the existing 08-05 directory. It does not create a quality
baseline or assume authority owned by independent review or Acceptance.

## 2. Target Users

### 2.1 Jobs To Be Done

- The **Toolchain Maintainer** repairs a Skill validation capability while
  preserving historical evidence and needs to know which behaviors are proven.
- The **Independent Reviewer** reconstructs what target, validator, scenarios,
  and consumers actually ran without trusting implementation prose.
- The **Acceptance Operator** consumes current, approved inputs and needs a
  fail-closed basis for a new lifecycle decision.
- A **Downstream Toolchain Consumer** invokes package validation and needs
  enable, disable, rollback, and error behavior to remain deterministic.
  [ASSUMPTION: It is treated as a direct internal user of this capability.]

### 2.2 Non-Users

TC-D1 is not a product surface for Phase service users, hosted-project users,
game developers, account operators, or automated Skill promotion systems.

### 2.3 Key User Journeys

- **UJ-1. A maintainer evaluates a candidate without false success.** The
  maintainer selects distinct Stable Package and Candidate Package identities,
  runs the required Replay Matrix, and receives a result only after every case
  and current Consumer executed with attributable evidence.
- **UJ-2. A reviewer reconstructs a replay.** The reviewer starts from a Replay
  Result, follows its Target, Validator Capability, dependency, Probe, Matrix
  Case, and Consumer Evidence bindings, and independently detects missing,
  substituted, stale, or reused evidence.
- **UJ-3. An operator rolls back a candidate.** The operator disables the
  Candidate Route, observes the Prior Route selected and executed by a real
  Consumer, verifies prior behavior, and confirms that failed and historical
  evidence remains intact.
- **UJ-4. Acceptance evaluates current evidence.** After independent approval,
  the operator provides a current Skill-input v2 binding and reproducible
  snapshot. Acceptance makes a fresh decision without inheriting Quick Dev or
  historical Acceptance authority.

## 3. Glossary

- **Target Package**: the exact repository-contained Skill package requested for
  validation and proven to be the package actually inspected.
- **Validator Capability**: the bounded validation behavior plus the trusted
  identities of the validator and semantic dependencies that determine it.
- **Stable Package**: the immutable comparison subject representing prior
  accepted behavior for a Replay Matrix run.
- **Candidate Package**: the immutable comparison subject containing the change
  being evaluated, distinct from the Stable Package where comparison is claimed.
- **Probe**: an independently materialized valid or invalid package executed by
  the Validator Capability to establish discrimination behavior.
- **Replay Matrix**: the complete set of independently executable Matrix Cases
  comparing Stable Package and Candidate Package observations.
- **Matrix Case**: one scenario with its own input state, expected observation,
  actual executions, and evidence identity.
- **Consumer**: a current, authoritatively declared Toolchain caller of the
  package validation capability.
- **Prior Route**: the validation behavior selected for Consumers before the
  Candidate Route is enabled.
- **Candidate Route**: the validation behavior under evaluation.
- **Replay Result**: a non-authorizing conclusion derived from current identities
  and real process evidence.
- **Exact Cover**: bidirectional coverage between source requirements and every
  acceptance assertion, selector, command, and runtime evidence item.
- **Current Snapshot**: the reconstructible identity of every current input that
  determines a Replay Result.
- **Supported Target Package**: a repository Toolchain Skill package consumed
  through the shared package-validation capability. The minimum set contains
  the current VDD and Acceptance Skill packages; a frozen policy may add targets
  but cannot remove this minimum set without an approved product-scope revision.
- **Semantic Dependency**: any executable, data, policy, configuration, or
  environment representation within the supported capability scope that can
  affect target selection, a verdict, a diagnostic category, or evidence
  validity. Probe reachability does not define or limit this closure.
- **Consumer Manifest**: the complete, maintainer-approved and version-bound set
  of current Consumers frozen before independent review.
- **Prior Behavior Baseline**: the Prior Route identity and its expected verdict
  and diagnostic category for every frozen rollback fixture.
- **Semantic Reproduction**: equality of the terminal verdict, diagnostic
  categories, Exact Cover, and all identity/evidence relationships required by
  this PRD when reconstructed from the same pinned inputs.
- **Trust Approval**: a current, explicitly authorized binding created outside
  the Candidate Package change set that freezes Validator Capability content,
  Semantic Dependencies, support policy, and scope before evaluation.
- **Atomic Obligation**: one independently decidable behavior, consequence,
  non-functional constraint, guardrail, or retained upstream duty with a
  distinct violation or failure witness.

## 4. Features And Functional Requirements

### 4.1 Target and Validator Trust

The system establishes that the requested Target Package is the inspected
Target Package and that the Validator Capability is the trusted capability
approved for the run. This realizes UJ-1 and UJ-2.

#### FR-1: Validate the requested target

The Toolchain Maintainer can request validation only for an existing,
repository-contained, Supported Target Package.

**Consequences:**

- Missing, non-directory, escaping, and unsupported targets are rejected.
- The minimum Supported Target Package set cannot be reduced by candidate-owned
  policy or by relabeling a required package as unsupported.
- The shared repository capability remains usable by both current VDD and
  Acceptance package-validation routes.
- No successful Replay Result is created for a rejected target.

#### FR-2: Prove actual target inspection

The Independent Reviewer can verify that each validation execution inspected
the requested Target Package.

**Consequences:**

- An adapter that validates another package causes failure.
- Target identity recorded beside an unrelated successful command is rejected.
- Evidence identifies the effective inspected content, not only the request.

#### FR-3: Establish Validator Capability identity

The system validates the trusted identity and compatibility of the Validator
Capability before relying on its result.

**Consequences:**

- Missing, substituted, drifted, escaping, or incompatible validators fail.
- Historical requirement `TC-D1-003` remains retained. Its `A05` sub-duty is
  narrowed only with respect to the identity of the permitted source root: a
  Validator Capability source remains bounded, cannot escape its approved
  root, and cannot be selected or substituted by the candidate itself.
- The historical Skill Creator root remains the permitted source unless a
  different source is first coordinated under the existing owner and Accepted
  ADR model and receives an independent Trust Approval bound to the exact
  source and content. This PRD revision approves no alternate source and does
  not prescribe the mechanism by which Architecture may represent one.
- Semantic Dependencies are identity-bound.
- Trust Approval is independent of the candidate and is frozen before
  evaluation. Candidate changes to the validator, descriptor, dependencies,
  support policy, or scope cannot approve themselves.
- Any jointly changed capability inputs require a new matching Trust Approval;
  that approval makes results bound to the prior approval stale.
- A successful result records validator version as descriptive provenance in
  addition to trusted content identity.
- Self-reported version text alone cannot establish trust.
- An always-success validator cannot produce a successful Replay Result.

### 4.2 Executed Probes and Historical Compatibility

The system proves discrimination with independent inputs and preserves historical
context without rewriting or upgrading its authority. This realizes UJ-1 and
UJ-2.

#### FR-4: Execute independent positive and negative Probes

The Toolchain Maintainer can run independently materialized valid and invalid
Probes through the selected Validator Capability.

**Consequences:**

- The valid Probe passes.
- The invalid Probe fails for its declared diagnostic reason.
- Each Probe binds its input, target, execution outcome, and output evidence.
- Prefilled or inferred Probe outcomes fail verification.

#### FR-5: Observe historical compatibility

The Independent Reviewer can compare preserved historical evidence with a
current equivalent replay without treating history as newly executed authority.

**Consequences:**

- Historical 08-01 and prior 08-05 tracked evidence remains unchanged.
- The original machine-bound historical command is retained as an auditable
  native fact but is neither current execution authority nor portability proof.
- Native historical references and content identities are verifiable.
- Current replay evidence states the equivalence boundary and remains
  non-authorizing.
- Machine-bound historical behavior is never described as portable.

### 4.3 Evaluation Seeds and Stable/Candidate Comparison

The system preserves cautious seed provenance and performs actual two-sided
comparison across materially different cases. This realizes UJ-1 and UJ-2.

#### FR-6: Preserve non-authorizing Evaluation Seeds

The Toolchain Maintainer can retain the three historical repair families as
candidate evidence with provenance and limits.

The stable seed identities are `candidate-baseline-contamination`,
`self-hosted-knowledge-read-set-collision`, and
`toolchain-policy-architecture-index-gap`.

**Consequences:**

- Each seed binds native evidence, content identity, applicability, missing
  labels, and a counterexample or explicit absence.
- Each stable seed identity occurs exactly once and uses only the approved
  non-baseline classifications: `anchor_candidate`, `challenge_candidate`, or
  `non_baseline_exploratory_candidate`.
- A seed cannot become a quality baseline or evaluation-set member in TC-D1.
- Missing or drifted seed evidence cannot be converted to success.

#### FR-7: Compare distinct Stable and Candidate Packages

The Toolchain Maintainer can evaluate independently identifiable Stable Package
and Candidate Package subjects.

**Consequences:**

- Both identities are immutable for the run.
- Comparison fails when distinct subjects are required but resolve to the same
  identity.
- Both sides execute for every Matrix Case.
- Their content identities differ, and the Candidate Package contains the real
  change under evaluation; different hashes alone are insufficient.
- The overall comparison must include a change relevant to at least one Matrix
  Case. Unaffected cases are expected to demonstrate preserved behavior and do
  not require artificial per-case differences.

#### FR-8: Execute six materially distinct Matrix Cases

The Replay Matrix covers valid package, invalid package, historical
compatibility, dirty baseline, knowledge read-set collision, and closed-policy
architecture-index gap behaviors.

**Consequences:**

- Each case owns a distinct fixture or state transition and expected behavior.
- Each case records separate Stable Package and Candidate Package observations.
- A missing, skipped, duplicate, unlaunched, mislabeled, or wrong-target case
  fails the Replay Matrix.
- Reusing another case's evidence or copying expected text into actual output
  fails the Replay Matrix.
- A completed case may record `pass` or an expected behavioral difference only
  when its frozen expectation permits that observation. Missing identity,
  execution, evidence, or an unexpected verdict makes the whole run invalid.
- Infrastructure failure, timeout, stale input, or undeclared diagnostic aborts
  the aggregate rather than being counted as a Stable/Candidate difference.
- Frozen expectations cannot waive these invariants: valid packages are handled
  according to their declared contract; invalid packages are rejected for the
  intended defect; historical limits are stated without authority promotion;
  dirty baselines cannot contaminate candidate identity; knowledge read-set
  collisions are detected without self-reference; and closed-policy gaps fail
  until the required policy/index relationship is satisfied.
- A changed Candidate behavior is acceptable only when the frozen requirement
  calls for that change and every invariant remains satisfied. An expected
  difference cannot pre-approve a regression.

### 4.4 Consumer Closure and Behavioral Rollback

The system verifies every declared Consumer and demonstrates that route changes
restore behavior rather than merely changing metadata. This realizes UJ-1,
UJ-2, and UJ-3.

#### FR-9: Validate the authoritative Consumer set

The Independent Reviewer can verify that every current Consumer ran through its
actual package validation interface.

**Consequences:**

- The Consumer Manifest is frozen before review. The Toolchain Maintainer owns
  additions and removals; any change requires renewed approval and makes prior
  results stale.
- Completeness is checked against the current repository call surface as well
  as the manifest. At minimum it includes the VDD package route, Acceptance
  package route, and workflow-model-routing terminal observation. A candidate
  cannot shrink this denominator by editing only the manifest.
- Each Consumer has attributable input, command, result, and output evidence.
- Omitting one Consumer or making a route check unreachable on success fails
  terminal validation.
- The workflow-model-routing terminal Consumer is reported as one compatibility
  observation, not universal quality proof.

#### FR-10: Demonstrate disable, rollback, and re-enable

The Toolchain Maintainer can exercise Candidate Route enablement, disablement,
rollback to the Prior Route, and re-enablement in isolation.

**Consequences:**

- Every Consumer in the non-empty frozen Consumer Manifest observes applicable
  enable, disable, rollback, and re-enable transitions through its real call
  surface. Any product-approved non-applicable transition is explicit and bound
  before execution.
- Disable and rollback restore the Prior Behavior Baseline: the same Prior Route
  identity and the same verdict/diagnostic category for every rollback fixture.
- A configuration-only change without restored execution behavior fails.
- Existing failed-candidate and historical evidence remains unchanged, and
  evidence created in this round remains append-only.

### 4.5 Coverage, Freshness, and Lifecycle Handoff

The system proves the whole requirement rather than a convenient subset and
hands current evidence to its proper lifecycle owner. This realizes UJ-2 and
UJ-4.

#### FR-11: Enforce Exact Cover

The Independent Reviewer can navigate bidirectionally between every source
requirement and its assertions, selectors, commands, and runtime evidence.

**Consequences:**

- Every FR consequence, NFR, guardrail, and retained upstream sub-duty is
  decomposed into Atomic Obligations before implementation.
- Every behavioral Atomic Obligation has its own independently observable fault
  witness; a representative failure cannot cover non-equivalent duties.
- Non-behavioral Atomic Obligations have a deterministic violation witness and
  need not manufacture a meaningless process test.
- Many-to-many reuse is allowed only when evidence proves each Atomic Obligation
  separately; coverage is not scored by raw test count.
- Orphan requirements, assertions, commands, and aggregate-only assertions fail.
- Coverage is computed against the rebuilt source requirements, not the old
  four-slice round-6 plan.

#### FR-12: Reconstruct and invalidate the Current Snapshot

The Acceptance Operator can reconstruct the semantic result from a fresh
checkout and the declared current inputs.

**Consequences:**

- The Current Snapshot covers all code, fixtures, contracts, Consumers, and
  tests that determine the verdict.
- It binds the current Git baseline and current Skill-input v2 selection and
  content identities as freshness inputs.
- A change to a bound target, validator, dependency, source, or evidence input
  marks the prior result stale.
- Reconstruction must satisfy Semantic Reproduction. Until Architecture defines
  a portable-field exclusion rule, an unexplained byte difference in a bound
  Current Snapshot input fails closed.
- Reconstruction first restores exact original input identities and verifies
  existing evidence; a replay then creates new process evidence bound to those
  inputs. New timestamps and process identifiers need not reproduce old output
  bytes, but may vary only when they cannot affect target selection, observation,
  diagnostic, evidence validity, or authority.
- Any normalization/exclusion policy is itself versioned and snapshot-bound;
  changing it requires review and makes affected results stale.

#### FR-13: Preserve lifecycle authority separation

The Acceptance Operator receives non-authorizing implementation and review
evidence and makes a fresh decision from current Skill-input v2 inputs.

**Consequences:**

- Every TC-D1 replay, seed, matrix, review, and Quick Dev evidence artifact has
  a machine-verifiable empty authorization set. It cannot publish plan-ready,
  implementation-complete, acceptance-passed, release, archive, or another
  owner's state.
- Quick Dev may report its own implementation predicate; a lifecycle owner must
  publish any state transition separately under the current repository contract.
- An independent formal review conclusion and explicit Toolchain Maintainer
  approval of its scope and bound candidate are required before deterministic
  Acceptance. The current review Skill may provide that conclusion, but this PRD
  does not create a new approval system or require one Skill name.
- Only the Acceptance lifecycle owner can produce a new `acceptance-passed`.
- Historical Acceptance and round-6 Q8 cannot satisfy the new decision.
- Where an old implementation contract conflicts with this source brief or an
  Accepted ADR, repository authority order applies and the conflict must be
  explicitly repaired rather than inherited.

## 5. Cross-Cutting Non-Functional Requirements

### NFR-1: Fail-closed integrity

Unknown, missing, stale, ambiguous, or unverifiable identity and execution facts
must prevent success. Operator-facing terminal categories are `pass`,
`comparison-failed`, `invalid-input`, `identity-invalid`, `evidence-invalid`,
`stale`, `execution-failed`, and `timed-out`. A Matrix Case may additionally
record `expected-difference`, but the aggregate passes only when that category
was frozen for that case and all execution/evidence gates passed.

These category names are stable product vocabulary for TC-D1 interoperability.
Spec may define their serialized representation and compatibility aliases but
cannot merge failure categories into success or silently reinterpret them.

### NFR-2: Auditability

A reviewer must be able to trace every verdict to current source identity and
real execution evidence without relying on assistant prose.

### NFR-3: Reproducibility

Pinned inputs in a fresh repository checkout must reproduce the same semantic
verdict and coverage result.

### NFR-4: Evidence isolation

Stable/Candidate, positive/negative, Matrix Cases, Consumers, and rollback stages
must not share mutable state or evidence in ways that can create false success.

### NFR-5: Historical immutability

Before work, the plan freezes membership, repository-relative path, and content
identity for every tracked file under the historical 08-01 directory and all
pre-repair tracked files under 08-05. Those members cannot be removed, renamed,
or changed. New repair/evidence paths may be appended; ignored runtime files are
outside the historical comparison unless explicitly promoted into the frozen
set.

### NFR-6: Platform compatibility

The supported repository environment includes Windows execution. Platform
specific behavior must be declared; user-profile paths cannot be current
capability authority.

### NFR-7: Bounded execution

[ASSUMPTION: Every external process and aggregate run will have an explicit
timeout, bounded output capture, and deterministic terminal state. Exact budgets
are deferred pending current baseline measurement.] Correctness and
reconstructibility take priority within that budget. Budget exhaustion produces
an unsuccessful diagnostic result and never reduces required coverage.

## 6. Constraints and Guardrails

- Repair the existing TC-D1 directory; do not create another requirement tree.
- Preserve 08-01 and earlier 08-05 evidence and lifecycle records.
- Reuse Skill-input v2; do not redesign v1 or current-pointer semantics.
- Do not implement TC-E0 or TC-D2 through TC-D6.
- Do not modify Phase service, runtime, browser/API, accounts, hosted workspaces,
  or user-sandbox behavior.
- Do not modify installed BMAD/GDS files under `_bmad/**`,
  `.agents/skills/bmad-*/**`, or `.agents/skills/gds-*/**`. Permission to repair
  repository replay or Consumer code does not authorize writes to those paths.
  This revision does not expand the historical implementation write set.
- Do not promote seeds, baselines, candidates, or Skill versions.
- Do not introduce autonomous Skill modification, SkillOS, learned ranking,
  percentage canaries, or RL.
- Before changing production behavior, establish and execute defect-revealing
  tests for each planned behavioral Atomic Obligation. Brownfield behavior that
  already passes needs a truthful characterization result plus a distinct fault
  witness; fabricated RED evidence and post-hoc failure records are forbidden.

## 7. MVP Scope

### 7.1 In Scope

- Target Package and effective inspection proof.
- Validator Capability and semantic-dependency identity.
- Independent positive and negative Probes.
- Preserved historical compatibility observation.
- Three non-authorizing Evaluation Seeds.
- Real Stable Package and Candidate Package Replay Matrix over six cases.
- Complete current Consumer execution.
- Behavioral enable, disable, rollback, and re-enable exercise.
- Exact Cover, Current Snapshot reconstruction, independent review handoff, and
  fresh deterministic Acceptance eligibility.

### 7.2 Out of Scope

- New quality baselines or evaluation-set promotion.
- Cross-plan longitudinal observability beyond evidence needed by TC-D1.
- Review topology and progressive context-loading experiments.
- Miner, Memory, Curator, automated promotion, or generalized governance.
- Any Phase service or user-facing product change.

## 8. Success Metrics

### Primary

- **SM-1: Requirement coverage** - 100% of Atomic Obligations derived from FR
  consequences, NFRs, guardrails, and retained upstream duties have
  bidirectional Exact Cover and their required fault/violation witnesses; zero
  orphan obligations, assertions, commands, or evidence. Validates FR-11.
- **SM-2: False-success resistance** - all required adversarial target,
  validator, dependency, invalid-package, unexecuted-case, reused-evidence,
  skipped-Consumer, stale-input, and foreign-authority tests reject success.
  Validates FR-1 through FR-4, FR-8, FR-9, FR-12, and FR-13.
- **SM-3: Matrix execution completeness** - all six Matrix Cases execute their
  declared distinct inputs and both required subjects; any missing execution
  makes the aggregate fail. Validates FR-7 and FR-8.
- **SM-4: Behavioral rollback** - 100% of the non-empty frozen Consumer Manifest
  completes every applicable enable, disable, rollback, and re-enable transition
  and observes the Prior Behavior Baseline after rollback, with no historical
  evidence loss. Validates FR-10.

### Secondary

- **SM-5: Receipt verifiability** - every successful Replay Result independently
  verifies Target Package, Validator Capability, semantic dependencies, command,
  Probe, output, Consumer, snapshot, and non-authority bindings. Validates FR-2,
  FR-3, FR-4, FR-9, FR-12, and FR-13.
- **SM-6: Fresh-checkout reconstruction** - the terminal semantic verdict and
  Exact Cover satisfy Semantic Reproduction from a current Git baseline and
  pinned inputs in a clean checkout. Validates FR-12.

### Counter-Metrics

- **SM-C1: Passing test count** - a larger number of passing tests is not a
  success metric unless those tests map to unique requirements and failures.
- **SM-C2: Evidence volume** - more receipts or larger logs do not improve
  confidence without attributable identities and execution.
- **SM-C3: Category count** - adding Matrix Case labels does not count as
  coverage unless cases use distinct inputs and observable behavior.
- **SM-C4: Runtime minimization** - speed cannot be optimized by skipping
  Consumers, Probes, comparison sides, or evidence capture.

## 9. Risks and Mitigations

- **Shared-assumption false positive:** implementation and validator may share
  the same defect. Mitigate with independent invalid fixtures and external review.
- **Trust-on-first-use:** a validator and descriptor could drift together.
  Mitigate by binding trust to current approved authority and baseline inputs.
- **Contract drift:** producer, schema, and terminal consumer may disagree.
  Mitigate with one versioned contract and consumer conformance checks.
- **Rollback illusion:** a state flag may disable all validation instead of
  restoring the Prior Route. Mitigate with Consumer-observed behavior.
- **Evidence staleness:** old Q8 evidence may look current. Mitigate with Current
  Snapshot invalidation and explicit lifecycle ownership.
- **Boundary creep:** repair may absorb roadmap work. Mitigate with the guardrails
  and per-requirement scope review.

## 10. Stakeholders and Approval

- The historical 08-05 implementation contract assigns
  `implementation-authorized` to the maintainer and
  `implementation-complete` to the Quick Dev TDD adapter. These assignments do
  not grant product-scope, Trust Approval, Consumer-exception, Acceptance,
  release, or archive authority.
- An Independent Reviewer supplies formal review evidence but no Acceptance
  authority.
- The deterministic Acceptance owner alone publishes `acceptance-passed`.
- ADR-0041 assigns durable semantics and authority to the owning standard,
  executable protocol to the repository Skill, plan-specific predicates to the
  execution plan, and business acceptance to the plan-local validator. The
  runner has no acceptance, done, commit, handoff, or release authority.
- ADR-0053 preserves separate Bootstrap semantic-review and Acceptance
  lifecycles. ADR-0058 replay evidence and ADR-0060 Skill-input records grant no
  lifecycle authority.
- Existing sources reviewed for this PRD do not identify an authority that may
  approve TC-D1 product scope, a new Trust Approval, or a Consumer exception.
  Those decisions require confirmation by an already-authorized repository or
  ADR owner before the first use of the claimed approval, or before Spec or
  Architecture freezes the affected downstream rule, whichever occurs first.
  This PRD creates no approval role or process.

## 11. Open Questions

1. What process budgets should NFR-7 set after baseline measurement? Owner:
   Toolchain Maintainer. Revisit condition: current full matrix, Consumer, and
   rollback baseline timing is available before implementation authorization.
2. Which Current Snapshot fields, if any, may vary across supported machines
   without changing Semantic Reproduction? Owner: Architecture, with Independent
   Reviewer approval. Revisit condition: snapshot identity design is reviewed;
   absence of a decision remains fail-closed.
3. Which existing authorized repository or ADR owner may approve TC-D1 product
   scope? Confirmation is required before that approval is first relied upon or
   before downstream Spec/Architecture scope is frozen, whichever is earlier.
4. Which existing authorized repository or ADR owner may issue a Trust Approval
   for a validator source different from the historical Skill Creator root?
   Confirmation and a content-matched independent approval are required before
   such a source is allowed or its downstream design is frozen.
5. Which existing authorized repository or ADR owner may approve an exception
   to the complete Consumer Manifest? Confirmation and an explicit exception
   are required before a Consumer is omitted or the downstream manifest rule is
   frozen. In the absence of confirmation, no exception exists.

## 12. Assumptions Index

- Section 2.1: Downstream Toolchain Consumers are treated as direct internal
  users of this capability.
- NFR-7: process and aggregate-run budgets will be selected from measured current
  behavior before implementation authorization.
- Section 10: no product-scope, Trust Approval, or Consumer-exception authority
  is inferred from role names or repository practice.
