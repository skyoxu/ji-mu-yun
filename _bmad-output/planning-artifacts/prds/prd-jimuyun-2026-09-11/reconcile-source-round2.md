# Source Reconciliation and PRD Decision Readiness: Round 2

## Verdict

**FAIL**

Source coverage is substantially complete, but the PRD is not yet decision-ready. One retained historical acceptance duty is unresolved: `A11` preserves a closed classification policy without naming the three allowed classifications. Two additional decisions are expressed too concretely for their current authority: who issues Trust Approval, and whether the enumerated terminal status names are product-facing requirements or a deferred contract design.

## Bound Inputs

| Input | SHA-256 |
| --- | --- |
| `docs/know-tc-d1-rebuild.md` | `c295de91b8224894c724758dbf865ab4f708a6bc7f0f433f8712755921fd89b7` |
| `prd.md` | `9ff5e57a8a02efdcbae4dd554563f66d3ceb160c600c2481fb9078f8041eef5760` |
| `addendum.md` | `e739b23ad3f146cd89198302788bc3e8796ea0fcce6c76449f4e0fb60517c598` |

The historical source checked for disposition was `execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/requirements.v1.json` as read during this review. Its requirements are `TC-D1-001..013` and its acceptance assertions are `TC-D1-A01..A17`.

## Blocking Finding

### B1. Historical `A11` is marked retained but its closed classification set is undefined

Historical `A11` permits only `anchor candidate`, `challenge candidate`, or explicitly non-baseline `exploratory candidate`. The addendum marks `A11` retained, while FR-6 requires “only the approved non-baseline candidate classifications defined by the repaired requirement.” Neither `prd.md` nor `addendum.md` actually names that closed set.

This is an unresolved product decision, not a schema detail. A downstream Spec cannot determine whether an observed classification is allowed without inventing the set. Resolve by either:

- retaining and naming the three historical classifications in FR-6; or
- explicitly superseding/narrowing `A11`, with the replacement classification policy and rationale.

## Source Brief Coverage: D1-R1..R11

| Source duty | Result | PRD coverage |
| --- | --- | --- |
| D1-R1 historical preservation and authority | PASS | FR-5, FR-12, FR-13, NFR-5 and constraints preserve prior bytes, append-only repair, Git baseline, Skill-input v2 freshness and stale-on-change behavior. |
| D1-R2 requested target equals inspected target | PASS | FR-1 and FR-2 reject invalid targets and require effective inspected-content identity. |
| D1-R3 validator and dependency identity | PASS | FR-3 binds validator and semantic dependencies, rejects drift/substitution/escape/incompatibility/always-success behavior, and rejects self-reported version as trust. |
| D1-R4 real positive and negative probes | PASS | FR-4 requires independent materialization, actual outcomes, intended negative diagnostic and attributable evidence. |
| D1-R5 historical compatibility | PASS | FR-5 preserves the original machine-bound command, native identities, current equivalent replay boundary and non-authority. |
| D1-R6 evaluation-seed provenance | PASS with A11 blocker | FR-6 names all three seeds, requires exact occurrence, provenance, applicability, missing labels, counterexample status and no promotion. The allowed candidate-class set remains undefined. |
| D1-R7 real stable/candidate matrix | PASS | FR-7 and FR-8 require distinct immutable subjects, both sides for every case, six materially distinct states, separate process evidence semantics and rejection of skipped/reused/copied observations. |
| D1-R8 downstream consumers | PASS | FR-9 freezes a non-shrinkable Consumer Manifest, checks repository call surfaces, includes VDD, Acceptance and workflow-model-routing, and rejects unreachable success-path checks. |
| D1-R9 disable and rollback | PASS | FR-10 requires real consumers to observe enable, disable, rollback and re-enable and restores prior route identity plus behavior. |
| D1-R10 exact cover and final evidence | PASS | FR-11 decomposes duties into Atomic Obligations and independent witnesses; FR-12 binds reconstructible inputs, Git baseline and Skill-input v2 and fails closed on unexplained drift. |
| D1-R11 authority separation | PASS | FR-13 requires machine-verifiable empty authorization for derived outputs, keeps Quick Dev to its own predicate, requires independent review before fresh Acceptance and denies inherited authority. |

