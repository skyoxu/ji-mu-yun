namespace PhaseA.Platform.Workflow;

public static class HostedRouteRecoveryContract
{
    public const string ContractId = RouteModuleContracts.RecoverySourceOrderRef;

    public static readonly IReadOnlyList<string> SourceOrder =
    [
        "parsed game-type route profile",
        "meta/project-execution-guide.md",
        "routes/prototype-contract/latest.json",
        "current route latest state",
        "current goal/step/session state when applicable",
        "repair ledger and failing acceptance/Godot diagnostic evidence when applicable",
        "latest live platform acceptance blocker"
    ];
}
