using System.Security.Cryptography;
using System.Text;

namespace PhaseA.Platform.Workflow;

public static class RouteActionDescriptors
{
    public const string DescriptorId = "phasea-workflow-actions";
    public const string DescriptorVersion = "1";

    public static readonly IReadOnlyList<RouteActionDescriptor> All =
    [
        new("create_gdd", "user_visible", "active", "/api/projects/{projectId}/gdd", "createGddDocument", "workflow.create_gdd", "run", "/api/projects/{projectId}/gdd", "1"),
        new("complete_gdd", "user_visible", "active", "/api/projects/{projectId}/gdd/outline", "createGddDocument", "workflow.complete_gdd", "readback", "/gdd-outline?projectId={projectId}", "1"),
        new("import_gdd_form", "user_visible", "active", "", "openGddQuestionFormModal", "workflow.import_gdd_form", "non_action", "", "1"),
        new("analyze_game_type", "admin_visible", "active", "", "currentProjectPanel", "workflow.analyze_game_type", "readback", "", "1"),
        new("confirm_scene_route", "user_visible", "active", "/api/projects/{projectId}/gdd/scene-route", "gddQuestionForm", "workflow.confirm_scene_route", "run", "", "1"),
        new("generate_gdd_document", "user_visible", "active", "/api/projects/{projectId}/gdd", "createGddDocument", "workflow.generate_gdd_document", "run", "/api/projects/{projectId}/gdd", "1"),
        new("generate_requirement_map", "user_visible", "active", "", "workflowRouteReadback", "workflow.generate_requirement_map", "readback", "", "1"),
        new("freeze_contract", "user_visible", "active", "", "workflowRouteReadback", "workflow.freeze_contract", "readback", "", "1"),
        new("refresh_contract", "user_visible", "active", "", "workflowRouteReadback", "workflow.refresh_contract", "readback", "", "1"),
        new("inspect_first", "user_visible", "active", "", "workflowRouteReadback", "workflow.inspect_first", "non_action", "", "1"),
        new("delete_project", "user_visible", "active", "/api/projects/{projectId}", "deleteProject", "workflow.delete_project", "project", "", "1"),
        new("create_prototype", "user_visible", "not_active", "/api/projects/{projectId}/prototype-7day-playable/from-gdd", "prototypeWorkflowPanel", "workflow.create_prototype", "run", "", "2"),
        new("create_iteration_plan", "user_visible", "not_active", "/api/projects/{projectId}/iteration-plan", "v2IterationPanel", "workflow.create_iteration_plan", "run", "", "2"),
        new("execute_next_goal", "user_visible", "not_active", "/api/projects/{projectId}/iteration-plan/execute-next", "v2IterationPanel", "workflow.execute_next_goal", "run", "", "2"),
        new("run_needs_fix", "user_visible", "not_active", "/api/projects/{projectId}/prototype-feedback-iterations", "v2RepairPanel", "workflow.run_needs_fix", "run", "", "2"),
        new("run_ui_closure", "user_visible", "not_active", "/api/projects/{projectId}/ui-optimization", "v2UiOptimizationPanel", "workflow.run_ui_closure", "run", "", "2"),
        new("preview_package", "user_visible", "not_active", "/api/projects/{projectId}/packages", "v2DownloadsFramePanel", "workflow.preview_package", "readback", "", "2")
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
            action.RequiredPhase))));

    public static RouteActionDescriptor Get(string actionId)
    {
        return All.FirstOrDefault(action => string.Equals(action.ActionId, actionId, StringComparison.Ordinal)) ??
               new RouteActionDescriptor(actionId, "internal", "blocked", "", "", $"workflow.{actionId}", "non_action", "", "unknown");
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
    string RequiredPhase);
