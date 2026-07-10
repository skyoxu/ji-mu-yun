# Route Contracts And Deterministic Guards

Source: `../2026-07-07-phase-a-frontend-gdd-to-module-workflow-hardening.md` lines 751-890.

## 11.1 TapTap-Derived Hardening Patterns

This section records reusable engineering patterns observed in the TapTap project and adapts them to the Phase A frontend GDD-to-module workflow. These are not TypeScript or MCP migrations. They are boundary and governance patterns that should be implemented in Phase A's existing C# service, browser UI, route-state sidecars, and deterministic test style.

### 11.1.1 Conflict Assessment Against This Plan

Potential conflicts and decisions:

| Borrowed pattern | Potential conflict | Decision |
| --- | --- | --- |
| Feature-module style ownership | Phase A currently groups many route services under `Runs/`, `Readback/`, and `Browser/` rather than per-feature folders | Borrow the ownership contract, not the directory layout. Each route gets a route module contract section and tests, while code can remain in current C# ownership areas until a later refactor. |
| Unified definition plus handler | Phase A has ASP.NET handlers, services, route writers, browser callers, and artifact readback instead of MCP tools | Implement a route action descriptor/readback contract per route; do not introduce MCP abstractions. |
| CLI-first initialization | The GDD and scene confirmation flows are intentionally browser-visible | Keep user-facing GDD/scene/review flows in the browser; move deterministic admin, backfill, diagnostics, and guard checks to scripts/CLI where appropriate. |
| Release/workflow guard tests | Current plan is about prototype route governance, not npm release automation | Borrow the deterministic guard-test idea only: tests assert invariant text, artifact fields, route prompts, source boundaries, and API envelope behavior. |
| Path resolution policy | Phase A already has hosted workspace, artifact, package, and admin evidence boundaries | Create a Phase-specific path/readback policy instead of adopting TapTap's `WORKSPACE_ROOT + project_path` formula literally. |
| Runtime lifecycle logging | Phase A already has runtime recovery scripts and watchdogs | Add bounded expected-exit/orphan-process/log-retention guidance without changing runtime startup scripts in this plan. |
| Capability allowlist | Phase A browser routes already have account/auth gates, not MCP remote tool exposure | Borrow the explicit allowlist posture for user-visible workflow actions and admin operations; do not expose raw maintenance capabilities as ordinary project buttons. |
| Context separation | Phase A has account/project/run context mixed across services and readback | Add context-boundary tests and DTO rules rather than adopting TapTap's context types. |
| Progress notifications | Phase A has run state and browser polling instead of MCP progress tokens | Borrow the requirement that long operations expose progress/status through the existing run/readback model. |
| Release guard recovery | Phase A does not use TapTap's npm release flow | Borrow retry/idempotency and deterministic guard principles for workflow operations, not release-specific GitHub mechanics. |

Acceptance criteria:

- No new section requires moving Phase A code into a TapTap-style TypeScript directory layout.
- Existing Phase service standards remain the higher authority for API naming, sidecar naming, status enums, auth, evidence, and readback security.
- Any future implementation that adopts a borrowed pattern must include route-specific tests or a documented reason why the pattern is not applicable to that route.
- Borrowed patterns that touch user-visible actions, admin operations, credentials, paths, process lifecycle, or source authority must be reviewed under the P0/P1/P2 acceptance severity standard.

### 11.1.2 Route Module Contract Template

Borrowed capability: TapTap keeps each feature's definition, handler, resources, docs, and tests under an explicit feature contract. Phase A should define an equivalent contract per browser-consumed prototype route.

Target Phase A route module contract:

1. Route purpose and owner.
2. Required source artifacts.
3. Artifact-local sidecar schema.
4. API/readback DTO projection.
5. Browser action and disabled-state behavior.
6. Service entrypoint and route-state writer.
7. Prompt source boundary, if the route invokes Codex/LLM.
8. Admin/readback visibility.
9. Deterministic tests and smoke evidence.
10. Migration behavior for old projects.
11. Canonical route-state path and any mirror/cache path ownership.
12. Admin review queue behavior for system-detected P0/P1 blockers, generated exemptions, and conflict decisions.
13. Hosted-route recovery source order inheritance from `AGENTS.md`, including fail-closed behavior when a required recovery source is missing.
14. Whether the route is allowed to appear as `recommended_action`, `allowed_actions`, or `forbidden_actions` in the current phase.

Routes that should receive this contract first:

- `gdd-requirements`
- `gdd-document-generation`
- `scene-route-confirmation`
- `structured-game-type-analysis`
- `prototype-contract`
- `prototype-skeleton-guard` (canonical route module ID; `prototype-skeleton` and concrete prototype endpoints are route/endpoint aliases)
- `workflow-recommendation`
- `ui-wiring-closure`
- `iteration-plan`
- `execute-next-goal`
- `needs-fix`
- `repair`
- `project-delete`

Acceptance criteria:

