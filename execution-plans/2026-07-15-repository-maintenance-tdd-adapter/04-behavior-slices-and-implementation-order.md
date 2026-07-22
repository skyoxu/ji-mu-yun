# Behavior Slices And Implementation Order

## RMAP-S0: Existing Framework ADR And Ownership Standard

- Phase: `P0`.
- Requirements: `RMAP-001`, `RMAP-002`, `RMAP-019`, `RMAP-020`, `RMAP-021`, `RMAP-024`, `RMAP-027`.
- Cite the existing Accepted `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md` and produce `docs/standards/repository-maintenance-agent-protocol.md`.
- Update standards and documentation indexes in the same change.
- Tests first: ownership registry rejects duplicate schema/evidence owners and an ADR-ID collision path.
- Register every review-added normative, projection, evidence, lineage, and validator artifact under the seven-dimensional artifact proof contract before any predicate consumes it.
- RED: deliberate duplicate ownership produces `RMAP-OWNERSHIP-DUPLICATE`. The ADR-ID collision remains an independent negative fixture that must produce `RMAP-OWNERSHIP-ADR-ID-COLLISION`.
- GREEN: `rmap-s0-preflight` proves the current non-authorizing `plan-ready` baseline. After REFACTOR evidence is recorded, `rmap-s0-slice-validate` checks the ADR, standard, standards index, and project documentation index under `slice-ready`.
- Exit: GREEN proof passes, the existing ADR remains Accepted, ownership validator and the exact artifact proof registry pass, and no current-capability claim is introduced. `plan-ready` alone cannot satisfy this exit.
- Rollback: remove only the new proposed standard/index links before any dependent slice starts.

## RMAP-S1: Common Contract And Self-Hosted Plan Instance

- Requirements: `RMAP-003`, `RMAP-004`, `RMAP-013`, `RMAP-022`, `RMAP-025`, `RMAP-026`, `RMAP-027`, `RMAP-028`.
- Phase: `P0`.
- Create the repository-owned Skill package, migrate the proposed common schema plus public Capsule/attempt schemas into it, and keep this plan's `implementation-contract.v1.json` as the first live instance.
- Define the reusable index-first target-report lookup, target-directory-only miss fallback, synchronized report creation/registration, target-plan audit contract, unique `95-*.md` rule, VDD repair handoff, post-repair validation/refreeze sequence, index/report hash exclusion, and non-authority boundary without adding a closed-schema top-level field.
- Tests first: schema, raw-shell, env, placeholder, predicate escalation, stale source, and missing acceptance fixtures.
- RED: deliberate `shell=true` fixture produces `RMAP-CMD-SHELL`.
- GREEN: `rmap-s1-preflight` proves the current non-authorizing `plan-ready` baseline. After REFACTOR evidence is recorded, `rmap-s1-slice-validate` proves the self-hosted Skill/schema outputs under `slice-ready`.
- Exit: no duplicate live common schema owner remains; implementation, Capsule, and attempt schemas pass; source hash and predicate authority are current.
- Rollback: quarantine the Skill candidate and retain this plan at `plan-ready` only.

## RMAP-S2: Stateless Capsule And Recovery Adapter

- Phase: `P1`.
- Requirements: `RMAP-005`, `RMAP-006`, `RMAP-007`, `RMAP-008`, `RMAP-009`, `RMAP-010`, `RMAP-011`, `RMAP-014`, `RMAP-015`, `RMAP-018`, `RMAP-021`, `RMAP-023`, `RMAP-025`, `RMAP-026`, `RMAP-028`, `RMAP-029`.
- Implement prepare, RED, GREEN, REFACTOR, finalize-candidate, status, and resume actions.
- Tests first: implementation-before-RED, unexpected GREEN, compile/harness failure, stale RED, write-set violation, index drift, read-set drift, dependency drift, stale successor state, and unrelated drift allowance.
- The adapter has no provider scheduler and no hidden state; every transition is reconstructed from append-only evidence.
- Every backend invocation consumes a new immutable Capsule revision. S2 persists minimized request/response envelopes, independently generates the diff manifest, writes the decision last, appends event lineage, and rejects partial or duplicate accepted stage histories.
- Before preparing RED, audit the current target plan. A material defect enters VDD repair, produces a target-validator PASS and append-only change entry, and forces a complete identity refreeze. Missing/ambiguous `95`, stale pre-repair identity, or a report included in authority/candidate hashes fails closed.
- Implement and test terminal reporting independently of any named requirement directory. Only the target's current declared terminal predicate can append the overall result; non-terminal slices and assistant summaries cannot.
- Stage evidence accepts a validated protocol binding only at first write. The stage writer derives it from an explicit protocol-bundle file or consumes a validated binding file, so the immutable stage result can bind its Capsule, context, attempt, and precomputed decision hash without later mutation.
- Protocol fixture construction is Skill-owned; the plan-side module is a compatibility import layer for existing guard tests and does not duplicate construction logic.
- Capsule and adapter-decision are observations only. The registered RED/GREEN/REFACTOR predicate result owns state transition.
- RED: `rmap-observe-adapter-red` is a shell-free, test-only probe that deliberately attempts GREEN without current RED and returns the observed `RMAP-TDD-RED-NOT-OBSERVED` guard as a controlled nonzero result. GREEN and REFACTOR: `rmap-adapter-tests` prove the Skill-owned lifecycle implementation. After REFACTOR evidence is recorded, `rmap-s2-slice-validate` independently proves the adapter lifecycle and explicit RED/GREEN/REFACTOR evidence under `slice-ready`.
- Exit: a non-protected repository-maintenance slice completes index lookup or target-only fallback -> synchronized registration when needed -> plan audit -> optional VDD repair/refreeze -> observed RED -> GREEN -> REFACTOR with valid Capsule and attempt lineage, while fixtures prove recursive plan scanning and early terminal reporting fail closed. Its lifecycle proof does not become the final implementation candidate because S3-S5 still change the candidate tree.
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

