using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeWorkflowService
{
    private const string RunType = "prototype-7day-playable";

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

        var missing = PrototypeWorkflowValidation.MissingRequiredFields(request);
        if (missing.Count > 0)
        {
            return new PrototypeWorkflowResult("", "missing_required_fields", 2, "", "", "", [], missing);
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
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
        var smoke = process.ExitCode == 0
            ? await RunPostPrototypeGodotSmokeAsync(project.RepoPath, cancellationToken)
            : GodotSmokeResult.NotRun("prototype_workflow_failed");
        var status = process.ExitCode == 0 && smoke.ExitCode == 0 ? "succeeded" : "failed";
        var exitCode = process.ExitCode != 0 ? process.ExitCode : smoke.ExitCode;
        var stdout = CombineProcessText(process.Stdout, smoke.Stdout);
        var stderr = CombineProcessText(process.Stderr, smoke.Stderr);
        var slug = PrototypeRecordWriter.SanitizeSlug(request.Slug!);
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

        var missing = PrototypeWorkflowValidation.MissingRequiredFields(request);
        if (missing.Count > 0)
        {
            return new PrototypeWorkflowResult("", "missing_required_fields", 2, "", "", "", [], missing);
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
        {
            throw new InvalidOperationException("Project not found.");
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

        var runs = await _metadataStore.ListRunsForProjectAsync(projectId, cancellationToken);
        var run = runs.FirstOrDefault(item => item.RunType == RunType);
        if (run is null)
        {
            return new PrototypeWorkflowProgress("idle", "", "", "尚未开始 7 日可玩原型路线。", null, null, null);
        }

        var step = string.IsNullOrWhiteSpace(run.ProgressStep) ? run.Status : run.ProgressStep;
        var label = string.IsNullOrWhiteSpace(run.ProgressLabel) ? DefaultLabel(run.Status) : run.ProgressLabel;
        return new PrototypeWorkflowProgress(
            run.Status,
            step,
            run.ProgressSubstep,
            label,
            run.ProgressUpdatedUtc,
            run.RunId,
            run.Status == "failed" ? FirstNonEmpty(run.StderrText, run.StdoutText, "原型路线失败。") : null);
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
        var smoke = process.ExitCode == 0
            ? await RunPostPrototypeGodotSmokeAsync(projectRepoPath, CancellationToken.None)
            : GodotSmokeResult.NotRun("prototype_workflow_failed");
        var status = process.ExitCode == 0 && smoke.ExitCode == 0 ? "succeeded" : "failed";
        var exitCode = process.ExitCode != 0 ? process.ExitCode : smoke.ExitCode;
        var stdout = CombineProcessText(process.Stdout, smoke.Stdout);
        var stderr = CombineProcessText(process.Stderr, smoke.Stderr);
        var slug = PrototypeRecordWriter.SanitizeSlug(request.Slug!);
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
        await _metadataStore.MarkRunStartedAsync(runId, CancellationToken.None);
        await SetProgressAsync(runId, "repairing", "prepare", "正在基于上一次失败原因修复原型。", CancellationToken.None);
        await AdvancePrototypeStepsAsync(runId, CancellationToken.None);

        _workspaceSeeder.EnsureSeeded(projectRepoPath);
        var repairRequest = new PrototypeWorkflowRequest(
            Slug: ExtractSlugFromPrototypeRecordPath(prototypeRecordPath),
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
        var smoke = process.ExitCode == 0
            ? await RunPostPrototypeGodotSmokeAsync(projectRepoPath, CancellationToken.None)
            : GodotSmokeResult.NotRun("prototype_repair_failed");
        var status = process.ExitCode == 0 && smoke.ExitCode == 0 ? "succeeded" : "failed";
        var exitCode = process.ExitCode != 0 ? process.ExitCode : smoke.ExitCode;
        var stdout = CombineProcessText(process.Stdout, smoke.Stdout);
        var stderr = CombineProcessText(process.Stderr, smoke.Stderr);
        var slug = ExtractSlugFromPrototypeRecordPath(prototypeRecordPath);
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

    private async Task<GodotSmokeResult> RunPostPrototypeGodotSmokeAsync(string projectRepoPath, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(_options.GodotBin))
        {
            return GodotSmokeResult.NotRun("godot_bin_not_configured");
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
                "res://Game.Godot/Scenes/Main.tscn",
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
        return new GodotSmokeResult(true, result.ExitCode, result.Stdout, result.Stderr, "strict_headless_main_scene");
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
        string Reason)
    {
        public static GodotSmokeResult NotRun(string reason)
        {
            return new GodotSmokeResult(false, 0, "", "", reason);
        }

        public object ToEvidence()
        {
            return new
            {
                ran = Ran,
                exit_code = ExitCode,
                reason = Reason
            };
        }
    }

}
