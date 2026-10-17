# TC-D1 Authority and Open Questions

## Confirmed Boundaries

- The historical 08-05 implementation contract assigns `implementation-authorized` to the maintainer and `implementation-complete` to Quick Dev TDD. Neither assignment grants product-scope, Trust Approval, Consumer-exception, Acceptance, release, or archive authority.
- Independent review supplies formal review evidence and no Acceptance authority.
- Only the deterministic Acceptance lifecycle owner can publish a new `acceptance-passed`; historical Acceptance and Q8 cannot satisfy it.
- ADR-0041 assigns durable semantics and authority to the owning standard, executable protocol to the repository Skill, plan predicates to the execution plan, and business acceptance to the plan-local validator. The runner owns no acceptance, done, commit, handoff, or release decision.
- ADR-0053 keeps Bootstrap semantic review separate from Acceptance. ADR-0058 replay outputs and ADR-0060 Skill-input records are non-authorizing.
- Every replay, seed, matrix, review, and Quick Dev artifact exposes a machine-verifiable empty authorization set and cannot publish another owner's state.
- Conflicts between historical implementation contracts, this source contract, and Accepted ADRs follow repository authority order and require explicit repair.

## A05 Source Evolution

Historical `TC-D1-003` is retained. `A05` is narrowed only so the historical Skill Creator root need not be permanent after valid governance. Until all conditions below are met, that historical root remains the permitted source:

1. An existing authorized repository or ADR owner is identified.
2. The alternate source is coordinated under that existing ownership and Accepted ADR model.
3. Independent Trust Approval binds the exact source and content, the complete Semantic Dependency closure, support policy, and scope.
4. The approval is frozen before evaluation and remains independent of the candidate.

This package approves no alternate source and defines no new approval mechanism.

## Installed Skill Boundary

Writes to `_bmad/**`, `.agents/skills/bmad-*/**`, and `.agents/skills/gds-*/**` remain forbidden. Authority to repair repository replay or Consumer code does not override these paths. This package expands no implementation write set.

## Open Questions and Deadlines

1. What process and aggregate-run budgets apply? The maintainer must use measured full-matrix, Consumer, and rollback timing before implementation authorization; until then, timeout remains mandatory and exhaustion fails.
2. Which Current Snapshot fields may vary across supported machines without changing Semantic Reproduction? Architecture must define a reviewed, versioned exclusion policy; until then, unexplained bound-input differences fail closed.
3. Which existing authorized repository or ADR owner may approve TC-D1 product scope? Confirmation is due before first reliance on that approval or before Spec/Architecture freezes the affected scope, whichever is earlier.
4. Which existing authorized repository or ADR owner may issue a Trust Approval for a source outside the historical Skill Creator root? Confirmation and content-matched independent approval are due before allowing that source or freezing its downstream design.
5. Which existing authorized repository or ADR owner may approve a Consumer Manifest exception? Confirmation and an explicit bound exception are due before omitting any Consumer or freezing the downstream manifest rule. Until then, no exception exists.

Questions 3-5 block the affected downstream decision. Role names and repository practice cannot answer them, and this package creates no owner or approval system.
