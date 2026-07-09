# Godot Diagnostics And Quality Gate Migration

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 2237-2412.

## 11.4 Godot Diagnostics And Quality Gate Migration

This section migrates TapTap's development quality-gate and troubleshooting discipline into a Godot/Phase service model. It is not a local tooling migration. The source capability idea is: diagnostics must run before build/preview/package, recurring symptoms should map to remediation, debug logs are useful during development but must become structured evidence before acceptance, interaction regions should be designed before implementation, preview is an immediate validation loop, and disposable/runtime resources must be released explicitly.

### 11.4.1 Conflict Assessment

| TapTap quality-gate capability | Conflict in this repo | Godot/Phase decision |
| --- | --- | --- |
| LSP diagnostics before build | Phase routes run through hosted workspaces, C#/.NET, Godot, Python scripts, and browser/API readback rather than a single local IDE | Translate this into pre-build/pre-preview diagnostics using `dotnet build`/tests, Godot self-check, GdUnit4, route-state validators, and saved evidence. No route can rely only on assistant prose. |
| Symptom-to-solution table in `AGENTS.md` | This repo keeps `AGENTS.md` as a routing layer and avoids large embedded rule catalogs | Create a durable diagnostics guide and admin triage taxonomy outside `AGENTS.md`, then link it from standards or workflow indexes. |
| Development-stage print-heavy logging | Phase service logs and browser readback can leak host paths, prompts, and secrets | Allow temporary diagnostics only when they are migrated to sanitized route evidence or removed before acceptance. Raw logs are admin-only or hidden unless redaction rules explicitly allow readback. |
| ASCII collision-region sketch before implementation | Godot prototypes need UI hit zones, CanvasLayer/world boundaries, collision shapes, and raycast areas, not only TapTap collision sketches | Require a lightweight interaction-region artifact for UI/physics/input-heavy goals: ASCII sketch, hit-zone table, node/collision map, or scene sketch. |
| Preview button immediate validation | Phase preview/package is browser/API hosted, ticketed, and source-hash-sensitive | Treat preview as an immediate validation route whose readiness is tied to current source hashes and diagnostic evidence. Preview failures must be actionable, not generic 500s. |
| Immediate `Dispose()` of Object subclasses | Godot nodes and C# resources have different lifecycle ownership | Translate this into explicit lifecycle checks: Godot `QueueFree`/scene ownership, C# `IDisposable`, process/file/SQLite watcher disposal, and orphan-process diagnostics. |

Acceptance criteria:

- No implementation prompt, route state, diagnostics guide, or durable workflow standard requires TapTap local runtime concepts, TapTap-specific LSP APIs, or TapTap disposal rules.
- Every migrated quality-gate capability has a Godot/Phase-owned equivalent, an evidence artifact, and a validation route or test.
- `AGENTS.md` remains a router; durable diagnostics tables live in standards/workflow docs and are linked from the appropriate index.
- Review records zero unresolved P0/P1/P2 findings for technology-stack leakage, missing Godot/Phase equivalent, or untestable acceptance.
- The quality-gate migration cannot pass unless review records zero unresolved P0/P1/P2 findings in diagnostics, preview validation, resource lifecycle, diagnostic spool, admin triage, redaction, or deleted-project retention behavior.

### 11.4.2 Full Quality Gate Migration Checklist

The workflow must treat the following capabilities as first-class diagnostics and quality gates for GDD-to-module execution:

Stable capability package IDs contributed by this document:

| Capability ID | Owner scope |
| --- | --- |
| `godot_diagnostic_spool_contract` | Project diagnostic spool schema, metadata DB index ownership, deleted-project lookup, redaction, retention, and reconciliation. |
| `godot_failure_family_taxonomy` | Bounded failure-family set, domain codes, symptom-to-remediation rows, and route diagnostic consistency. |
| `godot_prebuild_preview_quality_gate` | Pre-build/pre-preview diagnostics, package readiness, preview validation, and blocker propagation. |
| `godot_interaction_region_gate` | Interaction-region artifacts for UI/input/physics/camera-heavy P0/P1 requirements. |
| `godot_resource_lifecycle_gate` | Debug-log lifecycle, explicit cleanup evidence, orphan process/resource diagnostics, and replacement evidence after compaction. |