- Requirements: `RMAP-010`, `RMAP-012`, `RMAP-016`, `RMAP-025`, `RMAP-026`, `RMAP-027`.
- Phase: `P3`.
- Recompute the complete current diff and exact candidate identity after S3-S5. Rename inference is disabled; a rename is represented as deterministic delete plus add.
- S6 owns only the candidate-projection control-plane files required to make that recomputation executable, including the stage-evidence projection schema and its guards. This repair boundary does not authorize changes to Bootstrap CLI, Phase services, or the protected 7-12 schemas.
- Require current deterministic tests, authority manifest, contract, command registry, validator, Git index, tracked diff, untracked manifest, cumulative candidate diff manifest, cross-slice lineage manifest, reproducible binary-safe test patch, final context-manifest and Capsule hashes, accepted attempt IDs, and accepted decision hashes.
- Fold immutable S0-S6 run artifacts in predecessor order and independently prove that the candidate manifest exactly equals both the scoped tracked-plus-untracked Git change set and the cumulative lineage fold. Omitted slices, stale run/final-event hashes, extra/deleted paths, misclassification, or add-then-delete drift fail closed.
- Candidate authorizes Bootstrap review only.
- GREEN and REFACTOR: `rmap-s6-slice-validate` verifies the current S6 lifecycle without requiring a candidate that itself is derived from that lifecycle. After REFACTOR, construct the candidate and run `rmap-s6-candidate-validate`; it consumes explicit TDD evidence and the candidate result only, never Bootstrap output.
- Exit: current candidate envelope authorizes only an external Bootstrap review.

## External Bootstrap Review

- Use the existing implementation-conformance profile, context classes, preflight, and plan-bound required checks.
- Do not modify the 7-12 CLI unless deterministic evidence proves an extension-point gap.
- The Round 3 `manual_pause` remains immutable history; the authorized successor cycle clears only plan re-entry and does not itself authorize any implementation slice.

## RMAP-S7: Implementation Acceptance And Handoff

- Requirements: `RMAP-011`, `RMAP-013`, `RMAP-016`, `RMAP-020`, `RMAP-027`.
- Phase: `P3`.
- Run fresh deterministic proof against current hashes and consume the repository Skill's `bootstrap-finalized-run-validation.v1` envelope.
- Consume an explicit `candidate-result-ref.json` that binds the S6 run, candidate bytes/hash, predicate, and `candidate-supersession-proof.json`. Recovery state, event log, final event hash, and a validator-owned scan of the canonical S6 recovery root must prove that run remains active. S6 and S7 run IDs are independent; no implicit latest, Boolean assertion, or caller-supplied empty successor list is allowed.
- Consume runtime `p2-dispositions.json` through the Bootstrap metrics hash; require complete owner/expiry/closure-test/reason fields and verifier source evidence when blocking findings exist. Reject high-risk or expired dispositions.
- Produce `implementation-accepted` only from the plan-local validator.
- After that current terminal predicate passes, append the overall implementation result to this plan's unique non-authorizing `95-*.md`; never use the report to satisfy the predicate.
- GREEN and REFACTOR: `rmap-s7-slice-validate` verifies the current S7 lifecycle without requiring an acceptance input that is derived from that lifecycle. After REFACTOR, `rmap-s7-acceptance-validate` validates the envelope schema, profile/control-plane/validator identity, finalized artifact hashes, non-authorizing boundary, authoritative candidate activity, and runtime finding closure before `implementation-accepted`.
- Exit explicitly excludes protected handoff and release.

## Dependency Order

`S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7`

No slice may forward-depend on a later slice. Removal of BMAD is not S8; it is a different future plan.
