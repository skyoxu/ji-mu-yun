using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeGoalAcceptanceValidator
{
    public static async Task<PrototypeGoalAcceptanceValidationResult> ValidateAsync(
        ProjectSnapshot project,
        ProjectIterationGoalSnapshot goal,
        IHostedProcessRunner processRunner,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(goal);
        ArgumentNullException.ThrowIfNull(processRunner);

        var contract = ResolveContract(project, goal);
        if (contract is null)
        {
            return PrototypeGoalAcceptanceValidationResult.NotRun();
        }

        var testProject = Path.Combine(project.RepoPath, "Game.Core.Tests", "Game.Core.Tests.csproj");
        if (!File.Exists(testProject))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind);
        }

        var testsPath = Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs");
        var corePath = Path.Combine(project.RepoPath, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs");
        if (!HasRequiredMarkers(testsPath, corePath, contract.RequiredMarkers))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind);
        }

        using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(2));
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(timeout.Token, cancellationToken);
        try
        {
            var result = await processRunner.RunAsync(
                new HostedProcessCommand(
                    "dotnet",
                    [
                        "test",
                        testProject,
                        "--filter",
                        "FullyQualifiedName~DqRpgPrototypeLoopTests"
                    ],
                    project.RepoPath,
                    new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)),
                linked.Token);
            return result.ExitCode == 0
                ? PrototypeGoalAcceptanceValidationResult.Pass(contract.Kind)
                : PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind);
        }
        catch (OperationCanceledException)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind);
        }
    }

    private static AcceptanceContract? ResolveContract(ProjectSnapshot project, ProjectIterationGoalSnapshot goal)
    {
        if (!IsRpgProject(project))
        {
            return null;
        }

        return goal.GoalIndex switch
        {
            1 => new AcceptanceContract(
                "rpg-step1-map-movement-first-encounter",
                ["MoveOnMap", "ResolveAttackTurn", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"]),
            2 => new AcceptanceContract(
                "rpg-step2-single-battle-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"]),
            3 => new AcceptanceContract(
                "rpg-step3-reward-choice-return-map",
                ["ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward", "RewardOptions.Count", "ApplyReward", "Battle reward selected"]),
            4 => new AcceptanceContract(
                "rpg-step4-win-loss-goal-visibility",
                ["VictoryBattleCount", "IsVictory", "IsGameOver", "Defeat"]),
            5 => new AcceptanceContract(
                "rpg-step5-reward-loop-return-map",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected", "Return to the map"]),
            _ => null
        };
    }

    private static bool IsRpgProject(ProjectSnapshot project)
    {
        var text = string.Join(" ", project.GameTypeSource, project.TemplateRuleId, project.Name, project.GameName).ToLowerInvariant();
        if (text.Contains("rpg", StringComparison.Ordinal) ||
            text.Contains("dragon quest", StringComparison.Ordinal))
        {
            return true;
        }

        if (text.Contains("勇者", StringComparison.Ordinal) ||
            text.Contains("斗恶龙", StringComparison.Ordinal))
        {
            return true;
        }

        return File.Exists(Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs"));
    }

    private static bool HasRequiredMarkers(string testsPath, string corePath, IReadOnlyList<string> requiredMarkers)
    {
        var text = "";
        if (File.Exists(testsPath))
        {
            text += File.ReadAllText(testsPath);
        }

        if (File.Exists(corePath))
        {
            text += Environment.NewLine + File.ReadAllText(corePath);
        }

        return requiredMarkers.All(marker => text.Contains(marker, StringComparison.Ordinal));
    }

    private sealed record AcceptanceContract(string Kind, IReadOnlyList<string> RequiredMarkers);
}

internal sealed record PrototypeGoalAcceptanceValidationResult(string Kind, string Status)
{
    public bool Passed => string.Equals(Status, "passed", StringComparison.Ordinal);

    public static PrototypeGoalAcceptanceValidationResult NotRun()
    {
        return new PrototypeGoalAcceptanceValidationResult("none", "not_run");
    }

    public static PrototypeGoalAcceptanceValidationResult Pass(string kind)
    {
        return new PrototypeGoalAcceptanceValidationResult(kind, "passed");
    }

    public static PrototypeGoalAcceptanceValidationResult Failed(string kind)
    {
        return new PrototypeGoalAcceptanceValidationResult(kind, "failed");
    }
}
