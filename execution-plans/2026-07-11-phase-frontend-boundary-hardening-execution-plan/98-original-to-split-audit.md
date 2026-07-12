# Original-To-Split Audit

## Source And Fidelity Boundary

The byte-for-byte pre-split monolith was not retained as an immutable source artifact. This audit therefore makes no line-count, section-count, textual-fidelity, or byte-level preservation claim.

The canonical recoverable source for the original intent is [`schemas/original-requirement-family-registry.v1.json`](schemas/original-requirement-family-registry.v1.json). It records a declared RFC-8785 family-payload SHA-256, two approval identities and an approval-evidence reference for protected verification, 19 semantic requirement families, their split owners, and machine-readable acceptance objects. Local validation proves declaration shape, payload integrity and internal mapping only; the protected verifier proves actual approval/custody. Coverage means that every declared family is represented by at least one normative owner book and by `99-source-coverage.md`; it does not mean that the former prose can be reconstructed verbatim or that an unavailable source hash exists.

## Canonical Semantic-Family Mapping

| Family | Original semantic intent | Normative split owner(s) | Acceptance ref |
| --- | --- | --- | --- |
| ORIG-01 | Authority, current state, scope and non-negotiable boundaries | top-level, 00, 01 | phase-boundary://original-requirements/ORIG-01/acceptance |
| ORIG-02 | Threat actors, trust boundaries and security invariants | 01 | phase-boundary://original-requirements/ORIG-02/acceptance |
| ORIG-03 | Work ownership, approval, Gates and task sizing | 01, 08 | phase-boundary://original-requirements/ORIG-03/acceptance |
| ORIG-04 | Permit trust, schema, lifecycle, revocation and factory | 02 | phase-boundary://original-requirements/ORIG-04/acceptance |
| ORIG-05 | Attestation, signing isolation, verifier and key lifecycle | 02 | phase-boundary://original-requirements/ORIG-05/acceptance |
| ORIG-06 | Platform and Hosted profiles, Preflight and Work Declaration | 03 | phase-boundary://original-requirements/ORIG-06/acceptance |
| ORIG-07 | Containment, provider/tool network split and tool broker | 03 | phase-boundary://original-requirements/ORIG-07/acceptance |
| ORIG-08 | Work Policy, mutation lease, fencing and concurrency | 04 | phase-boundary://original-requirements/ORIG-08/acceptance |
| ORIG-09 | Journal, staging, rollback, Acceptance and quarantine | 04 | phase-boundary://original-requirements/ORIG-09/acceptance |
| ORIG-10 | React route ownership, migration ledger and legacy retirement | 05 | phase-boundary://original-requirements/ORIG-10/acceptance |
| ORIG-11 | Browser session, authentication, CSRF, proxy and cache boundary | 05 | phase-boundary://original-requirements/ORIG-11/acceptance |
| ORIG-12 | Frontend toolchain, supply chain, typed contracts and rollback | 05 | phase-boundary://original-requirements/ORIG-12/acceptance |
| ORIG-13 | Correlation, errors, version projection and release identity | 06 | phase-boundary://original-requirements/ORIG-13/acceptance |
| ORIG-14 | Endpoint architecture, dependency rules and maintainability | 06 | phase-boundary://original-requirements/ORIG-14/acceptance |
| ORIG-15 | Data and workflow refactor, online migration and compatibility | 06 | phase-boundary://original-requirements/ORIG-15/acceptance |
| ORIG-16 | Evidence custody, retention, privacy and telemetry | 07 | phase-boundary://original-requirements/ORIG-16/acceptance |
| ORIG-17 | Capacity, performance, audit-only evaluation and budgets | 07 | phase-boundary://original-requirements/ORIG-17/acceptance |
| ORIG-18 | Implementation sequence, phase exits, tests and review | 08, 96 | phase-boundary://original-requirements/ORIG-18/acceptance |
| ORIG-19 | Risks, global Definition of Done, glossary and stop conditions | 09 | phase-boundary://original-requirements/ORIG-19/acceptance |

## Post-Split Additions

Second-pass and adversarial-review additions are tracked in `97-post-split-requirements-ledger.md`. They are new requirements with stable `PBR-*` identities; they do not retroactively alter the 19-family extraction or masquerade as original-plan text.

## Normalization

- The top-level file retains only recovery metadata, authority, Gate summary, book routing, global order and global completion.
- Detailed normative text belongs in exactly one owner book.
- Summaries may link but cannot restate full contracts.
- New findings are preserved through the PBR ledger and generated Finding Status Registry rather than silently folded into an original family.

## Acceptance

- The canonical registry parses as JSON, its semantic-family payload matches the approved SHA-256, and it contains exactly `ORIG-01` through `ORIG-19` in order with acceptance objects and stable URIs.
- Each registry owner exists in the split plan and each family appears exactly once in the original-family coverage section of `99-source-coverage.md`.
- The repository-local plan-readiness validator passes these checks.
- Passing this audit proves semantic split coverage only; it does not prove code completion or satisfy the protected BH-HANDOFF verifier.