1. Pre-build diagnostics gate
   - Godot/Phase ownership: `dotnet build`, .NET tests, analyzer/nullable diagnostics where enabled, Godot self-check, GdUnit4, scene load checks, route-state validators, and source-hash validation.
   - Required workflow data: diagnostic command, route, project/account scope, source hash set, status, evidence refs, failure family, and remediation hint.
2. Symptom-to-remediation table
   - Godot/Phase ownership: durable diagnostics guide outside `AGENTS.md`, with entries for GDD/scene/requirement/contract/iteration/execute/repair/UI/preview/package/project-delete failures.
   - Required workflow data: symptom, likely causes, owner route, safe first checks, admin-only checks, evidence paths, and recovery action.
3. Debug log lifecycle
   - Godot/Phase ownership: temporary `GD.Print`, `Console.WriteLine`, stdout/stderr, and route debug traces are allowed during development but must be removed, reduced, or converted to sanitized evidence before acceptance.
   - Required workflow data: raw path policy, redaction status, retention class, cleanup status, and replacement evidence refs.
4. Interaction-region design artifact
   - Godot/Phase ownership: ASCII diagram, hit-zone table, collision-shape map, CanvasLayer/world-boundary sketch, raycast/camera transform note, or scene sketch for UI/physics/input-heavy work.
   - Required workflow data: affected requirement IDs, scene/node paths, input devices, hit zones, invalid zones, collision shapes or Control rects, and validation refs.
5. Preview validation loop
   - Godot/Phase ownership: preview route, package route, web preview smoke, Godot smoke, screenshot/canvas-pixel/exported evidence, ticket/readback rules, and source-hash readiness.
   - Required workflow data: preview source hash set, preview readiness status, artifact refs, failure family, browser-safe diagnostic summary, and retry guidance.
6. Explicit resource lifecycle
   - Godot/Phase ownership: C# `IDisposable` resources, SQLite connections, file streams, process handles, watchers, temporary directories, Godot node ownership/`QueueFree`, preview/package helper cleanup, and orphan-process diagnostics.
   - Required workflow data: owned resource list, cleanup strategy, expected exit behavior, orphan detection, evidence refs, and failure handling.
7. Project diagnostic spool and admin triage
   - Godot/Phase ownership: project-scoped diagnostic sidecars outside the deletable workspace, admin triage queue, failure-family taxonomy, redacted summaries, and deletion-safe retention.
   - Required workflow data: account ID, project ID, project name, run ID, route, failure family, severity, source refs, redaction status, triage status, created UTC, and preserved evidence refs.
8. Route failure taxonomy
   - Godot/Phase ownership: bounded failure families such as `gdd_missing`, `gdd_form_missing`, `game_type_structured_missing`, `game_type_structured_stale`, `scene_route_missing`, `scene_route_unconfirmed`, `gdd_scene_hash_write_failed`, `generated_gdd_hash_mismatch`, `requirement_map_invalid`, `coverage_gap`, `contract_stale`, `source_unknown`, `ui_contract_unknown`, `prototype_skeleton_stale`, `workflow_recommendation_unmapped`, `missing_ui_surface`, `reference_example_missing`, `godot_build_failed`, `scene_load_failed`, `preview_blank`, `package_missing`, `workspace_delete_failed`, `duplicate_active_run`, and `diagnostic_spool_write_failed`.
   - Required workflow data: failure family enum, route domain code, remediation table entry, admin visibility, user-safe summary, and test coverage.

Acceptance criteria:

- Each quality-gate capability above has a route contract field, diagnostics guide entry, validator, smoke, or explicit non-applicability record before the corresponding route phase is accepted.
- Any P0/P1 route that invokes build, Godot validation, preview, package, repair, or UI closure must pass the pre-build/pre-preview diagnostics gate or return a structured blocker before invoking downstream work.
- Temporary debug output cannot be the only acceptance evidence for a changed route; final acceptance must cite sanitized evidence refs or structured route state.
- Interaction-heavy P0/P1 goals cannot be marked complete unless the iteration goal or evidence includes an interaction-region artifact or an explicit `no_interaction_region_needed` rationale.
- Preview/package readiness cannot be marked `ready` or `succeeded` when source hashes, diagnostic evidence, package artifact, preview ticket, or browser-safe readback is stale, missing, or invalid.
- Project diagnostic spool records must survive workspace deletion and remain admin-triable without exposing raw host paths, token material, provider secrets, or raw prompts to normal users.
- The quality-gate checklist is considered complete only when review records zero unresolved P0/P1/P2 findings.
- The full-target closure ledger includes the stable capability IDs from this document and rejects missing or prose-derived diagnostic capability rows.
- Diagnostics for UI, custom drawing, camera, input, physics, TileMap/map, preview, and package routes must validate the applicable Godot semantic family from `04d-godot-engine-semantics-and-reference-examples.md`, including viewport/scale mode and curated reference-example evidence when used.

