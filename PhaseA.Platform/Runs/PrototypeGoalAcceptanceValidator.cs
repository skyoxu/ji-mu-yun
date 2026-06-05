using System.Text.RegularExpressions;
using System.Text.Json;
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

        var contract = GameTypeRouteStrategies.Resolve(project).ResolveAcceptanceContract(project, goal);
        if (contract is null)
        {
            return PrototypeGoalAcceptanceValidationResult.NotRun();
        }

        var testsPath = Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs");
        var corePath = Path.Combine(project.RepoPath, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs");
        var assetUsageFailureReason = GetRpgSceneAssetUsageFailureReason(project.RepoPath, requireSplitScenes: contract.FinalAcceptance);
        if (contract.AssetUsageAcceptance && assetUsageFailureReason is not null)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, assetUsageFailureReason);
        }

        var mapEntryFailureReason = GetRpgMapEntryAcceptanceFailureReason(project.RepoPath);
        if (contract.MapEntryAcceptance && mapEntryFailureReason is not null)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, mapEntryFailureReason);
        }

        var battleSceneFailureReason = GetRpgBattleSceneAcceptanceFailureReason(project.RepoPath);
        if (contract.BattleSceneAcceptance && battleSceneFailureReason is not null)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, battleSceneFailureReason);
        }

        var rewardFlowFailureReason = GetRpgRewardFlowAcceptanceFailureReason(project.RepoPath);
        if (contract.RewardFlowAcceptance && rewardFlowFailureReason is not null)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, rewardFlowFailureReason);
        }

        if (contract.MainSceneHostUiHiddenAcceptance && !HasMainSceneDefaultPrototypeHostUiHidden(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "main_scene_default_ui_not_hidden");
        }

        if (contract.FinalAcceptance && !HasRpgFinalAcceptanceFiles(project.RepoPath))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "missing_rpg_final_acceptance_contract");
        }

        if (contract.FinalAcceptance && !HasRpgPrototypeContractValueAcceptance(project))
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "rpg_form_contract_values_not_reflected");
        }

        var missingMarkers = GetMissingRequiredMarkers(testsPath, corePath, contract.RequiredMarkers);
        if (missingMarkers.Count > 0)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(
                contract.Kind,
                "missing_required_core_markers: " + string.Join("; ", missingMarkers.Select(marker => $"missing_marker={marker}")));
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
            await ShutdownDotnetBuildServerAsync(project.RepoPath, processRunner, linked.Token);
            var validationEnvironment = PrototypeValidationProcessEnvironment.Create(project.RepoPath);
            var coreTestIsolationArguments = PrototypeValidationProcessEnvironment.CreateMsBuildIsolationArguments(validationEnvironment, "core-tests");
            var result = await processRunner.RunAsync(
                new HostedProcessCommand(
                    "dotnet",
                    [
                        "test",
                        testProject,
                        "--filter",
                        "FullyQualifiedName~DqRpgPrototypeLoopTests",
                        .. coreTestIsolationArguments
                    ],
                    project.RepoPath,
                    validationEnvironment),
                linked.Token);
            if (result.ExitCode != 0)
            {
                if (ShouldRetryCoreTestAfterRestore(testProject, result))
                {
                    await ShutdownDotnetBuildServerAsync(project.RepoPath, processRunner, linked.Token);
                    var retryEnvironment = PrototypeValidationProcessEnvironment.Create(project.RepoPath);
                    var retryIsolationArguments = PrototypeValidationProcessEnvironment.CreateMsBuildIsolationArguments(retryEnvironment, "core-tests-retry");
                    await processRunner.RunAsync(
                        new HostedProcessCommand(
                            "dotnet",
                            [
                                "restore",
                                testProject,
                                .. retryIsolationArguments
                            ],
                            project.RepoPath,
                            retryEnvironment),
                        linked.Token);
                    var retryResult = await processRunner.RunAsync(
                        new HostedProcessCommand(
                            "dotnet",
                            [
                                "test",
                                testProject,
                                "--filter",
                                "FullyQualifiedName~DqRpgPrototypeLoopTests",
                                .. retryIsolationArguments
                            ],
                            project.RepoPath,
                            retryEnvironment),
                        linked.Token);
                    if (retryResult.ExitCode == 0)
                    {
                        result = retryResult;
                    }
                    else
                    {
                        return PrototypeGoalAcceptanceValidationResult.Failed(
                            contract.Kind,
                            "core_tests_failed",
                            ExtractDotnetTestFailureDetails(retryResult));
                    }
                }
                else
                {
                    return PrototypeGoalAcceptanceValidationResult.Failed(
                        contract.Kind,
                        "core_tests_failed",
                        ExtractDotnetTestFailureDetails(result));
                }
            }

            if (result.ExitCode != 0)
            {
                return PrototypeGoalAcceptanceValidationResult.Failed(
                    contract.Kind,
                    "core_tests_failed",
                    ExtractDotnetTestFailureDetails(result));
            }

            var godotProject = Path.Combine(project.RepoPath, "GodotGame.csproj");
            if (File.Exists(godotProject))
            {
                var godotBuildStabilityArguments = PrototypeValidationProcessEnvironment.CreateMsBuildStabilityArguments();
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
                            .. godotBuildStabilityArguments
                        ],
                        project.RepoPath,
                        validationEnvironment),
                    linked.Token);
                if (buildResult.ExitCode != 0)
                {
                    return PrototypeGoalAcceptanceValidationResult.Failed(
                        contract.Kind,
                        "godot_project_build_failed",
                        ExtractProcessFailureDetails(buildResult));
                }
            }

            return PrototypeGoalAcceptanceValidationResult.Pass(contract.Kind);
        }
        catch (OperationCanceledException)
        {
            return PrototypeGoalAcceptanceValidationResult.Failed(contract.Kind, "acceptance_validation_timeout");
        }
    }

    private static async Task ShutdownDotnetBuildServerAsync(
        string repoPath,
        IHostedProcessRunner processRunner,
        CancellationToken cancellationToken)
    {
        try
        {
            await processRunner.RunAsync(
                new HostedProcessCommand(
                    "dotnet",
                    ["build-server", "shutdown"],
                    repoPath,
                    PrototypeValidationProcessEnvironment.Create(repoPath)),
                cancellationToken);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch
        {
        }
    }

    private static bool ShouldRetryCoreTestAfterRestore(string testProject, HostedProcessResult result)
    {
        var details = ExtractDotnetTestFailureDetails(result) ?? "";
        if (!details.Contains("CS0246", StringComparison.OrdinalIgnoreCase) ||
            (!details.Contains("Xunit", StringComparison.OrdinalIgnoreCase) &&
             !details.Contains("FluentAssertions", StringComparison.OrdinalIgnoreCase)))
        {
            return false;
        }

        if (!File.Exists(testProject))
        {
            return false;
        }

        var projectText = File.ReadAllText(testProject);
        return projectText.Contains("PackageReference Include=\"xunit\"", StringComparison.OrdinalIgnoreCase) &&
               projectText.Contains("PackageReference Include=\"FluentAssertions\"", StringComparison.OrdinalIgnoreCase);
    }

    private static string? ExtractDotnetTestFailureDetails(HostedProcessResult result)
    {
        var text = string.Join(
            Environment.NewLine,
            new[] { result.Stdout, result.Stderr }.Where(value => !string.IsNullOrWhiteSpace(value)));
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        var lines = text
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var details = new List<string>();
        foreach (var line in lines)
        {
            if (IsDotnetTestFailureSignal(line))
            {
                AddDistinctDetail(details, line);
            }

            if (details.Count >= 12)
            {
                break;
            }
        }

        return details.Count == 0 ? ExtractProcessFailureDetails(result) : string.Join(" | ", details);
    }

    private static bool IsDotnetTestFailureSignal(string line)
    {
        return line.Contains("失败 ", StringComparison.Ordinal) ||
               line.Contains("Failed", StringComparison.OrdinalIgnoreCase) ||
               line.Contains("InvalidOperationException", StringComparison.Ordinal) ||
               line.Contains(".cs(", StringComparison.Ordinal) ||
               line.Contains("Assert.", StringComparison.Ordinal) ||
               line.Contains("Expected:", StringComparison.Ordinal) ||
               line.Contains("Actual:", StringComparison.Ordinal) ||
               line.Contains("Error Message", StringComparison.OrdinalIgnoreCase) ||
               line.Contains("错误消息", StringComparison.Ordinal) ||
               line.Contains("DqRpgPrototypeLoopTests.", StringComparison.Ordinal);
    }

    private static string? ExtractProcessFailureDetails(HostedProcessResult result)
    {
        var text = FirstNonEmpty(result.Stdout, result.Stderr);
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        return TrimDetail(text);
    }

    private static void AddDistinctDetail(List<string> details, string line)
    {
        var trimmed = TrimDetail(line);
        if (!string.IsNullOrWhiteSpace(trimmed) &&
            !details.Any(existing => string.Equals(existing, trimmed, StringComparison.OrdinalIgnoreCase)))
        {
            details.Add(trimmed);
        }
    }

    private static string TrimDetail(string value)
    {
        var trimmed = value.Trim();
        return trimmed.Length <= 700 ? trimmed : trimmed[..700];
    }

    private static string? FirstNonEmpty(params string?[] values)
    {
        return values.FirstOrDefault(value => !string.IsNullOrWhiteSpace(value));
    }

    private static IReadOnlyList<string> GetMissingRequiredMarkers(string testsPath, string corePath, IReadOnlyList<string> requiredMarkers)
    {
        var searchFiles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        AddMarkerSearchFile(searchFiles, testsPath);
        AddMarkerSearchFile(searchFiles, corePath);
        AddMarkerSearchDirectory(searchFiles, Path.GetDirectoryName(testsPath));
        AddMarkerSearchDirectory(searchFiles, Path.GetDirectoryName(corePath));

        var text = string.Join(
            Environment.NewLine,
            searchFiles.Select(path => File.ReadAllText(path)));

        return requiredMarkers
            .Where(marker => !text.Contains(marker, StringComparison.Ordinal))
            .ToArray();
    }

    private static void AddMarkerSearchFile(HashSet<string> searchFiles, string path)
    {
        if (File.Exists(path))
        {
            searchFiles.Add(path);
        }
    }

    private static void AddMarkerSearchDirectory(HashSet<string> searchFiles, string? directory)
    {
        if (string.IsNullOrWhiteSpace(directory) || !Directory.Exists(directory))
        {
            return;
        }

        foreach (var path in Directory.EnumerateFiles(directory, "*.cs", SearchOption.TopDirectoryOnly))
        {
            searchFiles.Add(path);
        }
    }

    private static bool HasRpgFinalAcceptanceFiles(string repoPath)
    {
        var requiredFiles = new[]
        {
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs"),
            Path.Combine(repoPath, "Game.Godot", "Scripts", "Prototypes", "PrototypeCatalog.cs"),
            Path.Combine(repoPath, "Game.Godot", "Scenes", "Main.tscn")
        };
        if (requiredFiles.Any(path => !File.Exists(path)))
        {
            return false;
        }

        if (!HasRpgSceneAssetUsage(repoPath, requireSplitScenes: true))
        {
            return false;
        }

        var catalogText = File.ReadAllText(Path.Combine(repoPath, "Game.Godot", "Scripts", "Prototypes", "PrototypeCatalog.cs"));
        return catalogText.Contains("res://Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn", StringComparison.Ordinal) &&
               HasMainSceneDefaultPrototypeHostUiHidden(repoPath) &&
               HasRpgMapEntryAcceptanceFiles(repoPath) &&
               HasRpgBattleSceneAcceptanceFiles(repoPath);
    }

    private static bool HasRpgPrototypeContractValueAcceptance(ProjectSnapshot project)
    {
        var contractPath = Path.Combine(project.MetaPath, "routes", "prototype-contract", "latest.json");
        if (!File.Exists(contractPath))
        {
            return false;
        }

        string contractText;
        try
        {
            contractText = File.ReadAllText(contractPath);
        }
        catch (IOException)
        {
            return false;
        }

        if (!TryReadFormFields(contractText, out var formText))
        {
            return false;
        }

        var corePath = Path.Combine(project.RepoPath, "Game.Core", "Prototypes", "DqRpgPrototypeLoop.cs");
        var testsPath = Path.Combine(project.RepoPath, "Game.Core.Tests", "Prototypes", "DqRpgPrototypeLoopTests.cs");
        if (!File.Exists(corePath) || !File.Exists(testsPath))
        {
            return false;
        }

        var implementationText = File.ReadAllText(corePath);
        var requiredNumbers = ExtractRpgRequiredNumbers(formText);
        if (requiredNumbers.Count == 0)
        {
            return true;
        }

        return requiredNumbers.All(number => ContainsWholeNumber(implementationText, number));
    }

    private static bool TryReadFormFields(string contractText, out string formText)
    {
        formText = "";
        try
        {
            using var document = JsonDocument.Parse(contractText);
            if (!document.RootElement.TryGetProperty("form_fields", out var formFields))
            {
                return false;
            }

            formText = formFields.GetRawText();
            return !string.IsNullOrWhiteSpace(formText);
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static IReadOnlyList<int> ExtractRpgRequiredNumbers(string formText)
    {
        var normalized = formText.Replace("\\u0025", "%", StringComparison.Ordinal);
        var requirements = new List<int>();
        AddIfMentioned(normalized, requirements, 100, "100");
        AddIfMentioned(normalized, requirements, 10, "10%");
        AddIfMentioned(normalized, requirements, 10, "10步");
        AddIfMentioned(normalized, requirements, 10, "10 ATK", "10点攻击");
        AddIfMentioned(normalized, requirements, 2, "2点防御", "2 DEF");
        AddIfMentioned(normalized, requirements, 30, "30点生命", "30 HP");
        AddIfMentioned(normalized, requirements, 5, "5点攻击", "5 ATK");
        AddIfMentioned(normalized, requirements, 5, "5点生命", "5 HP");
        AddIfMentioned(normalized, requirements, 2, "2点攻击", "2 ATK");
        AddIfMentioned(normalized, requirements, 1, "1点防御", "1 DEF");
        AddIfMentioned(normalized, requirements, 15, "15场", "15 battles");
        return requirements.Distinct().ToArray();
    }

    private static void AddIfMentioned(string text, ICollection<int> requirements, int value, params string[] markers)
    {
        if (markers.Any(marker => text.Contains(marker, StringComparison.OrdinalIgnoreCase)))
        {
            requirements.Add(value);
        }
    }

    private static bool ContainsWholeNumber(string text, int value)
    {
        return Regex.IsMatch(text, $@"(?<!\d){value}(?!\d)", RegexOptions.CultureInvariant);
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

    private static string? GetRpgMapEntryAcceptanceFailureReason(string repoPath)
    {
        var mainScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn");
        var mainScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs");
        var mapScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn");
        var missingFiles = new[] { mainScene, mainScript, mapScene }
            .Where(path => !File.Exists(path))
            .Select(path => Path.GetRelativePath(repoPath, path).Replace('\\', '/'))
            .ToList();
        if (missingFiles.Count > 0)
        {
            return "missing_rpg_map_entry_contract: " + string.Join("; ", missingFiles.Select(path => $"missing_file={path}"));
        }

        var mapScript = ResolveSceneScriptPath(repoPath, mapScene, Path.Combine("Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs"));
        if (string.IsNullOrWhiteSpace(mapScript) || !File.Exists(mapScript))
        {
            return "missing_rpg_map_entry_contract: missing_file=Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs";
        }

        var mainSceneText = File.ReadAllText(mainScene);
        var mainScriptText = File.ReadAllText(mainScript);
        var mapSceneText = File.ReadAllText(mapScene);
        var mapScriptText = File.ReadAllText(mapScript);

        var missing = new List<string>();
        AddMissing(missing, mainSceneText.Contains("StartButton", StringComparison.Ordinal), "main_scene_missing_StartButton");
        AddMissing(missing, mainSceneText.Contains("Start Adventure", StringComparison.Ordinal), "main_scene_missing_Start_Adventure_text");
        AddMissing(missing, mainSceneText.Contains("MapScene", StringComparison.Ordinal), "main_scene_missing_MapScene_instance");
        AddMissing(missing, mainSceneText.Contains("parent=\"CanvasLayer/UI\"", StringComparison.Ordinal), "main_scene_MapScene_not_under_CanvasLayer_UI");
        AddMissing(missing, mainSceneText.Contains("anchors_preset = 15", StringComparison.Ordinal), "main_scene_missing_full_viewport_anchor");
        AddMissing(missing, HasStartAdventureMapEntry(mainScriptText), "main_script_StartButton_not_wired_to_ShowMapScene_or_StartRun");
        AddMissing(missing, mainScriptText.Contains("CanvasLayer/UI/MapScene", StringComparison.Ordinal), "main_script_missing_CanvasLayer_UI_MapScene_lookup");
        AddMissing(missing, HasMapSceneVisibilityEntry(mainScriptText), "main_script_missing_MapScene_visible_true_entry");
        AddMissing(missing, mapSceneText.Contains("MapScene", StringComparison.Ordinal), "map_scene_missing_MapScene_root");
        AddMissing(missing, HasUniqueExtResourceIds(mapSceneText), "map_scene_ext_resource_ids_not_unique");
        AddMissing(missing, HasSceneRootScript(mapSceneText), "map_scene_root_missing_script_ext_resource");
        AddMissing(missing, mapSceneText.Contains("TrackLayer", StringComparison.Ordinal), "map_scene_missing_TrackLayer");
        AddMissing(missing, mapSceneText.Contains("custom_minimum_size = Vector2(600, 600)", StringComparison.Ordinal), "map_scene_missing_600x600_custom_minimum_size");
        AddMissing(missing, HasSceneNodeUnderAnyParent(mapSceneText, "RpgMapAsset", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer", "TrackLayer"), "map_scene_RpgMapAsset_not_under_TrackLayer");
        AddMissing(missing, HasSceneNodeUnderAnyParent(mapSceneText, "Grid", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer", "TrackLayer"), "map_scene_Grid_not_under_TrackLayer");
        AddMissing(missing, HasSceneNodeUnderAnyParent(mapSceneText, "Overlay", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer", "TrackLayer"), "map_scene_Overlay_not_under_TrackLayer");
        AddMissing(missing, HasSceneNodeUnderAnyParent(mapSceneText, "RpgPlayerAsset", "Panel/Margin/VBox/TrackFrame/TrackMargin/TrackLayer/Overlay", "TrackLayer/Overlay", "TrackLayer"), "map_scene_RpgPlayerAsset_not_under_TrackLayer_or_Overlay");
        AddMissing(missing, mapSceneText.Contains("Grid", StringComparison.Ordinal), "map_scene_missing_Grid");
        AddMissing(missing, mapSceneText.Contains("RpgMapAsset", StringComparison.Ordinal), "map_scene_missing_RpgMapAsset");
        AddMissing(missing, mapSceneText.Contains("RpgPlayerAsset", StringComparison.Ordinal), "map_scene_missing_RpgPlayerAsset");
        AddMissing(missing, mapSceneText.Contains("RpgEnemyAsset", StringComparison.Ordinal), "map_scene_missing_RpgEnemyAsset");
        AddMissing(missing, mapScriptText.Contains("TrackLayer", StringComparison.Ordinal), "map_script_missing_TrackLayer_lookup");
        AddMissing(missing, HasGridToVisiblePosition(mapScriptText), "map_script_missing_GridToPosition_or_MapTokenPosition");
        AddMissing(missing, HasPlayerVisibilityRestore(mapScriptText), "map_script_missing_player_visibility_restore");
        AddMissing(missing, HasMapMovementEntry(mapScriptText), "map_script_missing_MovePlayer_or_MoveOnMap_or_TryHandleMapKey");
        AddMissing(missing, HasEncounterEntry(mapScriptText), "map_script_missing_EncounterEntered_or_EncounterPressed_or_EncounterTriggered");

        return missing.Count == 0
            ? null
            : "missing_rpg_map_entry_contract: " + string.Join("; ", missing);
    }

    private static bool HasRpgMapEntryAcceptanceFiles(string repoPath)
    {
        return GetRpgMapEntryAcceptanceFailureReason(repoPath) is null;
    }

    private static void AddMissing(List<string> missing, bool condition, string reason)
    {
        if (!condition)
        {
            missing.Add(reason);
        }
    }

    private static string? GetRpgBattleSceneAcceptanceFailureReason(string repoPath)
    {
        var battleScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn");
        var battleScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs");
        var missingFiles = new[] { battleScene, battleScript }
            .Where(path => !File.Exists(path))
            .Select(path => Path.GetRelativePath(repoPath, path).Replace('\\', '/'))
            .ToList();
        if (missingFiles.Count > 0)
        {
            return "missing_rpg_battle_scene_contract: " + string.Join("; ", missingFiles.Select(path => $"missing_file={path}"));
        }

        var battleSceneText = File.ReadAllText(battleScene);
        var battleScriptText = File.ReadAllText(battleScript);
        var battleAssetUsages = ReadSceneAssetUsages(repoPath, battleScene).ToList();
        var missing = new List<string>();
        AddMissing(missing, battleSceneText.Contains("BattleScene", StringComparison.Ordinal), "battle_scene_missing_BattleScene_node");
        AddMissing(missing, battleSceneText.Contains("AttackButton", StringComparison.Ordinal) || battleSceneText.Contains("Attack", StringComparison.Ordinal), "battle_scene_missing_AttackButton");
        AddMissing(missing, HasRequiredRpgAssetUsage(battleAssetUsages, "RpgPlayerAsset", IsPlayerAssetPath), "battle_scene_missing_RpgPlayerAsset_Texture2D");
        AddMissing(missing, HasRequiredRpgAssetUsage(battleAssetUsages, "RpgEnemyAsset", IsEnemyAssetPath), "battle_scene_missing_RpgEnemyAsset_Texture2D");
        AddMissing(missing, battleScriptText.Contains("ResolveAttackTurn", StringComparison.Ordinal) || battleScriptText.Contains("ResolveBattle", StringComparison.Ordinal), "battle_script_missing_ResolveBattle_or_ResolveAttackTurn");
        AddMissing(missing, !battleScriptText.Contains("_loop.ResolveBattle(_state", StringComparison.Ordinal), "battle_script_still_only_delegates_to_main_loop_ResolveBattle");
        AddMissing(missing, battleScriptText.Contains("BattleFinished", StringComparison.Ordinal), "battle_script_missing_BattleFinished");
        return missing.Count == 0
            ? null
            : "missing_rpg_battle_scene_contract: " + string.Join("; ", missing);
    }

    private static bool HasRpgBattleSceneAcceptanceFiles(string repoPath)
    {
        return GetRpgBattleSceneAcceptanceFailureReason(repoPath) is null;
    }

    private static string? GetRpgRewardFlowAcceptanceFailureReason(string repoPath)
    {
        var mainScript = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "Scripts", "DqRpgPrototype.cs");
        var mapScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn");
        var missingFiles = new[] { mainScript, mapScene }
            .Where(path => !File.Exists(path))
            .Select(path => Path.GetRelativePath(repoPath, path).Replace('\\', '/'))
            .ToList();
        if (missingFiles.Count > 0)
        {
            return "missing_rpg_reward_flow_contract: " + string.Join("; ", missingFiles.Select(path => $"missing_file={path}"));
        }

        var mapScript = ResolveSceneScriptPath(repoPath, mapScene, Path.Combine("Game.Godot", "Prototypes", "dq-rpg", "Scripts", "MapScene.cs"));
        if (string.IsNullOrWhiteSpace(mapScript) || !File.Exists(mapScript))
        {
            return "missing_rpg_reward_flow_contract: missing_file=Game.Godot/Prototypes/dq-rpg/Scripts/MapScene.cs";
        }

        var mainScriptText = File.ReadAllText(mainScript);
        var mapScriptText = File.ReadAllText(mapScript);
        var missing = new List<string>();
        AddMissing(missing, HasRewardListGuard(mainScriptText), "reward_flow_missing_reward_list_guard");
        AddMissing(missing, !mainScriptText.Contains("if (isVictory && rewards.Count > 0)", StringComparison.Ordinal), "reward_flow_still_uses_unreachable_isVictory_reward_guard");
        AddMissing(missing, HasRewardEntry(repoPath, mainScriptText), "reward_flow_missing_reward_entry");
        AddMissing(missing, HasRewardReturnToMapEntry(mainScriptText), "reward_flow_missing_return_to_map_after_reward");
        AddMissing(missing, HasRewardReturnFeedback(mainScriptText, mapScriptText), "reward_flow_missing_map_return_feedback");
        AddMissing(missing, HasPlayerVisibilityRestore(mapScriptText) || HasMainScriptRewardRefresh(mainScriptText), "reward_flow_missing_player_visibility_or_view_refresh_restore");

        return missing.Count == 0
            ? null
            : "missing_rpg_reward_flow_contract: " + string.Join("; ", missing);
    }

    private static bool HasRpgRewardFlowAcceptanceFiles(string repoPath)
    {
        return GetRpgRewardFlowAcceptanceFailureReason(repoPath) is null;
    }

    private static bool HasStartAdventureMapEntry(string mainScriptText)
    {
        return mainScriptText.Contains("Pressed += ShowMapScene", StringComparison.Ordinal) ||
               (mainScriptText.Contains("Pressed += StartRun", StringComparison.Ordinal) &&
                mainScriptText.Contains("StartRun", StringComparison.Ordinal) &&
                (mainScriptText.Contains("ShowMapScene()", StringComparison.Ordinal) ||
                 mainScriptText.Contains("StartAdventure(", StringComparison.Ordinal)));
    }

    private static bool HasMapSceneVisibilityEntry(string mainScriptText)
    {
        return mainScriptText.Contains("_mapScene.Visible = true", StringComparison.Ordinal) ||
               mainScriptText.Contains("mapVisible", StringComparison.Ordinal) ||
               mainScriptText.Contains("StartAdventure(", StringComparison.Ordinal);
    }

    private static bool HasGridToVisiblePosition(string mapScriptText)
    {
        return mapScriptText.Contains("GridToPosition", StringComparison.Ordinal) ||
               mapScriptText.Contains("MapTokenPosition", StringComparison.Ordinal);
    }

    private static bool HasPlayerVisibilityRestore(string mapScriptText)
    {
        return mapScriptText.Contains("_player.Visible = true", StringComparison.Ordinal) ||
               mapScriptText.Contains("_playerAsset.Visible = true", StringComparison.Ordinal) ||
               mapScriptText.Contains("_playerToken", StringComparison.Ordinal);
    }

    private static bool HasMapMovementEntry(string mapScriptText)
    {
        return ContainsAny(mapScriptText, "MovePlayer", "MoveOnMap", "TryHandleMapKey");
    }

    private static bool HasEncounterEntry(string mapScriptText)
    {
        return ContainsAny(mapScriptText, "EncounterEntered", "EncounterPressed", "EncounterTriggered");
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.Ordinal));
    }

    private static bool HasRewardListGuard(string mainScriptText)
    {
        return mainScriptText.Contains("rewards.Count > 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("rewards.Count <= 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("rewards.Count == 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("RewardOptions.Count > 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("RewardOptions.Count <= 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("RewardOptions.Count == 0", StringComparison.Ordinal) ||
               mainScriptText.Contains("rewards.Count", StringComparison.Ordinal) ||
               mainScriptText.Contains("RewardOptions.Count", StringComparison.Ordinal) ||
               mainScriptText.Contains("_currentRewards.Count", StringComparison.Ordinal);
    }

    private static bool HasRewardEntry(string repoPath, string mainScriptText)
    {
        return HasRewardSceneEntry(mainScriptText) ||
               HasBattleSceneOwnedRewardEntry(repoPath, mainScriptText) ||
               HasMainScriptOwnedRewardPanelEntry(mainScriptText);
    }

    private static bool HasRewardSceneEntry(string mainScriptText)
    {
        return mainScriptText.Contains("ShowRewardScene(rewards)", StringComparison.Ordinal) ||
               Regex.IsMatch(
                   mainScriptText,
                   @"ShowRewardScene\s*\(\s*(?:[\w.]+\.)?IReadOnlyList<[^>]+>\s+rewards\s*\)",
                   RegexOptions.CultureInvariant);
    }

    private static bool HasRewardReturnToMapEntry(string mainScriptText)
    {
        return mainScriptText.Contains("ShowMapScene()", StringComparison.Ordinal) ||
               (mainScriptText.Contains("ApplyReward", StringComparison.Ordinal) &&
                 mainScriptText.Contains("RefreshView()", StringComparison.Ordinal) &&
                 ContainsAny(mainScriptText, "ResumeAfterReward", "ShowRewardReturnStatus", "ApplyState", "_rewardPanel.Visible = false", "DebugGetRpgRewardFlowContract", "rpg_reward_flow_contract"));
    }

    private static bool HasRewardReturnFeedback(string mainScriptText, string mapScriptText)
    {
        return ContainsAny(mapScriptText, "ShowRewardReturnStatus", "ApplyState", "ResumeAfterReward") ||
               ContainsAny(mainScriptText, "ShowRewardReturnStatus", "ApplyState", "ResumeAfterReward", "Return to the map", "Battle reward selected", "rpg_reward_flow_contract");
    }

    private static bool HasMainScriptRewardRefresh(string mainScriptText)
    {
        return mainScriptText.Contains("RefreshView()", StringComparison.Ordinal) &&
               ContainsAny(mainScriptText, "SelectReward", "ApplyRewardSelection", "OnRewardSelected");
    }

    private static bool HasMainScriptOwnedRewardPanelEntry(string mainScriptText)
    {
        return ContainsAny(mainScriptText, "SelectReward", "ApplyRewardSelection", "OnRewardSelected") &&
               mainScriptText.Contains("ApplyReward", StringComparison.Ordinal) &&
               HasRewardChoiceCountContract(mainScriptText) &&
               ContainsAny(mainScriptText, "_rewardButtons", "RewardButtons", "RewardOptionOne", "RewardOptionTwo", "RewardOptionThree", "RewardOptions") &&
               ContainsAny(mainScriptText, "_rewardPanel.Visible = true", "rewardVisible = true", "ShowRewardScene") &&
               ContainsAny(mainScriptText, "_rewardPanel.Visible = false", "rewardVisible = false", "ShowMapScene()", "RefreshView()");
    }

    private static bool HasRewardChoiceCountContract(string mainScriptText)
    {
        return ContainsAny(
            mainScriptText,
            "RewardOptions.Count",
            "rewards.Count",
            "_rewardButtons.Length",
            "choice_count",
            "choice count",
            "exactly three",
            "== 3",
            "Count == 3",
            "Count != 3") ||
            Regex.IsMatch(mainScriptText, @"\[\s*2\s*\]", RegexOptions.CultureInvariant);
    }

    private static bool HasBattleSceneOwnedRewardEntry(string repoPath, string mainScriptText)
    {
        var battleScene = Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn");
        var battleScript = ResolveSceneScriptPath(repoPath, battleScene, Path.Combine("Game.Godot", "Prototypes", "dq-rpg", "Scripts", "BattleScene.cs"));
        if (string.IsNullOrWhiteSpace(battleScript) || !File.Exists(battleScript))
        {
            return false;
        }

        var battleScriptText = File.ReadAllText(battleScript);
        return mainScriptText.Contains("RewardSelected", StringComparison.Ordinal) &&
               mainScriptText.Contains("ApplyReward", StringComparison.Ordinal) &&
               HasRewardSelectionHandler(mainScriptText) &&
               ContainsAny(mainScriptText, "ShowRewardReturnStatus", "ResumeAfterReward", "ApplyState") &&
               battleScriptText.Contains("RewardSelected", StringComparison.Ordinal) &&
               battleScriptText.Contains("RewardOptions.Count", StringComparison.Ordinal) &&
               ContainsAny(battleScriptText, "== 3", "Count == 3", "Count != 3") &&
               ContainsAny(battleScriptText, "RewardOptionOne", "RewardOptionTwo", "RewardOptionThree", "ConfigureRewardButton");
    }

    private static bool HasRewardSelectionHandler(string mainScriptText)
    {
        return ContainsAny(mainScriptText, "ApplyBattleReward", "ApplyRewardSelection", "OnRewardSelected") ||
               Regex.IsMatch(
                   mainScriptText,
                   @"RewardSelected\s*\+=\s*\w+",
                   RegexOptions.CultureInvariant);
    }

    private static bool HasSceneNodeUnderParent(string sceneText, string nodeName, string parent)
    {
        return Regex.IsMatch(
            sceneText,
            "\\[node\\s+name=\"" + Regex.Escape(nodeName) + "\"[^\\]]*parent=\"" + Regex.Escape(parent) + "\"[^\\]]*\\]",
            RegexOptions.CultureInvariant);
    }

    private static bool HasSceneRootScript(string sceneText)
    {
        var match = Regex.Match(
            sceneText,
            "\\[node\\s+name=\"MapScene\"[^\\]]*\\](?<body>.*?)(?=\\r?\\n\\[node|\\r?\\n\\[connection|\\z)",
            RegexOptions.Singleline | RegexOptions.CultureInvariant);
        return match.Success &&
               Regex.IsMatch(match.Groups["body"].Value, "script\\s*=\\s*ExtResource\\(\"[^\"]+\"\\)", RegexOptions.CultureInvariant);
    }

    private static bool HasUniqueExtResourceIds(string sceneText)
    {
        var ids = Regex.Matches(
                sceneText,
                "\\[ext_resource\\s+[^\\]]*id=\"(?<id>[^\"]+)\"[^\\]]*\\]",
                RegexOptions.CultureInvariant)
            .Cast<Match>()
            .Select(match => match.Groups["id"].Value)
            .ToList();
        return ids.Count == ids.Distinct(StringComparer.Ordinal).Count();
    }

    private static bool HasSceneNodeUnderAnyParent(string sceneText, string nodeName, params string[] parents)
    {
        return parents.Any(parent => HasSceneNodeUnderParent(sceneText, nodeName, parent));
    }

    private static string? ResolveSceneScriptPath(string repoPath, string scenePath, string fallbackRelativePath)
    {
        var sceneText = File.ReadAllText(scenePath);
        var scriptResource = Regex.Matches(
                sceneText,
                "\\[ext_resource\\s+[^\\]]*type=\"Script\"[^\\]]*path=\"(?<path>[^\"]+)\"[^\\]]*id=\"(?<id>[^\"]+)\"[^\\]]*\\]",
                RegexOptions.CultureInvariant)
            .Cast<Match>()
            .Select(match => match.Groups["path"].Value)
            .FirstOrDefault(path => path.EndsWith(".cs", StringComparison.OrdinalIgnoreCase));
        if (!string.IsNullOrWhiteSpace(scriptResource))
        {
            return ResolveGodotResourcePath(repoPath, scriptResource);
        }

        return Path.Combine(repoPath, fallbackRelativePath);
    }

    private static string ResolveGodotResourcePath(string repoPath, string resourcePath)
    {
        const string resPrefix = "res://";
        return resourcePath.StartsWith(resPrefix, StringComparison.Ordinal)
            ? Path.Combine(repoPath, resourcePath[resPrefix.Length..].Replace('/', Path.DirectorySeparatorChar))
            : Path.Combine(repoPath, resourcePath.Replace('/', Path.DirectorySeparatorChar));
    }

    private static bool HasRpgSceneAssetUsage(string repoPath, bool requireSplitScenes)
    {
        return GetRpgSceneAssetUsageFailureReason(repoPath, requireSplitScenes) is null;
    }

    private static string? GetRpgSceneAssetUsageFailureReason(string repoPath, bool requireSplitScenes)
    {
        var sceneFiles = new[]
        {
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "DqRpgPrototype.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "MapScene.tscn"),
            Path.Combine(repoPath, "Game.Godot", "Prototypes", "dq-rpg", "BattleScene.tscn")
        };
        if (!File.Exists(sceneFiles[0]))
        {
            return "missing_rpg_prototype_scene";
        }

        if (requireSplitScenes && sceneFiles.Skip(1).Any(path => !File.Exists(path)))
        {
            return "missing_rpg_split_scene_asset_targets";
        }

        if (File.Exists(Path.Combine(repoPath, "Game.Godot", ".gdignore")))
        {
            return "game_godot_gdignore_blocks_rpg_assets";
        }

        var usages = sceneFiles
            .Where(File.Exists)
            .SelectMany(path => ReadSceneAssetUsages(repoPath, path))
            .ToList();
        if (!HasRequiredRpgAssetUsage(usages, "RpgMapAsset", IsMapAssetPath))
        {
            return "missing_rpg_map_asset_usage";
        }

        if (!HasRequiredRpgAssetUsage(usages, "RpgPlayerAsset", IsPlayerAssetPath))
        {
            return "missing_rpg_player_asset_usage";
        }

        if (!HasRequiredRpgAssetUsage(usages, "RpgEnemyAsset", IsEnemyAssetPath))
        {
            return "missing_rpg_enemy_asset_usage";
        }

        return null;
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
}

internal sealed record PrototypeGoalAcceptanceValidationResult(string Kind, string Status, string? Reason = null, string? Details = null)
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

    public static PrototypeGoalAcceptanceValidationResult Failed(string kind, string? reason = null, string? details = null)
    {
        return new PrototypeGoalAcceptanceValidationResult(kind, "failed", reason, details);
    }
}
