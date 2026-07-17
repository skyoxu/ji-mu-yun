# Repository Maintenance TDD Adapter VDD Plan

Status: `blocked` (`manual_pause_after_round_3`)

Plan ID: `repository-maintenance-tdd-adapter`

Approved intent source: [`../../agentbuild.txt`](../../agentbuild.txt)

Durable clarification authority: [`schemas/clarification-decisions.v1.json`](schemas/clarification-decisions.v1.json), projected from the closed creation and repair clarification runs without raw conversation content.

Current review blocker: [`schemas/review-blocking-state.v1.json`](schemas/review-blocking-state.v1.json). Its immutable successor selector is [`schemas/review-policy-reentry.v1.json`](schemas/review-policy-reentry.v1.json). Round 3 finalized eight P1 findings and exhausted the three-round hard limit. No Round 4 or implementation predicate is authorized under the current policy revision; re-entry requires a distinct successor policy/authority cycle plus a hash-bound independent semantic closure envelope.

## Outcome

Create a repository-owned, stateless TDD adapter protocol that projects VDD plans into compact implementation contracts and immutable persisted Slice Capsule revisions, proves an observed RED before production writes, constrains GREEN and REFACTOR work, records every backend attempt in an append-only hash chain, and produces an implementation candidate for the existing Bootstrap semantic-review route. The implementation backend, Capsule, and adapter decision never own review, `done`, commit, acceptance, or release authority.

## Current-State Truth

- No `quick-dev-tdd-adapter`, `implementation-contract.v1`, or `tdd-result.v1` capability is currently operational.
- Stock BMAD Quick Dev still performs its own semantic review, marks its spec done, and may create a local commit. It is not an implementation-only backend.
- The repository-owned Bootstrap Skill is the current review-policy authority. The 7-12 plan/profile remain hash-bound compatibility and migration inputs, not current policy authority.
- The 7-11 frontend boundary plan remains paused behind the 7-07 handoff. Metadata backfill in this plan cannot change that state.

## Authority Order

1. `AGENTS.md` and accepted ADRs.
2. The closed clarification snapshot and `agentbuild.txt` source history.
3. Durable standards and accepted ADR-0041 ownership-pattern authority.
4. Machine owners in this directory.
5. Explanatory Markdown in this directory.
6. Run-scoped evidence under `logs/`.

## Reading Order

1. [Intent, authority, and non-goals](01-intent-authority-and-non-goals.md)
2. [Executable contracts and invariants](02-executable-contracts-and-invariants.md)
3. [Validators, fixtures, and control gates](03-validators-fixtures-and-control-gates.md)
4. [Behavior slices and implementation order](04-behavior-slices-and-implementation-order.md)
5. [Diagnostics, repair, and re-entry](05-diagnostics-repair-and-reentry.md)
6. [Testing, observability, and evidence](06-testing-observability-and-evidence.md)
7. [Implementation phases](07-implementation-phases.md)
8. [Risks, DoD, and glossary](08-risks-dod-and-glossary.md)
9. [Global review and validation](96-global-review-and-validation.md)
10. [Requirements ledger](97-requirements-ledger.md)
11. [Source-to-split audit](98-source-to-split-audit.md)
12. [Source coverage](99-source-coverage.md)

## Machine Owners