### 11.4.3 Project Diagnostic Spool

The project diagnostic spool is the Phase-specific extension of TapTap's symptom table and debug-log discipline. Because Phase projects live in hosted workspaces that may be deleted, critical diagnostics must be preserved outside the project workspace.

Recommended durable path:

```text
logs/phase-a-innernet/diagnostics/projects/<account_id>/<project_id>/
```

Runtime-state boundary:

- This path is runtime evidence under the `AGENTS.md` Phase service scope. Implementation must write it only through platform services, approved recovery/admin scripts, or smoke/drill scripts; manual mutation of live diagnostic history is not an accepted workflow.
- Default browser/admin query owner is a metadata DB diagnostic index table that stores account/project scope, route, failure family, severity, triage status, retention class, redaction status, and a pointer to the preserved spool file. The spool file remains the append-only evidence source.
- Minimum diagnostic index table contract: required stable key `diagnostic_id`; required columns `diagnostic_id`, `account_id`, `project_id`, `project_name_snapshot`, `run_id`, `route`, `failure_family`, `severity`, `triage_status`, `retention_class`, `redaction_status`, `spool_ref`, `user_safe_summary`, `source_refs_json`, `evidence_refs_json`, `created_utc`, `updated_utc`, `resolved_utc`, `triage_decision_by`, `triage_decision_reason`, `deletion_event_id`, and `project_tombstone_id`.
- Required diagnostic indexes: unresolved admin triage by `(triage_status, severity, updated_utc)`, project lookup by `(account_id, project_id, triage_status)`, deleted-project lookup by `(project_tombstone_id, deletion_event_id)`, route/family analytics by `(route, failure_family, created_utc)`, and retention cleanup by `(retention_class, triage_status, updated_utc)`.
- Triage mutation rule: updates are append-only or audit-backed. A triage update may add decision metadata and replacement evidence, but cannot rewrite `failure_family`, raw spool refs, original source refs, account/project identity, or deletion tombstone identity.
- Direct spool scanning is allowed only for recovery/rebuild tooling or smoke/drill validation, not as the normal browser/API query path, unless a later Phase ADR or decision log changes that owner.
- Recovery must be able to rebuild the metadata DB diagnostic index from preserved spool files without rewriting failure history or deleting replacement evidence.
- Deletion-safe diagnostics must not live only inside hosted project workspaces.

Recommended record schema:

```json
{
  "schema_version": "project-diagnostic-spool.v1",
  "account_id": "...",
  "project_id": "...",
  "project_name": "...",
  "deletion_event_id": "",
  "project_tombstone_id": "",
  "run_id": "...",
  "route": "structured-game-type-analysis|gdd-requirements|gdd-document-generation|scene-route-confirmation|prototype-contract|prototype-skeleton|workflow-recommendation|iteration-plan|execute-next-goal|needs-fix|repair|ui-wiring-closure|preview-package|project-delete",
  "failure_family": "gdd_missing|gdd_form_missing|game_type_structured_missing|game_type_structured_stale|scene_route_missing|scene_route_unconfirmed|gdd_scene_hash_write_failed|generated_gdd_hash_mismatch|requirement_map_invalid|coverage_gap|contract_stale|source_unknown|ui_contract_unknown|prototype_skeleton_stale|workflow_recommendation_unmapped|missing_ui_surface|godot_build_failed|scene_load_failed|preview_blank|package_missing|workspace_delete_failed|duplicate_active_run|diagnostic_spool_write_failed",
  "severity": "P0|P1|P2|info",
  "triage_status": "unresolved|resolved|ignored|backlog",
  "created_utc": "...",
  "source_refs": [],
  "evidence_refs": [],
  "redaction_status": "redacted|raw_admin_only|blocked",
  "retention_class": "unresolved_blocker|resolved_audit|ignored_audit|backlog_audit|info_ephemeral",
  "cleanup_status": "preserved|compacted|redacted_compacted|eligible_after_retention|not_eligible",
  "replacement_evidence_refs": [],
  "user_safe_summary": "",
  "admin_summary": "",
  "remediation_hint_id": ""
}
```

