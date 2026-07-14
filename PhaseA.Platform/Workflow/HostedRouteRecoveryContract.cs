namespace PhaseA.Platform.Workflow;

public static class HostedRouteRecoveryContract
{
    public const string ContractId = RouteModuleContracts.RecoverySourceOrderRef;
    public const string ParsedRouteProfileSource = "parsed game-type route profile";
    public const string SelectedRouteSkillPromptBlockSource = "selected route skill prompt block";
    public const string ParsedRouteProfileHashKey = "parsed_game_type_route_profile";
    public const string SelectedRouteSkillPromptBlockHashKey = "selected_route_skill_prompt_block";

    public static readonly IReadOnlyList<string> SourceOrder =
    [
        ParsedRouteProfileSource,
        SelectedRouteSkillPromptBlockSource,
        "meta/project-execution-guide.md",
        "routes/prototype-contract/latest.json",
        "current route latest state",
        "current goal/step/session state when applicable",
        "repair ledger and failing acceptance/Godot diagnostic evidence when applicable",
        "latest live platform acceptance blocker"
    ];
}
