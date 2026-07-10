using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class RouteModuleContracts
{
    public const string ContractSetId = "phasea-gdd-to-module-route-contracts";
    public const string ContractSetVersion = "1";
    public const string RecoverySourceOrderRef = "hosted-route-recovery-order.v1";

    public static readonly IReadOnlyList<RouteModuleContract> All =
    [
        Contract("gdd-requirements", "Runs/GameDesignRequirementMapService", "meta/routes/gdd-requirements/latest.json", null, true, ["generate_requirement_map"], ["/api/projects/{projectId}/gdd/requirements-map", "/api/projects/{projectId}/gdd/requirements-map/latest"], ["workflowRouteReadback"], ["docs/gdd/GDD.md", "meta/routes/scene-route/latest.json", "meta/routes/gdd-document/latest.json"], ["source_gdd_hash", "source_scene_route_hash", "source_generated_gdd_hash", "source_game_type_structured_hash"], "route_readback"),
        Contract("gdd-document-generation", "Runs/GameDesignDocumentService", "meta/routes/gdd-document/latest.json", "docs/gdd/GDD.md", true, ["generate_gdd_document", "create_gdd", "complete_gdd", "import_gdd_form"], ["/api/projects/{projectId}/gdd/document/generate", "/api/projects/{projectId}/gdd/document/status", "/api/projects/{projectId}/gdd"], ["createGddDocument", "openGddQuestionFormModal"], ["meta/routes/gdd-question-form/latest.json", "meta/routes/scene-route/latest.json"], ["generated_gdd_hash", "source_scene_route_hash"], "route_readback"),
        Contract("scene-route-confirmation", "Runs/GameDesignSceneRouteService", "meta/routes/scene-route/latest.json", "meta/routes/gdd-scene-route/latest.json", true, ["confirm_scene_route"], ["/api/projects/{projectId}/gdd/scene-route", "/api/projects/{projectId}/gdd/scene-route/confirm", "/api/projects/{projectId}/gdd/scene-route/latest"], ["gddQuestionForm"], ["meta/routes/gdd-question-form/latest.json", "docs/gdd/GDD.md"], ["confirmed_scene_route_hash", "source_generated_gdd_hash", "source_game_type_structured_hash"], "scene_route_confirmation"),
        Contract("structured-game-type-analysis", "Projects/ProjectGameTypeMatchService", "metadata:projects.game_type_match_json", null, false, ["analyze_game_type"], ["/api/admin/game-type-match-records", "/api/admin/projects/{projectId}/game-type-contract-snapshot/refresh"], ["currentProjectPanel"], ["metadata:projects.game_type_match_json", "metadata:project_game_type_match_failures"], ["source_game_type_structured_hash"], "route_readback"),
        Contract("prototype-contract", "Runs/PrototypeContractFreezeService", "routes/prototype-contract/latest.json", "meta/routes/prototype-contract/latest.json", true, ["freeze_contract", "refresh_contract"], ["/api/projects/{projectId}/prototype-contract/freeze", "/api/projects/{projectId}/prototype-contract/status"], ["workflowRouteReadback"], ["docs/gdd/GDD.md", "meta/routes/scene-route/latest.json", "meta/routes/gdd-requirements/latest.json"], ["contract_hash", "source_gdd_hash", "source_scene_route_hash", "source_requirement_map_hash"], "route_readback"),
        Contract("prototype-skeleton", "Runs/PrototypeWorkflowService", "meta/routes/prototype-skeleton/latest.json", "meta/routes/prototype/latest.json", true, ["create_prototype"], ["/api/projects/{projectId}/prototype-7day-playable/from-gdd", "/api/projects/{projectId}/prototype-skeleton/status"], ["prototypeWorkflowPanel"], ["routes/prototype-contract/latest.json", "meta/routes/gdd-requirements/latest.json"], ["source_contract_hash", "source_scene_route_hash", "source_requirement_map_hash"], "prototype_skeleton_source"),
        Contract("workflow-recommendation", "Runs/ProjectWorkflowRouteService", "meta/routes/workflow-recommendation/latest.json", null, false, RouteActionDescriptors.CanonicalActionIds, ["/api/projects/{projectId}/workflow-route", "/api/projects/{projectId}/workflow-recommendation"], ["workflowRouteReadback"], ["route-state-readback", "PhaseA.Platform/Workflow/RouteActionDescriptors.cs"], ["descriptor_hash"], "readiness_label"),
        Contract("ui-wiring-closure", "Runs/PrototypeUiOptimizationService", "meta/routes/ui-wiring/latest.json", "meta/routes/ui-closure/latest.json", true, ["run_ui_closure"], ["/api/projects/{projectId}/ui-optimization", "/api/projects/{projectId}/ui-wiring-closure/latest"], ["v2UiOptimizationPanel"], ["routes/prototype-contract/latest.json", "meta/routes/gdd-requirements/latest.json"], ["source_iteration_session_hash", "source_validation_input_hash", "source_contract_hash", "source_requirement_map_hash", "source_godot_ui_contract_hash", "source_ui_style_contract_hash", "ui_style_snapshot_hash"], "route_readback"),
        Contract("iteration-plan", "Runs/PrototypeIterationPlanService", "meta/routes/iteration-plan/latest.json", null, true, ["create_iteration_plan"], ["/api/projects/{projectId}/iteration-plan", "/api/projects/{projectId}/iteration-plan/latest"], ["v2IterationPanel"], ["routes/prototype-contract/latest.json", "meta/routes/gdd-requirements/latest.json", "meta/routes/prototype-skeleton/latest.json"], ["source_contract_hash", "source_requirement_map_hash", "source_scene_route_hash"], "route_readback"),
        Contract("execute-next-goal", "Runs/PrototypeIterationGoalService", "meta/routes/execute-next-goal/latest.json", null, true, ["execute_next_goal"], ["/api/projects/{projectId}/iteration-plan/execute-next"], ["v2IterationPanel"], ["meta/routes/iteration-plan/latest.json", "routes/prototype-contract/latest.json"], ["source_iteration_session_hash", "source_contract_hash", "source_requirement_map_hash"], "route_readback"),
        Contract("needs-fix", "Runs/PrototypeNeedsFixRouteService", "meta/routes/needs-fix/latest.json", null, true, ["run_needs_fix"], ["/api/projects/{projectId}/needs-fix-route", "/api/projects/{projectId}/prototype-feedback-iterations"], ["v2RepairPanel"], ["meta/routes/iteration-plan/latest.json", "routes/prototype-contract/latest.json", "latest live platform acceptance blocker"], ["source_iteration_session_hash", "source_contract_hash", "source_validation_input_hash"], "route_readback"),
        Contract("repair", "Runs/PrototypeQuickFixService", "meta/routes/repair/latest.json", "meta/routes/repair-plan/latest.json", true, ["run_needs_fix"], ["/api/projects/{projectId}/repair-plan", "/api/projects/{projectId}/repair-plan/execute-next", "/api/projects/{projectId}/prototype-quick-fixes"], ["v2RepairPanel"], ["repair ledger", "Godot diagnostic evidence", "latest live platform acceptance blocker"], ["source_repair_ledger_hash", "source_validation_input_hash", "source_contract_hash"], "route_readback"),
        Contract("preview-package", "Runs/ProjectPackageService", "metadata:packages", null, false, ["preview_package"], ["/api/projects/{projectId}/packages"], ["v2DownloadsFramePanel"], ["routes/prototype-contract/latest.json", "meta/routes/ui-wiring/latest.json", "metadata:project_diagnostic_spool"], ["source_contract_hash", "diagnostic_spool_updated_utc"], "readiness_label"),
        Contract("project-delete", "Projects/ProjectCreationService", "metadata:project_delete_tombstones", null, false, ["delete_project"], ["/api/projects/{projectId}", "/api/admin/project-delete-tombstones"], ["deleteProject"], ["metadata:projects", "metadata:project_admin_review_queue", "metadata:project_diagnostic_spool"], ["project_id"], "operation_status")
    ];

    public static string ContractSetHash => Sha256(string.Join("\n", All.Select(contract =>
        string.Join("|",
            ContractSetId,
            ContractSetVersion,
            contract.RouteId,
            contract.Owner,
            contract.CanonicalRouteStatePath,
            contract.MirrorRouteStatePath ?? "",
            contract.PromptSourceBoundaryRequired,
            string.Join(",", contract.ActionIds),
            string.Join(",", contract.ApiRoutes),
            string.Join(",", contract.BrowserEntrypoints),
            string.Join(",", contract.RequiredSourceArtifacts),
            string.Join(",", contract.SourceHashFields),
            contract.StatusDimension,
            contract.RecoverySourceOrderRef,
            contract.ExposureClass,
            contract.PhaseEligibility))));

    public static RouteModuleContract? Find(string routeId)
    {
        return All.FirstOrDefault(contract => string.Equals(contract.RouteId, routeId, StringComparison.Ordinal));
    }

    private static RouteModuleContract Contract(
        string routeId,
        string owner,
        string canonicalRouteStatePath,
        string? mirrorRouteStatePath,
        bool promptSourceBoundaryRequired,
        IReadOnlyList<string> actionIds,
        IReadOnlyList<string> apiRoutes,
        IReadOnlyList<string> browserEntrypoints,
        IReadOnlyList<string> requiredSourceArtifacts,
        IReadOnlyList<string> sourceHashFields,
        string statusDimension)
    {
        var exposure = actionIds.Any(action => RouteActionDescriptors.Get(action).ExposureClass == "admin_visible")
            ? "admin_visible"
            : "user_visible";
        if (routeId == "project-delete")
        {
            exposure = "user_visible";
        }

        return new RouteModuleContract(
            routeId,
            owner,
            canonicalRouteStatePath,
            mirrorRouteStatePath,
            promptSourceBoundaryRequired,
            promptSourceBoundaryRequired ? RecoverySourceOrderRef : "source_boundary_not_applicable",
            actionIds,
            apiRoutes,
            browserEntrypoints,
            requiredSourceArtifacts,
            sourceHashFields,
            statusDimension,
            exposure,
            actionIds.All(RouteActionDescriptors.IsPhase1Action) ? "active" : "phase_gated",
            ["admin review queue", "diagnostic spool", "workflow recommendation readback"],
            ["PhaseA.Platform.Tests/Runs", "PhaseA.Platform.Tests/Workflow", "PhaseA.Platform.Tests/Browser"]);
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }
}

public sealed record RouteModuleContract(
    string RouteId,
    string Owner,
    string CanonicalRouteStatePath,
    string? MirrorRouteStatePath,
    bool PromptSourceBoundaryRequired,
    string RecoverySourceOrderRef,
    IReadOnlyList<string> ActionIds,
    IReadOnlyList<string> ApiRoutes,
    IReadOnlyList<string> BrowserEntrypoints,
    IReadOnlyList<string> RequiredSourceArtifacts,
    IReadOnlyList<string> SourceHashFields,
    string StatusDimension,
    string ExposureClass,
    string PhaseEligibility,
    IReadOnlyList<string> AdminReadbackSurfaces,
    IReadOnlyList<string> DeterministicTestOwners);
