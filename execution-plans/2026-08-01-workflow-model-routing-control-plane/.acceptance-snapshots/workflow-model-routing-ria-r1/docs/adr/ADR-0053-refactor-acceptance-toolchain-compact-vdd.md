# ADR-0053: Refactor Acceptance Toolchain Domain And Compact VDD Projection

- Status: Accepted
- Date: 2026-08-01

## Context

Refactor Acceptance originally admitted only the `phase_service` code-review
domain and expected every target to provide the full Repository Maintenance
implementation contract. A completed compact VDD plan can have an exact Git
baseline, terminal validator, requirements, and candidate bytes without that
RMAP-specific contract. Treating such a target as Phase-only leaves its VDD,
Quick Dev, standards, and plan changes in an unreviewed external partition;
inventing RMAP slices after implementation would falsify its history.

Repository workflow changes may also include a shared Phase entrypoint such as
`scripts/sc/_llm_backend.py`. That dependency must remain explicit rather than
being silently reclassified or excluded.

## Decision

- Refactor Acceptance supports `phase_service` and `toolchain` as closed run
  input domains. Unknown domains fail closed.
- The existing Phase policy and `resolve-phase-policy` compatibility entrypoint
  retain their behavior.
- A separate versioned toolchain policy owns a closed set of repository
  workflow prefixes. Every changed path must be covered. Shared Phase
  entrypoints are listed as exact cross-domain paths and projected into the
  binding as `crossDomainDependencyPaths`.
- A compact VDD target may substitute one
  `compact-vdd-acceptance-prerequisite-bundle.v1` for the full implementation
  contract only after it is `implementation-complete`.
- The deterministic projector consumes explicit sorted changed paths,
  consumers, actions, commands, baseline revision, policy, and an
  Acceptance-owned knowledge context. It never discovers the candidate from
  repository-wide dirty state.
- Dirty candidate bytes are copied to the target-owned
  `.acceptance-snapshots/<run-id>` namespace. Baseline Git blobs, candidate
  bytes, deletions, manifests, policy, action DAG, registry, run request,
  validator, and knowledge context are hash-bound before the bundle is
  published.
- The bundle and policy binding carry `authorizes=[]`. Acceptance lifecycle,
  Bootstrap semantic review, model launch, cost acknowledgement, lineage,
  commit, release, and archive authority do not change.

This extends ADR-0041 and ADR-0052 and supersedes none.

## Consequences

- Compact plans can enter Acceptance without retroactively pretending to be
  Repository Maintenance TDD plans.
- Toolchain candidates cannot pass while silently omitting repository workflow
  files.
- Phase behavior and historical artifact-only runs remain backward compatible.
- Operators must still provide exact changed paths and a current knowledge
  context; missing or ambiguous prerequisites remain `prerequisite_blocked`.

## References

- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`
- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/adr/ADR-0052-bootstrap-review-calibration-and-exact-envelope-reuse.md`
- `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`
