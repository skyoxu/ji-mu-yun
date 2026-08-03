# Acceptance Repair Closure For Exhausted Lineage

- Acceptance target: `execution-plans/2026-07-26-knowledge-locator-workflow-integration`
- Current predecessor review: `logs/ci/2026-07-27/review-gateway-bootstrap-knowledge-locator-workflow-plan-r3b-20260727/`
- Current confirmed findings: `BSR-4F8A9341CD3CDFBC`, `BSR-59092136A5D5D414`, `BSR-ABDD6277892B502F`, `BSR-F0AF746EDA67B150`
- Trigger: repair the exact four confirmed Round 3 findings and close the three-round lineage through ADR-0054 deterministic manual-pause closure.
- Scope: enforce the bounded rejection vocabulary, required-module and decision-owner validation, preserve current slice evidence when targeted-validation sidecars exist, refresh current authority and VDD-owned knowledge-context bindings, repair Windows long-path handling in the publication integration fixture, and replay the plan-local predicates.
- Non-goals: change Locator behavior, reopen requirement discovery, create a successor plan, reset Bootstrap lineage, or modify historical review evidence.

## Repair Slices

1. `KWI-R1-AUTHORITY`: verify the four changed authority documents preserve the original Locator and adapter invariants, then update only their hashes in `authority-manifest.v1.json`.
2. `KWI-R1-CONTEXT`: replace the stale legacy `knowledge-context.v1.json` through the VDD producer and publish `knowledge-context.freeze.v1.json`, preserving the old context in `knowledge-context.history/`.
3. `KWI-R1-WINDOWS`: exclude generated acceptance snapshots from the publication test's temporary clone and enable Git for Windows long-path checkout without changing the evaluator or Locator inputs.
4. `KWI-R1-REPLAY`: run the plan validator, plan-validator tests, publication tests, and the registered terminal integration validator with its declared 900-second per-command budget.
5. `KWI-R1-ROUND3`: run the shared context validator, VDD preflight, and Quick Dev route tests that deterministically cover all four confirmed Round 3 findings.

The repair remains non-authorizing until `repair-closure.json` binds current inputs and successful command results. No Round 4 or model review is authorized; Refactor Acceptance owns the ADR-0054 closure.
