# Bootstrap Review Operability Hardening

## Purpose

Improve operator ergonomics and deterministic diagnostics for `run-phase-bootstrap-review`, make semantic-review requirement routing Acceptance-owned, and reduce discovery wall time through an isolated Bootstrap-owned concurrent wave without weakening evidence, lineage, scope, or authority rules.

## Profile

`self-hosted`: this changes a workflow-control Skill and its validators, so the plan includes protocol fixtures, migration checks, and one terminal replay.

## Scope

The plan covers closure-binding generation, prepare dry-run diagnostics, frozen/repair-window state reporting, planned-new-file classification, context-class completeness diagnostics, Windows-safe transport and bounded no-progress recovery, reviewer read-only repository access, exact Artifact View evidence-range binding, Acceptance-owned review requirement decisions, frozen deterministic facts, typed risk lenses that preserve full coverage, zero-findings validity, explicit semantic stop rules, deterministic-only routing, bounded re-entry compatibility, Bootstrap-owned concurrent discovery, partial-role retry, non-authorizing telemetry, and a Quick Dev terminal implementation predicate.

## Non-goals

Do not relax closure hashes, context requirements, Artifact View coverage, reviewer isolation, independent verification, lineage budgets, hard limits, or `authorizes=[]` envelope rules. Do not change product acceptance, commit, release, or handoff authority.

## Authority

Implementation must cite ADR-0041, ADR-0051, ADR-0056 and `docs/standards/bootstrap-review-control-plane.md`. Existing review evidence remains immutable historical input.

## Slices

1. BROH-S0: deterministic prepare diagnostics and binding preview.
2. BROH-S1: freeze/repair-window and planned-file diagnostics.
3. BROH-S2: transport, stale-attempt, Windows heartbeat, and stop-loss recovery.
4. BROH-S3: reviewer read boundary and exact-evidence generation.
5. BROH-S4: Acceptance-owned review requirement and risk routing.
6. BROH-S5: bounded re-entry and legacy compatibility.
7. BROH-S6: Bootstrap-owned concurrent discovery wave and non-authorizing telemetry.
8. BROH-S7: Quick Dev implementation terminal predicate and cross-skill composition.

## Completion

Plan readiness requires the plan validator, plan-local tests, and a current VDD knowledge preflight. The current knowledge context is fresh and Quick Dev routing resolves to `BROH-S0`. The plan remains blocked for implementation completion until the dependency-ordered S0-S7 slice predicates and terminal validation pass; no `implementation-complete` authority is implied. Quick Dev may proceed without pre-implementation Bootstrap evidence.

Each slice uses the plan-local `single_maintainer_tdd_bridge.py` in four current-session calls. The first call freezes the complete exact write set and pauses before RED. The AI maintainer then adds or updates only the declared target test. The second call must observe that target test failing and pauses before production changes. The AI maintainer then implements the minimal production change. The third call requires the same target test to pass and pauses before refactor. The AI maintainer may then update declared documentation or apply other declared refactor edits. The fourth call runs the declared refactor suites, composes shared Quick Dev protocol evidence, builds the plan-local stage projection, and evaluates the slice predicate. RED permits only declared test changes; GREEN permits only declared production changes; REFACTOR permits only the complete declared write set. No model subprocess, parallel implementation owner, or external requirement source is part of this bridge.

Every `slice-ready` result exposes slice-scoped freshness roots and direct predecessor result hashes. The roots bind the selected slice contract, registered commands, authority, validators, and current predecessor evidence without binding unrelated downstream worktree churn. A successor result for an upstream slice therefore invalidates its dependent results deterministically, while a downstream change to an overlapping production file does not incorrectly reopen an already completed upstream slice. Protocol identity drift creates a new append-only run linked to the previous run instead of reusing or overwriting stale evidence.

Do not use `persistent_plan_loop.py` for this plan. It cannot wait for the current AI session to perform the required edits between phases and supplies only one snapshot path, while this plan requires complete exact snapshot coverage. Invoke the shared `loop_plan_directory.py` once per bridge phase with every current slice `execution_snapshot_paths` entry. S0-S6 produce non-authorizing `slice-ready`; S7 runs the separate `validate_implementation.py` predicate. Implementation completion additionally requires current, hash-bound RED/GREEN/REFACTOR results, projection, recovery, attempt ledger, event chain, protocol bindings, predecessor bindings, and registered Bootstrap, Acceptance, and plan-local consumer suites. The target-local predicate never launches Bootstrap or publishes Acceptance. Post-implementation Acceptance remains external and is expected to classify this workflow-control-plane change as required.

Every observed command is surrounded by a full Git worktree manifest check. RED, GREEN, and REFACTOR command-side effects must remain inside their stage write class; REFACTOR pre-observation suites and the terminal predicate must leave the worktree unchanged. Before accepting a terminal result, the bridge performs a stable guard outside the S7 write set: it independently checks projection integrity, stage-result linkage, current validator identity, current slice freshness roots, terminal predicate fields, and the empty authority envelope. This prevents undeclared command artifacts and prevents S7 from self-verifying a changed terminal validator.

The contract may use `planned_new_files` only for explicitly intended additions. The S4 acceptance package declares its new producer, schema, and target test there. Plan validation rejects every other missing snapshot path; the bridge allows those three paths to be absent only during preparation, requires the test file before RED, requires production files before GREEN, and requires all three before REFACTOR and terminal validation.
