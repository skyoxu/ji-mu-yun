# Godot Diagnostics And Quality Gates

Status: Living standard
Language: English
Scope: Phase A/B GDD-to-module diagnostics, preview/package readiness, diagnostic spool, admin triage, interaction-region evidence, and resource lifecycle checks.

## Authority

This standard implements the Godot/Phase replacement for TapTap development quality-gate capabilities. No TapTap local runtime concept, TapTap-specific LSP API, TapTap disposal rule, or TapTap runtime technology is normative here. The authoritative implementation surface is:

- `PhaseA.Platform/Workflow/GodotDiagnosticsQualityGate.cs` for capability IDs, failure-family taxonomy, route seeds, bounded status values, and remediation rows.
- `PhaseA.Platform/Data/SqliteMetadataSchema.cs` and `PhaseA.Platform/Data/PhaseAMetadataStore.cs` for the metadata DB diagnostic index, retained diagnostic spool refs, deletion-safe tombstone joins, triage mutation, and account-scoped readback.
- `docs/schemas/project-diagnostic-spool.v1.example.json` for the preserved spool record shape.
- `PhaseA.Platform.Tests/Workflow/GodotDiagnosticsQualityGateTests.cs` and `PhaseA.Platform.Tests/Data/SqliteMetadataSchemaTests.cs` for consistency and persistence checks.

## Capability Package IDs

- `godot_diagnostic_spool_contract`: project diagnostic spool schema, metadata DB diagnostic index ownership, deleted-project lookup, redaction, retention, and reconciliation.
- `godot_failure_family_taxonomy`: bounded failure-family set, domain route mapping, symptom-to-remediation rows, and route diagnostic consistency.
- `godot_prebuild_preview_quality_gate`: pre-build/pre-preview diagnostics, package readiness, preview validation, and blocker propagation.
- `godot_interaction_region_gate`: interaction-region artifacts for UI/input/physics/camera-heavy P0/P1 requirements.
- `godot_resource_lifecycle_gate`: debug-log lifecycle, explicit cleanup evidence, orphan process/resource diagnostics, and replacement evidence after compaction.

## Diagnostic Spool Contract

Critical diagnostics are preserved outside hosted workspaces under the runtime evidence root:

```text
logs/phase-a-innernet/diagnostics/projects/<account_id>/<project_id>/
```

Normal browser/admin query authority is the metadata DB diagnostic index, not direct spool scanning. Spool files are append-only evidence; route and admin screens query `project_diagnostic_spool` and use `spool_ref` only as a preserved evidence pointer.

Required metadata DB diagnostic index fields:

- `diagnostic_id`, `account_id`, `project_id`, `project_name_snapshot`, `run_id`, `route`, `failure_family`, `severity`, `triage_status`, `retention_class`, `redaction_status`, `spool_ref`, `user_safe_summary`, `source_refs_json`, `evidence_refs_json`, `created_utc`, `updated_utc`, `resolved_utc`, `triage_decision_by`, `triage_decision_reason`, `deletion_event_id`, `project_tombstone_id`.

Required indexes:

- unresolved admin triage: `(triage_status, severity, updated_utc)`.
- project lookup: `(account_id, project_id, triage_status)`.
- deleted-project lookup: `(project_tombstone_id, deletion_event_id)`.
- route/family analytics: `(route_id, failure_family, created_utc)`.
- retention cleanup: `(retention_class, triage_status, updated_utc)`.

Triage updates are admin-only and may update `triage_status`, decision metadata, and replacement evidence. They must not rewrite `failure_family`, `spool_ref`, original source refs, account/project identity, or deletion tombstone identity.

Normal-user readback can only list diagnostics for the caller account and project. It must return redacted `user_safe_summary` and must not expose raw host paths, token material, provider secrets, raw prompts, or admin-only evidence.

## Retention And Cleanup

- `unresolved_blocker` records for P0/P1/P2 diagnostics are preserved outside hosted workspaces and are not eligible for deletion or destructive compaction.
- `resolved_audit`, `ignored_audit`, and `backlog_audit` records may be compacted or redacted after a future documented retention window, but must retain account/project scope, route, failure family, severity, triage decision, timestamps, and replacement evidence refs.
- `info_ephemeral` records may be cleaned only when they are not referenced by unresolved blockers, admin review queue entries, route-state blockers, package/readiness blockers, or decision logs.
- Ordinary project deletion never deletes diagnostic spool records. It records a `project-delete` diagnostic event and joins preserved diagnostics to `project_delete_tombstones` using `deletion_event_id` and `project_tombstone_id`.

