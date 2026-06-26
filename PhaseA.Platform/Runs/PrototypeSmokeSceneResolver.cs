using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

internal static class PrototypeSmokeSceneResolver
{
    public static async Task<string?> ResolveLatestAsync(
        PhaseAMetadataStore metadataStore,
        ProjectSnapshot project,
        PrototypeRouteStateWriter stateWriter,
        int? goalIndex = null,
        CancellationToken cancellationToken = default,
        string? sessionId = null,
        ProjectIterationGoalSnapshot? goal = null,
        bool allowMissingGoalStateScene = false,
        bool allowBaselineFallbackForGoalContext = false)
    {
        var hasCurrentGoalContext = goalIndex is > 0 &&
                                    goal is not null &&
                                    !string.IsNullOrWhiteSpace(sessionId);
        if (hasCurrentGoalContext)
        {
            var goalStateScene = ResolveCurrentGoalStateScene(project, stateWriter, goalIndex!.Value, sessionId!, goal!, allowMissingGoalStateScene);
            if (!string.IsNullOrWhiteSpace(goalStateScene))
            {
                return goalStateScene;
            }

            var recordedGoalScene = await ResolveRecordedPrototypeSceneAsync(metadataStore, project, stateWriter, cancellationToken, goal);
            if (!string.IsNullOrWhiteSpace(recordedGoalScene))
            {
                return recordedGoalScene;
            }

            if (!allowBaselineFallbackForGoalContext)
            {
                return null;
            }

            var recordedBaselineScene = await ResolveRecordedPrototypeSceneAsync(metadataStore, project, stateWriter, cancellationToken);
            if (!string.IsNullOrWhiteSpace(recordedBaselineScene))
            {
                return recordedBaselineScene;
            }
        }

        var mainScene = ResolvePrototypeMainSceneFromProjectGodot(project.RepoPath);
        if (!string.IsNullOrWhiteSpace(mainScene))
        {
            return mainScene;
        }

        if (goalIndex is > 0 && !hasCurrentGoalContext)
        {
            foreach (var state in new[]
                     {
                         stateWriter.ReadLatestNeedsFixState(project, goalIndex.Value),
                         stateWriter.ReadLatestExecuteNextGoalState(project, goalIndex.Value)
                     })
            {
                var scene = PrototypeGodotSmokeService.ResolveSmokeScene(project.RepoPath, state);
                if (!string.IsNullOrWhiteSpace(scene))
                {
                    return scene;
                }
            }
        }

        var recordedScene = await ResolveRecordedPrototypeSceneAsync(metadataStore, project, stateWriter, cancellationToken);
        return string.IsNullOrWhiteSpace(recordedScene) ? null : recordedScene;
    }

    private static async Task<string?> ResolveRecordedPrototypeSceneAsync(
        PhaseAMetadataStore metadataStore,
        ProjectSnapshot project,
        PrototypeRouteStateWriter stateWriter,
        CancellationToken cancellationToken,
        ProjectIterationGoalSnapshot? currentGoal = null)
    {
        var runs = await metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        foreach (var run in runs
                     .Where(run =>
                         string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                         string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase) &&
                         IsFreshForGoal(run, currentGoal))
                     .OrderByDescending(run => run.CreatedUtc, StringComparer.Ordinal))
        {
            var scene = PrototypeGodotSmokeService.ResolveSmokeScene(project.RepoPath, run.EvidenceJson);
            if (!string.IsNullOrWhiteSpace(scene))
            {
                return scene;
            }
        }

        var prototypeState = stateWriter.ReadLatestPrototypeState(project);
        if (!IsFreshForGoal(prototypeState, currentGoal))
        {
            return null;
        }