## Historical Requirement Disposition: TC-D1-001..013

**PASS.** The addendum accounts for every historical requirement exactly once. All thirteen are retained, with strengthened coverage where needed. It separately identifies one-time directory creation and Skill-input v1 as superseded context and narrows creation of already-existing artifacts to repair/conformance. No historical requirement is silently dropped.

The dispositions are consistent with the current PRD except for the `A11` sub-duty described in B1.

## Historical Acceptance Disposition: A01..A17

| Acceptance group | Result | Notes |
| --- | --- | --- |
| A01-A04 | PASS | Historical byte preservation, no historical writes, repository-relative Windows execution and the two current package routes are retained. |
| A05 | PASS, architecture-gated | Explicitly narrowed from one historical Skill Creator root to a current Trust Approval. The addendum correctly requires Architecture and ADR reconciliation before this narrowing can become accepted authority. |
| A06-A10 | PASS | Receipt identity, adversarial validator cases, historical command/evidence, exact seed identities and drift rejection are preserved or strengthened. |
| A11 | FAIL | Disposition says retained, but the three allowed classification values are absent. |
| A12-A15 | PASS | Six cases, two-sided execution, workflow-model-routing observation, empty authority and behavioral rollback are retained or strengthened. |
| A16-A17 | PASS | Phase/runtime/workspace/account/sandbox/BMAD/GDS write boundaries and roadmap exclusions are preserved. |

## Implementation Leakage Review

Most implementation material is correctly isolated in `addendum.md`: CLI vectors, schemas, hashing, fixture layout, timeout capture, registry storage, route switching, Quick Dev artifacts and evidence paths remain deferred.

Two PRD details need explicit ownership before they are treated as frozen requirements:

1. **Terminal status identifiers.** NFR-1 fixes literal identifiers such as `comparison-failed`, `identity-invalid`, and `expected-difference`. Requiring bounded, distinguishable outcomes is a product requirement; choosing exact enum spellings is normally a Spec contract decision. Either state that these names are an intentional compatibility contract sourced from an accepted authority, or move the names to the addendum and keep the PRD at diagnostic semantics.
2. **Trust Approval mechanism.** Candidate-independent trust is a valid product outcome derived from D1-R3. The PRD goes further by defining a separately created binding that freezes content, dependency, policy and scope. This is close to architecture. The existing A05 disposition properly gates it on Architecture and ADR reconciliation, so it is not an additional blocker if that gate remains explicit.

The PRD does not leak command lines, receipt fields, path algorithms, fixture construction or route-switch implementation.

## Open Product Decisions

### Must resolve before Spec

- The allowed Evaluation Seed candidate classifications for retained `A11`, or an explicit disposition changing `A11`.

### May remain architecture-gated

- The accepted trust root and authorized issuer for Trust Approval, including reconciliation with historical A05 and the governing ADR set.
- Which Current Snapshot fields may vary across supported machines without affecting Semantic Reproduction. Current fail-closed behavior makes the unresolved choice safe.

### May remain implementation-authorization-gated

- Exact timeout and output budgets after baseline measurement. The PRD already states that exhaustion is unsuccessful and cannot reduce coverage.
- Confirmation of the Toolchain Maintainer governance assumption. The PRD grants no lifecycle authority and explicitly requires confirmation before lifecycle use.

## Required Closure

1. Name `anchor candidate`, `challenge candidate`, and explicitly non-baseline `exploratory candidate` in FR-6, or record an approved replacement policy and change the A11 disposition.
2. Clarify whether NFR-1's literal status names are a deliberate public/toolchain compatibility contract. If not, defer the enum names to Spec.

After item 1, source reconciliation can pass. PRD decision readiness can pass once item 2 is either affirmed as a product contract or deferred without weakening the diagnostic distinctions.
