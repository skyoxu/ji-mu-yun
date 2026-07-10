namespace PhaseA.Platform.Workflow;

public static class RouteOperationPreflight
{
    public static readonly IReadOnlyList<RoutePreflightCapability> Capabilities =
    [
        new("codex_command", "PHASEA_CODEX_COMMAND", "Codex command path for executable route operations.", "admin_only_redacted", ["create_prototype", "create_iteration_plan", "execute_next_goal", "run_needs_fix", "run_ui_closure"]),
        new("godot_binary", "GODOT_BIN", "Godot binary path for validation, preview, package, and UI closure.", "admin_only_redacted", ["execute_next_goal", "run_needs_fix", "run_ui_closure", "preview_package"]),
        new("hosted_workspace_root", "HOSTED_WORKSPACE_ROOT", "Hosted workspace root for project files.", "admin_only_redacted", RouteActionDescriptors.CanonicalActionIds),
        new("metadata_db", "PHASEA_METADATA_DB_PATH", "Phase metadata database path.", "admin_only_redacted", ["analyze_game_type", "generate_requirement_map", "freeze_contract", "inspect_first", "delete_project"]),
        new("game_type_index", "docs/game-type-guides/game-types.csv", "Game type guide index for project creation and structured matching.", "user_safe_summary", ["create_gdd", "analyze_game_type", "confirm_scene_route"])
    ];

    public static IReadOnlyList<RoutePreflightCapability> ForAction(string actionId)
    {
        return Capabilities.Where(capability => capability.RequiredForActionIds.Contains(actionId, StringComparer.Ordinal)).ToArray();
    }
}

public sealed record RoutePreflightCapability(
    string CapabilityId,
    string Source,
    string Description,
    string ReadbackVisibility,
    IReadOnlyList<string> RequiredForActionIds);
