using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class RouteActionDescriptors
{
    public const string DescriptorId = "phasea-workflow-actions";
    public const string DescriptorVersion = "1";

    public static readonly IReadOnlyList<RouteActionDescriptor> All =
    [
        Action("create_gdd", "user_visible", "active", "/api/projects/{projectId}/gdd", "createGddDocument", "workflow.create_gdd", "run", "/api/projects/{projectId}/gdd", "1"),
        Action("complete_gdd", "user_visible", "active", "/api/projects/{projectId}/gdd/outline", "createGddDocument", "workflow.complete_gdd", "readback", "/gdd-outline?projectId={projectId}", "1"),
        Action("import_gdd_form", "user_visible", "active", "", "openGddQuestionFormModal", "workflow.import_gdd_form", "non_action", "", "1"),
        Action("analyze_game_type", "admin_visible", "active", "", "currentProjectPanel", "workflow.analyze_game_type", "readback", "", "1"),
        Action("confirm_scene_route", "user_visible", "active", "/api/projects/{projectId}/gdd/scene-route", "gddQuestionForm", "workflow.confirm_scene_route", "run", "", "1"),
        Action("generate_gdd_document", "user_visible", "active", "/api/projects/{projectId}/gdd", "createGddDocument", "workflow.generate_gdd_document", "run", "/api/projects/{projectId}/gdd", "1"),
        Action("generate_requirement_map", "user_visible", "active", "", "workflowRouteReadback", "workflow.generate_requirement_map", "readback", "", "1"),
        Action("freeze_contract", "user_visible", "active", "", "workflowRouteReadback", "workflow.freeze_contract", "readback", "", "1"),
        Action("refresh_contract", "user_visible", "active", "", "workflowRouteReadback", "workflow.refresh_contract", "readback", "", "1"),
        Action("inspect_first", "user_visible", "active", "", "workflowRouteReadback", "workflow.inspect_first", "non_action", "", "1"),
        Action("delete_project", "user_visible", "active", "/api/projects/{projectId}", "deleteProject", "workflow.delete_project", "project", "", "1"),
        Action("create_prototype", "user_visible", "not_active", "/api/projects/{projectId}/prototype-7day-playable/from-gdd", "prototypeWorkflowPanel", "workflow.create_prototype", "run", "", "2"),
        Action("create_iteration_plan", "user_visible", "active", "/api/projects/{projectId}/iteration-plan", "v2IterationPanel", "workflow.create_iteration_plan", "run", "/api/projects/{projectId}/iteration-plan/latest", "2"),
        Action("execute_next_goal", "user_visible", "not_active", "/api/projects/{projectId}/iteration-plan/execute-next", "v2IterationPanel", "workflow.execute_next_goal", "run", "", "2"),
        Action("run_needs_fix", "user_visible", "not_active", "/api/projects/{projectId}/prototype-feedback-iterations", "v2RepairPanel", "workflow.run_needs_fix", "run", "", "2"),
        Action("run_ui_closure", "user_visible", "not_active", "/api/projects/{projectId}/ui-optimization", "v2UiOptimizationPanel", "workflow.run_ui_closure", "run", "", "2"),
        Action("preview_package", "user_visible", "not_active", "/api/projects/{projectId}/packages", "v2DownloadsFramePanel", "workflow.preview_package", "readback", "", "2")
    ];

    public static readonly IReadOnlyList<string> CanonicalActionIds = All.Select(action => action.ActionId).ToArray();

    public static readonly IReadOnlyList<string> Phase1ActionIds = All
        .Where(action => action.RequiredPhase == "1")
        .Select(action => action.ActionId)
        .ToArray();

    public static readonly IReadOnlyList<string> DisabledDomainCodes =
    [
        "route_contract_not_active",
        "phase_gate_blocked",
        "source_stale",
        "admin_review_blocked",
        "diagnostic_blocked",
        "account_forbidden",
        "not_applicable"
    ];

    public static string DescriptorHash => Sha256(string.Join("\n", All.Select(action =>
        string.Join("|",
            DescriptorId,
            DescriptorVersion,
            action.ActionId,
            action.ExposureClass,
            action.DefaultPhaseEligibility,
            action.ApiRouteTemplate,
            action.BrowserActionId,
            action.DisplayLabelKey,
            action.OperationScope,
            action.ReadbackUrlTemplate,
            action.RequiredPhase,
            action.AccountBoundary,
            action.AuthBoundary,
            action.DuplicateRunPolicy))));

    public static RouteActionDescriptor Get(string actionId)
    {
        return All.FirstOrDefault(action => string.Equals(action.ActionId, actionId, StringComparison.Ordinal)) ??
               Action(actionId, "internal", "blocked", "", "", $"workflow.{actionId}", "non_action", "", "unknown");
    }

    public static bool IsPhase1Action(string actionId)
    {
        return Phase1ActionIds.Contains(actionId, StringComparer.Ordinal);
    }

    public static string ResolveTemplate(string template, string projectId)
    {
        if (string.IsNullOrWhiteSpace(template))
        {
            return "";
        }

        return template.Replace("{projectId}", Uri.EscapeDataString(projectId), StringComparison.Ordinal);
    }

    private static string Sha256(string value)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(value));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    private static RouteActionDescriptor Action(
        string actionId,
        string exposureClass,
        string defaultPhaseEligibility,
        string apiRouteTemplate,
        string browserActionId,
        string displayLabelKey,
        string operationScope,
        string readbackUrlTemplate,
        string requiredPhase)
    {
        var adminOnly = string.Equals(exposureClass, "admin_visible", StringComparison.Ordinal);
        var duplicateRunPolicy = operationScope switch
        {
            "run" => "request_identity_or_active_run_reuse",
            "project" => "idempotent_project_mutation",
            _ => "read_only_or_non_action"
        };
        return new RouteActionDescriptor(
            actionId,
            exposureClass,
            defaultPhaseEligibility,
            apiRouteTemplate,
            browserActionId,
            displayLabelKey,
            operationScope,
            readbackUrlTemplate,
            requiredPhase,
            adminOnly ? "admin_cross_account_redacted" : "account_project_ownership",
            adminOnly ? "admin_only" : "authenticated_account_member",
            duplicateRunPolicy);
    }
}

public sealed record RouteActionDescriptor(
    string ActionId,
    string ExposureClass,
    string DefaultPhaseEligibility,
    string ApiRouteTemplate,
    string BrowserActionId,
    string DisplayLabelKey,
    string OperationScope,
    string ReadbackUrlTemplate,
    string RequiredPhase,
    string AccountBoundary,
    string AuthBoundary,
    string DuplicateRunPolicy);