        var stateScene = PrototypeGodotSmokeService.ResolveSmokeScene(project.RepoPath, prototypeState);
        return string.IsNullOrWhiteSpace(stateScene) ? null : stateScene;
    }

    private static bool IsFreshForGoal(RunSnapshot run, ProjectIterationGoalSnapshot? currentGoal)
    {
        if (currentGoal is null)
        {
            return true;
        }

        return HasCurrentGoalIdentity(run.EvidenceJson, currentGoal);
    }

    private static bool IsFreshForGoal(string stateJson, ProjectIterationGoalSnapshot? currentGoal)
    {
        if (currentGoal is null)
        {
            return true;
        }

        if (string.IsNullOrWhiteSpace(stateJson))
        {
            return false;
        }

        try
        {
            using var document = System.Text.Json.JsonDocument.Parse(stateJson);
            var root = document.RootElement;
            return MatchesCurrentGoalIdentity(root, currentGoal);
        }
        catch (System.Text.Json.JsonException)
        {
            return false;
        }
    }

    private static bool HasCurrentGoalIdentity(string? json, ProjectIterationGoalSnapshot currentGoal)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return false;
        }

        try
        {
            using var document = System.Text.Json.JsonDocument.Parse(json);
            return MatchesCurrentGoalIdentity(document.RootElement, currentGoal);
        }
        catch (System.Text.Json.JsonException)
        {
            return false;
        }
    }

    private static bool MatchesCurrentGoalIdentity(System.Text.Json.JsonElement root, ProjectIterationGoalSnapshot currentGoal)
    {
        return MatchesString(root, "session_id", currentGoal.SessionId) ||
               MatchesString(root, "sessionId", currentGoal.SessionId) ||
               MatchesString(root, "goal_id", currentGoal.GoalId) ||
               MatchesString(root, "goalId", currentGoal.GoalId);
    }

    private static bool MatchesString(System.Text.Json.JsonElement root, string propertyName, string expected)
    {
        return root.TryGetProperty(propertyName, out var property) &&
               property.ValueKind == System.Text.Json.JsonValueKind.String &&
               string.Equals(property.GetString(), expected, StringComparison.Ordinal);
    }

    private static string? ResolveCurrentGoalStateScene(
        ProjectSnapshot project,
        PrototypeRouteStateWriter stateWriter,
        int goalIndex,
        string sessionId,
        ProjectIterationGoalSnapshot goal,
        bool allowMissingScene)
    {
        var selectedStates = PrototypeRouteStateSelection.SelectCurrentRouteStates(
            stateWriter.ReadLatestNeedsFixState(project, goalIndex),
            stateWriter.ReadLatestExecuteNextGoalState(project, goalIndex),
            sessionId,
            goal);

        foreach (var state in selectedStates)
        {
            var scene = ResolveGoalStateScene(project.RepoPath, state, allowMissingScene);
            if (!string.IsNullOrWhiteSpace(scene))
            {
                return scene;
            }
        }

        return null;
    }

    private static string? ResolveGoalStateScene(string repoPath, string state, bool allowMissingScene)
    {
        var scene = PrototypeGodotSmokeService.ResolveSmokeScene(repoPath, state);
        if (!string.IsNullOrWhiteSpace(scene) || !allowMissingScene)
        {
            return scene;
        }

        return PrototypeGodotSmokeService.ResolveSafeRecordedSmokeScene(repoPath, state);
    }

    private static string? ResolvePrototypeMainSceneFromProjectGodot(string repoPath)
    {
        var projectGodotPath = Path.Combine(repoPath, "project.godot");
        if (!File.Exists(projectGodotPath))
        {
            return null;
        }

        string? resolvedScene = null;
        foreach (var rawLine in File.ReadLines(projectGodotPath))
        {
            var line = rawLine.Trim();
            if (line.StartsWith(";", StringComparison.Ordinal) ||
                line.StartsWith("#", StringComparison.Ordinal))
            {
                continue;
            }

            var separatorIndex = line.IndexOf('=', StringComparison.Ordinal);
            if (separatorIndex < 0 ||
                !string.Equals(line[..separatorIndex].Trim(), "run/main_scene", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var value = line[(separatorIndex + 1)..].Trim().Trim('"');
            var scene = PrototypeGodotSmokeService.ResolveSceneReference(repoPath, value);
            if (!string.IsNullOrWhiteSpace(scene))
            {
                resolvedScene = IsHostMainScene(scene) ? null : scene;
            }
        }

        return resolvedScene;
    }

    private static bool IsHostMainScene(string scene)
    {
        return string.Equals(scene, "res://Game.Godot/Scenes/Main.tscn", StringComparison.OrdinalIgnoreCase);
    }
}
