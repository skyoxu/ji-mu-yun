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
        string latestStatus)
    {
        ArgumentNullException.ThrowIfNull(project);

        var path = Path.Combine(project.RepoPath, ProjectExecutionGuideRelativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(
            path,
            BuildProjectExecutionGuide(project, prototypeContract, prototypeRecordPath, slug, latestRoute, latestRunId, latestStatus),
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
            snapshot.Status);
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

    private static void WriteState(ProjectSnapshot project, string relativePath, object payload)
    {
        var serialized = JsonSerializer.Serialize(payload, JsonOptions);
        WriteStateFile(Path.Combine(project.MetaPath, relativePath), serialized);
        WriteStateFile(Path.Combine(project.RepoPath, "meta", relativePath), serialized);
    }

    private static string ReadState(ProjectSnapshot project, string relativePath)
    {
        var path = Path.Combine(project.MetaPath, relativePath);
        if (File.Exists(path))
        {
            return File.ReadAllText(path, Encoding.UTF8);
        }

        var mirroredPath = Path.Combine(project.RepoPath, "meta", relativePath);
        return File.Exists(mirroredPath) ? File.ReadAllText(mirroredPath, Encoding.UTF8) : "";
    }

    private static void WriteStateFile(string path, string serialized)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, serialized, Utf8NoBom);
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

            - Default route skill context:
              - RPG projects use `prototype-rpg-godot-zh`.
              - Non-RPG prototype projects use `prototype-7day-playable-godot-zh`.
            - The same route skill context is inherited by prototype, iteration plan, execute-next-goal, and needs-fix.
              - The project prototype contract is the source of truth for user form fields.
              - User form fields override route skill templates and generic type defaults.

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
        string latestStatus)
    {
        var routeProfile = PrototypeRouteSkillPolicy.ResolveProfile(project);
        var routeSkill = routeProfile.RouteSkill;
        var normalizedSlug = string.IsNullOrWhiteSpace(slug) ? "<prototype-slug>" : PrototypeRecordWriter.SanitizeSlug(slug.Trim());
        var prototypeRoot = $"Game.Godot/Prototypes/{normalizedSlug}";
        var isRpg = string.Equals(routeProfile.GameTypeId, "rpg", StringComparison.OrdinalIgnoreCase);
        var typeSpecificProtocol = isRpg
            ? """
                ## RPG Type Protocol

                - Treat this project as an RPG route project unless the prototype contract explicitly says otherwise.
                - Preserve the main menu entry path: main shell -> Start Adventure -> visible MapScene -> battle/reward/map loop.
                - User form fields override RPG defaults, template examples, and fallback kit values.
                - RPG work should keep MapScene, BattleScene, reward selection, win/fail visibility, and final acceptance aligned.
                - If platform validation names a concrete compile, node, asset, navigation, or GdUnit blocker, repair that blocker before gameplay polish.

                ## RPG Expected Artifact Anchors

                - Prototype shell scene: Game.Godot/Prototypes/<slug>/<PascalSlug>Prototype.tscn
                - RPG map scene: Game.Godot/Prototypes/<slug>/MapScene.tscn
                - RPG battle scene: Game.Godot/Prototypes/<slug>/BattleScene.tscn
                - RPG scripts: Game.Godot/Prototypes/<slug>/Scripts/
                - RPG core loop: Game.Core/Prototypes/
                - RPG core tests: Game.Core.Tests/Prototypes/
                - RPG Godot tests: Tests.Godot/tests/Prototype/
                """
            : """
                ## Default Type Protocol

                - Treat this project as a default playable Godot prototype route project.
                - User form fields override templates and examples.
                - Keep the smallest playable loop, user-visible UI feedback, and final acceptance aligned with the prototype contract.
                - If platform validation names a concrete compile, scene, asset, or smoke blocker, repair that blocker before feature polish.
                """;

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
            - SkillId: {routeSkill.RouteSkillId}
            - SkillPath: {routeSkill.SkillRelativePath}
            - SkillContractPath: {routeSkill.ContractRelativePath ?? "(none)"}

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
            - Core gameplay logic root: Game.Core/
            - Core test root: Game.Core.Tests/
            - Godot test root: Tests.Godot/
            - Prototype logs/artifacts: logs/ci/active-prototypes/
            - Iteration run logs: logs/phase-a-iteration/

            {typeSpecificProtocol}

            ## Route Recovery Protocol

            Every iteration-plan, execute-next-goal, needs-fix, prototype-repair, and repair-step route must start from this order:

            1. Read this guide to identify game type, route profile, skill, and artifact paths.
            2. Read the prototype contract and treat user form fields as authoritative.
            3. Read the latest relevant route state for the current route and current step only.
            4. For needs-fix, read the current step repair ledger before changing files.
            5. Use the latest live platform acceptance blocker as highest priority when it differs from older route state or ledger memory.
            6. Keep changes scoped to the hosted game project unless the current goal explicitly asks for platform changes.
            7. Before reporting succeeded, verify the work against the current goal, prototype contract, and type-specific route rules.
            8. Do not use AGENTS.md as hosted project recovery memory; AGENTS.md is platform-repo guidance, not this project-level route memory.

            ## Priority Rules

            - Current platform acceptance blocker overrides prior assistant summaries, this guide, and repair ledger history.
            - Repair ledger is continuity memory; it is not authority over live validation.
            - Current goal or repair step overrides later goals.
            - Prototype contract overrides type templates and generic examples.
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
            return new PrototypeGuideStateSnapshot("", "", "", "", "");
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
                ReadString(root, "slug"));
        }
        catch (JsonException)
        {
            return new PrototypeGuideStateSnapshot("", "", "", "", "");
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
        string Slug);
}
