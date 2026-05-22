using System.Text.RegularExpressions;
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

        var testsPath = Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs");
        var corePath = Path.Combine(project.RepoPath, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs");
        if (contract.AssetUsageAcceptance && !HasRpgSceneAssetUsage(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "missing_rpg_asset_usage");
        }

        if (contract.MapEntryAcceptance && !HasRpgMapEntryAcceptanceFiles(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "missing_rpg_map_entry_contract");
        }

        if (contract.BattleSceneAcceptance && !HasRpgBattleSceneAcceptanceFiles(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "missing_rpg_battle_scene_contract");
        }

        if (contract.RewardFlowAcceptance && !HasRpgRewardFlowAcceptanceFiles(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "missing_rpg_reward_flow_contract");
        }

        if (contract.MainSceneHostUiHiddenAcceptance && !HasMainSceneDefaultPrototypeHostUiHidden(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "main_scene_default_ui_not_hidden");
        }

        if (contract.FinalAcceptance && !HasRpgFinalAcceptanceFiles(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "missing_rpg_final_acceptance_contract");
        }

        if (!HasRequiredMarkers(testsPath, corePath, contract.RequiredMarkers))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "missing_required_core_markers");
        }

        if (contract.StaticAcceptanceOnly)
        {
            return PrototypeGoalAcceptanceValidationResult.Pass(contract.Kind);
        }

        var testProject = Path.Combine(project.RepoPath, "Game.Core.Tests", "Game.Core.Tests.csproj");
        if (!File.Exists(testProject))
        {
            return PrototypeGoalAcceptanceValidationResult.NotRun();
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
            if (result.ExitCode != 0)
            {
                return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "core_tests_failed");
            }

            var godotProject = Path.Combine(project.RepoPath, "GodotGame.csproj");
            if (File.Exists(godotProject))
            {
                var buildResult = await processRunner.RunAsync(
                    new HostedProcessCommand(
                        "dotnet",
                        [
                            "build",
                            godotProject,
                            "-c",
                            "Debug",
                            "-v",
                            "minimal",
                            "--no-restore"
                        ],
                        project.RepoPath,
                        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)),
                    linked.Token);
                if (buildResult.ExitCode != 0)
                {
                    return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "godot_project_build_failed");
                }
            }

            return PrototypeGoalAcceptanceValidationResult.Pass(contract.Kind);
        }
        catch (OperationCanceledException)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "acceptance_validation_timeout");
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
                "rpg-step1-basic-assets-ui-validation",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count"],
                AssetUsageAcceptance: true),
            2 => new AcceptanceContract(
                "rpg-step2-start-adventure-visible-mapscene",
                ["MoveOnMap", "ShouldReachRewardPhase_AfterWinningTheFirstEncounter"],
                MapEntryAcceptance: true),
            3 => new AcceptanceContract(
                "rpg-step3-battlescene-settlement",
                ["ShouldReachRewardPhase_AfterWinningTheFirstEncounter", "ResolveAttackTurn", "BattlesWon", "Victory"],
                BattleSceneAcceptance: true),
            4 => new AcceptanceContract(
                "rpg-step4-main-scene-switching",
                ["MoveOnMap", "ResolveAttackTurn", "ShouldReturnToMap_WithUpdatedStats_AfterChoosingReward"],
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true),
            5 => new AcceptanceContract(
                "rpg-step5-reward-loop-return-map",
                ["RewardOptions.Count", "ApplyReward", "Battle reward selected", "Return to the map"],
                RewardFlowAcceptance: true,
                StaticAcceptanceOnly: true),
            6 => new AcceptanceContract(
                "rpg-final-full-playable-acceptance",
                ["MoveOnMap", "ResolveAttackTurn", "RewardOptions.Count", "ApplyReward", "Battle reward selected", "VictoryBattleCount", "IsVictory", "IsGameOver"],
                AssetUsageAcceptance: true,
                MapEntryAcceptance: true,
                BattleSceneAcceptance: true,
                RewardFlowAcceptance: true,
                MainSceneHostUiHiddenAcceptance: true,
                FinalAcceptance: true),
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

    private static bool HasRpgFinalAcceptanceFiles(string repoPath)
    {
        var requiredFiles = new[]
        {
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs"),
            Path.Combine(repoPath, "Game.Godot", "Scripts", "Prototypes", "PrototypeCatalog.cs"),
            Path.Combine(repoPath, "Game.Godot", "Scenes", "Main.tscn")
        };
        if (requiredFiles.Any(path => !File.Exists(path)))
        {
            return false;
        }

        if (!HasRpgSceneAssetUsage(repoPath))
        {
            return false;
        }

        var catalogText = File.ReadAllText(Path.Combine(repoPath, "Game.Godot", "Scripts", "Prototypes", "PrototypeCatalog.cs"));
        return catalogText.Contains("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", StringComparison.Ordinal) &&
               HasMainSceneDefaultPrototypeHostUiHidden(repoPath) &&
               HasRpgMapEntryAcceptanceFiles(repoPath) &&
               HasRpgBattleSceneAcceptanceFiles(repoPath);
    }

    private static bool HasMainSceneDefaultPrototypeHostUiHidden(string repoPath)
    {
        var mainScene = Path.Combine(repoPath, "Game.Godot", "Scenes", "Main.tscn");
        if (!File.Exists(mainScene))
        {
            return false;
        }

        var sceneText = File.ReadAllText(mainScene);
        return IsSceneNodeDefaultHidden(sceneText, "VBox", ".") &&
               IsSceneNodeDefaultHidden(sceneText, "Overlays", ".") &&
               IsSceneNodeDefaultHidden(sceneText, "ScreenRoot", ".");
    }

    private static bool IsSceneNodeDefaultHidden(string sceneText, string nodeName, string parent)
    {
        var match = Regex.Match(
            sceneText,
            "\\[node\\s+name=\"" + Regex.Escape(nodeName) + "\"[^\\]]*parent=\"" + Regex.Escape(parent) + "\"[^\\]]*\\](?<body>.*?)(?=\\r?\\n\\[node|\\r?\\n\\[connection|\\z)",
            RegexOptions.Singleline | RegexOptions.CultureInvariant);
        if (!match.Success)
        {
            return false;
        }

        return Regex.IsMatch(
            match.Groups["body"].Value,
            "(^|\\r?\\n)visible\\s*=\\s*false(\\r?\\n|$)",
            RegexOptions.CultureInvariant);
    }

    private static bool HasRpgMapEntryAcceptanceFiles(string repoPath)
    {
        var mainScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
        var mainScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs");
        var mapScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn");
        var mapScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs");
        if (new[] { mainScene, mainScript, mapScene, mapScript }.Any(path => !File.Exists(path)))
        {
            return false;
        }

        var mainSceneText = File.ReadAllText(mainScene);
        var mainScriptText = File.ReadAllText(mainScript);
        var mapSceneText = File.ReadAllText(mapScene);
        var mapScriptText = File.ReadAllText(mapScript);

        return mainSceneText.Contains("StartButton", StringComparison.Ordinal) &&
               mainSceneText.Contains("Start Adventure", StringComparison.Ordinal) &&
               mainSceneText.Contains("MapScene", StringComparison.Ordinal) &&
               mainSceneText.Contains("parent=\"CanvasLayer/UI\"", StringComparison.Ordinal) &&
               mainSceneText.Contains("anchors_preset = 15", StringComparison.Ordinal) &&
               mainScriptText.Contains("Pressed += ShowMapScene", StringComparison.Ordinal) &&
               mainScriptText.Contains("CanvasLayer/UI/MapScene", StringComparison.Ordinal) &&
               mainScriptText.Contains("_mapScene.Visible = true", StringComparison.Ordinal) &&
               mapSceneText.Contains("MapScene", StringComparison.Ordinal) &&
               mapSceneText.Contains("TrackLayer", StringComparison.Ordinal) &&
               mapSceneText.Contains("custom_minimum_size = Vector2(600, 600)", StringComparison.Ordinal) &&
               HasSceneNodeUnderParent(mapSceneText, "RpgMapAsset", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer") &&
               HasSceneNodeUnderParent(mapSceneText, "Grid", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer") &&
               HasSceneNodeUnderParent(mapSceneText, "Overlay", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer") &&
               HasSceneNodeUnderParent(mapSceneText, "RpgPlayerAsset", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay") &&
               mapSceneText.Contains("Grid", StringComparison.Ordinal) &&
               mapSceneText.Contains("RpgMapAsset", StringComparison.Ordinal) &&
               mapSceneText.Contains("RpgPlayerAsset", StringComparison.Ordinal) &&
               mapSceneText.Contains("RpgEnemyAsset", StringComparison.Ordinal) &&
               mapScriptText.Contains("TrackLayer", StringComparison.Ordinal) &&
               mapScriptText.Contains("GridToPosition", StringComparison.Ordinal) &&
               mapScriptText.Contains("_player.Visible = true", StringComparison.Ordinal) &&
               mapScriptText.Contains("MovePlayer", StringComparison.Ordinal) &&
               mapScriptText.Contains("EncounterEntered", StringComparison.Ordinal);
    }

    private static bool HasRpgBattleSceneAcceptanceFiles(string repoPath)
    {
        var battleScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn");
        var battleScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs");
        if (new[] { battleScene, battleScript }.Any(path => !File.Exists(path)))
        {
            return false;
        }

        var battleSceneText = File.ReadAllText(battleScene);
        var battleScriptText = File.ReadAllText(battleScript);
        return battleSceneText.Contains("BattleScene", StringComparison.Ordinal) &&
               battleSceneText.Contains("Attack", StringComparison.Ordinal) &&
               battleScriptText.Contains("ResolveAttackTurn", StringComparison.Ordinal) &&
               !battleScriptText.Contains("_loop.ResolveBattle(_state", StringComparison.Ordinal) &&
               battleScriptText.Contains("BattleFinished", StringComparison.Ordinal);
    }

    private static bool HasRpgRewardFlowAcceptanceFiles(string repoPath)
    {
        var mainScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs");
        var mapScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs");
        if (new[] { mainScript, mapScript }.Any(path => !File.Exists(path)))
        {
            return false;
        }

        var mainScriptText = File.ReadAllText(mainScript);
        var mapScriptText = File.ReadAllText(mapScript);
        return HasRewardListGuard(mainScriptText) &&
               !mainScriptText.Contains("if (isVictory && rewards.Count > 0)", StringComparison.Ordinal) &&
               HasRewardSceneEntry(mainScriptText) &&
               mainScriptText.Contains("ShowMapScene()", StringComparison.Ordinal) &&
               mapScriptText.Contains("ShowRewardReturnStatus", StringComparison.Ordinal) &&
               mapScriptText.Contains("_player.Visible = true", StringComparison.Ordinal);
    }

    private static bool HasRewardListGuard(string mainScriptText)
    {
        return mainScriptText.Contains("rewards.Count > 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("rewards.Count <= 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("rewards.Count == 0", StringComparison.Ordinal);
    }

    private static bool HasRewardSceneEntry(string mainScriptText)
    {
        return mainScriptText.Contains("ShowRewardScene(rewards)", StringComparison.Ordinal) ||
               Regex.IsMatch(
                   mainScriptText,
                   @"ShowRewardScene\s*\(\s*(?:[\w.]+\.)?IReadOnlyList<[^>]+>\s+rewards\s*\)",
                   RegexOptions.CultureInvariant);
    }

    private static bool HasSceneNodeUnderParent(string sceneText, string nodeName, string parent)
    {
        return Regex.IsMatch(
            sceneText,
            "\\[node\\s+name=\"" + Regex.Escape(nodeName) + "\"[^\\]]*parent=\"" + Regex.Escape(parent) + "\"[^\\]]*\\]",
            RegexOptions.CultureInvariant);
    }

    private static bool HasRpgSceneAssetUsage(string repoPath)
    {
        var sceneFiles = new[]
        {
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn")
        };
        if (sceneFiles.Any(path => !File.Exists(path)))
        {
            return false;
        }

        if (File.Exists(Path.Combine(repoPath, "Game.Godot", ".gdignore")))
        {
            return false;
        }

        var usages = sceneFiles.SelectMany(path => ReadSceneAssetUsages(repoPath, path)).ToList();
        return HasRequiredRpgAssetUsage(usages, "RpgMapAsset", IsMapAssetPath) &&
               HasRequiredRpgAssetUsage(usages, "RpgPlayerAsset", IsPlayerAssetPath) &&
               HasRequiredRpgAssetUsage(usages, "RpgEnemyAsset", IsEnemyAssetPath);
    }

    private static IEnumerable<SceneAssetUsage> ReadSceneAssetUsages(string repoPath, string sceneFile)
    {
        var text = File.ReadAllText(sceneFile);
        var resources = Regex.Matches(
                text,
                "\\[ext_resource\\s+[^\\]]*type=\"Texture2D\"[^\\]]*path=\"(?<path>[^\"]+)\"[^\\]]*id=\"(?<id>[^\"]+)\"[^\\]]*\\]",
                RegexOptions.CultureInvariant)
            .Cast<Match>()
            .ToDictionary(
                match => match.Groups["id"].Value,
                match => match.Groups["path"].Value,
                StringComparer.Ordinal);
        if (resources.Count == 0)
        {
            yield break;
        }

        var nodeMatches = Regex.Matches(
            text,
            "\\[node\\s+name=\"(?<name>[^\"]+)\"\\s+type=\"(?<type>TextureRect|Sprite2D|AnimatedSprite2D)\"[^\\]]*\\](?<body>.*?)(?=\\r?\\n\\[node|\\r?\\n\\[connection|\\z)",
            RegexOptions.Singleline | RegexOptions.CultureInvariant);
        foreach (Match nodeMatch in nodeMatches)
        {
            var textureMatch = Regex.Match(
                nodeMatch.Groups["body"].Value,
                "texture\\s*=\\s*ExtResource\\(\"(?<id>[^\"]+)\"\\)",
                RegexOptions.CultureInvariant);
            if (!textureMatch.Success)
            {
                continue;
            }

            var id = textureMatch.Groups["id"].Value;
            if (!resources.TryGetValue(id, out var resourcePath))
            {
                continue;
            }

            yield return new SceneAssetUsage(
                nodeMatch.Groups["name"].Value,
                nodeMatch.Groups["type"].Value,
                resourcePath,
                GodotResourceExists(repoPath, resourcePath));
        }
    }

    private static bool HasRequiredRpgAssetUsage(
        IEnumerable<SceneAssetUsage> usages,
        string requiredNodeName,
        Func<string, bool> isExpectedAssetPath)
    {
        return usages.Any(usage =>
            string.Equals(usage.NodeName, requiredNodeName, StringComparison.Ordinal) &&
            usage.ResourceExists &&
            isExpectedAssetPath(usage.ResourcePath));
    }

    private static bool GodotResourceExists(string repoPath, string resourcePath)
    {
        const string resPrefix = "res://";
        if (!resourcePath.StartsWith(resPrefix, StringComparison.Ordinal))
        {
            return false;
        }

        var relativePath = resourcePath[resPrefix.Length..].Replace('/', Path.DirectorySeparatorChar);
        return File.Exists(Path.Combine(repoPath, relativePath));
    }

    private static bool IsMapAssetPath(string resourcePath)
    {
        return IsAssetPath(resourcePath, "/assets/map/") ||
               ContainsAssetToken(resourcePath, "map", "tile", "floor", "backdrop", "overworld");
    }

    private static bool IsPlayerAssetPath(string resourcePath)
    {
        return IsAssetPath(resourcePath, "/assets/player/") ||
               ContainsAssetToken(resourcePath, "player", "hero", "main_character", "protagonist");
    }

    private static bool IsEnemyAssetPath(string resourcePath)
    {
        return IsAssetPath(resourcePath, "/assets/enemy/") ||
               ContainsAssetToken(resourcePath, "enemy", "boss", "monster", "slime");
    }

    private static bool IsAssetPath(string resourcePath, string requiredSegment)
    {
        return resourcePath.Replace('\\', '/').ToLowerInvariant().Contains(requiredSegment, StringComparison.Ordinal);
    }

    private static bool ContainsAssetToken(string resourcePath, params string[] tokens)
    {
        var normalized = resourcePath.Replace('\\', '/').ToLowerInvariant();
        return tokens.Any(token =>
            normalized.Contains($"{token}.png", StringComparison.Ordinal) ||
            normalized.Contains($"{token}_", StringComparison.Ordinal) ||
            normalized.Contains($"_{token}", StringComparison.Ordinal) ||
            normalized.Contains($"/{token}", StringComparison.Ordinal));
    }

    private sealed record SceneAssetUsage(string NodeName, string NodeType, string ResourcePath, bool ResourceExists);

    private sealed record AcceptanceContract(
        string Kind,
        IReadOnlyList<string> RequiredMarkers,
        bool AssetUsageAcceptance = false,
        bool MapEntryAcceptance = false,
        bool BattleSceneAcceptance = false,
        bool RewardFlowAcceptance = false,
        bool MainSceneHostUiHiddenAcceptance = false,
        bool FinalAcceptance = false,
        bool StaticAcceptanceOnly = false);
}

internal sealed record PrototypeGoalAcceptanceValidationResult(string Kind, string Status, string? Reason = null)
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

    public static PrototypeGoalAcceptanceValidationResult Failed(string kind, string? reason = null)
    {
        return new PrototypeGoalAcceptanceValidationResult(kind, "failed", reason);
    }
}
