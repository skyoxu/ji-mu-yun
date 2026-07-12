using System.Text;
using System.Text.Json;
using PhaseA.Platform.Data;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeRouteStateWriter
{
    public const string ProjectExecutionGuideRelativePath = "meta/project-execution-guide.md";

    private static readonly Encoding Utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true
    };

    public void WriteProjectReadme(ProjectSnapshot project)
    {
        ArgumentNullException.ThrowIfNull(project);

        Directory.CreateDirectory(project.RepoPath);
        var path = Path.Combine(project.RepoPath, "README.md");
        File.WriteAllText(path, BuildProjectReadme(project), Utf8NoBom);
    }

    public void WriteProjectReadme(
        string repoPath,
        string projectId,
        string accountId,
        string projectName,
        string gameName,
        string gameTypeSource,
        string templateRuleId,
        string workspaceId,
        string metaPath)
    {
        Directory.CreateDirectory(repoPath);
        var path = Path.Combine(repoPath, "README.md");
        File.WriteAllText(
            path,
            BuildProjectReadme(projectId, accountId, projectName, gameName, gameTypeSource, templateRuleId, workspaceId, metaPath),
            Utf8NoBom);
    }

    public void WritePrototypeState(ProjectSnapshot project, object payload)
    {
        WriteState(project, Path.Combine("routes", "prototype", "latest.json"), payload);
    }

    public void WritePrototypeSkeletonState(ProjectSnapshot project, object payload)
    {
        WriteState(project, Path.Combine("routes", "prototype-skeleton", "latest.json"), payload);
    }

    public void WritePrototypeRepairState(ProjectSnapshot project, object payload)
    {
        WriteState(project, Path.Combine("routes", "prototype-repair", "latest.json"), payload);
    }

    public string ReadLatestPrototypeRepairState(ProjectSnapshot project)
    {
        return ReadState(project, Path.Combine("routes", "prototype-repair", "latest.json"));
    }

    public void WriteIterationPlanState(ProjectSnapshot project, object payload)
    {
        WriteState(project, Path.Combine("routes", "iteration-plan", "latest.json"), payload);
    }

    public void WriteIterationPlanAnalysisState(ProjectSnapshot project, object payload)
    {
        WriteState(project, Path.Combine("routes", "iteration-plan", "planning-analysis.json"), payload);
    }

    public void WriteIterationPlanPromptEvidenceState(ProjectSnapshot project, object payload)
    {
        WriteState(project, Path.Combine("routes", "iteration-plan", "prompt-evidence.json"), payload);
    }

    public void WriteIterationPlanInteractionRegionState(ProjectSnapshot project, int goalIndex, object payload, string artifactRef = "")
    {
        var goal = goalIndex <= 0 ? "goal-unknown" : $"goal-{goalIndex:00}";
        var relativePath = string.IsNullOrWhiteSpace(artifactRef)
            ? Path.Combine("routes", "iteration-plan", "interaction-regions", $"{goal}.json")
            : artifactRef.Replace('/', Path.DirectorySeparatorChar).StartsWith($"meta{Path.DirectorySeparatorChar}", StringComparison.OrdinalIgnoreCase)
                ? artifactRef.Replace('/', Path.DirectorySeparatorChar)[5..]
                : artifactRef.Replace('/', Path.DirectorySeparatorChar);
        EnsureInteractionArtifactPath(project, relativePath);
        WriteState(project, relativePath, payload);
    }

    public void WriteIterationPlanSessionState(ProjectSnapshot project, string sessionId, object payload)
    {
        WriteState(project, Path.Combine("routes", "iteration-plan", "sessions", $"{sessionId}.json"), payload);
    }

    public void WriteIterationPlanAttemptState(ProjectSnapshot project, string attemptId, object payload)
    {
        WriteState(project, Path.Combine("routes", "iteration-plan", "attempts", $"{attemptId}.json"), payload);
    }

    public string ReadIterationPlanSessionState(ProjectSnapshot project, string sessionId)
    {
        return ReadState(project, Path.Combine("routes", "iteration-plan", "sessions", $"{sessionId}.json"));
    }

    public void ClearIterationPlanState(ProjectSnapshot project)
    {
        DeleteState(project, Path.Combine("routes", "iteration-plan", "latest.json"));
        DeleteState(project, Path.Combine("routes", "iteration-plan", "planning-analysis.json"));
    }

    public void DeleteIterationPlanSessionState(ProjectSnapshot project, string sessionId)
    {
        DeleteState(project, Path.Combine("routes", "iteration-plan", "sessions", $"{sessionId}.json"));
    }

    public void WriteRepairPlanState(ProjectSnapshot project, object payload)
    {
        WriteState(project, Path.Combine("routes", "repair-plan", "latest.json"), payload);
    }

    public void WriteRepairPlanExecutionState(ProjectSnapshot project, int goalIndex, object payload)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        WriteState(project, Path.Combine("routes", "repair-plan", step, "latest.json"), payload);
    }

    public void WriteExecuteNextGoalState(ProjectSnapshot project, int goalIndex, object payload)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        WriteState(project, Path.Combine("routes", "execute-next-goal", step, "latest.json"), payload);
    }

    public void WriteNeedsFixState(ProjectSnapshot project, int goalIndex, object payload)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        WriteState(project, Path.Combine("routes", "needs-fix", step, "latest.json"), payload);
    }

    public void WriteNeedsFixRepairLedger(ProjectSnapshot project, int goalIndex, object payload)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        WriteState(project, Path.Combine("routes", "needs-fix", step, "repair-ledger.json"), payload);
    }

    public void WriteProjectExecutionGuide(
        ProjectSnapshot project,
        PrototypeContractSnapshot prototypeContract,
        string prototypeRecordPath,
        string slug,
        string latestRoute,
        string latestRunId,
        string latestStatus,
        string? defaultScene = null,
        string? playableScene = null,
        string? smokeScene = null)
    {
        ArgumentNullException.ThrowIfNull(project);

        var path = Path.Combine(project.RepoPath, ProjectExecutionGuideRelativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(
            path,
            BuildProjectExecutionGuide(project, prototypeContract, prototypeRecordPath, slug, latestRoute, latestRunId, latestStatus, defaultScene, playableScene, smokeScene),
            Utf8NoBom);
    }

    public string ReadProjectReadme(ProjectSnapshot project)
    {
        var path = Path.Combine(project.RepoPath, "README.md");
        return File.Exists(path) ? File.ReadAllText(path, Encoding.UTF8) : "";
    }

    public string ReadProjectExecutionGuide(ProjectSnapshot project)
    {
        var path = Path.Combine(project.RepoPath, ProjectExecutionGuideRelativePath.Replace('/', Path.DirectorySeparatorChar));
        return File.Exists(path) ? File.ReadAllText(path, Encoding.UTF8) : "";
    }

    public string ReadOrCreateProjectExecutionGuide(ProjectSnapshot project, PrototypeContractSnapshot prototypeContract)
    {
        var existing = ReadProjectExecutionGuide(project);
        if (!string.IsNullOrWhiteSpace(existing))
        {
            return existing;
        }

        var prototypeState = ReadLatestPrototypeState(project);
        if (string.IsNullOrWhiteSpace(prototypeState) && string.IsNullOrWhiteSpace(prototypeContract.Json))
        {
            return "";
        }

        var snapshot = TryReadPrototypeSnapshot(prototypeState);
        WriteProjectExecutionGuide(
            project,
            prototypeContract,
            snapshot.PrototypeRecord,
            snapshot.Slug,
            string.IsNullOrWhiteSpace(snapshot.Route) ? "prototype-7day-playable" : snapshot.Route,
            snapshot.RunId,
            snapshot.Status,
            snapshot.DefaultScene,
            snapshot.PlayableScene,
            snapshot.SmokeScene);
        return ReadProjectExecutionGuide(project);
    }

    public string ReadLatestNeedsFixState(ProjectSnapshot project, int goalIndex)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        return ReadState(project, Path.Combine("routes", "needs-fix", step, "latest.json"));
    }

    public string ReadNeedsFixRepairLedger(ProjectSnapshot project, int goalIndex)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        return ReadState(project, Path.Combine("routes", "needs-fix", step, "repair-ledger.json"));
    }

    public string GetNeedsFixRepairLedgerRelativePath(int goalIndex)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        return ToSlash(Path.Combine("meta", "routes", "needs-fix", step, "repair-ledger.json"));
    }

    public string ReadLatestExecuteNextGoalState(ProjectSnapshot project, int goalIndex)
    {
        var step = goalIndex <= 0 ? "step-unknown" : $"step-{goalIndex:00}";
        return ReadState(project, Path.Combine("routes", "execute-next-goal", step, "latest.json"));
    }

    public string ReadLatestIterationPlanState(ProjectSnapshot project)
    {
        return ReadState(project, Path.Combine("routes", "iteration-plan", "latest.json"));
    }

    public string ReadLatestRepairPlanState(ProjectSnapshot project)
    {
        return ReadState(project, Path.Combine("routes", "repair-plan", "latest.json"));
    }

    public string ReadLatestPrototypeState(ProjectSnapshot project)
    {
        return ReadState(project, Path.Combine("routes", "prototype", "latest.json"));
    }

    public string ReadLatestPrototypeSkeletonState(ProjectSnapshot project)
    {
        return ReadState(project, Path.Combine("routes", "prototype-skeleton", "latest.json"));
    }

    public (string MetadataState, string ProjectMirrorState) ReadPrototypeSkeletonStateCopies(ProjectSnapshot project)
    {
        var relativePath = Path.Combine("routes", "prototype-skeleton", "latest.json");
        return (
            ReadStateFile(Path.Combine(project.MetaPath, relativePath)),
            ReadStateFile(Path.Combine(project.RepoPath, "meta", relativePath)));
    }

    private static void WriteState(ProjectSnapshot project, string relativePath, object payload)
    {
        var serialized = JsonSerializer.Serialize(payload, JsonOptions);
        WriteStateFile(Path.Combine(project.MetaPath, relativePath), serialized);
        WriteStateFile(Path.Combine(project.RepoPath, "meta", relativePath), serialized);
    }

    private static string ReadState(ProjectSnapshot project, string relativePath)
    {
        var path = Path.Combine(project.MetaPath, relativePath);
        var primary = ReadValidJsonStateFile(path);
        if (!string.IsNullOrWhiteSpace(primary))
        {
            return primary;
        }

        var mirroredPath = Path.Combine(project.RepoPath, "meta", relativePath);
        return ReadValidJsonStateFile(mirroredPath);
    }

    private static string ReadStateFile(string path)
    {
        return File.Exists(path) ? File.ReadAllText(path, Encoding.UTF8) : "";
    }

    private static void DeleteState(ProjectSnapshot project, string relativePath)
    {
        var path = Path.Combine(project.MetaPath, relativePath);
        if (File.Exists(path))
        {
            File.Delete(path);
        }

        var mirroredPath = Path.Combine(project.RepoPath, "meta", relativePath);
        if (File.Exists(mirroredPath))
        {
            File.Delete(mirroredPath);
        }
    }

    private static void DeleteStateDirectory(ProjectSnapshot project, string relativePath)
    {
        foreach (var root in new[] { project.MetaPath, Path.Combine(project.RepoPath, "meta") })
        {
            var path = Path.GetFullPath(Path.Combine(root, relativePath));
            var boundary = Path.GetFullPath(root) + Path.DirectorySeparatorChar;
            if (path.StartsWith(boundary, StringComparison.OrdinalIgnoreCase) && Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
    }

    private static void WriteStateFile(string path, string serialized)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var tempPath = Path.Combine(
            Path.GetDirectoryName(path)!,
            $".{Path.GetFileName(path)}.{Guid.NewGuid():N}.tmp");
        try
        {
            File.WriteAllText(tempPath, serialized, Utf8NoBom);
            File.Move(tempPath, path, overwrite: true);
        }
        finally
        {
            if (File.Exists(tempPath))
            {
                File.Delete(tempPath);
            }
        }
    }

    private static string ReadValidJsonStateFile(string path)
    {
        if (!File.Exists(path))
        {
            return "";
        }

        var state = File.ReadAllText(path, Encoding.UTF8);
        try
        {
            using var _ = JsonDocument.Parse(state);
            return state;
        }
        catch (JsonException)
        {
            return "";
        }
    }

    private static void EnsureInteractionArtifactPath(ProjectSnapshot project, string relativePath)
    {
        var allowedRoot = Path.GetFullPath(Path.Combine(
            project.MetaPath,
            "routes",
            "iteration-plan",
            "interaction-regions"));
        var candidate = Path.GetFullPath(Path.Combine(project.MetaPath, relativePath));
        var boundary = allowedRoot + Path.DirectorySeparatorChar;
        if (!candidate.StartsWith(boundary, StringComparison.OrdinalIgnoreCase) ||
            !string.Equals(Path.GetExtension(candidate), ".json", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Iteration-plan interaction artifact path escaped its canonical directory.");
        }
    }

    private static string ToSlash(string value)
    {
        return value.Replace('\\', '/');
    }

    private static string BuildProjectReadme(ProjectSnapshot project)
    {
        return BuildProjectReadme(
            project.ProjectId,
            project.AccountId,
            project.Name,
            project.GameName,
            project.GameTypeSource,
            project.TemplateRuleId,
            project.WorkspaceId,
            project.MetaPath);
    }

    private static string BuildProjectReadme(
        string projectId,
        string accountId,
        string projectName,
        string gameName,
        string gameTypeSource,
        string templateRuleId,
        string workspaceId,
        string metaPath)
    {
        return $"""
            # {projectName}

            This file is generated by Phase A for project-level recovery.

            ## Project

            - ProjectId: {projectId}
            - AccountId: {accountId}
            - WorkspaceId: {workspaceId}
            - ProjectName: {projectName}
            - GameName: {gameName}
            - GameTypeSource: {gameTypeSource}
            - TemplateRuleId: {templateRuleId}

            ## Prototype Route Contract

            - Prototype route state: meta/routes/prototype/latest.json
            - Prototype contract state: meta/routes/prototype-contract/latest.json
            - Iteration plan route state: meta/routes/iteration-plan/latest.json
            - Execute next goal route state: meta/routes/execute-next-goal/step-XX/latest.json
            - Needs fix route state: meta/routes/needs-fix/step-XX/latest.json

            ## Recovery Rules

            - The project prototype contract is the source of truth for user form fields and gameplay requirements after GDD generation.
            - Only the GDD route may read broad game-type sources such as docs/game-type-guides, prototype type kits, or route skill documents for design semantics.
            - Prototype, iteration plan, execute-next-goal, needs-fix, repair, validation, and UI routes must not read docs/game-type-guides, docs/prototype-type-kits, or .agents/skills route documents to add gameplay requirements.

            - Start from this README to identify the project and game type.
            - Prototype, iteration plan, execute next goal, and needs fix must read the prototype contract before reporting success.
            - Execute next goal must read this README, prototype contract, prototype route state, and iteration plan route state before running a step.
            - For needs fix, read only the current step state under meta/routes/needs-fix/step-XX.
            - If the current step has no needs fix state, read meta/routes/execute-next-goal/step-XX/latest.json.
            - If both current-step states are missing, read meta/routes/prototype/latest.json.
            - Do not consume other steps' needs fix state.
            - Project meta root: {metaPath}
            """;
    }

    private static string BuildProjectExecutionGuide(
        ProjectSnapshot project,
        PrototypeContractSnapshot prototypeContract,
        string prototypeRecordPath,
        string slug,
        string latestRoute,
        string latestRunId,
        string latestStatus,
        string? defaultScene,
        string? playableScene,
        string? smokeScene)
    {
        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var normalizedSlug = string.IsNullOrWhiteSpace(slug) ? "<prototype-slug>" : PrototypeRecordWriter.SanitizeSlug(slug.Trim());
        var prototypeRoot = $"Game.Godot/Prototypes/{normalizedSlug}";

        return $"""
            # Project Execution Guide

            This file is generated by Phase A after prototype skeleton creation. It is the lightweight recovery protocol for project routes that start without conversational memory.

            ## Project Identity

            - ProjectId: {project.ProjectId}
            - AccountId: {project.AccountId}
            - WorkspaceId: {project.WorkspaceId}
            - ProjectName: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - GameTypeId: {routeProfile.GameTypeId}
            - Slug: {normalizedSlug}

            ## Game Type Route

            - ProfileId: {routeProfile.ProfileId}
            - RouteSetId: {routeProfile.RouteSetId}
            - PromptProtocolId: {routeProfile.PromptProtocolId}
            - PlannerId: {routeProfile.PlannerId}
            - EvaluatorId: {routeProfile.EvaluatorId}
            - ExecutorId: {routeProfile.ExecutorId}
            - NeedsFixId: {routeProfile.NeedsFixId}
            - FinalAcceptanceId: {routeProfile.FinalAcceptanceId}

            ## Source Of Truth

            - Project README: README.md
            - This guide: {ProjectExecutionGuideRelativePath}
            - Prototype record: {EmptyAsMissing(prototypeRecordPath)}
            - Prototype contract: {prototypeContract.RelativePath}
            - Prototype route state: meta/routes/prototype/latest.json
            - Prototype repair state: meta/routes/prototype-repair/latest.json
            - Iteration plan state: meta/routes/iteration-plan/latest.json
            - Execute-next-goal state: meta/routes/execute-next-goal/step-XX/latest.json
            - Needs-fix state: meta/routes/needs-fix/step-XX/latest.json
            - Needs-fix repair ledger: meta/routes/needs-fix/step-XX/repair-ledger.json
            - Repair plan state: meta/routes/repair-plan/latest.json

            ## Prototype Chapter 3/6 Lite Protocol

            - Iteration plan creation uses Prototype Chapter 3 Lite: understand the project context, split small ordered goals, keep each goal executable and recoverable, and do not create Taskmaster triplets or formal task files.
            - Iteration execution, needs-fix, prototype-repair, and repair-step routes use Prototype Chapter 6 Lite: read recovery context first, execute only one current step, record structured results, and continue repair from current-step evidence.
            - Prototype Lite explicitly does not create or validate formal acceptance files, overlays, architecture contract files, or Chapter 6 review pipelines.
            - Prototype Lite keeps only the lightweight prototype contract, project execution guide, route state, and repair ledger required for playable prototype recovery.

            ## Runtime Artifact Layout

            - Godot project file: project.godot
            - Buildable C# project: GodotGame.csproj
            - Runtime Godot content root: Game.Godot/
            - Runtime prototype root: {prototypeRoot}/
            - Local prototype entry scene: {EmptyAsMissing(defaultScene)}
            - Local playable scene: {EmptyAsMissing(playableScene)}
            - Local smoke scene: {EmptyAsMissing(smokeScene)}
            - Core gameplay logic root: Game.Core/
            - Core test root: Game.Core.Tests/
            - Godot test root: Tests.Godot/
            - Prototype logs/artifacts: logs/ci/active-prototypes/
            - Iteration run logs: logs/phase-a-iteration/

            ## Downstream Source Boundary

            - Only the GDD route may read broad game-type sources such as docs/game-type-guides, prototype type kits, or route skill documents for design semantics.
            - After GDD generation, gameplay requirements must come from the prototype contract, current module spec, route state, repair ledger, and latest validation evidence.
            - Do not read docs/game-type-guides, docs/prototype-type-kits, or .agents/skills route documents to add gameplay requirements during iteration planning, execution, needs-fix, repair, validation, UI optimization, or readback.
            - User form fields and the GDD-derived prototype contract override templates, examples, and generic defaults.
            - If platform validation names a concrete compile, scene, asset, navigation, or smoke blocker, repair that blocker before feature polish.
            - Prefer PrototypeRoot for orchestration, small View components for UI/feedback, Systems for gameplay calculation, and Data/State classes for tuning or transient state when that split is cheaper than one large script.
            - Treat components as Godot Node/scene responsibility boundaries, not ECS. Do not introduce ECS, EntityComponent, IComponent, or a new framework.
            - Prefer exported NodePath bindings or one local binding method for stable scene references instead of repeating long GetNode("CanvasLayer/...") strings.
            - Prefer direct calls, Godot signals, or C# events inside one prototype. Use EventBus only for true global notifications or promotion candidates.
            - If the local prototype entry scene is a shell and the playable scene is different, validate both the menu-to-entry path and the entry-to-playable instancing path before reporting a module as complete.

            ## Route Recovery Protocol

            Every iteration-plan, execute-next-goal, needs-fix, prototype-repair, and repair-step route must start from this order:

            1. Read this guide to identify the project, route profile, source boundary, and artifact paths.
            2. Read the prototype contract and treat user form fields as authoritative.
            3. Read the latest relevant route state for the current route and current step only.
            4. For needs-fix, read the current step repair ledger before changing files.
            5. Use the latest live platform acceptance blocker as highest priority when it differs from older route state or ledger memory.
            6. Keep changes scoped to the hosted game project unless the current goal explicitly asks for platform changes.
            7. Before reporting succeeded, verify the work against the current goal, prototype contract, current module spec, and latest validation evidence.
            8. Do not use AGENTS.md as hosted project recovery memory; AGENTS.md is platform-repo guidance, not this project-level route memory.

            ## Priority Rules

            - Current platform acceptance blocker overrides prior assistant summaries, this guide, and repair ledger history.
            - Repair ledger is continuity memory; it is not authority over live validation.
            - Current goal or repair step overrides later goals.
            - Prototype contract overrides external templates, route skill documents, and generic examples.
            - Do not use needs-fix state from another step.
            - Do not treat route/platform tests as proof that a gameplay goal is complete.
            - Do not expose local paths, commands, script names, logs, or environment values in browser-facing output.

            ## Latest Route Snapshot

            - LatestRoute: {EmptyAsMissing(latestRoute)}
            - LatestRunId: {EmptyAsMissing(latestRunId)}
            - LatestStatus: {EmptyAsMissing(latestStatus)}
            - UpdatedUtc: {DateTimeOffset.UtcNow:O}
            """;
    }

    private static string EmptyAsMissing(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "(missing)" : value.Trim();
    }

    private static PrototypeGuideStateSnapshot TryReadPrototypeSnapshot(string prototypeState)
    {
        if (string.IsNullOrWhiteSpace(prototypeState))
        {
            return new PrototypeGuideStateSnapshot("", "", "", "", "", "", "", "");
        }

        try
        {
            using var document = JsonDocument.Parse(prototypeState);
            var root = document.RootElement;
            return new PrototypeGuideStateSnapshot(
                ReadString(root, "route"),
                ReadString(root, "run_id"),
                ReadString(root, "status"),
                ReadString(root, "prototype_record"),
                ReadString(root, "slug"),
                ReadString(root, "default_scene"),
                ReadString(root, "playable_scene"),
                ReadString(root, "smoke_scene"));
        }
        catch (JsonException)
        {
            return new PrototypeGuideStateSnapshot("", "", "", "", "", "", "", "");
        }
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? ""
            : "";
    }

    private sealed record PrototypeGuideStateSnapshot(
        string Route,
        string RunId,
        string Status,
        string PrototypeRecord,
        string Slug,
        string DefaultScene,
        string PlayableScene,
        string SmokeScene);
}