Retention and cleanup boundary:

- `unresolved_blocker` records for P0/P1/P2 diagnostics are preserved outside hosted workspaces and are not eligible for deletion or destructive compaction.
- `resolved_audit`, `ignored_audit`, and `backlog_audit` records may be compacted or redacted after the retention window defined by a durable standard, but the compacted record must retain account/project scope, route, failure family, severity, triage decision, timestamps, and replacement evidence refs.
- `info_ephemeral` records may be cleaned according to bounded log policy only when they are not referenced by an unresolved blocker, admin review queue entry, route-state blocker, package/readiness blocker, or decision log.
- Ordinary project deletion never deletes diagnostic spool records. It may add a `project-delete` diagnostic event and mark workspace-local evidence as unavailable while preserving diagnostic identity and admin triage.
- `project-delete` diagnostic events and preserved diagnostics from the same delete transaction share `deletion_event_id` and `project_tombstone_id` with admin review queue tombstones. Rebuild/reconciliation tests fail when diagnostic and admin-review tombstones for the same deleted project cannot be joined by these IDs.

Acceptance criteria:

- Diagnostic spool files are written outside the hosted workspace so project deletion removes workspace files without deleting preserved diagnostics.
- Diagnostic spool writes respect the protected-runtime-state rule: no implementation step edits or deletes live spool records by hand to make tests pass.
- The metadata DB diagnostic index has additive schema migration/reuse tests and a rebuild/reconciliation path from preserved spool files.
- The metadata DB diagnostic index is required before diagnostic spool blockers become browser/admin API query authority. Implementation cannot defer the index choice to route-specific code.
- Deleting a project preserves diagnostic spool records and records a `project-delete` diagnostic event with result code, account scope, and sanitized project identity.
- The spool schema example, failure-family taxonomy seed, and symptom-to-remediation table use the same initial `failure_family` values, or the standards file explicitly declares the schema field as open-ended and points to the taxonomy as authority.
- Tests must compare the bounded failure-family checklist, spool schema example, and symptom-to-remediation table and fail if any initial family is missing from one of the three places.
- The initial route seed covers every Phase 1 route/readback surface that can block GDD-to-module flow, including scene route confirmation, prototype-skeleton guard, and workflow recommendation. Adding a blocking route requires updating the diagnostic route seed, failure-family taxonomy, and tests in the same implementation slice.
- Admin readback can list unresolved diagnostics by account, project, route, failure family, severity, and age without reading raw logs.
- Normal-user readback cannot access another account's diagnostic spool and cannot see raw host paths, raw prompts, token material, provider secrets, or admin-only evidence.
- Phase review diagnostics record which local official Godot reference examples were read for touched semantic families, or record `reference_example_missing` with approved substitute evidence before implementation can claim readiness for that family.
- Triage status updates are admin-only, append-only or audit-backed, and cannot rewrite raw failure history.
- Retention/cleanup rules must preserve unresolved P0/P1/P2 diagnostics and must never delete diagnostics as a side effect of ordinary project deletion.
- Cleanup jobs may compact or redact resolved diagnostics only under a documented retention class, and must leave replacement evidence sufficient for admin triage, audit export, and repair-history explanation.
- Diagnostic spool blockers feed final package readiness; unresolved P0/P1/P2 diagnostics prevent final readiness even when ordinary package download remains available for compatibility.
- Tests cover spool write, deleted-project lookup, account isolation, admin aggregation, redaction, triage status update, and cleanup/retention non-destruction for unresolved P0/P1/P2 diagnostics.
- Project diagnostic spool review records zero unresolved P0/P1/P2 findings for schema drift, failure-family mismatch, redaction, account isolation, retention, cleanup, triage auditability, or deleted-project lookup.

### 11.4.4 Symptom-To-Remediation Table

