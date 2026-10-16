# Hosted Workspaces And Artifacts Architecture

## Intent

Hosted workspaces give browser/API users isolated project copies that can run repository-native Godot prototype workflows without exposing arbitrary host filesystem access or user-provided Git remotes.

Artifacts and readback make workflow outputs inspectable without requiring users or agents to know local filesystem paths.

## Boundary

In scope:

- Workspace layout under `logs/phase-a-innernet/workspaces/**`.
- Project seeding, project initialization recovery, and workspace maintenance.
- Artifact indexing and readback for runs, packages, GDDs, assets, previews, project health, prototype evidence, and logs.
- Package download tickets and asset preview tickets that resolve ownership before file reads.

Out of scope:

- Treating workspace sidecars as a replacement for Godot scene/source files.
- Browser write access to arbitrary scene geometry, collision, spawn, region, or tilemap data without a Godot-native or repository-validated write path.
- Object storage or remote worker storage before Phase C storage abstraction.

## Key Decisions

- The platform controls workspace roots and project seeding instead of accepting browser-provided repository URLs.
- New workspaces receive project-facing `AGENTS.md` and `README.md` from the dedicated templates under `PhaseA.Platform/Workspaces/HostedProjectTemplate/`; the Seeder does not use the platform-root entry documents when both templates are available.
- Existing project entry documents are project-instance data and are preserved. Template source files are not recursively copied into the Hosted workspace.
- Browser/API readback uses logical artifact IDs, tickets, or workspace-relative sanitized paths instead of raw absolute paths.
- Sidecars are for planning, readback, audit, validation, and route recovery. They must not replace engine-owned project files.
- Package and preview services are readback/product surfaces but must still validate account/project ownership.

## Invariants

- All paths must stay within the workspace root after normalization.
- A copied project entry document does not inherit platform repository authority. It can narrow project behavior but cannot expand server route, Skill, account, sandbox, network, tool, or knowledge-policy ceilings.
- Repository-template, project-instance, and run-artifact-view snapshots remain distinct as required by ADR-0044. Project entry documents do not replace route state, acceptance evidence, or a signed run context.
- The repository Locator is not currently a Phase browser-route capability. Hosted child Skills cannot establish trusted repository context by invoking the CLI directly; a future Phase adapter must be server-owned and separately validated.
- Readback must be account-scoped unless the route is explicitly admin-only.
- Generated evidence and artifacts must be additive; do not rewrite history to hide failures.
- Package and preview files must be resolved through ticket/ownership checks before download or display.

## Change Rules

- New artifact types must define producer, owner, storage path, readback scope, and sanitization behavior.
- New browser/API readback must avoid raw host paths and secrets.
- New package or asset features must update readback tests and account-boundary tests.
- Workspace layout changes require recovery and restore notes.
- Seeder entry-template changes require temporary-root coverage for fresh workspaces and preservation coverage for existing project-owned files. Existing live workspaces are never rewritten by documentation maintenance.

## Related Code

- `PhaseA.Platform/Workspaces/WorkspaceLayoutBuilder.cs`
- `PhaseA.Platform/Workspaces/WorkspacePathPolicy.cs`
- `PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs`
- `PhaseA.Platform/Workspaces/HostedProjectTemplate/AGENTS.template.md`
- `PhaseA.Platform/Workspaces/HostedProjectTemplate/README.template.md`
- `PhaseA.Platform/Projects/ProjectCreationService.cs`
- `PhaseA.Platform/Projects/ProjectInitializationRecoveryService.cs`
- `PhaseA.Platform/Readback/ArtifactReadbackService.cs`
- `PhaseA.Platform/Readback/ProjectPackageService.cs`
- `PhaseA.Platform/Readback/ProjectWebPreviewService.cs`
- `PhaseA.Platform/Readback/ProjectAssetLibraryService.cs`
- `PhaseA.Platform/Readback/ProjectAssetInventoryService.cs`

## Related Tests

- `PhaseA.Platform.Tests/Workspaces/**`
- `PhaseA.Platform.Tests/Readback/**`
- `PhaseA.Platform.Tests/Projects/**`

## Related Decisions

- `docs/adr/ADR-0035-phase-controlled-runner-workspace-execution.md`
- `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`

## Package version recovery (2026-10-04)

The protected Runner registration owns a stable physical storage root. A package
restore creates an active generation under `.restore-generations/<attempt-id>/`.
`workspaces.root_path/repo_path/runtime_path/meta_path` switch together with an
append-only `project_workspace_activations` record and succeeded run receipt.
Read-only consumers may finish using the previous generation; mutating dispatch
continues to use the project lock and current DB paths. Export/preview readback
uses the stable root's original `repo/exports` so historical downloads survive.
The activation table is project/account-scoped control-plane metadata, not a user
sidecar authority. Schema installation is additive for existing databases.

Workspace recovery restores files and invalidates current readiness. It does not
roll back platform identities, chat/run/audit history or process state. Current
module plans require review, and final validation must be newer than activation.
See ADR-0061 and `docs/workflows/phase-service-runner-and-business-acceptance.md`.
