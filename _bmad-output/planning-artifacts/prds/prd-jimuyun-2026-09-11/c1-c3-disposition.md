# TC-D1 PRD C1-C3 Disposition

This append-only record describes the candidate revision made after commit
`b76b9f3e1e6c85354389d4a6ce86c5d80b5d0e58`. It is a maintainer-facing
disposition record, not an external-review verdict, approval, or lifecycle
transition.

## C1: Normative Effect of the A05 Evolution

- **Issue:** The normative PRD did not state the disposition and effective
  conditions of historical `A05`; the informative addendum carried them alone.
- **Modified locations:** `prd.md` FR-3; `addendum.md` historical requirement
  and acceptance sub-duty disposition.
- **Authority:** Historical `requirements.v1.json` `TC-D1-003`/`A05`;
  historical `implementation-contract.v1.json`; ADR-0058 bounded replay and
  non-authorizing evidence; ADR-0041 ownership separation.
- **Disposition:** **CLOSED in this candidate.** `TC-D1-003` remains retained.
  Only the fixed historical source-root identity in `A05` is narrowed. Bounded,
  non-escaping, non-self-substitutable selection remains normative.
- **Remaining condition:** An alternate source is ineffective until an existing
  authorized owner and Accepted ADR coordinate it and an independent Trust
  Approval is bound to the exact source and content. This candidate grants no
  such approval and chooses no implementation mechanism.

## C2: Installed BMAD/GDS No-Write Boundary

- **Issue:** The phrase "outside the repository-owned Toolchain scope" could be
  read as allowing changes to installed BMAD/GDS files inside that scope.
- **Modified locations:** `prd.md` Section 6; `addendum.md` dispositions for
  `TC-D1-012` and `A16`.
- **Authority:** Historical `implementation-contract.v1.json`
  `forbidden_changes`, including `_bmad/**`, `.agents/skills/bmad-*/**`, and
  `.agents/skills/gds-*/**`; historical `requirements.v1.json`
  `TC-D1-012`/`A16`.
- **Disposition:** **CLOSED in this candidate.** All three forbidden path sets
  are restored without a repository-owned-scope exception. Permission to
  repair replay or Consumer code does not permit writes to them.
- **Remaining condition:** None for the PRD correction. Any future boundary
  change requires its own governing authority; this revision expands no write
  scope.

## C3: Product Approval Authority and Confirmation Deadline

- **Issue:** The PRD inferred product-scope authority from repository practice
  and deferred confirmation until an imprecise lifecycle-use point.
- **Modified locations:** `prd.md` Sections 10-12.
- **Authority:** Root `AGENTS.md`; ADR-0041; ADR-0053; ADR-0058; ADR-0060;
  `docs/standards/repository-maintenance-agent-protocol.md`; historical
  `implementation-contract.v1.json` lifecycle ownership.
- **Disposition:** **PARTIALLY RESOLVED; AUTHORITY CONFIRMATION OPEN.** The
  unsupported inference is removed. Confirmed lifecycle assignments are stated
  without extending them. The deadline is now the earlier of first reliance on
  the claimed approval or freezing the affected Spec/Architecture rule.
- **Remaining condition:** Existing sources reviewed do not name who may approve
  TC-D1 product scope, issue a Trust Approval for an alternate validator source,
  or approve a Consumer Manifest exception. An already-authorized repository or
  ADR owner must identify and confirm each applicable authority before its
  deadline. Until then, no such approval or exception exists, and C3 must not be
  reported as closed.

## Consistency Statement

The normative requirements remain in `prd.md`; `addendum.md` remains
informative and mirrors the dispositions without creating requirements. This
revision does not alter the source brief, historical execution plan, Q8,
evidence, or prior review records. It does not weaken the previously retained
target checks, dependency closure, matrix, Consumer coverage, rollback, Exact
Cover, or empty-authorization requirements.
