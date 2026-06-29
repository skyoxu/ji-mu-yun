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
- Browser/API readback uses logical artifact IDs, tickets, or workspace-relative sanitized paths instead of raw absolute paths.
- Sidecars are for planning, readback, audit, validation, and route recovery. They must not replace engine-owned project files.
- Package and preview services are readback/product surfaces but must still validate account/project ownership.

## Invariants

- All paths must stay within the workspace root after normalization.
- Readback must be account-scoped unless the route is explicitly admin-only.
- Generated evidence and artifacts must be additive; do not rewrite history to hide failures.
- Package and preview files must be resolved through ticket/ownership checks before download or display.

## Change Rules

- New artifact types must define producer, owner, storage path, readback scope, and sanitization behavior.
- New browser/API readback must avoid raw host paths and secrets.
- New package or asset features must update readback tests and account-boundary tests.
- Workspace layout changes require recovery and restore notes.

## Related Code

- `PhaseA.Platform/Workspaces/WorkspaceLayoutBuilder.cs`
- `PhaseA.Platform/Workspaces/WorkspacePathPolicy.cs`
- `PhaseA.Platform/Workspaces/ProjectWorkspaceSeeder.cs`
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