## Prebuild And Preview Quality Gate

P0/P1 routes that invoke Godot build, validation, preview, package, repair, or UI closure must provide structured diagnostic evidence before downstream work is considered ready. Accepted evidence refs include `dotnet build`, .NET tests, Godot self-check, GdUnit4, scene load checks, route-state validators, source hash validation, screenshot/canvas-pixel evidence, package artifact refs, and browser-safe preview ticket/readback refs.

Preview/package readiness cannot be `ready` or `succeeded` when source hashes, diagnostic evidence, package artifact, preview ticket, or browser-safe readback are stale, missing, or invalid. Unresolved P0/P1/P2 diagnostic spool blockers feed final package readiness through workflow severity review; package download compatibility may remain available, but final readiness remains blocked.

## Interaction Region Gate

P0/P1 UI, input, physics, route-map, card-dragging, collision, or camera-transform work must include an interaction-region artifact unless the route state includes `no_interaction_region_needed` with a reviewed rationale. Accepted artifact forms are ASCII diagrams, hit-zone tables, Godot node maps with `Control` rects or collision shapes, CanvasLayer/world-boundary sketches, raycast/camera transform notes, or coordinate-annotated screenshots.

Each artifact records affected requirement IDs, scene IDs, node paths, input devices, valid regions, invalid regions, state transitions, and validation refs. Deckbuilder route-map path selection and hand-card dragging cannot be accepted without an interaction-region artifact.

Before file-changing execution, a planned interaction artifact uses `validation_status=contract_validated`, `artifact_form=planned-godot-node-map`, an explicit coordinate-semantics field, and `runtime_validation_required=true`. This status validates the frozen design contract only; it must not claim runtime smoke success. Preview/package acceptance must replace planning evidence with Godot readback, interaction smoke, collision/Control-rect evidence, or another accepted runtime artifact form.

## Resource Lifecycle Gate

Changed routes that create processes, temp directories, file handles, filesystem watchers, SQLite handles, preview/package helpers, or Godot runtime nodes must include lifecycle tests or documented non-applicability. Cleanup failures write diagnostics and are never hidden behind a green route status. Cleanup must not delete user workspaces silently and must never delete preserved diagnostic spool records.

## Failure Family Taxonomy And Symptom Remediation

Every known failure family has an owner route, user-safe summary policy, admin evidence policy, and recovery action. New failure families must update `GodotDiagnosticsQualityGate.FailureFamilies`, this table, and tests in the same implementation slice.

