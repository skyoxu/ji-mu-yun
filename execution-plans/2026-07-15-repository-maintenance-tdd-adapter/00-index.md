# Repository Maintenance TDD Adapter VDD Plan

Status: `plan-ready`

Plan ID: `repository-maintenance-tdd-adapter`

Approved intent source: [`../../agentbuild.txt`](../../agentbuild.txt)

Clarification authority: `logs/vdd-clarifications/2026-07-15-repository-maintenance-tdd-adapter-f6d1143a/clarification-20260715T094322Z/state.json` at SHA-256 `21da9212cdeb767c579dcdad6e374cba01d81d63563064724335e7016a85a0ec`.

## Outcome

Create a repository-owned, stateless TDD adapter protocol that projects VDD plans into compact implementation contracts, proves an observed RED before production writes, constrains GREEN and REFACTOR work, recovers from append-only evidence, and produces an implementation candidate for the existing Bootstrap semantic-review route. The implementation backend never owns review, `done`, commit, acceptance, or release authority.

## Current-State Truth

- No `quick-dev-tdd-adapter`, `implementation-contract.v1`, or `tdd-result.v1` capability is currently operational.
- Stock BMAD Quick Dev still performs its own semantic review, marks its spec done, and may create a local commit. It is not an implementation-only backend.
- The 7-12 Bootstrap CLI is operational as supplemental review evidence and already exposes scope, context-class, deterministic preflight, and required-check extension points.
- The 7-11 frontend boundary plan remains paused behind the 7-07 handoff. Metadata backfill in this plan cannot change that state.

## Authority Order

1. `AGENTS.md` and accepted ADRs.
2. The closed clarification snapshot and `agentbuild.txt` source history.
3. Durable standards and the planned framework ADR.
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
- Self-hosted contract instance: [`implementation-contract.v1.json`](implementation-contract.v1.json)
- Command registry: [`schemas/command-registry.v1.json`](schemas/command-registry.v1.json)
- Shadow migration registry: [`schemas/shadow-backfill.v1.json`](schemas/shadow-backfill.v1.json)
- Composite validator: [`tools/validate_all.py`](tools/validate_all.py)

## Validation Commands

```powershell
py -3 execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/validate_all.py --predicate plan-ready
py -3 -m unittest discover -s execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/tests -p "test_*.py" -v
```

A successful `plan-ready` result authorizes only `plan-ready`. It does not authorize a slice, implementation, acceptance, handoff, or release.

## Phase Order

`P0 framework ADR and ownership` -> `P1 contract and self-hosted adapter` -> `P2 old-plan shadow backfill` -> `P3 Bootstrap-bound candidate and acceptance`.

Removal of BMAD is explicitly outside this plan and requires a separate future plan.
