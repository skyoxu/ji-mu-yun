# ADR-0036: Prototype Route Recovery Authority And Machine-Closed Acceptance

- Status: Accepted
- Date: 2026-06-28

## Context

Phase browser flows use prototype routes for project creation, prototype execution, iteration, repair, GDD, assets, packages, and previews. These routes produce project-local state and evidence over multiple runs.

Without an explicit authority order, future agents can treat stale assistant summaries, browser state, or route memory as acceptance truth.

## Decision

Prototype routes are contracted, not implied, and file-changing routes must consume recovery sources in authority order before editing.

Authority order:

1. Parsed game-type route profile.
2. Selected route skill prompt block.
3. `meta/project-execution-guide.md`.
4. `routes/prototype-contract/latest.json`.
5. Current route latest state, such as `meta/routes/prototype/latest.json`, `meta/routes/iteration-plan/latest.json`, or `meta/routes/execute-next-goal/latest.json`.
6. Current goal, step, repair step, or session state.
7. Repair ledger and failing acceptance or Godot diagnostic evidence for repair routes.
8. Latest live platform acceptance blocker.

Each route must declare which recovery sources are required and which are legacy or optional. Missing required recovery sources fail closed. Missing optional legacy sources may degrade to an explicit stale or unknown state, but must not silently mark acceptance green.

Acceptance must be derived from validators, markers, scripts, logs, database rows, imported assets, package outputs, route state, or stable diagnostics. Assistant text alone cannot mark completion.

## Consequences

- Route recovery is more reliable after context resets.
- New game-type support needs type kit/contract, route profile, strategy, skill contract, acceptance markers, recovery inputs, and tests.
- Browser/API readback may display route state but must not reinterpret route decisions independently.
- Phase B evidence bundles and readiness catalogs must be generated from source-linked evidence.

## References

- `docs/architecture/phase-service/prototype-routes-and-recovery.md`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
- `PhaseA.Platform/Runs/PrototypeRouteStateWriter.cs`
- `PhaseA.Platform/Runs/PrototypeGoalAcceptanceValidator.cs`

## Addendum (2026-10 asynchronous GDD fixture readiness)

- The GDD integration fixture waits for both the expected terminal run status
  and its completed progress step before inspecting downstream artifacts.
- Use a monotonic readiness deadline of 30 seconds, consistent with the existing
  prototype workflow fixtures, instead of counting short polling iterations.
  This is a test readiness bound, not a product latency guarantee. Failed,
  blocked, or cancelled runs fail immediately with their current diagnostics.
- The fake Runner deliberately completes after the former two-second window;
  the fixture still validates the full GDD, milestone, asset, and package chain.
  Temporary database cleanup yields while final background writes close.
- Terminal metadata and progress are not a background-completion fence. Before
  reading route files, queued prototype fixtures acquire and release a lease
  on the same project in the production queue. That lease becomes available
  only after prior queued work, including route and audit writes, exits.
