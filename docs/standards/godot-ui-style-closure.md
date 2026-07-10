# Godot UI Style Closure Standard

Status: Living standard
Language: English
Scope: Style-aware UI closure, style drift gap rows, style repair prompt inputs, and final-readiness style gates for Phase hosted Godot routes.

## Purpose

UI closure validates both whether the player can use the interface and whether the interface still belongs to the selected frozen style. This standard consumes the normalized drift taxonomy from `docs/standards/godot-ui-style-contract.md`; do not create a second taxonomy here.

## Machine-Readable Contract

The runtime registry is `PhaseA.Platform/Workflow/GodotUiStyleClosureContract.cs`.
The deterministic test owner is `PhaseA.Platform.Tests/Workflow/GodotUiStyleClosureContractTests.cs`.
Readback enforcement lives in `PhaseA.Platform/Runs/ProjectRouteStateArtifactService.cs`.

Stable capability IDs:

- `ui_style_closure_gap_taxonomy`
- `ui_style_repair_prompt_contract`
- `ui_final_readiness_style_gate`

## Style Gap Rows

`meta/routes/ui-wiring/latest.json` may include `style_gap_rows`. When present, every row must include:

- `gap_id`
- `style_drift_family`
- `requirement_ids`
- `scene_node_path`
- `expected_style_token_or_rule`
- `observed_drift`
- `severity`
- `affected_viewport_or_component_state`
- `visual_evidence_method`
- `follow_up_goal_recommendation`
- `status`

`style_drift_family` must be one of the bounded families in `GodotUiStyleCatalog`. Unknown families block UI closure. Unresolved P0/P1 rows block final readiness unless their status is `resolved` or `reviewed_not_applicable`.

P2 style drift may be advisory for ordinary user execution only when tracked under the acceptance severity standard. Final implementation review still requires zero unresolved P0/P1/P2 findings.

## Repair Prompt Inputs

When `style_repair_prompt_inputs` is present, it must include these frozen/source-bound inputs instead of broad mutable style-guide prose:

- `frozen_style_snapshot_ref`
- `runtime_environment_ref`
- `affected_node_paths`
- `component_defaults_ref`
- `exception_rules_ref`
- `composition_rules_ref`
- `motion_transition_rules_ref`
- `pointer_event_shape_ref`
- `gesture_phase_ref`
- `drag_drop_payload_policy_ref`
- `theme_resource_token_coverage_ref`
- `visual_evidence_method`
- `ui_tree_readback_refs`

Missing inputs block UI closure with `diagnostic_blocked`.

## Final Readiness

Full-target UI closure ledger statuses are:

- `covered`
- `reviewed_not_applicable`
- `explicitly_deferred`

`not_consumed_by_first_slice` is an interim Phase 1 coverage value only. It cannot satisfy final readiness or full non-technology UI target closure.

Preview/package download remains separate from final readiness. Final readiness remains blocked by unresolved P0/P1 style drift, stale style snapshots, invalid style gap taxonomy, missing repair prompt inputs when repair is required, invalid full-target ledger status, diagnostics, source-boundary, or admin review blockers.

## Validation

Minimum deterministic validation:

```powershell
dotnet test PhaseA.Platform.Tests --filter "FullyQualifiedName~GodotUiStyleClosureContractTests|FullyQualifiedName~ProjectRouteStateArtifactServiceTests"
```
