# Prototype Routes And Recovery Architecture

## Intent

Phase browser flows use prototype routes to turn game ideas, GDDs, iteration goals, repair requests, assets, packages, and previews into controlled repository-native executions.

The architecture goal is to let the platform expose useful route control and readback without letting assistant summaries, browser state, or free-form prompts become acceptance authority.

## Boundary

In scope:

- Project workflow intent classification.
- Prototype 7-day playable route, prototype TDD route, scene creation, iteration planning, goal execution, needs-fix, repair plan, quick fix, feedback iteration, UI optimization, GDD milestone routes, package and preview flows.
- Route state files under project-local `meta/**` and `routes/**` paths.
- Prototype contracts, route ledgers, repair ledgers, latest state, and acceptance evidence.
- Game-type route profiles and skill prompt blocks selected by route services.

Out of scope:

- Human-only or AI-only subjective acceptance as the system of record.
- Treating BMAD/GDS guide coverage as executable support without a type kit, route profile, strategy, skill contract, plan guard, recovery inputs, acceptance markers, and tests.
- Replacing Godot project files with an external scene schema.

## Key Decisions

- Prototype routes are contracted, not implied.
- Route state and repair ledgers are continuity memory, not current acceptance authority.
- Latest live platform acceptance blockers win over old assistant summaries and stale route state.
- Completion cannot be marked based only on assistant text.
- Phase B absorption work should prefer machine-closed evidence, readiness catalogs, route ledgers, evidence bundles, and validators over manual green status.

## Recovery Authority Order

For file-changing hosted game-project routes, consume project-level recovery sources before editing:

1. Parsed game-type route profile.
2. Selected route skill prompt block.
3. `meta/project-execution-guide.md`.
4. `routes/prototype-contract/latest.json`.
5. Current route latest state, such as `meta/routes/prototype/latest.json`, `meta/routes/iteration-plan/latest.json`, or `meta/routes/execute-next-goal/latest.json`.
6. Current goal, step, repair step, or session state.
7. Repair ledger and failing acceptance or Godot diagnostic evidence for repair routes.
8. Latest live platform acceptance blocker.

Missing required recovery sources must fail closed.

The ordered list is represented by the shared `hosted-route-recovery-order.v1` contract. Prompt-producing routes persist structured evidence that repeats the contract ID, the exact ordered list, and the route-local source-hash map; free-text token presence is not accepted as proof.

The persisted evidence also carries `hosted-route-forbidden-source-scan.v1`, computed from the exact in-memory prompt before dispatch. The manifest keeps a database-bound `execution_prompt_hash` for the scan and a separate `persisted_prompt_hash` for the secret-redacted internal artifact. The scan must match the declared patterns, authority-derived allowed source references, and complete paragraph/overlapping-window fingerprint set, with no matches or violations. Missing catalogs, empty required fingerprint sets, missing prompt artifacts, cross-project runs, incomplete runs, or mismatched database bindings fail closed. Authoritative hashes are recomputed from current structured content; copied sidecar hash declarations are not authority.

The pre-freeze GDD lane may use one selected game-type guide whose ID, path, and content hash are recorded. It rejects unapproved guide chunks before Codex dispatch. Post-freeze requirement and execution lanes reject raw mutable guide chunks even if paths were removed or whitespace changed.

## Invariants

- Route state must be source-linked and stale-state aware.
- A frozen `prototype-contract.v2` is immutable authority for the current chain. Prototype execution may read it and repair an identical mirror, but request-derived legacy contract generation must not overwrite the frozen canonical contract or change its hash.
- Frozen-contract consumption recomputes the canonical contract hash and current GDD, semantic scene-route, requirement-map, and contract-snapshot hashes. An invalid canonical contract cannot fall back to legacy request-derived content.
- Registered JSON route artifacts must match the registry's exact route ID, schema version, status dimension, allowed subset, and status; switching to another known contract or removing schema and dimension together fails closed.
- Acceptance status must be derived from validators, markers, scripts, logs, database rows, imported assets, package outputs, or stable diagnostics.
- Browser/API readback may display route state, but must not reinterpret route decisions independently.
- Any new route must declare recovery inputs, authority order, missing-source behavior, browser-safe output rules, and tests.

## Change Rules

- New game-type support requires route profile, type kit/contract, strategy, skill contract, acceptance markers, recovery inputs, and negative stale-state tests.
- New route sidecars must use bounded status enums and evidence references.
- New browser actions must call existing route services or script-owned entrypoints; do not fork route logic into UI code.
- New repair behavior must write structured state before and after execution.

## Related Code

- `PhaseA.Platform/Runs/ProjectWorkflowRouteService.cs`
- `PhaseA.Platform/Runs/GameTypeRouteEngine.cs`
- `PhaseA.Platform/Runs/GameTypeRouteStrategies.cs`
- `PhaseA.Platform/Runs/PrototypeRouteStateWriter.cs`
- `PhaseA.Platform/Runs/PrototypeWorkflowService.cs`
- `PhaseA.Platform/Runs/PrototypeIterationPlanService.cs`
- `PhaseA.Platform/Runs/PrototypeIterationGoalService.cs`
- `PhaseA.Platform/Runs/PrototypeNeedsFixRouteService.cs`
- `PhaseA.Platform/Runs/PrototypeRepairPlanService.cs`
- `PhaseA.Platform/Runs/PrototypeGoalAcceptanceValidator.cs`
- `scripts/python/run_prototype_workflow.py`
- `scripts/python/run_prototype_tdd.py`

## Related Tests And Docs

- `PhaseA.Platform.Tests/Runs/Prototype*Tests.cs`
- `scripts/python/tests/test_prototype_workflow_router*.py`
- `docs/workflows/prototype-lane.md`
- `docs/workflows/prototype-lane-playbook.md`
- `docs/workflows/prototype-tdd.md`
- `docs/workflows/phase-b-agf-godogen-absorption.md`