- Plan status and predicate authority: [`schemas/plan-state.v1.json`](schemas/plan-state.v1.json)
- Requirement registry: [`schemas/requirements.v1.json`](schemas/requirements.v1.json)
- Source coverage: [`schemas/source-coverage.v1.json`](schemas/source-coverage.v1.json)
- Spec deltas: [`schemas/spec-deltas.v1.json`](schemas/spec-deltas.v1.json)
- Proposed common contract schema: [`schemas/implementation-contract.v1.schema.json`](schemas/implementation-contract.v1.schema.json)
- Persisted context schemas: [`schemas/context-manifest.v1.schema.json`](schemas/context-manifest.v1.schema.json) and [`schemas/slice-capsule.v1.schema.json`](schemas/slice-capsule.v1.schema.json)
- Attempt ledger schemas: [`schemas/backend-request.v1.schema.json`](schemas/backend-request.v1.schema.json), [`schemas/backend-response.v1.schema.json`](schemas/backend-response.v1.schema.json), [`schemas/diff-manifest.v1.schema.json`](schemas/diff-manifest.v1.schema.json), [`schemas/adapter-decision.v1.schema.json`](schemas/adapter-decision.v1.schema.json), and [`schemas/agent-attempt-event.v1.schema.json`](schemas/agent-attempt-event.v1.schema.json)
- Final candidate schemas: [`schemas/candidate-diff-manifest.v1.schema.json`](schemas/candidate-diff-manifest.v1.schema.json), [`schemas/candidate-slice-effect.v1.schema.json`](schemas/candidate-slice-effect.v1.schema.json), [`schemas/candidate-lineage-manifest.v1.schema.json`](schemas/candidate-lineage-manifest.v1.schema.json), [`schemas/candidate-result-ref.v1.schema.json`](schemas/candidate-result-ref.v1.schema.json), and [`schemas/candidate-supersession-proof.v1.schema.json`](schemas/candidate-supersession-proof.v1.schema.json)
- Review-added artifact proof contract and exact registry: [`schemas/artifact-proof.v1.schema.json`](schemas/artifact-proof.v1.schema.json) and [`schemas/artifact-proof-registry.v1.json`](schemas/artifact-proof-registry.v1.json)
- Capsule and attempt mutation fixtures: [`fixtures/capsule-attempt-cases.v1.json`](fixtures/capsule-attempt-cases.v1.json)
- Candidate diff and predecessor mutation fixtures: [`fixtures/candidate-diff-cases.v1.json`](fixtures/candidate-diff-cases.v1.json)
- Self-hosted contract instance: [`implementation-contract.v1.json`](implementation-contract.v1.json)
- Command registry: [`schemas/command-registry.v1.json`](schemas/command-registry.v1.json)
- Executable acceptance registry: [`schemas/acceptance-contracts.v1.json`](schemas/acceptance-contracts.v1.json)
- Durable authority manifest: [`schemas/authority-manifest.v1.json`](schemas/authority-manifest.v1.json)
- Clarification decision projection: [`schemas/clarification-decisions.v1.json`](schemas/clarification-decisions.v1.json)
- Bootstrap blocking disposition: [`schemas/review-blocking-state.v1.json`](schemas/review-blocking-state.v1.json)
- Bootstrap policy re-entry selector: [`schemas/review-policy-reentry.v1.json`](schemas/review-policy-reentry.v1.json)
- Shadow migration registry: [`schemas/shadow-backfill.v1.json`](schemas/shadow-backfill.v1.json)
- Composite validator: [`tools/validate_all.py`](tools/validate_all.py)
- Capsule and attempt validator: [`tools/protocol_guards.py`](tools/protocol_guards.py)
- Candidate diff validator: [`tools/candidate_diff_guards.py`](tools/candidate_diff_guards.py)
- Cross-slice lineage and supersession validator: [`tools/candidate_lineage_guards.py`](tools/candidate_lineage_guards.py)
- Review-added artifact proof validator: [`tools/artifact_proof_guards.py`](tools/artifact_proof_guards.py)

## Validation Commands

```powershell
py -3 execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py --predicate plan-repair-verified
py -3 execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py --predicate plan-ready
py -3 -m unittest discover -s execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests -p "test_*.py" -v
```

A successful `plan-repair-verified` result proves only that the blocked plan is internally coherent and reproducible. `plan-ready` and every implementation predicate must return nonzero with `RMAP-REVIEW-MANUAL-PAUSE` until `review-policy-reentry.v1` binds the immutable blocker hash, a distinct successor policy/authority decision, and a current independent clean semantic closure envelope.

## Phase Order

`P0 framework ADR and ownership` -> `P1 contract and adapter lifecycle` -> `P2 old-plan shadow backfill` -> `P3 final candidate` -> external Bootstrap review -> `P3 implementation acceptance`.

Removal of BMAD is explicitly outside this plan and requires a separate future plan.