| Symptom | Likely failure family | Owner route | User-safe summary policy | Admin evidence policy | Recovery action |
| --- | --- | --- | --- | --- | --- |
| GDD route state or draft artifact is missing | `gdd_missing` | `gdd-requirements` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Return to GDD creation or draft-completion flow and block downstream route generation. |
| GDD question-form source is missing for a legacy GDD-only project | `gdd_form_missing` | `gdd-question-form` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Offer non-destructive GDD form import/backfill or new GDD question-form confirmation before scene route confirmation. |
| Project structured game-type metadata is missing | `game_type_structured_missing` | `structured-game-type-analysis` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Block scene route or requirement map generation until project metadata is analyzed or repaired. |
| Project structured game-type metadata changed after scene confirmation | `game_type_structured_stale` | `structured-game-type-analysis` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Mark scene route stale and require reconfirmation or contract snapshot refresh before requirement mapping. |
| GDD run completes but no scene confirmation appears | `scene_route_missing` | `scene-route-confirmation` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Regenerate scene route or mark route state invalid with evidence. |
| Workflow recommends scene confirmation but the user cannot confirm it | `scene_route_unconfirmed` | `scene-route-confirmation` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Block requirement map generation until confirmation mapping exists or route state is repaired. |
| GDD document generation cannot write its hash back to scene route state | `gdd_scene_hash_write_failed` | `gdd-document-generation` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Preserve GDD generation evidence, block requirement map generation, and repair scene-route sidecar write path. |
| Generated GDD no longer matches confirmed scene route state | `generated_gdd_hash_mismatch` | `gdd-document-generation` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Reconfirm scene route or create a requirement-map mismatch blocker before downstream generation. |
| Requirement map is empty or too small | `requirement_map_invalid` | `gdd-requirements` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Regenerate requirement map; block contract freeze if P0/P1 gaps remain. |
| Iteration plan ignores required modules | `coverage_gap` | `iteration-plan` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Block plan or create follow-up required module goals. |
| Execute-next-goal starts from stale source | `contract_stale` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Reject before Codex invocation and recommend refresh/freeze. |
| Route cannot prove which frozen source produced an artifact | `source_unknown` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Reject downstream execution and regenerate from declared authority sources. |
| UI-facing requirement lacks a frozen UI capability contract | `ui_contract_unknown` | `ui-wiring-closure` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Refresh requirement map/contract after the UI capability contract is available. |
| Prototype skeleton starts without a fresh frozen contract | `prototype_skeleton_stale` | `prototype-skeleton` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Reject new-chain skeleton creation and require contract refresh/freeze. |
| Workflow recommendation emits an unmapped action | `workflow_recommendation_unmapped` | `workflow-recommendation` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Block primary action display and repair descriptor or recommendation mapping. |
| UI closure says success but player cannot use feature | `missing_ui_surface` | `ui-wiring-closure` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Create UI follow-up goal and block final readiness. |
| Required local Godot reference example is missing | `reference_example_missing` | `repair` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Add or refresh the curated reference index, approve substitute repo-owned evidence, or block the touched semantic family. |
| Example copy is requested but the example directory has no usable manifest | `reference_example_manifest_missing` | `repair` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Add a manifest, approve substitute copy evidence, or block copying while allowing read-only API-pattern reference use. |
| Required Godot feature-family recipe or durable standard row is missing | `godot_recipe_missing` | `repair` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Add or refresh the recipe/standard index, approve substitute evidence, or block implementation for the touched feature family. |
| A touched P0/P1 feature family has no recorded reading evidence | `feature_family_reading_missing` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Record feature-family reading evidence or return to the appropriate planning/repair step. |
| Geometry or fixed-format UI work has no measured size source | `geometry_size_source_missing` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Block implementation or repair route state until size source and coordinate space are recorded. |
| Material, shader, texture, or pure-color visual work lacks a repo-approved Godot profile | `material_profile_missing` | `ui-wiring-closure` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Select or extend a repo-approved material profile with evidence. |
| Lighting, fog, sky, environment, or postprocess work lacks a repo-approved rendering profile | `rendering_profile_missing` | `ui-wiring-closure` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Select or extend a rendering profile and record readability evidence. |
| Character animation or state-machine work lacks a declared animation profile | `animation_state_profile_missing` | `ui-wiring-closure` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Select or extend an animation profile or block character animation readiness. |
| Dynamic UI updates do not declare construction owner, update ownership, state owner, signal ownership, stable identity, or cleanup path | `ui_update_ownership_missing` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Block execution or create a follow-up repair goal. |
| Third-person camera work does not use or create the repo-owned camera rig/profile with movement and camera-state ownership | `third_person_camera_profile_missing` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Create or repair the shared camera rig/profile before execution. |
| An interaction-heavy P0/P1 goal has no interaction-region artifact or reviewed exemption | `interaction_region_missing` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Record the interaction-region artifact or return to iteration planning. |
| The current hash-bound iteration plan has not been confirmed | `plan_confirmation_required` | `execute-next-goal` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Confirm the current session and plan hash before execution. |
| Godot build or validation command fails | `godot_build_failed` | `preview-package` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Run repair with preserved diagnostics and block preview/package readiness. |
| Godot scene fails to load | `scene_load_failed` | `preview-package` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Run repair with latest Godot diagnostic evidence. |
| Preview opens blank or stale content | `preview_blank` | `preview-package` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Rebuild preview/package from current source hash set. |
| Package artifact is missing | `package_missing` | `preview-package` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Re-run package or surface artifact readback blocker. |
| Project deletion fails or leaves workspace | `workspace_delete_failed` | `project-delete` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Preserve diagnostic spool and surface admin cleanup action. |
| Active run is reused incorrectly | `duplicate_active_run` | `workflow-recommendation` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Reject stale reuse and start or resume only matching hash scope. |
| Diagnostic spool write or index update fails | `diagnostic_spool_write_failed` | `workflow-recommendation` | Redacted browser-safe summary only. | Metadata DB diagnostic index row plus preserved spool ref outside hosted workspaces. | Return a structured blocker and repair spool/index before readiness. |

## Review Requirements

The gate is accepted only when review records zero unresolved P0/P1/P2 findings for technology-stack leakage, missing Godot/Phase equivalents, untestable acceptance, diagnostics, preview validation, resource lifecycle, diagnostic spool, admin triage, redaction, and deleted-project retention behavior.
