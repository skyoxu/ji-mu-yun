# Behavior Slices And Implementation Order

## RMAP-S0: Framework ADR And Ownership Standard

- Phase: `P0`.
- Requirements: `RMAP-001`, `RMAP-002`, `RMAP-019`, `RMAP-020`, `RMAP-021`, `RMAP-024`.
- Produce one accepted framework ADR and `docs/standards/repository-maintenance-agent-protocol.md`.
- Update standards and documentation indexes in the same change.
- Tests first: ownership registry rejects duplicate schema or evidence owners.
- RED: deliberate duplicate owner fixture produces `RMAP-OWNERSHIP-DUPLICATE`.
- GREEN: `rmap-s0-slice-validate` checks the ADR, standard, standards index, and project documentation index under `slice-ready`.
- Exit: GREEN proof passes, ADR is accepted, ownership validator passes, and no current-capability claim is introduced. `plan-ready` alone cannot satisfy this exit.
- Rollback: remove only the new proposed standard/index links before any dependent slice starts.

## RMAP-S1: Common Contract And Self-Hosted Plan Instance

- Requirements: `RMAP-003`, `RMAP-004`, `RMAP-013`, `RMAP-022`.
- Phase: `P0`.
- Create the repository-owned Skill package, migrate the proposed common schema into it, and keep this plan's `implementation-contract.v1.json` as the first live instance.
- Tests first: schema, raw-shell, env, placeholder, predicate escalation, stale source, and missing acceptance fixtures.
- RED: deliberate `shell=true` fixture produces `RMAP-CMD-SHELL`.
- GREEN: `rmap-s1-slice-validate` proves the self-hosted Skill/schema outputs under `slice-ready`.
- Exit: no duplicate live common schema owner remains; source hash and predicate authority are current.
- Rollback: quarantine the Skill candidate and retain this plan at `plan-ready` only.

## RMAP-S2: Stateless Capsule And Recovery Adapter

- Phase: `P1`.
- Requirements: `RMAP-005`, `RMAP-006`, `RMAP-007`, `RMAP-008`, `RMAP-009`, `RMAP-010`, `RMAP-011`, `RMAP-014`, `RMAP-015`, `RMAP-018`, `RMAP-021`, `RMAP-023`.
- Implement prepare, RED, GREEN, REFACTOR, finalize-candidate, status, and resume actions.
- Tests first: implementation-before-RED, unexpected GREEN, compile/harness failure, stale RED, write-set violation, index drift, read-set drift, dependency drift, stale successor state, and unrelated drift allowance.
- The adapter has no provider scheduler and no hidden state; every transition is reconstructed from append-only evidence.
- GREEN: `rmap-s2-slice-validate` proves the adapter lifecycle and explicit RED/GREEN/REFACTOR evidence under `slice-ready`.
- Exit: a non-protected repository-maintenance slice completes observed RED -> GREEN -> REFACTOR. Its lifecycle proof does not become the final implementation candidate because S3-S5 still change the candidate tree.
- Rollback: mark the run failed or stale, preserve evidence, and remove only the candidate Skill files.

## RMAP-S3: 7-12 Shadow Canary

- Requirements: `RMAP-017`, `RMAP-018`.
- Phase: `P2`.
- Add only an implementation-contract instance and shadow fixtures to `execution-plans/2026-07-12-llm-review-evidence-gate-hardening/`.
- Do not modify its books, status, existing validators, CLI, tests, or historical evidence.
- Shadow validation compares adapter results with the existing 62-test and Whole-directory baselines.
- Before additive files exist, `schemas/shadow-protected-baseline.v1.json` freezes every other file by protected-tree SHA-256 and file count.
- GREEN: `rmap-s3-slice-validate` proves the 7-12 contract and shadow fixture under `slice-ready`.
- Exit: shadow results are non-authoritative, current, and contain no status promotion.
- Rollback: remove the additive metadata files; existing 7-12 bytes remain unchanged.

## RMAP-S4: 7-07 Shadow Backfill

- Requirements: `RMAP-017`, `RMAP-018`.
- Phase: `P2`.
- Add only the contract instance and shadow fixtures to the GDD-to-module split directory.
- Preserve the active implementation authority, acceptance matrix, historical review evidence, and handoff semantics.
- GREEN: `rmap-s4-slice-validate` proves the 7-07 additive contract and shadow fixture under `slice-ready`.
- Exit: shadow validator consumes the plan without authorizing a Phase transition.

## RMAP-S5: 7-11 Shadow Backfill

- Requirements: `RMAP-017`, `RMAP-018`.
- Phase: `P2`.
- Start only after S4 evidence is current.
- Add only the contract instance and shadow fixtures to the paused frontend-boundary plan.
- Preserve `paused`, BH-HANDOFF, protected verifier, and future-capability boundaries.
- GREEN: `rmap-s5-slice-validate` proves the 7-11 additive contract and shadow fixture under `slice-ready`.
- Exit: shadow validation passes without changing current-state claims.

## RMAP-S6: Finalize Current Implementation Candidate

- Requirements: `RMAP-010`, `RMAP-012`, `RMAP-016`.
- Phase: `P3`.
- Recompute the complete current diff and exact candidate identity after S3-S5.
- Require current RED/GREEN/REFACTOR lineage, deterministic tests, authority manifest, contract, command registry, validator, Git index, tracked diff, untracked manifest, changed-file manifest, and test-diff hashes.
- Candidate authorizes Bootstrap review only.
- GREEN: `rmap-s6-candidate-validate` consumes explicit TDD evidence and candidate result only. It does not consume Bootstrap output.
- Exit: current candidate envelope authorizes only an external Bootstrap review.

## External Bootstrap Review

- Use the existing implementation-conformance profile, context classes, preflight, and plan-bound required checks.
- Do not modify the 7-12 CLI unless deterministic evidence proves an extension-point gap.
- The current Round 3 `manual_pause` blocks launching another review under the existing policy revision.

## RMAP-S7: Implementation Acceptance And Handoff

- Requirements: `RMAP-011`, `RMAP-013`, `RMAP-016`, `RMAP-020`.
- Phase: `P3`.
- Run fresh deterministic proof against current hashes and consume finalized Bootstrap evidence.
- Reject high-risk or expired P2 deferrals.
- Produce `implementation-accepted` only from the plan-local validator.
- GREEN: `rmap-s7-acceptance-validate` consumes the same explicitly bound evidence set, requires a non-blocking final review, rejects open accepted P0/P1, and requires a current valid disposition for every accepted P2 under `implementation-accepted`.
- Exit explicitly excludes protected handoff and release.

## Dependency Order

`S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7`

No slice may forward-depend on a later slice. Removal of BMAD is not S8; it is a different future plan.