- Each new or changed route has a documented route module contract before implementation is marked complete.
- The route module contract names the route's artifact paths, API DTO fields, browser entrypoints, source hashes, stale behavior, and tests.
- A route cannot be marked complete if its service, browser caller, readback, sidecar schema, and tests disagree on action names, status values, error envelope shape, or source hash fields.
- Prompt-producing routes must include the common `source_boundary_enforced` and `source_boundary` schema from `02a-route-state-artifacts.md`; non-prompt routes must record a not-applicable reason.
- Prompt-producing route contracts must merge route-local authority sources with `hosted-route-recovery-order.v1`; a contract that lists only route-local sources is incomplete and cannot be implemented.
- A route cannot appear in workflow recommendation readback until its contract declares descriptor mapping, exposure class, disabled-state behavior, account boundary, and phase eligibility.
- Route contracts that touch the prototype contract must name `routes/prototype-contract/latest.json` as canonical and treat `meta/routes/prototype-contract/latest.json` only as a readback/cache mirror.

### 11.1.3 Unified Route Action Descriptor

Borrowed capability: TapTap pairs tool definition and handler in one registration object to prevent schema/handler drift. Phase A should use a C#-appropriate version.

Recommended shape:

- Define a route action descriptor per action that names:
  - `actionId`
  - optional `legacyAliasIds` or `endpointAliasIds`
  - optional `subOperations`, where each row declares `subOperationId`, `selectionAuthority`, `eligibilityStates`, `requiredRecoveryInputs`, `fileChanging`, `apiRoute`, and endpoint aliases
  - API route
  - required source artifacts
  - operation status set
  - route/readback status set and frontend stage-status mapping
  - allowed HTTP status/error envelope mappings
  - browser label and disabled-state reason
  - service handler
  - readback sidecar path
  - exposure class: `user_visible|admin_visible|script_only|internal`
  - non-action display mapping when a recommendation is not a direct POST action

This can be implemented as C# records, constants, or test fixtures. The important requirement is single-source verification, not a specific implementation class.

Canonical registry:

- Phase 0A must create a single route action descriptor registry before any route emits `recommended_action`.
- Default implementation location: create the `PhaseA.Platform/Workflow/` workflow-governance namespace and `PhaseA.Platform.Tests/Fixtures/` fixture directory if they do not already exist, then add `PhaseA.Platform/Workflow/RouteActionDescriptors.cs` for runtime/service use, with a test fixture or generated JSON snapshot at `PhaseA.Platform.Tests/Fixtures/route-action-descriptors.v1.json`.
- `recommended_action` values are canonical action IDs from this registry. Existing endpoint-specific names, legacy route names, or service method names may appear only as descriptor aliases/projections and must not be emitted as canonical recommendations.
- Browser code must consume an API/readback projection from the same registry or a generated artifact derived from it; it must not maintain an independent hardcoded action catalog.
- Phase 0A must choose one browser-consumed descriptor projection path before implementation starts: either a project workflow API/readback projection generated from `RouteActionDescriptors.cs`, or a generated JSON artifact checked by fixture parity tests. Browser code may import only that projection and cannot define action IDs independently.
- Route-state artifacts that include `action_descriptor_ref` must store `descriptor_id`, `descriptor_version`, and `descriptor_hash` from this registry snapshot.
- Any later move to a different canonical path requires a decision log and a guard test update in the same change.

Acceptance criteria:

- `recommended_action`, browser button action, API action, and service handler names are checked by deterministic tests.
- The same action cannot have different names in browser JavaScript, API DTOs, route-state JSON, and service tests.
- If existing endpoints require different method names, the descriptor must record them as aliases/projections and tests must prove the canonical action ID maps to exactly the intended browser/API operation.
- Adding a new action requires updating the descriptor and a guard test that fails if the browser or readback omits it.
- `complete_gdd` is explicitly mapped to the GDD draft-completion browser flow or a non-action display mapping before `ProjectWorkflowRouteService` may emit it.
- `create_gdd` is explicitly mapped to the GDD question-form/start browser flow or a concrete API descriptor before `ProjectWorkflowRouteService` may emit it.
- `import_gdd_form` is explicitly mapped to the legacy GDD form import/backfill or confirmation browser flow before `ProjectWorkflowRouteService` may emit it.
- `analyze_game_type` is explicitly mapped to the structured game-type metadata analysis/backfill API or browser/admin-safe flow before `ProjectWorkflowRouteService` may emit it.
- `confirm_scene_route` is explicitly mapped to the scene-route confirmation browser flow or a concrete confirmation API before `ProjectWorkflowRouteService` may emit it.
- `generate_gdd_document` is explicitly mapped to the GDD document-generation API or browser flow before `ProjectWorkflowRouteService` may emit it.
- `delete_project` is explicitly mapped to the ordinary project-delete API/browser action before `ProjectWorkflowRouteService` may expose it as a secondary allowed/forbidden action; the service may not emit it as the primary recommendation.
- `run_needs_fix` is the canonical workflow action for the needs-fix/repair route family. `schemas/workflow-action-contracts.v1.json` is the machine authority for its exact `subOperations` rows: `needs_fix_plan` and file-changing `repair`, server-only `selectionAuthority`, exact eligibility-state enums, exact ordered `requiredRecoveryInputs`, API route, aliases, acceptance refs, and tests. `repair` is not emitted as a second canonical workflow recommendation ID.
- `delete_project` is classified as a stage-independent destructive secondary action, never the stage-driven primary recommendation. The descriptor defines account-scoped `allowedActions[]`; deletion `forbiddenActions[]` may use only `route_contract_not_active`, `account_forbidden`, or `diagnostic_blocked`, never `phase_gate_blocked`.
- The phase-gated downstream subset `generate_requirement_map`, `freeze_contract`, `refresh_contract`, `create_prototype`, `create_iteration_plan`, `execute_next_goal`, `run_needs_fix`, `run_ui_closure`, `preview_package`, and `inspect_first` is explicitly mapped to route descriptors, browser actions, or non-action display mappings before they may appear in workflow recommendation readback. If their route contract is not active in the current phase, they must appear only as disabled/forbidden actions with browser-safe reasons.
- Guard tests compute `descriptor_hash` from the canonical registry snapshot and fail when `action_descriptor_ref` in workflow recommendation readback differs from the browser/API action catalog.

