using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeWorkflowService
{
    private const string RunType = "prototype-7day-playable";
    private const int CurrentWorkflowMaxDay = 7;

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly PrototypeRecordWriter _recordWriter;
    private readonly PrototypeWorkflowCommandBuilder _commandBuilder;
    private readonly PrototypeArtifactIndexer _artifactIndexer;
    private readonly LlmBindingService _llmBindingService;
    private readonly LlmStopLossService _llmStopLossService;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;

    public PrototypeWorkflowService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        PrototypeRecordWriter recordWriter,
        PrototypeWorkflowCommandBuilder commandBuilder,
        PrototypeArtifactIndexer artifactIndexer,
        LlmBindingService llmBindingService,
        LlmStopLossService llmStopLossService)
        : this(metadataStore, options, processRunner, recordWriter, commandBuilder, artifactIndexer, llmBindingService, llmStopLossService, new ProjectWorkspaceSeeder(options))
    {
    }

    public PrototypeWorkflowService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        PrototypeRecordWriter recordWriter,
        PrototypeWorkflowCommandBuilder commandBuilder,
        PrototypeArtifactIndexer artifactIndexer,
        LlmBindingService llmBindingService,
        LlmStopLossService llmStopLossService,
        IProjectWorkspaceSeeder workspaceSeeder)
    {
        _metadataStore = metadataStore;
        _options = options;
        _processRunner = processRunner;
        _recordWriter = recordWriter;
        _commandBuilder = commandBuilder;
        _artifactIndexer = artifactIndexer;
        _llmBindingService = llmBindingService;
        _llmStopLossService = llmStopLossService;
        _workspaceSeeder = workspaceSeeder;
    }

    public async Task<PrototypeWorkflowResult> RunAsync(string projectId, PrototypeWorkflowRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        request = await EnrichRequestFromLatestDraftAsync(project.ProjectId, request, cancellationToken);
        request = EnrichRequestFromProject(project, request);
        var missing = PrototypeWorkflowValidation.MissingRequiredFields(request);
        if (missing.Count > 0)
        {
            return new PrototypeWorkflowResult("", "missing_required_fields", 2, "", "", "", [], missing);
        }

        var usesLlm = IsLlmScoring(request.ScoreEngine);
        LlmCostEstimate? llmEstimate = null;
        LlmStopLossDecision? stopLoss = null;
        if (usesLlm)
        {
            var binding = await _llmBindingService.GetAsync(project.AccountId, cancellationToken);
            if (binding is null)
            {
                return new PrototypeWorkflowResult("", "llm_binding_required", 402, "", "", "new-api binding is required", [], []);
            }

            llmEstimate = new LlmCostEstimate(0.50m, Model: request.ScoreEngine, RequestId: null);
            stopLoss = await _llmStopLossService.CheckAsync(project.AccountId, llmEstimate, cancellationToken);
            if (!stopLoss.Allowed)
            {
                return new PrototypeWorkflowResult("", stopLoss.FailureCode!, 402, "", "", "LLM stop-loss blocked the operation", [], []);
            }
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var prototypeRecordPath = _recordWriter.Write(request, project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await SetProgressAsync(runId, "queued", "", "已提交，等待 runner。", cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);
        await SetProgressAsync(runId, "preparing", "write_record", "正在写入原型记录并准备执行环境。", cancellationToken);
        await AdvancePrototypeStepsAsync(runId, cancellationToken);

        var process = await _processRunner.RunAsync(_commandBuilder.Build(request, prototypeRecordPath, project.RepoPath), cancellationToken);
        var slug = ResolvePrototypeSlug(project.RepoPath, prototypeRecordPath, request.Slug!);
        var validation = process.ExitCode == 0
            ? ValidateCompletedPrototypeState(project.RepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_workflow_failed");
        var smoke = process.ExitCode == 0 && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunPostPrototypeGodotSmokeAsync(project.RepoPath, validation.SmokeScene, cancellationToken)
            : GodotSmokeResult.NotRun(process.ExitCode != 0 ? "prototype_workflow_failed" : "prototype_completion_validation_failed");
        var status = process.ExitCode == 0 && smoke.ExitCode == 0 && validation.Succeeded ? "succeeded" : "failed";
        var exitCode = ResolveRunExitCode(process.ExitCode, smoke.ExitCode, validation.Succeeded);
        var stdout = CombineProcessText(process.Stdout, smoke.Stdout);
        var stderr = process.ExitCode == 0
            ? CombineProcessText(process.Stderr, CombineProcessText(smoke.Stderr, validation.Error ?? ""))
            : CombineProcessText(process.Stderr, smoke.Stderr);
        var discoveredArtifacts = _artifactIndexer.Discover(project.RepoPath, runId, project.ProjectId, slug, prototypeRecordPath);

        foreach (var artifact in discoveredArtifacts)
        {
            await _metadataStore.AddArtifactAsync(artifact, cancellationToken);
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            prototype_record = prototypeRecordPath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, cancellationToken);
        await SetProgressAsync(
            runId,
            status,
            "",
            status == "succeeded" ? "原型路线已完成。" : "原型路线失败，请查看运行记录错误输出。",
            cancellationToken);
        if (usesLlm && llmEstimate is not null && stopLoss is not null)
        {
            await _metadataStore.RecordRunLlmAuditAsync(
                runId,
                _options.LlmGatewayProvider,
                llmEstimate.RequestId,
                llmEstimate.Model,
                LlmStopLossService.BuildCostJson(llmEstimate, stopLoss),
                cancellationToken);
        }

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);

        return new PrototypeWorkflowResult(runId, status, exitCode, prototypeRecordPath, stdout, stderr, artifacts, [], await GetProgressAsync(projectId, cancellationToken));
    }

    public async Task<PrototypeWorkflowResult> QueueAsync(string projectId, PrototypeWorkflowRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        request = await EnrichRequestFromLatestDraftAsync(project.ProjectId, request, cancellationToken);
        request = EnrichRequestFromProject(project, request);
        var missing = PrototypeWorkflowValidation.MissingRequiredFields(request);
        if (missing.Count > 0)
        {
            return new PrototypeWorkflowResult("", "missing_required_fields", 2, "", "", "", [], missing);
        }

        if (await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeWorkflowResult("", "project_busy", 423, "", "", "Project runner is busy.", [], []);
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var prototypeRecordPath = _recordWriter.Write(request, project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await SetProgressAsync(runId, "queued", "", "已提交，等待 runner。", cancellationToken);

        _ = Task.Run(async () =>
        {
            try
            {
                await RunQueuedAsync(project.ProjectId, project.WorkspaceId, project.RepoPath, runId, prototypeRecordPath, request);
            }
            catch (Exception ex)
            {
                await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), FailureEvidenceJson(prototypeRecordPath), CancellationToken.None);
                await SetProgressAsync(runId, "failed", "", "原型路线失败，请查看运行记录错误输出。", CancellationToken.None);
            }
        }, CancellationToken.None);

        return new PrototypeWorkflowResult(
            runId,
            "queued",
            202,
            prototypeRecordPath,
            "",
            "",
            [],
            [],
            await GetProgressAsync(projectId, cancellationToken));
    }

    public async Task<PrototypeWorkflowResult> RepairAsync(string projectId, PrototypeRepairRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        if (await _metadataStore.HasRunnerLockAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeWorkflowResult("", "project_busy", 423, "", "", "Project runner is busy.", [], []);
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        if (runs.Any(run => run.RunType == RunType && run.Status is "queued" or "running"))
        {
            return new PrototypeWorkflowResult("", "prototype_workflow_already_running", 409, "", "", "", [], []);
        }

        var latestPrototypeRun = runs.FirstOrDefault(run => run.RunType == RunType);
        var prototypeRecordPath = ExtractPrototypeRecordPath(latestPrototypeRun);
        if (latestPrototypeRun?.Status != "failed" || string.IsNullOrWhiteSpace(prototypeRecordPath))
        {
            return new PrototypeWorkflowResult("", "prototype_repair_not_available", 404, "", "", "No failed prototype workflow with a repairable prototype record was found.", [], []);
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await SetProgressAsync(runId, "queued", "repair", "已提交原型修复，等待 runner。", cancellationToken);

        _ = Task.Run(async () =>
        {
            try
            {
                await RunRepairQueuedAsync(project.ProjectId, project.WorkspaceId, project.RepoPath, runId, prototypeRecordPath, request.Model);
            }
            catch (Exception ex)
            {
                await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), FailureEvidenceJson(prototypeRecordPath, repair: true), CancellationToken.None);
                await SetProgressAsync(runId, "failed", "repair", "原型修复失败，请查看新的失败原因。", CancellationToken.None);
            }
        }, CancellationToken.None);

        return new PrototypeWorkflowResult(
            runId,
            "queued",
            202,
            prototypeRecordPath,
            "",
            "",
            [],
            [],
            await GetProgressAsync(projectId, cancellationToken));
    }

    public async Task<PrototypeWorkflowProgress> GetProgressAsync(string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        var run = runs.FirstOrDefault(item => item.RunType == RunType);
        if (run is null)
        {
            return new PrototypeWorkflowProgress("idle", "", "", "尚未开始 7 日可玩原型路线。", null, null, null, null);
        }

        var step = string.IsNullOrWhiteSpace(run.ProgressStep) ? run.Status : run.ProgressStep;
        var label = string.IsNullOrWhiteSpace(run.ProgressLabel) ? DefaultLabel(run.Status) : run.ProgressLabel;
        var completionSummary = ReadCompletionSummaryFromRun(run);
        var packaging = ReadPackagingSummaryFromRun(project.RepoPath, run);
        return new PrototypeWorkflowProgress(
            run.Status,
            step,
            run.ProgressSubstep,
            label,
            run.ProgressUpdatedUtc,
            run.RunId,
            run.Status == "failed" ? ResolveUserFacingFailure(run) : null,
            completionSummary,
            packaging?.DefaultScene,
            packaging?.DefaultSceneLabel,
            packaging?.TddSummaryCount,
            packaging?.TddRedCount,
            packaging?.TddGreenCount,
            packaging?.TddRefactorCount,
            packaging?.PlaytestFocusPoints);
    }

    private async Task RunQueuedAsync(
        string projectId,
        string? workspaceId,
        string projectRepoPath,
        string runId,
        string prototypeRecordPath,
        PrototypeWorkflowRequest request)
    {
        await _metadataStore.MarkRunStartedAsync(runId, CancellationToken.None);
        await SetProgressAsync(runId, "preparing", "write_record", "正在写入原型记录并准备执行环境。", CancellationToken.None);
        await AdvancePrototypeStepsAsync(runId, CancellationToken.None);

        _workspaceSeeder.EnsureSeeded(projectRepoPath);
        var process = await _processRunner.RunAsync(_commandBuilder.Build(request, prototypeRecordPath, projectRepoPath), CancellationToken.None);
        var slug = ResolvePrototypeSlug(projectRepoPath, prototypeRecordPath, request.Slug!);
        var validation = process.ExitCode == 0
            ? ValidateCompletedPrototypeState(projectRepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_workflow_failed");
        var smoke = process.ExitCode == 0 && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunPostPrototypeGodotSmokeAsync(projectRepoPath, validation.SmokeScene, CancellationToken.None)
            : GodotSmokeResult.NotRun(process.ExitCode != 0 ? "prototype_workflow_failed" : "prototype_completion_validation_failed");
        var status = process.ExitCode == 0 && smoke.ExitCode == 0 && validation.Succeeded ? "succeeded" : "failed";
        var exitCode = ResolveRunExitCode(process.ExitCode, smoke.ExitCode, validation.Succeeded);
        var stdout = CombineProcessText(process.Stdout, smoke.Stdout);
        var stderr = process.ExitCode == 0
            ? CombineProcessText(process.Stderr, CombineProcessText(smoke.Stderr, validation.Error ?? ""))
            : CombineProcessText(process.Stderr, smoke.Stderr);
        var discoveredArtifacts = _artifactIndexer.Discover(projectRepoPath, runId, projectId, slug, prototypeRecordPath);

        foreach (var artifact in discoveredArtifacts)
        {
            await _metadataStore.AddArtifactAsync(artifact, CancellationToken.None);
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            prototype_record = prototypeRecordPath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        await SetProgressAsync(
            runId,
            status,
            "",
            status == "succeeded" ? "原型路线已完成。" : "原型路线失败，请查看运行记录错误输出。",
            CancellationToken.None);
    }

    private async Task RunRepairQueuedAsync(
        string projectId,
        string? workspaceId,
        string projectRepoPath,
        string runId,
        string prototypeRecordPath,
        string? model)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, CancellationToken.None)
            ?? throw new InvalidOperationException("Project not found.");
        await _metadataStore.MarkRunStartedAsync(runId, CancellationToken.None);
        await SetProgressAsync(runId, "repairing", "prepare", "正在基于上一次失败原因修复原型。", CancellationToken.None);
        await AdvancePrototypeStepsAsync(runId, CancellationToken.None);

        _workspaceSeeder.EnsureSeeded(projectRepoPath);
        var effectiveSlug = ReadSlugFromPrototypeRecord(projectRepoPath, prototypeRecordPath)
            ?? ExtractSlugFromPrototypeRecordPath(prototypeRecordPath);
        var repairRequest = new PrototypeWorkflowRequest(
            Slug: effectiveSlug,
            GameName: project.GameName,
            GameType: NormalizeGameType(project.GameTypeSource),
            GameTypeSource: project.GameTypeSource,
            Hypothesis: "Repair previous failed prototype workflow.",
            CorePlayerFantasy: "Repair previous failed prototype workflow.",
            MinimumPlayableLoop: "Repair previous failed prototype workflow.",
            SuccessCriteria: ["Previous failed prototype workflow is repaired."],
            GameFeature: "Repair previous failed prototype workflow.",
            CoreGameplayLoop: "Repair previous failed prototype workflow.",
            WinFailConditions: "Repair previous failed prototype workflow.",
            Confirm: true,
            ScoreEngine: "deterministic",
            Model: model);
        var process = await _processRunner.RunAsync(_commandBuilder.Build(repairRequest, prototypeRecordPath, projectRepoPath), CancellationToken.None);
        var slug = ReadSlugFromPrototypeRecord(projectRepoPath, prototypeRecordPath)
            ?? effectiveSlug;
        var validation = process.ExitCode == 0
            ? ValidateCompletedPrototypeState(projectRepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_repair_failed");
        var smoke = process.ExitCode == 0 && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunPostPrototypeGodotSmokeAsync(projectRepoPath, validation.SmokeScene, CancellationToken.None)
            : GodotSmokeResult.NotRun(process.ExitCode != 0 ? "prototype_repair_failed" : "prototype_completion_validation_failed");
        var status = process.ExitCode == 0 && smoke.ExitCode == 0 && validation.Succeeded ? "succeeded" : "failed";
        var exitCode = ResolveRunExitCode(process.ExitCode, smoke.ExitCode, validation.Succeeded);
        var stdout = CombineProcessText(process.Stdout, smoke.Stdout);
        var stderr = process.ExitCode == 0
            ? CombineProcessText(process.Stderr, CombineProcessText(smoke.Stderr, validation.Error ?? ""))
            : CombineProcessText(process.Stderr, smoke.Stderr);
        var discoveredArtifacts = _artifactIndexer.Discover(projectRepoPath, runId, projectId, slug, prototypeRecordPath);

        foreach (var artifact in discoveredArtifacts)
        {
            await _metadataStore.AddArtifactAsync(artifact, CancellationToken.None);
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            repair = true,
            prototype_record = prototypeRecordPath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        await SetProgressAsync(
            runId,
            status,
            "repair",
            status == "succeeded" ? "原型修复已完成。" : "原型修复失败，请查看新的失败原因。",
            CancellationToken.None);
    }

    private async Task AdvancePrototypeStepsAsync(string runId, CancellationToken cancellationToken)
    {
        foreach (var (step, substep, label) in ProgressSteps)
        {
            await SetProgressAsync(runId, step, substep, label, cancellationToken);
        }
    }

    private Task SetProgressAsync(string runId, string step, string substep, string label, CancellationToken cancellationToken)
    {
        return _metadataStore.UpdateRunProgressAsync(runId, step, substep, label, cancellationToken);
    }

    private async Task<GodotSmokeResult> RunPostPrototypeGodotSmokeAsync(string projectRepoPath, string scenePath, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            return GodotSmokeResult.NotRun("godot_bin_not_configured", scenePath);
        }

        var command = new HostedProcessCommand(
            _options.PythonCommand,
            [
                "-3",
                "scripts/python/smoke_headless.py",
                "--godot-bin",
                _options.GodotBin,
                "--project-path",
                projectRepoPath,
                "--scene",
                scenePath,
                "--timeout-sec",
                "10",
                "--strict"
            ],
            projectRepoPath,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = _options.GodotBin
            });

        var result = await _processRunner.RunAsync(command, cancellationToken);
        var sceneSmokeExitCode = ResolvePrototypeSmokeExitCode(result);
        if (sceneSmokeExitCode != 0)
        {
            return new GodotSmokeResult(true, sceneSmokeExitCode, result.Stdout, result.Stderr, "strict_headless_prototype_scene", scenePath);
        }

        var navigationCommand = new HostedProcessCommand(
            _options.PythonCommand,
            [
                "-3",
                "scripts/python/prototype_main_menu_navigation_smoke.py",
                "--godot-bin",
                _options.GodotBin,
                "--project-path",
                projectRepoPath,
                "--expected-scene",
                scenePath,
                "--timeout-sec",
                "15"
            ],
            projectRepoPath,
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["GODOT_BIN"] = _options.GodotBin
            });
        var navigationResult = await _processRunner.RunAsync(navigationCommand, cancellationToken);
        var navigationExitCode = navigationResult.ExitCode;
        var stdout = CombineProcessText(result.Stdout, navigationResult.Stdout);
        var stderr = CombineProcessText(result.Stderr, navigationResult.Stderr);
        return new GodotSmokeResult(
            true,
            navigationExitCode,
            stdout,
            stderr,
            navigationExitCode == 0 ? "strict_headless_main_menu_navigation" : "prototype_main_menu_navigation_failed",
            scenePath);
    }

    private static int ResolvePrototypeSmokeExitCode(HostedProcessResult result)
    {
        if (result.ExitCode == 0)
        {
            return 0;
        }

        var combined = $"{result.Stdout}\n{result.Stderr}";
        return combined.Contains("SMOKE PASS", StringComparison.OrdinalIgnoreCase) ? 0 : result.ExitCode;
    }

    private static string CombineProcessText(string primary, string secondary)
    {
        if (string.IsNullOrWhiteSpace(secondary))
        {
            return primary;
        }

        return string.IsNullOrWhiteSpace(primary)
            ? secondary
            : $"{primary.TrimEnd()}{Environment.NewLine}{Environment.NewLine}[post-prototype-godot-smoke]{Environment.NewLine}{secondary}";
    }

    private static string? ExtractPrototypeRecordPath(RunSnapshot? run)
    {
        if (run is null || string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty("prototype_record", out var value)
                ? value.GetString()
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string ExtractSlugFromPrototypeRecordPath(string prototypeRecordPath)
    {
        var name = Path.GetFileNameWithoutExtension(prototypeRecordPath);
        if (string.IsNullOrWhiteSpace(name))
        {
            return "prototype-repair";
        }

        var parts = name.Split('-', 4, StringSplitOptions.RemoveEmptyEntries);
        return parts.Length == 4 ? parts[3] : name;
    }

    private static string? ReadSlugFromPrototypeRecord(string repositoryRoot, string prototypeRecordPath)
    {
        try
        {
            var fullPath = Path.Combine(repositoryRoot, prototypeRecordPath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(fullPath))
            {
                return null;
            }

            foreach (var rawLine in File.ReadLines(fullPath))
            {
                var line = rawLine.Trim();
                if (line.StartsWith("# Prototype:", StringComparison.OrdinalIgnoreCase))
                {
                    var value = line["# Prototype:".Length..].Trim();
                    var slug = PrototypeRecordWriter.SanitizeSlug(value);
                    return string.IsNullOrWhiteSpace(slug) ? null : slug;
                }
            }
        }
        catch (IOException)
        {
            return null;
        }

        return null;
    }

    private static string ResolvePrototypeSlug(string repositoryRoot, string prototypeRecordPath, string fallbackSlug)
    {
        return ReadSlugFromPrototypeRecord(repositoryRoot, prototypeRecordPath)
            ?? PrototypeRecordWriter.SanitizeSlug(fallbackSlug);
    }

    private static string FailureEvidenceJson(string prototypeRecordPath, bool repair = false)
    {
        return JsonSerializer.Serialize(new
        {
            run_type = RunType,
            repair,
            prototype_record = prototypeRecordPath,
            slug = ExtractSlugFromPrototypeRecordPath(prototypeRecordPath)
        });
    }

    private static string? ReadCompletionSummaryFromRun(RunSnapshot run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_completion", out var completion) ||
                completion.ValueKind != JsonValueKind.Object ||
                !completion.TryGetProperty("completion_summary", out var summaryElement) ||
                summaryElement.ValueKind != JsonValueKind.String)
            {
                return null;
            }

            return summaryElement.GetString();
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static PrototypePackagingSummaryReadback? ReadPackagingSummaryFromRun(string repositoryRoot, RunSnapshot run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_artifacts", out var artifactsElement) ||
                artifactsElement.ValueKind != JsonValueKind.Array)
            {
                return null;
            }

            var packagingPath = artifactsElement.EnumerateArray()
                .Where(item => item.ValueKind == JsonValueKind.String)
                .Select(item => item.GetString() ?? "")
                .FirstOrDefault(path => path.EndsWith(".packaging.json", StringComparison.OrdinalIgnoreCase));
            if (string.IsNullOrWhiteSpace(packagingPath))
            {
                return null;
            }

            var absolutePath = Path.Combine(repositoryRoot, packagingPath.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(absolutePath))
            {
                return null;
            }

            using var packagingDocument = JsonDocument.Parse(File.ReadAllText(absolutePath, System.Text.Encoding.UTF8));
            var root = packagingDocument.RootElement;
            var defaultScene = root.TryGetProperty("default_scene", out var defaultSceneElement) && defaultSceneElement.ValueKind == JsonValueKind.String
                ? defaultSceneElement.GetString()
                : null;
            var defaultSceneLabel = root.TryGetProperty("default_scene_label", out var defaultSceneLabelElement) && defaultSceneLabelElement.ValueKind == JsonValueKind.String
                ? defaultSceneLabelElement.GetString()
                : null;
            var tddSummaryCount = root.TryGetProperty("tdd_summary_paths", out var tddElement) && tddElement.ValueKind == JsonValueKind.Array
                ? tddElement.GetArrayLength()
                : 0;
            var redCount = 0;
            var greenCount = 0;
            var refactorCount = 0;
            if (root.TryGetProperty("tdd_stage_counts", out var stageCountsElement) && stageCountsElement.ValueKind == JsonValueKind.Object)
            {
                redCount = TryReadInt(stageCountsElement, "red");
                greenCount = TryReadInt(stageCountsElement, "green");
                refactorCount = TryReadInt(stageCountsElement, "refactor");
            }
            var focusPoints = root.TryGetProperty("playtest_focus_points", out var focusElement) && focusElement.ValueKind == JsonValueKind.Array
                ? focusElement.EnumerateArray()
                    .Where(item => item.ValueKind == JsonValueKind.String)
                    .Select(item => item.GetString() ?? "")
                    .Where(item => !string.IsNullOrWhiteSpace(item))
                    .ToArray()
                : [];
            return new PrototypePackagingSummaryReadback(defaultScene, defaultSceneLabel, tddSummaryCount, redCount, greenCount, refactorCount, focusPoints);
        }
        catch (JsonException)
        {
            return null;
        }
        catch (IOException)
        {
            return null;
        }
    }

    private static int TryReadInt(JsonElement root, string propertyName)
    {
        return root.TryGetProperty(propertyName, out var valueElement) && valueElement.ValueKind == JsonValueKind.Number
            ? valueElement.GetInt32()
            : 0;
    }

    private static PrototypeCompletionValidation ValidateCompletedPrototypeState(string repositoryRoot, string slug)
    {
        var activeStatePath = Path.Combine(
            repositoryRoot,
            "logs",
            "ci",
            "active-prototypes",
            $"{PrototypeRecordWriter.SanitizeSlug(slug)}.active.json");
        if (!File.Exists(activeStatePath))
        {
            return PrototypeCompletionValidation.Failure("prototype_completion_state_missing");
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(activeStatePath, System.Text.Encoding.UTF8));
            var root = document.RootElement;
            var status = root.TryGetProperty("status", out var statusElement) ? statusElement.GetString() ?? "" : "";
            var completedThroughDay = root.TryGetProperty("completed_through_day", out var dayElement) && dayElement.ValueKind == JsonValueKind.Number
                ? dayElement.GetInt32()
                : 0;
            var missingRequiredFields = root.TryGetProperty("missing_required_fields", out var missingElement) && missingElement.ValueKind == JsonValueKind.Array
                ? missingElement.GetArrayLength()
                : 0;
            var prototypeSpec = root.TryGetProperty("prototype_spec", out var specElement) ? specElement.GetString() ?? "" : "";
            var specExists = !string.IsNullOrWhiteSpace(prototypeSpec) &&
                             File.Exists(Path.Combine(repositoryRoot, prototypeSpec.Replace('/', Path.DirectorySeparatorChar)));

            if (!string.Equals(status, "completed-through-day", StringComparison.OrdinalIgnoreCase))
            {
                return PrototypeCompletionValidation.Failure($"prototype_completion_status_not_completed:{status}");
            }

            if (completedThroughDay < CurrentWorkflowMaxDay)
            {
                return PrototypeCompletionValidation.Failure($"prototype_completion_incomplete_day:{completedThroughDay}");
            }

            if (missingRequiredFields > 0)
            {
                return PrototypeCompletionValidation.Failure($"prototype_completion_missing_fields:{missingRequiredFields}");
            }

            if (!specExists)
            {
                return PrototypeCompletionValidation.Failure("prototype_completion_spec_missing");
            }

            if (!TryValidateRequiredSteps(root, out var stepError))
            {
                return PrototypeCompletionValidation.Failure(stepError);
            }

            if (!TryResolvePrototypeSmokeScene(repositoryRoot, prototypeSpec, slug, out var smokeScene, out var sceneError))
            {
                return PrototypeCompletionValidation.Failure(sceneError);
            }

            if (completedThroughDay >= 6)
            {
                var packagingSummaryPath = Path.Combine(
                    repositoryRoot,
                    "logs",
                    "ci",
                    "active-prototypes",
                    $"{PrototypeRecordWriter.SanitizeSlug(slug)}.packaging.json");
                if (!File.Exists(packagingSummaryPath))
                {
                    return PrototypeCompletionValidation.Failure("prototype_packaging_summary_missing");
                }
            }

            var completionSummary = root.TryGetProperty("completion_summary", out var completionSummaryElement) && completionSummaryElement.ValueKind == JsonValueKind.String
                ? completionSummaryElement.GetString()
                : null;
            if (completedThroughDay >= CurrentWorkflowMaxDay && string.IsNullOrWhiteSpace(completionSummary))
            {
                return PrototypeCompletionValidation.Failure("prototype_completion_summary_missing");
            }

            if (completedThroughDay >= CurrentWorkflowMaxDay)
            {
                var completionReportPath = Path.Combine(
                    repositoryRoot,
                    "logs",
                    "ci",
                    "active-prototypes",
                    $"{PrototypeRecordWriter.SanitizeSlug(slug)}.completion.md");
                if (!File.Exists(completionReportPath))
                {
                    return PrototypeCompletionValidation.Failure("prototype_completion_report_missing");
                }
            }

            return PrototypeCompletionValidation.Success(status, completedThroughDay, smokeScene, completionSummary);
        }
        catch (JsonException)
        {
            return PrototypeCompletionValidation.Failure("prototype_completion_state_invalid_json");
        }
        catch (IOException)
        {
            return PrototypeCompletionValidation.Failure("prototype_completion_state_unreadable");
        }
    }

    private static int ResolveRunExitCode(int processExitCode, int smokeExitCode, bool validationSucceeded)
    {
        if (processExitCode != 0)
        {
            return processExitCode;
        }

        if (!validationSucceeded)
        {
            return 1;
        }

        return smokeExitCode;
    }

    private static bool TryValidateRequiredSteps(JsonElement root, out string error)
    {
        error = "";
        if (!root.TryGetProperty("steps_run", out var stepsElement) || stepsElement.ValueKind != JsonValueKind.Array)
        {
            error = "prototype_completion_steps_missing";
            return false;
        }

        var stepsByDay = new Dictionary<int, JsonElement>();
        foreach (var step in stepsElement.EnumerateArray())
        {
            if (!step.TryGetProperty("day", out var dayElement) || dayElement.ValueKind != JsonValueKind.Number)
            {
                continue;
            }

            var day = dayElement.GetInt32();
            if (day < 1 || day > CurrentWorkflowMaxDay)
            {
                continue;
            }

            stepsByDay[day] = step;
        }

        for (var day = 1; day <= CurrentWorkflowMaxDay; day++)
        {
            if (!stepsByDay.TryGetValue(day, out var step))
            {
                error = $"prototype_completion_missing_step:{day}";
                return false;
            }

            var status = step.TryGetProperty("status", out var statusElement)
                ? statusElement.GetString() ?? ""
                : "";
            if (!IsAcceptableWorkflowStep(day, status, step))
            {
                error = $"prototype_completion_step_not_ok:{day}:{status}";
                return false;
            }
        }

        return true;
    }

    private static bool IsAcceptableWorkflowStep(int day, string status, JsonElement step)
    {
        if (string.Equals(status, "ok", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (day == 2 && string.Equals(status, "skipped", StringComparison.OrdinalIgnoreCase))
        {
            var reason = step.TryGetProperty("reason", out var reasonElement)
                ? reasonElement.GetString() ?? ""
                : "";
            return string.Equals(reason, "prototype_scaffold_already_exists", StringComparison.OrdinalIgnoreCase);
        }

        return false;
    }

    private static bool TryResolvePrototypeSmokeScene(string repositoryRoot, string prototypeSpec, string slug, out string smokeScene, out string error)
    {
        smokeScene = "";
        error = "";

        var prototypeSpecPath = Path.Combine(repositoryRoot, prototypeSpec.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(prototypeSpecPath))
        {
            error = "prototype_completion_spec_missing";
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(prototypeSpecPath, System.Text.Encoding.UTF8));
            var root = document.RootElement;
            if (TryGetPrototypeManifestScene(root, out smokeScene) && IsValidPrototypeSceneForSlug(repositoryRoot, smokeScene, slug))
            {
                return true;
            }
        }
        catch (JsonException)
        {
            error = "prototype_completion_spec_invalid_json";
            return false;
        }
        catch (IOException)
        {
            error = "prototype_completion_spec_unreadable";
            return false;
        }

        if (TryFindGeneratedPrototypeScene(repositoryRoot, slug, out smokeScene))
        {
            return true;
        }

        error = "prototype_valid_godot_scene_missing";
        smokeScene = "";
        return false;
    }

    private static bool TryGetPrototypeManifestScene(JsonElement root, out string scene)
    {
        scene = "";
        if (!root.TryGetProperty("prototype_type_kit", out var typeKit) || typeKit.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        if (!typeKit.TryGetProperty("manifest", out var manifest) || manifest.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        if (manifest.TryGetProperty("default_scene", out var defaultScene) && defaultScene.ValueKind == JsonValueKind.String)
        {
            scene = defaultScene.GetString() ?? "";
        }

        if (string.IsNullOrWhiteSpace(scene) &&
            manifest.TryGetProperty("paths", out var paths) &&
            paths.ValueKind == JsonValueKind.Object &&
            paths.TryGetProperty("default_scene", out var pathScene) &&
            pathScene.ValueKind == JsonValueKind.String)
        {
            scene = pathScene.GetString() ?? "";
        }

        return !string.IsNullOrWhiteSpace(scene);
    }

    private static bool PrototypeSceneExists(string repositoryRoot, string scene)
    {
        return TryResolvePrototypeScenePath(repositoryRoot, scene, out _, out var fullPath)
               && IsValidGodotSceneFile(fullPath);
    }

    private static bool TryResolvePrototypeScenePath(string repositoryRoot, string scene, out string relativePath, out string fullPath)
    {
        relativePath = "";
        fullPath = "";
        if (string.IsNullOrWhiteSpace(scene) || !scene.StartsWith("res://", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        relativePath = scene["res://".Length..].Replace('/', Path.DirectorySeparatorChar);
        fullPath = Path.Combine(repositoryRoot, relativePath);
        return true;
    }

    private static bool TryFindGeneratedPrototypeScene(string repositoryRoot, string slug, out string scene)
    {
        scene = "";
        var prototypeSceneDirectory = Path.Combine(
            repositoryRoot,
            "Game.Godot",
            "Prototypes",
            PrototypeRecordWriter.SanitizeSlug(slug));
        if (!Directory.Exists(prototypeSceneDirectory))
        {
            return false;
        }

        foreach (var file in Directory.EnumerateFiles(prototypeSceneDirectory, "*.tscn", SearchOption.AllDirectories)
                     .OrderBy(path => path, StringComparer.OrdinalIgnoreCase))
        {
            if (!IsValidGodotSceneFile(file))
            {
                continue;
            }

            var relativePath = Path.GetRelativePath(repositoryRoot, file).Replace(Path.DirectorySeparatorChar, '/');
            scene = $"res://{relativePath}";
            return true;
        }

        return false;
    }

    private static bool IsValidPrototypeSceneForSlug(string repositoryRoot, string scene, string slug)
    {
        if (!TryResolvePrototypeScenePath(repositoryRoot, scene, out var relativePath, out var fullPath))
        {
            return false;
        }

        var expectedPrefix = Path.Combine("Game.Godot", "Prototypes", PrototypeRecordWriter.SanitizeSlug(slug)) + Path.DirectorySeparatorChar;
        if (!relativePath.StartsWith(expectedPrefix, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        return IsValidGodotSceneFile(fullPath);
    }

    private static bool IsValidGodotSceneFile(string fullPath)
    {
        if (!File.Exists(fullPath))
        {
            return false;
        }

        try
        {
            using var reader = new StreamReader(fullPath, System.Text.Encoding.UTF8, true);
            while (!reader.EndOfStream)
            {
                var line = reader.ReadLine();
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                return line.TrimStart().StartsWith("[gd_scene", StringComparison.Ordinal);
            }
        }
        catch (IOException)
        {
            return false;
        }

        return false;
    }

    private static bool IsLlmScoring(string? scoreEngine)
    {
        return string.Equals(scoreEngine, "codex", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(scoreEngine, "hybrid", StringComparison.OrdinalIgnoreCase);
    }

    private static string DefaultLabel(string status)
    {
        return status switch
        {
            "queued" => "已提交，等待 runner。",
            "running" => "原型路线运行中。",
            "succeeded" => "原型路线已完成。",
            "failed" => "原型路线失败。",
            _ => "尚未开始 7 日可玩原型路线。"
        };
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Length > 1600 ? value[^1600..] : value;
            }
        }

        return "";
    }

    private static string ResolveUserFacingFailure(RunSnapshot run)
    {
        var processTrace = FirstNonEmpty(run.StderrText, run.StdoutText);
        var translatedTrace = TranslateFailureForUser(processTrace);
        if (!string.Equals(translatedTrace, "原型路线失败，请查看运行记录。", StringComparison.Ordinal))
        {
            return translatedTrace;
        }

        var rawFailure = FirstNonEmpty(
            TryReadFailureCodeFromEvidence(run.EvidenceJson),
            run.StderrText,
            run.StdoutText,
            "原型路线失败。");
        return TranslateFailureForUser(rawFailure);
    }

    private static string? TryReadFailureCodeFromEvidence(string? evidenceJson)
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
                completion.TryGetProperty("error", out var errorElement) &&
                errorElement.ValueKind == JsonValueKind.String)
            {
                return errorElement.GetString();
            }

            if (document.RootElement.TryGetProperty("godot_smoke", out var smoke) &&
                smoke.ValueKind == JsonValueKind.Object &&
                smoke.TryGetProperty("reason", out var reasonElement) &&
                reasonElement.ValueKind == JsonValueKind.String)
            {
                return reasonElement.GetString();
            }
        }
        catch (JsonException)
        {
            return null;
        }

        return null;
    }

    private static string TranslateFailureForUser(string rawFailure)
    {
        if (string.IsNullOrWhiteSpace(rawFailure))
        {
            return "原型路线失败。";
        }

        if (rawFailure.Contains("prototype_valid_godot_scene_missing", StringComparison.OrdinalIgnoreCase) ||
            rawFailure.Contains("prototype_completion_scene_missing", StringComparison.OrdinalIgnoreCase))
        {
            return "没有创建有效的godot场景文件";
        }

        if (rawFailure.Contains("prototype_main_menu_navigation_failed", StringComparison.OrdinalIgnoreCase) ||
            rawFailure.Contains("MAIN_MENU_PROTOTYPE_NAV FAIL", StringComparison.OrdinalIgnoreCase))
        {
            return "Main.tscn 未能通过主菜单“原型”入口跳转到本次创建的原型场景。";
        }

        if (rawFailure.Contains("prototype_completion_state_missing", StringComparison.OrdinalIgnoreCase))
        {
            return "原型完成状态文件缺失。";
        }

        if (rawFailure.Contains("prototype_completion_spec_missing", StringComparison.OrdinalIgnoreCase))
        {
            return "原型规格文件缺失。";
        }

        if (rawFailure.Contains("prototype_completion_steps_missing", StringComparison.OrdinalIgnoreCase))
        {
            return "7步原型执行记录缺失。";
        }

        if (rawFailure.Contains("prototype_completion_step_not_ok", StringComparison.OrdinalIgnoreCase))
        {
            if (rawFailure.Contains(":3:skipped", StringComparison.OrdinalIgnoreCase))
            {
                return "TDD 红灯阶段未出现预期失败，当前原型不符合严格 TDD 预期。";
            }

            return "7步原型未完整跑通，至少有一个步骤未达到成功条件。";
        }

        if (rawFailure.Contains("PROTOTYPE_TDD status=unexpected_green", StringComparison.OrdinalIgnoreCase) &&
            rawFailure.Contains("stage=red", StringComparison.OrdinalIgnoreCase))
        {
            return "TDD 红灯阶段未出现预期失败，当前原型不符合严格 TDD 预期。";
        }

        if (rawFailure.Contains("prototype_packaging_summary_missing", StringComparison.OrdinalIgnoreCase))
        {
            return "原型打包摘要缺失。";
        }

        if (rawFailure.Contains("prototype_completion_summary_missing", StringComparison.OrdinalIgnoreCase))
        {
            return "原型完成总结缺失。";
        }

        if (rawFailure.Contains("prototype_completion_report_missing", StringComparison.OrdinalIgnoreCase))
        {
            return "原型完成报告缺失。";
        }

        if (rawFailure.Contains("prototype_workflow_failed", StringComparison.OrdinalIgnoreCase))
        {
            return "原型创建执行失败。";
        }

        if (rawFailure.Contains("prototype_repair_failed", StringComparison.OrdinalIgnoreCase))
        {
            return "原型修复执行失败。";
        }

        if (rawFailure.Contains("godot_bin_not_configured", StringComparison.OrdinalIgnoreCase))
        {
            return "服务器未配置 Godot，无法完成原型验收。";
        }

        if (rawFailure.Contains("prototype_completion_validation_failed", StringComparison.OrdinalIgnoreCase))
        {
            return "原型验收未通过。";
        }

        return "原型路线失败，请查看运行记录。";
    }

    private async Task<PrototypeWorkflowRequest> EnrichRequestFromLatestDraftAsync(
        string projectId,
        PrototypeWorkflowRequest request,
        CancellationToken cancellationToken)
    {
        var draft = await _metadataStore.GetProjectPrototypeDraftAsync(projectId, cancellationToken);
        if (draft is null)
        {
            return request;
        }

        var draftSuccessCriteria = DeserializeStringArray(draft.SuccessCriteriaJson);
        return new PrototypeWorkflowRequest(
            Slug: PreferDraftSlug(request.Slug, draft.PrototypeSlug),
            GameName: request.GameName,
            GameType: request.GameType,
            GameTypeSource: request.GameTypeSource,
            Hypothesis: PreferDraftText(request.Hypothesis, draft.Hypothesis),
            CorePlayerFantasy: PreferDraftText(request.CorePlayerFantasy, draft.CorePlayerFantasy),
            MinimumPlayableLoop: PreferDraftText(request.MinimumPlayableLoop, draft.MinimumPlayableLoop),
            SuccessCriteria: PreferDraftList(request.SuccessCriteria, draftSuccessCriteria),
            GameFeature: PreferDraftText(request.GameFeature, draft.GameFeature),
            CoreGameplayLoop: PreferDraftText(request.CoreGameplayLoop, draft.CoreGameplayLoop),
            WinFailConditions: PreferDraftText(request.WinFailConditions, draft.WinFailConditions),
            Confirm: request.Confirm,
            StopAfterDay: request.StopAfterDay,
            ScoreEngine: request.ScoreEngine,
            Model: request.Model);
    }

    private static PrototypeWorkflowRequest EnrichRequestFromProject(ProjectSnapshot project, PrototypeWorkflowRequest request)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(request);

        var normalizedGameType = NormalizeGameType(project.GameTypeSource);
        return request with
        {
            GameName = PreferProjectText(request.GameName, project.GameName),
            GameType = PreferProjectText(request.GameType, normalizedGameType),
            GameTypeSource = PreferProjectText(request.GameTypeSource, project.GameTypeSource)
        };
    }

    private static string? PreferDraftSlug(string? current, string? draft)
    {
        var candidate = PreferDraftText(current, draft);
        return string.IsNullOrWhiteSpace(candidate) ? null : PrototypeRecordWriter.SanitizeSlug(candidate);
    }

    private static string? PreferDraftText(string? current, string? draft)
    {
        if (string.IsNullOrWhiteSpace(draft))
        {
            return current;
        }

        return string.IsNullOrWhiteSpace(current) || LooksCorruptedText(current)
            ? draft.Trim()
            : current.Trim();
    }

    private static string? PreferProjectText(string? current, string? projectValue)
    {
        if (string.IsNullOrWhiteSpace(projectValue))
        {
            return string.IsNullOrWhiteSpace(current) ? current : current.Trim();
        }

        return string.IsNullOrWhiteSpace(current) || LooksCorruptedText(current)
            ? projectValue.Trim()
            : current.Trim();
    }

    private static IReadOnlyList<string>? PreferDraftList(IReadOnlyList<string>? current, IReadOnlyList<string> draft)
    {
        var normalizedCurrent = (current ?? [])
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .Select(item => item.Trim())
            .ToArray();
        if (draft.Count == 0)
        {
            return normalizedCurrent;
        }

        return normalizedCurrent.Length == 0 || normalizedCurrent.All(LooksCorruptedText)
            ? draft.ToArray()
            : normalizedCurrent;
    }

    private static bool LooksCorruptedText(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var text = value.Trim();
        return text.Contains("??", StringComparison.Ordinal) || text.Contains('\uFFFD');
    }

    private static string[] DeserializeStringArray(string json)
    {
        if (string.IsNullOrWhiteSpace(json))
        {
            return [];
        }

        try
        {
            return JsonSerializer.Deserialize<string[]>(json) ?? [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static string? NormalizeGameType(string? gameTypeSource)
    {
        if (string.IsNullOrWhiteSpace(gameTypeSource))
        {
            return null;
        }

        var lowered = gameTypeSource.Trim().ToLowerInvariant();
        if (lowered.Contains("rpg", StringComparison.Ordinal) || lowered.Contains("角色扮演", StringComparison.Ordinal) || lowered.Contains("勇者斗恶龙", StringComparison.Ordinal))
        {
            return "rpg";
        }

        return null;
    }

    private static readonly (string Step, string Substep, string Label)[] ProgressSteps =
    [
        ("running_step01_intake", "", "Step 01：正在整理输入信息。"),
        ("running_step02_brief", "", "Step 02：正在形成原型简报。"),
        ("running_step03_design", "analyzing", "Step 03：正在分析玩法方向。"),
        ("running_step03_design", "planning", "Step 03：正在规划最小可玩循环。"),
        ("running_step03_design", "freezing_scope", "Step 03：正在冻结本次原型范围。"),
        ("running_step04_implementation", "scaffolding", "Step 04：正在搭建实现骨架。"),
        ("running_step04_implementation", "coding", "Step 04：正在实现核心逻辑。"),
        ("running_step04_implementation", "asset_wiring", "Step 04：正在接线资源与占位资产。"),
        ("running_step04_implementation", "scene_wiring", "Step 04：正在接线 Godot 原型场景。"),
        ("running_step05_verification", "unit_tests", "Step 05：正在运行单元测试。"),
        ("running_step05_verification", "godot_smoke", "Step 05：正在运行 Godot 冒烟验证。"),
        ("running_step05_verification", "playability_check", "Step 05：正在检查可玩性。"),
        ("running_step05_verification", "fixing", "Step 05：正在处理验证发现的问题。"),
        ("running_step06_packaging", "", "Step 06：正在整理产物与报告。"),
        ("running_step07_review", "", "Step 07：正在生成最终摘要。")
    ];

    private sealed record GodotSmokeResult(
        bool Ran,
        int ExitCode,
        string Stdout,
        string Stderr,
        string Reason,
        string? ScenePath)
    {
        public static GodotSmokeResult NotRun(string reason, string? scenePath = null)
        {
            return new GodotSmokeResult(false, 0, "", "", reason, scenePath);
        }

        public object ToEvidence()
        {
            return new
            {
                ran = Ran,
                exit_code = ExitCode,
                reason = Reason,
                scene = ScenePath
            };
        }
    }

    private sealed record PrototypeCompletionValidation(
        bool Succeeded,
        string Status,
        int CompletedThroughDay,
        string? Error,
        string? SmokeScene,
        string? CompletionSummary)
    {
        public static PrototypeCompletionValidation Failure(string error)
        {
            return new PrototypeCompletionValidation(false, "", 0, error, null, null);
        }

        public static PrototypeCompletionValidation Success(string status, int completedThroughDay, string smokeScene, string? completionSummary)
        {
            return new PrototypeCompletionValidation(true, status, completedThroughDay, null, smokeScene, completionSummary);
        }

        public object ToEvidence()
        {
            return new
            {
                succeeded = Succeeded,
                status = Status,
                completed_through_day = CompletedThroughDay,
                error = Error,
                smoke_scene = SmokeScene,
                completion_summary = CompletionSummary
            };
        }
    }

    private sealed record PrototypePackagingSummaryReadback(
        string? DefaultScene,
        string? DefaultSceneLabel,
        int TddSummaryCount,
        int TddRedCount,
        int TddGreenCount,
        int TddRefactorCount,
        IReadOnlyList<string> PlaytestFocusPoints);

}
