# K12 Protected Write-Set Preflight

Status: frozen for the current K12 migration attempt.

Authority: ADR-0044, ADR-0046, and the explicit maintainer authorization for
K11-K13. This preflight is derived from
`inventories/hosted-callsite-migration-ledger.v1.json`; its source snapshot
must remain current throughout the attempt.

## Allowed Production Paths

- `PhaseA.Platform/Llm/HostedContextGate.cs` (new)
- `PhaseA.Platform/Llm/LlmRouteEngine.cs`
- `PhaseA.Platform/Runs/CodexHostedProcessCommandFactory.cs`
- `PhaseA.Platform/Llm/ChatService.cs`
- `PhaseA.Platform/Projects/ProjectDraftImportService.cs`
- `PhaseA.Platform/Readback/ProjectAssetInventoryService.cs`
- `PhaseA.Platform/Readback/ProjectAssetLibraryService.cs`
- `PhaseA.Platform/Readback/ProjectWebPreviewDedicatedAdapterService.cs`
- `PhaseA.Platform/Readback/ProjectWebPreviewSemanticAdapterService.cs`
- `PhaseA.Platform/Runs/GameDesignDocumentService.cs`
- `PhaseA.Platform/Runs/GameDesignQuestionFormService.cs`
- `PhaseA.Platform/Runs/GameDesignRequirementMapService.cs`
- `PhaseA.Platform/Runs/GameDesignSceneRouteService.cs`
- `PhaseA.Platform/Runs/GddMilestoneStepService.cs`
- `PhaseA.Platform/Runs/ProjectWorkflowRouteService.cs`
- `PhaseA.Platform/Runs/PrototypeIterationGoalService.cs`
- `PhaseA.Platform/Runs/PrototypeIterationPlanService.cs`
- `PhaseA.Platform/Runs/PrototypeQuickFixService.cs`
- `PhaseA.Platform/Runs/PrototypeRepairPlanService.cs`
- `PhaseA.Platform/Runs/PrototypeUiOptimizationService.cs`
- `PhaseA.Platform/Runs/PrototypeWorkflowService.cs`
- `PhaseA.Platform/Skills/SkillActionService.cs`

## Allowed Test Paths

- `PhaseA.Platform.Tests/Llm/LlmRouteEngineTests.cs`
- `PhaseA.Platform.Tests/Runs/CodexHostedProcessCommandFactoryTests.cs`
- route-service test files corresponding to changed production callers.

## Explicit Exclusions

- `PhaseA.Platform/Program.cs`, `PhaseA.Platform/Browser/**`, `/ui-v2`, session
  paths, Permit/Preflight, Change Origin Gate, and legacy frontend boundary work.
- `runtime/phase-a/**`, Caddy, public deployment configuration, live DB files,
  live Hosted workspaces, and all paths under `logs/phase-a-innernet/**`.
- `scripts/sc/**` and `scripts/python/**`: the ledger proves these candidates are
  Toolchain or a backend definition, not current Hosted-route dispatch.

## Compatibility And Rollback

All affected callsites begin in server-controlled `legacy` mode. K12 may move a
callsite only to `observe` or a verified read-only `enforce` mode. The gate must
reject client-selected escalation and return only the stable K12 codes. A server
policy rollback records append-only evidence and immediately makes E2 readiness
false. This K12 write set does not authorize K13 DB/nonce persistence, Browser
output changes, or release documentation; those require a separately frozen
write set after K12 validation.

## Required Validation

Run the current migration-ledger rebuild, whole-directory validation,
`dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj`, and the
targeted shared-entrypoint tests. Any ledger source-snapshot drift, unknown
reachability, direct invocation violation, or write outside this file fails
closed and returns to this preflight.