### 11.1.4 Deterministic Guard Tests For Workflow Invariants

Borrowed capability: TapTap uses tests to assert release and workflow guard behavior instead of relying on reviewers to remember rules.

Phase A should add deterministic guard tests for these invariants:

- Source-boundary prompts after contract freeze do not include raw `docs/game-type-guides` excerpts.
- Prompt-producing route states include `source_boundary_enforced=true` and the common source-boundary object; saved prompt evidence must match the declared authority sources.
- New sidecars use snake_case and API/readback projections use camelCase.
- Prototype contract authority uses `routes/prototype-contract/latest.json`; any `meta/routes/prototype-contract/latest.json` mirror must match `contract_hash`.
- `operationStatus` values remain `returned_existing|active_run_reused|created_run|rejected`.
- `operationStatus=rejected` returns the standard error envelope.
- Route-state sidecars include `status`, `status_reason`, `updated_utc`, and `evidence_refs` when applicable.
- Status vocabulary remains separated across stage timeline, route/readback state, UI surface matrix, and readiness labels.
- `evidence_refs.kind` stays within the Phase standard closed enum.
- `recommended_action` includes every action used by browser primary/secondary controls.
- The complete canonical workflow action set from `02a-route-state-artifacts.md` maps to explicit descriptors or browser-flow mappings; none may be emitted as an unmapped recommendation string.
- Phase eligibility tests fail when a downstream action is recommended before its route contract, descriptor, account boundary, and disabled-state behavior are active for the current phase.
- `no_ui_needed` and `style_not_applicable` keep their separate exemption scopes and cannot be substituted for each other.
- Preview/package compatibility cannot be treated as final package readiness while blockers remain unresolved.
- `contract_hash` excludes volatile fields and source hashes use the canonicalization rules defined in this plan.
- Admin-only conflict/defer decisions cannot be made by normal user routes.
- Admin review queue entries are account-safe, admin-only for raw readback, and auditable for mutations.
- Cross-account/existence-hiding responses do not expose fine-grained domain codes.

Acceptance criteria:

- Guard tests fail on string, enum, prompt-source, or route-state drift before manual review is required.
- Guard tests read saved prompts/evidence artifacts for source-boundary checks, not only summary route-state fields.
- Guard tests are deterministic and do not call external LLM, Steam, GitHub, or public network services.
- Each guard test names the invariant it protects and the route(s) it covers.

### 11.1.5 CLI/Script-First Admin And Backfill Operations

Borrowed capability: TapTap Maker keeps one-time initialization, environment checks, project binding, and repair-like operations in CLI workflows instead of spreading them across user-facing MCP/browser actions.

Phase A should keep browser flows for user decisions, but use deterministic scripts/CLI for:

- project game-type match backfill
- contract snapshot refresh inspection
- requirement map regeneration diagnostics
- stale artifact inspection
- route-state consistency audits
- prompt source-boundary audits
- admin review queue export
- admin review queue consistency and decision-audit inspection
- readback path/security smoke
- runtime/orphan-process diagnostics

Acceptance criteria:

- Browser UI does not expose raw maintenance actions that can mutate many projects without explicit admin intent.
- Each admin/backfill script writes evidence under `logs/` and includes `timestamp_utc`, operation label, scoped IDs, and sanitized paths.
- Scripts are idempotent by default or explicitly document when they create new runs/states.
- Scripts do not manually mutate the live metadata DB unless the user explicitly authorizes that operation and a decision log records the reason.
- Admin queue scripts never bypass admin API/account-boundary rules when an API exists; offline inspection scripts are read-only unless an explicit approved repair path records sidecar evidence.
