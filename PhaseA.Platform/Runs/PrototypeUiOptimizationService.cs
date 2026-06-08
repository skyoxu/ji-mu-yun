using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeUiOptimizationService
{
    private const string RunType = "prototype-ui-optimization";
    private static readonly TimeSpan DefaultExecutionTimeout = TimeSpan.FromMinutes(8);
    private static readonly TimeSpan GodotSmokeValidationTimeout = TimeSpan.FromSeconds(75);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly TimeSpan _executionTimeout;

    public PrototypeUiOptimizationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner)
        : this(metadataStore, options, processRunner, new ProjectWorkspaceSeeder(options))
    {
    }

    public PrototypeUiOptimizationService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        TimeSpan? executionTimeout = null,
        HeavyRunnerQueueService? heavyRunnerQueue = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _keyPoolService = keyPoolService;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
        _executionTimeout = executionTimeout ?? DefaultExecutionTimeout;
    }

    public async Task<PrototypeUiOptimizationResult> RunAsync(
        string accountId,
        string projectId,
        PrototypeUiOptimizationRequest? request = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            return new PrototypeUiOptimizationResult("", "project_not_found", "Project was not found.");
        }

        if (project.BootstrapStatus == "running" ||
            await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken) ||
            await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeUiOptimizationResult("", "project_busy", "Project is busy.");
        }

        var planReadiness = await ValidateIterationPlanCompleteAsync(project.ProjectId, cancellationToken);
        if (planReadiness is not null)
        {
            return new PrototypeUiOptimizationResult("", planReadiness, FormatReadinessSummary(planReadiness));
        }

        if (!await HasSucceededPrototypeSkeletonAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeUiOptimizationResult("", "prototype_skeleton_not_ready", "Create the prototype skeleton before running UI optimization.");
        }

        var projectRoot = Path.GetFullPath(project.RepoPath);
        if (!WorkspacePathPolicy.IsUnderRoot(_options.HostedWorkspaceRoot, projectRoot))
        {
            throw new InvalidOperationException("Project repository path escaped the hosted workspace root.");
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeUiOptimizationResult(runId, "project_busy", "Project is busy.");
        }

        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, CancellationToken.None);
        await _metadataStore.UpdateRunProgressAsync(runId, "running", "prepare", "\u6b63\u5728\u51c6\u5907 UI \u4f18\u5316\u3002", CancellationToken.None);
        var runLogRelativeDir = Path.Combine("logs", "phase-a-ui-optimization", project.ProjectId, runId);
        var promptRelativePath = Path.Combine(runLogRelativeDir, "ui-optimization-prompt.md");
        var outputRelativePath = Path.Combine(runLogRelativeDir, "codex-output.jsonl");
        var promptAbsolutePath = Path.Combine(projectRoot, promptRelativePath);
        var outputAbsolutePath = Path.Combine(projectRoot, outputRelativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(promptAbsolutePath)!);
        Directory.CreateDirectory(Path.GetDirectoryName(outputAbsolutePath)!);

        try
        {
            var model = PrototypeModelPolicy.Normalize(request?.Model);
            var prompt = BuildPrompt(project);
            await File.WriteAllTextAsync(promptAbsolutePath, prompt, System.Text.Encoding.UTF8, CancellationToken.None);
            var command = CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
                projectRoot,
                outputAbsolutePath,
                prompt,
                model,
                "high",
                Sandbox: "workspace-write",
                Json: true));
            var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, cancellationToken);
            using var timeout = new CancellationTokenSource(_executionTimeout);
            await _metadataStore.UpdateRunProgressAsync(runId, "running", "codex", "Codex \u6b63\u5728\u8fd0\u884c UI \u4f18\u5316\u8def\u7531\u3002", CancellationToken.None);
            var process = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(command, runtimeCredential),
                timeout.Token);
            var smokeScene = process.ExitCode == 0
                ? await ResolveLatestPrototypeSmokeSceneAsync(project, CancellationToken.None)
                : null;
            var godotSmoke = process.ExitCode == 0
                ? await RunGodotSmokeValidationAsync(runId, project, smokeScene, CancellationToken.None)
                : PrototypeGodotSmokeResult.NotRun("codex_ui_optimization_failed", smokeScene);
            var status = process.ExitCode == 0 && (!godotSmoke.Ran || godotSmoke.ExitCode == 0)
                ? "succeeded"
                : "failed";
            var exitCode = process.ExitCode != 0 ? process.ExitCode : godotSmoke.Ran ? godotSmoke.ExitCode : 0;
            var progressSubstep = status == "succeeded"
                ? godotSmoke.Ran ? "completed" : "validation_skipped"
                : process.ExitCode == 0 ? "validation_failed" : "codex_failed";
            var progressLabel = status == "succeeded"
                ? godotSmoke.Ran
                    ? "UI \u4f18\u5316\u5df2\u5b8c\u6210\uff0c\u77ed\u9a8c\u8bc1\u5df2\u901a\u8fc7\u3002"
                    : "UI \u4f18\u5316\u5df2\u5b8c\u6210\uff0c\u77ed\u9a8c\u8bc1\u5df2\u8df3\u8fc7\u3002"
                : process.ExitCode == 0
                    ? "UI \u4f18\u5316\u5df2\u4fee\u6539\uff0c\u4f46\u77ed\u9a8c\u8bc1\u5931\u8d25\u3002"
                    : "UI \u4f18\u5316\u5931\u8d25\u3002";
            var evidenceJson = JsonSerializer.Serialize(new
            {
                route = RunType,
                model,
                template = ResolveTemplateName(project),
                prompt = promptRelativePath.Replace('\\', '/'),
                output = outputRelativePath.Replace('\\', '/'),
                timeout_seconds = (int)_executionTimeout.TotalSeconds,
                validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
                codex_exit_code = process.ExitCode,
                validation_required = godotSmoke.Ran,
                godot_smoke = godotSmoke.ToEvidence()
            });
            await _metadataStore.CompleteRunAsync(runId, status, exitCode, process.Stdout, process.Stderr, evidenceJson, CancellationToken.None);
            await _metadataStore.RecordRunLlmAuditAsync(
                runId,
                "codex-cli",
                null,
                model,
                LlmUsageAuditJson.BuildCodexUsageJson(
                    operation: RunType,
                    model: model,
                    tokenUsage: CodexUsageExtractor.Extract(process.Stdout, process.Stderr),
                    runType: RunType,
                    projectId: project.ProjectId,
                    skillName: "prototype-rpg-ui-optimizer-zh",
                    route: RunType,
                    exitCode: exitCode),
                CancellationToken.None);
            await _metadataStore.AddArtifactAsync(
                new ArtifactCreationCommand(runId, project.ProjectId, "prototype-ui-optimization-prompt", promptRelativePath.Replace('\\', '/'), "UI optimization prompt"),
                CancellationToken.None);
            await _metadataStore.AddArtifactAsync(
                new ArtifactCreationCommand(runId, project.ProjectId, "prototype-ui-optimization-output", outputRelativePath.Replace('\\', '/'), "UI optimization Codex output"),
                CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(
                runId,
                status,
                progressSubstep,
                progressLabel,
                CancellationToken.None);
            return new PrototypeUiOptimizationResult(
                runId,
                status,
                status == "succeeded"
                    ? "UI optimization completed."
                    : process.ExitCode == 0
                        ? "UI optimization changed files, but short validation failed."
                        : "UI optimization failed.");
        }
        catch (OperationCanceledException ex)
        {
            var evidenceJson = JsonSerializer.Serialize(new
            {
                route = RunType,
                timeout_seconds = (int)_executionTimeout.TotalSeconds,
                failure_code = "ui_optimization_codex_timeout",
                validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
                prompt = promptRelativePath.Replace('\\', '/'),
                output = outputRelativePath.Replace('\\', '/')
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 408, "", ex.ToString(), evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "timeout", "UI \u4f18\u5316\u8d85\u65f6\u3002", CancellationToken.None);
            return new PrototypeUiOptimizationResult(runId, "failed", "UI optimization timed out.");
        }
        catch (Exception ex)
        {
            var evidenceJson = JsonSerializer.Serialize(new
            {
                route = RunType,
                failure_code = "ui_optimization_route_error",
                validation_policy = "codex_ui_edit_only_platform_short_godot_smoke",
                prompt = promptRelativePath.Replace('\\', '/'),
                output = outputRelativePath.Replace('\\', '/')
            });
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), evidenceJson, CancellationToken.None);
            await _metadataStore.UpdateRunProgressAsync(runId, "failed", "error", "UI \u4f18\u5316\u5931\u8d25\u3002", CancellationToken.None);
            return new PrototypeUiOptimizationResult(runId, "failed", "UI optimization failed.");
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    private async Task<string?> ValidateIterationPlanCompleteAsync(string projectId, CancellationToken cancellationToken)
    {
        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (details is null || details.Goals.Count == 0)
        {
            return "iteration_plan_not_ready";
        }

        return details.Goals.All(goal => IsCompletedGoalStatus(goal.Status))
            ? null
            : "iteration_plan_not_complete";
    }

    private static bool IsCompletedGoalStatus(string? status)
    {
        return string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase);
    }

    private async Task<bool> HasSucceededPrototypeSkeletonAsync(string projectId, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        return runs.Any(run =>
            string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
            string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase));
    }

    private async Task<string?> ResolveLatestPrototypeSmokeSceneAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        foreach (var run in runs.Where(run =>
                     string.Equals(run.RunType, "prototype-7day-playable", StringComparison.OrdinalIgnoreCase) &&
                     string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase)))
        {
            var scene = TryReadSmokeScene(run.EvidenceJson);
            if (!string.IsNullOrWhiteSpace(scene))
            {
                return scene;
            }
        }

        return TryReadMainSceneFromProjectGodot(project.RepoPath);
    }

    private static string? TryReadMainSceneFromProjectGodot(string repoPath)
    {
        var projectGodotPath = Path.Combine(repoPath, "project.godot");
        if (!File.Exists(projectGodotPath))
        {
            return null;
        }

        foreach (var rawLine in File.ReadLines(projectGodotPath))
        {
            var line = rawLine.Trim();
            if (!line.StartsWith("run/main_scene=", StringComparison.Ordinal))
            {
                continue;
            }

            var value = line["run/main_scene=".Length..].Trim().Trim('"');
            return string.IsNullOrWhiteSpace(value) ? null : value;
        }

        return null;
    }

    private async Task<PrototypeGodotSmokeResult> RunGodotSmokeValidationAsync(string runId, ProjectSnapshot project, string? scenePath, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(scenePath))
        {
            return PrototypeGodotSmokeResult.NotRun("prototype_smoke_scene_missing");
        }

        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(GodotSmokeValidationTimeout);
        try
        {
            await _metadataStore.UpdateRunProgressAsync(
                runId,
                "running",
                "short_validation",
                "正在运行 UI 优化短验证。",
                CancellationToken.None);
            return await PrototypeGodotSmokeService.RunPostPrototypeAcceptanceAsync(_options, _processRunner, project.RepoPath, scenePath, timeout.Token);
        }
        catch (OperationCanceledException)
        {
            return new PrototypeGodotSmokeResult(
                true,
                408,
                "",
                $"UI optimization Godot smoke validation exceeded the {GodotSmokeValidationTimeout.TotalSeconds:0} second timeout.",
                "ui_optimization_godot_smoke_timeout",
                scenePath);
        }
    }

    private static string? TryReadSmokeScene(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            if (document.RootElement.TryGetProperty("prototype_completion", out var completion) &&
                completion.ValueKind == JsonValueKind.Object &&
                completion.TryGetProperty("smoke_scene", out var smokeScene) &&
                smokeScene.ValueKind == JsonValueKind.String)
            {
                return smokeScene.GetString();
            }

            if (document.RootElement.TryGetProperty("godot_smoke", out var smoke) &&
                smoke.ValueKind == JsonValueKind.Object &&
                smoke.TryGetProperty("scene", out var scene) &&
                scene.ValueKind == JsonValueKind.String)
            {
                return scene.GetString();
            }
        }
        catch (JsonException)
        {
        }

        return null;
    }

    private static string FormatReadinessSummary(string status)
    {
        return status switch
        {
            "iteration_plan_not_ready" => "\u8bf7\u5148\u751f\u6210\u5e76\u5b8c\u6210\u8fed\u4ee3\u8ba1\u5212\uff0c\u518d\u8fd0\u884c UI \u4f18\u5316\u3002",
            "iteration_plan_not_complete" => "\u5f53\u524d\u8fed\u4ee3\u8ba1\u5212\u4ecd\u6709\u672a\u5b8c\u6210\u6b65\u9aa4\uff0c\u8bf7\u5148\u5b8c\u6210\u8fed\u4ee3\u8ba1\u5212\uff0c\u518d\u8fd0\u884c UI \u4f18\u5316\u3002",
            _ => status
        };
    }

    private async Task<AiCodeMirrorRuntimeCredential> ResolveRuntimeCredentialAsync(string accountId, CancellationToken cancellationToken)
    {
        if (_keyPoolService is null)
        {
            return new AiCodeMirrorRuntimeCredential(accountId, null, null);
        }

        var credential = await _keyPoolService.ResolveRuntimeCredentialForAccountAsync(accountId, cancellationToken);
        return credential.BillingKeyName is null && credential.CodexHomePath is null
            ? new AiCodeMirrorRuntimeCredential(accountId, null, null)
            : credential;
    }

    private static string BuildPrompt(ProjectSnapshot project)
    {
        var templateName = ResolveTemplateName(project);
        return $"""
            You are running the Phase A prototype UI optimization route.
            Invoke `$prototype-rpg-ui-optimizer-zh` when the project is RPG/JRPG/DQ-like.

            Goal:
            - Improve the current Godot prototype UI so it visually and structurally resembles the game-type template.
            - For RPG/JRPG/DQ-like projects, use the He-is-Coming prototype UI as the target reference style.

            Project:
            - ProjectId: {project.ProjectId}
            - ProjectName: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - TemplateReference: {templateName}

            Recovery protocol:
            - Read AGENTS.md, README.md, meta/project-context.md when present, and the latest route state under meta/routes/.
            - Inspect Game.Godot/Prototypes and project.godot before editing.
            - Prefer modifying existing prototype scenes, scripts, labels, layout, theme, and asset references.
            - Do not create a second unrelated prototype. Do not add new workflow rules.
            - Do not delete existing playable logic.

            RPG UI target:
            - Current game should launch into the actual playable RPG prototype, not the generic template Main.tscn demo UI.
            - UI should include RPG-specific status, encounter, map, battle, reward, result, and log panels where applicable.
            - Use Chinese user-facing labels when the project input/GDD is Chinese.
            - If a DefaultRpgTemplate or He-is-Coming-like prototype exists locally, reuse its layout/style patterns rather than inventing a new UI.

            Validation:
            - Keep the Godot project loadable.
            - Preserve existing scenes/scripts unless directly needed for UI alignment.
            - Do not run long Godot/headless validation commands from this route; the platform runs a short Godot smoke after Codex exits.
            - If you validate locally, keep checks short and deterministic, such as a C# build or static scene/script inspection.
            - Leave full Godot prototype acceptance to the dedicated prototype acceptance route.
            - Report changed files and remaining gaps.
            """;
    }

    private static string ResolveTemplateName(ProjectSnapshot project)
    {
        var source = $"{project.GameTypeSource} {project.GameName} {project.Name}";
        return source.Contains("rpg", StringComparison.OrdinalIgnoreCase) ||
               source.Contains("jrpg", StringComparison.OrdinalIgnoreCase) ||
               source.Contains("dragon quest", StringComparison.OrdinalIgnoreCase) ||
               source.Contains("he-is-coming", StringComparison.OrdinalIgnoreCase)
            ? "He-is-Coming"
            : "game-type-template";
    }
}

public sealed record PrototypeUiOptimizationResult(
    string RunId,
    string Status,
    string Summary);

public sealed record PrototypeUiOptimizationRequest(
    string? Model);