The diagnostics guide should include an initial table for the GDD-to-module workflow. This table should be durable documentation, not hidden implementation knowledge.

Initial symptom families:

| Symptom | Likely failure family | First checks | Recovery action |
| --- | --- | --- | --- |
| GDD route state or draft artifact is missing | `gdd_missing` | GDD route state, draft artifact readback, account/project scope | Return to GDD creation or draft-completion flow and block downstream route generation. |
| GDD question-form source is missing for a legacy GDD-only project | `gdd_form_missing` | `docs/gdd/GDD.md`, missing `meta/routes/gdd-question-form/latest.json`, legacy import/backfill evidence | Offer non-destructive GDD form import/backfill or new GDD question-form confirmation before scene route confirmation. |
| Project structured game-type metadata is missing | `game_type_structured_missing` | Project metadata readback, Steam/game-type analysis evidence, selected game-type ID, selected guide ID | Block scene route or requirement map generation until project metadata is analyzed or repaired. |
| Project structured game-type metadata changed after scene confirmation | `game_type_structured_stale` | Current structured metadata hash, scene-route `source_game_type_structured_hash`, contract snapshot mirror | Mark scene route stale and require reconfirmation or contract snapshot refresh before requirement mapping. |
| GDD run completes but no scene confirmation appears | `scene_route_missing` | GDD run state, scene-route sidecar, workflow recommendation | Regenerate scene route or mark route state invalid with evidence. |
| Workflow recommends scene confirmation but the user cannot confirm it | `scene_route_unconfirmed` | Scene-route confirmation descriptor, browser flow/API mapping, account scope | Block requirement map generation until confirmation mapping exists or route state is repaired. |
| GDD document generation cannot write its hash back to scene route state | `gdd_scene_hash_write_failed` | GDD document route state, scene-route sidecar write result, account/project scope, filesystem/write-lock evidence | Preserve GDD generation evidence, block requirement map generation, and repair scene-route sidecar write path. |
| Generated GDD no longer matches confirmed scene route state | `generated_gdd_hash_mismatch` | `docs/gdd/GDD.md` hash, scene-route `source_generated_gdd_hash`, reconfirmation or mismatch blocker | Reconfirm scene route or create a requirement-map mismatch blocker before downstream generation. |
| Requirement map is empty or too small | `requirement_map_invalid` | GDD hash, scene route hash, contract snapshot, LLM JSON validity | Regenerate requirement map; block contract freeze if P0/P1 gaps remain. |
| Iteration plan ignores required modules | `coverage_gap` | Requirement IDs, default contract modules, admin conflict decisions | Block plan or create follow-up required module goals. |
| Execute-next-goal starts from stale source | `contract_stale` | Source hash set, current frozen contract, requirement map | Reject before Codex invocation and recommend refresh/freeze. |
| Route cannot prove which frozen source produced an artifact | `source_unknown` | Source-boundary evidence, source hash fields, route action descriptor, prompt evidence refs | Reject downstream execution and regenerate from declared authority sources. |
| UI-facing requirement lacks a frozen UI capability contract | `ui_contract_unknown` | Godot UI contract version/hash, prototype contract, requirement map UI domains | Refresh requirement map/contract after the UI capability contract is available. |
| Prototype skeleton starts without a fresh frozen contract | `prototype_skeleton_stale` | Prototype-skeleton guard state, contract hash, requirement map hash, legacy compatibility label | Reject new-chain skeleton creation and require contract refresh/freeze. |
| Workflow recommendation emits an unmapped action | `workflow_recommendation_unmapped` | Route action descriptor hash, browser/API projection, recommendation readback | Block primary action display and repair descriptor or recommendation mapping. |
| UI closure says success but player cannot use feature | `missing_ui_surface` | UI surface matrix, interaction-region artifact, screenshot/canvas evidence | Create UI follow-up goal and block final readiness. |
| Required local Godot reference example is missing | `reference_example_missing` | `docs/reference/godot-official-examples-index.md`, affected semantic family, attempted local example path, substitute repo-owned example/test evidence | Add or refresh the curated reference index, approve substitute repo-owned evidence, or block the touched semantic family before implementation proceeds. |
| Godot build or validation command fails | `godot_build_failed` | `dotnet build`, Godot self-check, GdUnit, import diagnostics, route source hash set | Run repair with preserved diagnostics and block preview/package readiness. |
| Preview opens blank or stale content | `preview_blank` | Preview source hash, package artifact, web preview smoke, browser console evidence | Rebuild preview/package from current source hash set. |
| Package artifact missing | `package_missing` | Package run evidence, artifact index, ticket creation, workspace path policy | Re-run package or surface artifact readback blocker. |
| Godot scene fails to load | `scene_load_failed` | Godot self-check, GdUnit, scene path, import diagnostics | Run repair with latest Godot diagnostic evidence. |
| Project deletion fails or leaves workspace | `workspace_delete_failed` | project diagnostic spool, delete diagnostic jsonl as legacy/runtime evidence only, workspace path, account/project scope | Preserve diagnostic spool, surface admin cleanup action. |
| Active run is reused incorrectly | `duplicate_active_run` | operation scope, source hash scope, account-project scope marker | Reject stale reuse and start or resume only matching hash scope. |
| Diagnostic spool write or index update fails | `diagnostic_spool_write_failed` | Spool path, metadata DB diagnostic index transaction, redaction status, protected runtime-state permissions | Return structured blocker, preserve route failure evidence elsewhere under `logs/`, and repair spool/index before readiness. |

