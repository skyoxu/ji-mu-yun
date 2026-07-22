# ADR-0042: Artifact-Proof Trust-Root Rotation Boundary

- Status: Accepted
- Date: 2026-07-20

## Context

The Repository Maintenance TDD Adapter consumes an artifact-proof trust root and a root verifier from the Bootstrap Review Skill. The prior projection classified both external inputs as artifacts in the plan-owned authority package. A trust-root rotation then changed the package that the root pins, while changing the root verifier changed the same package again. This created a recursive hash dependency that prevented a valid plan-ready result.

## Decision

The artifact-proof root document and `artifact_proof_root_guards.py` are a protected external input pair. They are loaded directly by the plan validator and remain fail-closed on any byte drift, but they are excluded from the plan-owned authority manifest, artifact-proof inventory, registry, and candidate-hash closure.

Trust-root rotation updates the external pair atomically under its separate custody, then runs the plan projection refresh and validation. The rotation itself does not authorize plan-ready, implementation acceptance, protected handoff, release, commit, or done.

## Consequences

- Plan projections no longer recursively hash their own root verifier.
- Root drift still blocks validation before predicate authorization.
- Historical evidence remains append-only; rotations use new sidecar evidence rather than rewriting a prior review envelope.
- Protected handoff and release continue to require the independent identity or trusted signed-envelope condition recorded by the plan.

## References

- ADR-0041: Bootstrap Review Execution Control Plane Ownership
- `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/tools/artifact_proof_guards.py`