Acceptance criteria:

- The diagnostics guide includes at least the symptom families above before Phase 6 is accepted.
- Every table row links to a route, failure family enum, safe user summary policy, admin evidence policy, and recovery action.
- New failure families added by implementation must update the table and tests in the same implementation slice.
- A route cannot expose only `unhandled_request_failed` for a known table symptom; it must return a structured domain code and evidence reference.
- The table is linked from `docs/standards/_index.md`, `docs/standards/phase-service.md`, or a route workflow doc before implementation is called complete.

### 11.4.5 Interaction-Region Design Gate

P0/P1 UI, input, physics, route-map, card-dragging, collision, or camera-transform work should include an interaction-region artifact before implementation.

Accepted artifact forms:

- ASCII diagram.
- Hit-zone table.
- Godot scene/node map with `Control` rects or collision shapes.
- CanvasLayer/world boundary sketch.
- Raycast/camera transform note.
- Screenshot annotated by coordinates or named regions.

Acceptance criteria:

- The artifact records affected requirement IDs, scene IDs, node paths, input devices, valid regions, invalid regions, state transitions, and validation refs.
- Deckbuilder route-map path selection and hand-card dragging cannot be accepted without an interaction-region artifact.
- If a goal declares `no_interaction_region_needed`, the route state must include a rationale and tests must prove the requirement has no UI/input/physics/camera interaction.
- The interaction-region artifact is included in prompt/evidence source refs for UI-touching execution and repair routes.
- Review records zero unresolved P0/P1/P2 findings for missing or stale interaction-region artifacts.

### 11.4.6 Resource Lifecycle And Orphan Diagnostics Gate

Resource lifecycle checks should prevent preview/package/repair helpers from leaking processes, handles, or temporary files.

Godot/Phase lifecycle rules:

- C# `IDisposable` resources are disposed through `using`, `await using`, or explicit cleanup in long-lived services.
- SQLite connections, file streams, process handles, filesystem watchers, and temporary workspace handles have deterministic cleanup paths.
- Godot nodes created dynamically have scene-tree ownership or `QueueFree`/`Free` cleanup rules appropriate to Godot object lifetime.
- Preview/package/helper processes record expected exit, timeout, cancellation, and orphan-detection evidence.
- Cleanup never deletes user workspaces silently and never deletes preserved diagnostic spool records.

Acceptance criteria:

- Changed routes that create processes, temp directories, file handles, or Godot runtime nodes include lifecycle tests or documented non-applicability.
- Orphan-process diagnostics run before a route claims preview/package/repair success when helper processes were involved.
- `workspace_delete_failed` and helper cleanup failures write project diagnostic spool records with redacted evidence.
- Resource cleanup failures are never hidden behind a green route status.
- Review records zero unresolved P0/P1/P2 findings for lifecycle leaks, unbounded temp files, or missing orphan diagnostics.
- The resource lifecycle gate cannot pass unless review records zero unresolved P0/P1/P2 findings for leaked processes, undisposed C# resources, unbounded temporary files, unsafe workspace cleanup, or deleted diagnostic spool records.
