using System.Text.Json;
using System.Text.RegularExpressions;
using System.Text;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Prototypes;
using PhaseA.Platform.Workspaces;
using PhaseA.Platform.Workflow;
using Microsoft.Extensions.DependencyInjection;

namespace PhaseA.Platform.Runs;

public sealed class PrototypeWorkflowService : IPrototypeFromGddWorkflow
{
    private const string RunType = "prototype-7day-playable";
    private const string GddRelativePath = "docs/gdd/GDD.md";
    private const string OutlineRelativePath = "docs/gdd/gdd-outline.json";
    private const int CurrentWorkflowMaxDay = 7;
    private const string RepairReasoningEffort = "high";
    private static readonly TimeSpan DefaultCreationTotalTimeout = TimeSpan.FromHours(1);
    private static readonly TimeSpan DefaultCreationInactivityTimeout = TimeSpan.FromMinutes(25);
    private static readonly TimeSpan RepairExecutionTimeout = TimeSpan.FromMinutes(12);

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly IHostedProcessRunner _processRunner;
    private readonly PrototypeRecordWriter _recordWriter;
    private readonly PrototypeWorkflowCommandBuilder _commandBuilder;
    private readonly PrototypeArtifactIndexer _artifactIndexer;
    private readonly LlmBindingService _llmBindingService;
    private readonly LlmStopLossService _llmStopLossService;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly GameTypeTemplateCatalog _templateCatalog;
    private readonly PrototypeRouteStateWriter _routeStateWriter;
    private readonly PrototypeContractService _contractService;
    private readonly PrototypeContractFreezeService _contractFreezeService;
    private readonly PrototypeEngineeringClosureService _engineeringClosure;
    private readonly IAiCodeMirrorBillingClient _billingClient;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly HeavyRunnerQueueService _prototypeCreationQueue;
    private readonly TimeSpan _creationTotalTimeout;
    private readonly TimeSpan _creationInactivityTimeout;

    public PrototypeWorkflowService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        IHostedProcessRunner processRunner,
        PrototypeRecordWriter recordWriter,
        PrototypeWorkflowCommandBuilder commandBuilder,
        PrototypeArtifactIndexer artifactIndexer,
        LlmBindingService llmBindingService,
        LlmStopLossService llmStopLossService)
        : this(metadataStore, options, processRunner, recordWriter, commandBuilder, artifactIndexer, llmBindingService, llmStopLossService, new ProjectWorkspaceSeeder(options), new GameTypeTemplateCatalog(options), new PrototypeRouteStateWriter(), new PrototypeContractService())
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
        IProjectWorkspaceSeeder workspaceSeeder,
        GameTypeTemplateCatalog templateCatalog,
        PrototypeRouteStateWriter? routeStateWriter = null,
        PrototypeContractService? contractService = null,
        PrototypeEngineeringClosureService? engineeringClosure = null,
        IAiCodeMirrorBillingClient? billingClient = null,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        HeavyRunnerQueueService? heavyRunnerQueue = null,
        [FromKeyedServices("prototype-creation")] HeavyRunnerQueueService? prototypeCreationQueue = null,
        TimeSpan? creationTotalTimeout = null,
        TimeSpan? creationInactivityTimeout = null,
        PrototypeContractFreezeService? contractFreezeService = null)
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
        _templateCatalog = templateCatalog;
        _routeStateWriter = routeStateWriter ?? new PrototypeRouteStateWriter();
        _contractService = contractService ?? new PrototypeContractService();
        _contractFreezeService = contractFreezeService ?? new PrototypeContractFreezeService(metadataStore);
        _engineeringClosure = engineeringClosure ?? new PrototypeEngineeringClosureService();
        _billingClient = billingClient ?? new DisabledAiCodeMirrorBillingClient();
        _keyPoolService = keyPoolService;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
        _prototypeCreationQueue = prototypeCreationQueue ?? _heavyRunnerQueue;
        _creationTotalTimeout = creationTotalTimeout ?? DefaultCreationTotalTimeout;
        _creationInactivityTimeout = creationInactivityTimeout ?? DefaultCreationInactivityTimeout;
    }

    public async Task<PrototypeWorkflowResult> RunAsync(string accountId, string projectId, PrototypeWorkflowRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var newChainGuard = _contractFreezeService.EvaluateNewChainGuard(project);
        if (newChainGuard.NewChainActive && !newChainGuard.Allowed)
        {
            return new PrototypeWorkflowResult(
                "",
                newChainGuard.Status,
                409,
                "",
                "",
                newChainGuard.Summary,
                [],
                []);
        }

        var lockedPrototype = await RejectPrototypeCreationIfLockedAsync(project, cancellationToken);
        if (lockedPrototype is not null)
        {
            return lockedPrototype;
        }

        if (string.IsNullOrWhiteSpace(request.SourceDocumentPath))
        {
            request = await EnrichRequestFromLatestDraftAsync(project.ProjectId, request, cancellationToken);
        }
        request = EnrichRequestFromProject(project, request);
        request = NormalizePrototypeSlug(project, request);
        EnsureTemplateManifestExistsForGameType(request);
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
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeWorkflowResult("", routeSkill.FailureCode, 428, "", "", routeSkill.FailureMessage, [], []);
        }

        EnsureGameTypeTemplateBaseline(project.RepoPath, request);
        var prototypeRecordPath = _recordWriter.Write(request, project.RepoPath);
        var contract = _contractService.WriteFromRequest(project, request, prototypeRecordPath, PrototypeRecordWriter.SanitizeSlug(request.Slug!));
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await SetProgressAsync(runId, "queued", "", "已提交，等待 runner。", cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeWorkflowResult(runId, "project_busy", 423, prototypeRecordPath, "", "Project runner is busy.", [], [], await GetProgressForProjectAsync(project, cancellationToken));
        }

        try
        {
        await using var heavyRunnerLease = await _prototypeCreationQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, cancellationToken);
        await SetProgressAsync(runId, "preparing", "write_record", "正在写入原型记录并准备执行环境。", cancellationToken);
        await AdvancePrototypeStepsAsync(runId, cancellationToken);

        var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, cancellationToken);
        var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
        var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, cancellationToken);
        var process = await RunPrototypeCreationCodexAsync(
            runId,
            _commandBuilder.Build(request, prototypeRecordPath, project.RepoPath),
            runtimeCredential,
            cancellationToken);
        var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None));
        var slug = ResolvePrototypeSlug(project.RepoPath, prototypeRecordPath, request.Slug!);
        var validation = process.ExitCode == 0
            ? ValidateCompletedPrototypeState(project.RepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_workflow_failed");
        var smoke = process.ExitCode == 0 && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunPostPrototypeGodotSmokeAsync(project.RepoPath, validation.SmokeScene, cancellationToken)
            : PrototypeGodotSmokeResult.NotRun(process.ExitCode != 0 ? "prototype_workflow_failed" : "prototype_completion_validation_failed");
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
            prototype_contract = contract.RelativePath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, cancellationToken);
        WritePrototypeRouteState(project, runId, status, exitCode, prototypeRecordPath, contract.RelativePath, slug, validation, smoke);
        await WriteSkeletonEngineeringClosureAsync(project, runId, status, smoke.ExitCode, discoveredArtifacts.Select(a => a.RelativePath).ToArray(), cancellationToken);
        await SetProgressAsync(
            runId,
            status,
            "",
            status == "succeeded" ? "游戏场景创建已完成。" : "游戏场景创建失败，请查看运行记录错误输出。",
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

        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            PrototypeModelPolicy.Normalize(request.Model),
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: RunType,
                model: PrototypeModelPolicy.Normalize(request.Model),
                tokenUsage: CodexUsageExtractor.Extract(process.Stdout, process.Stderr),
                runType: RunType,
                projectId: project.ProjectId,
                route: "prototype",
                exitCode: exitCode,
                providerBilling: providerBilling),
            cancellationToken);

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);

        return new PrototypeWorkflowResult(runId, status, exitCode, prototypeRecordPath, stdout, stderr, artifacts, [], await GetProgressForProjectAsync(project, cancellationToken));
        }
        catch (Exception ex)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), FailureEvidenceJson(prototypeRecordPath), CancellationToken.None);
            await SetProgressAsync(runId, "failed", "", "Prototype skeleton creation failed. Check run stderr for details.", CancellationToken.None);
            return new PrototypeWorkflowResult(runId, "failed", 500, prototypeRecordPath, "", ex.ToString(), [], [], await GetProgressForProjectAsync(project, CancellationToken.None));
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    public async Task<PrototypeWorkflowResult> QueueAsync(string accountId, string projectId, PrototypeWorkflowRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var lockedPrototype = await RejectPrototypeCreationIfLockedAsync(project, cancellationToken);
        if (lockedPrototype is not null)
        {
            return lockedPrototype;
        }

        if (string.IsNullOrWhiteSpace(request.SourceDocumentPath))
        {
            request = await EnrichRequestFromLatestDraftAsync(project.ProjectId, request, cancellationToken);
        }
        request = EnrichRequestFromProject(project, request);
        request = NormalizePrototypeSlug(project, request);
        EnsureTemplateManifestExistsForGameType(request);
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
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeWorkflowResult("", routeSkill.FailureCode, 428, "", "", routeSkill.FailureMessage, [], []);
        }

        EnsureGameTypeTemplateBaseline(project.RepoPath, request);
        var prototypeRecordPath = _recordWriter.Write(request, project.RepoPath);
        var contract = _contractService.WriteFromRequest(project, request, prototypeRecordPath, PrototypeRecordWriter.SanitizeSlug(request.Slug!));
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await SetProgressAsync(runId, "queued", "", "已提交，等待 runner。", cancellationToken);

        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeWorkflowResult(runId, "project_busy", 423, prototypeRecordPath, "", "Project runner is busy.", [], [], await GetProgressForProjectAsync(project, cancellationToken));
        }

        _ = Task.Run(async () =>
        {
            try
            {
                await _prototypeCreationQueue.ExecuteAsync(
                    runId,
                    project.AccountId,
                    project.ProjectId,
                    RunType,
                    async (queueStart, _) =>
                    {
                        await RunQueuedAsync(project.ProjectId, project.WorkspaceId, project.RepoPath, runId, prototypeRecordPath, contract.RelativePath, request, queueStart.QueuePositionAtStart);
                        return true;
                    },
                    CancellationToken.None);
            }
            catch (Exception ex)
            {
                await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), FailureEvidenceJson(prototypeRecordPath), CancellationToken.None);
                await SetProgressAsync(runId, "failed", "", "游戏场景创建失败，请查看运行记录错误输出。", CancellationToken.None);
            }
            finally
            {
                await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
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
            await GetProgressForProjectAsync(project, cancellationToken));
    }

    public async Task<PrototypeWorkflowResult> QueueFromGddAsync(
        string accountId,
        string projectId,
        PrototypeFromGddRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var gddPath = Path.Combine(project.RepoPath, GddRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(gddPath))
        {
            return new PrototypeWorkflowResult("", "gdd_not_found", 404, "", "", "Create the GDD before creating the prototype skeleton.", [], []);
        }

        var gddText = await File.ReadAllTextAsync(gddPath, Encoding.UTF8, cancellationToken);
        if (string.IsNullOrWhiteSpace(gddText))
        {
            return new PrototypeWorkflowResult("", "gdd_empty", 409, "", "", "The current GDD is empty.", [], []);
        }

        var incompleteOutlineSections = await ReadIncompleteGddOutlineSectionsAsync(project, cancellationToken);
        if (incompleteOutlineSections.Count > 0)
        {
            return new PrototypeWorkflowResult(
                "",
                "gdd_outline_incomplete",
                409,
                "",
                "",
                $"请先补全所有策划大纲章节后再创建游戏场景。未补全：{string.Join("、", incompleteOutlineSections.Take(5))}",
                [],
                []);
        }

        await GddMilestoneSpecDocumentWriter.WriteFromGddAsync(project, gddText, cancellationToken);
        var workflowRequest = BuildPrototypeRequestFromGdd(project, gddText, request);
        return await QueueAsync(accountId, projectId, workflowRequest, cancellationToken);
    }

    private async Task<PrototypeWorkflowResult?> RejectPrototypeCreationIfLockedAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        if (!runs.Any(run =>
                run.RunType == RunType &&
                string.Equals(run.Status, "succeeded", StringComparison.OrdinalIgnoreCase) &&
                LatestPrototypeCompletionSucceeded(run.EvidenceJson)))
        {
            return null;
        }

        return new PrototypeWorkflowResult(
            "",
            "prototype_skeleton_locked",
            409,
            "",
            "",
            "Prototype skeleton has already been created and validated.",
            [],
            [],
            await GetProgressForProjectAsync(project, cancellationToken));
    }

    private static async Task<IReadOnlyList<string>> ReadIncompleteGddOutlineSectionsAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var outlinePath = Path.Combine(project.RepoPath, OutlineRelativePath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(outlinePath))
        {
            return [];
        }

        try
        {
            await using var stream = File.OpenRead(outlinePath);
            var outline = await JsonSerializer.DeserializeAsync<GameDesignOutlineDocument>(stream, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                ReadCommentHandling = JsonCommentHandling.Skip,
                AllowTrailingCommas = true
            }, cancellationToken);
            return (outline?.Sections ?? [])
                .Where(section => string.IsNullOrWhiteSpace(section.Content))
                .Select(section => string.IsNullOrWhiteSpace(section.Title) ? section.Id : section.Title)
                .Where(section => !string.IsNullOrWhiteSpace(section))
                .ToArray();
        }
        catch (JsonException)
        {
            return ["策划大纲文件无法解析"];
        }
    }

    public async Task<PrototypeWorkflowResult> RepairAsync(string accountId, string projectId, PrototypeRepairRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
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

        var postValidationFailureRun = runs.FirstOrDefault(run =>
            run.RunType == RunType &&
            SamePrototypeRecord(ExtractPrototypeRecordPath(run), prototypeRecordPath) &&
            ShouldUsePostValidationRepair(run));

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeWorkflowResult("", routeSkill.FailureCode, 428, prototypeRecordPath, "", routeSkill.FailureMessage, [], []);
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeWorkflowResult(runId, "project_busy", 423, prototypeRecordPath, "", "Project runner is busy.", [], [], await GetProgressForProjectAsync(project, cancellationToken));
        }
        await SetProgressAsync(runId, "queued", "repair", "已提交原型修复，等待 runner。", cancellationToken);

        _ = Task.Run(async () =>
        {
            try
            {
                await _heavyRunnerQueue.ExecuteAsync(
                    runId,
                    project.AccountId,
                    project.ProjectId,
                    RunType,
                    async (queueStart, _) =>
                    {
                        await RunRepairQueuedAsync(project.ProjectId, project.WorkspaceId, project.RepoPath, runId, prototypeRecordPath, latestPrototypeRun, postValidationFailureRun, request.Model, queueStart.QueuePositionAtStart);
                        return true;
                    },
                    CancellationToken.None);
                await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
            }
            catch (Exception ex)
            {
                await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), FailureEvidenceJson(prototypeRecordPath, repair: true), CancellationToken.None);
                await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
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
            await GetProgressForProjectAsync(project, cancellationToken));
    }

    public async Task<PrototypeWorkflowResult> ValidateAsync(string accountId, string projectId, CancellationToken cancellationToken = default)
    {
        return await ValidateExistingPrototypeAsync(accountId, projectId, RequireCompletedIterationPlan: true, SkeletonValidationOnly: false, cancellationToken);
    }

    public async Task<PrototypeWorkflowResult> ValidateSkeletonAsync(string accountId, string projectId, CancellationToken cancellationToken = default)
    {
        return await ValidateExistingPrototypeAsync(accountId, projectId, RequireCompletedIterationPlan: false, SkeletonValidationOnly: true, cancellationToken);
    }

    private async Task<PrototypeWorkflowResult> ValidateExistingPrototypeAsync(
        string accountId,
        string projectId,
        bool RequireCompletedIterationPlan,
        bool SkeletonValidationOnly,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var newChainGuard = _contractFreezeService.EvaluateNewChainGuard(project);
        if (SkeletonValidationOnly && newChainGuard.NewChainActive && !newChainGuard.Allowed)
        {
            return new PrototypeWorkflowResult(
                "",
                newChainGuard.Status,
                409,
                "",
                "",
                newChainGuard.Summary,
                [],
                []);
        }

        if (await _metadataStore.HasActiveRunAsync(project.ProjectId, cancellationToken))
        {
            return new PrototypeWorkflowResult("", "project_busy", 423, "", "", "Project runner is busy.", [], []);
        }

        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var latestPrototypeRun = runs.FirstOrDefault(run => run.RunType == RunType);
        var prototypeRecordPath = ExtractPrototypeRecordPath(latestPrototypeRun);
        if (string.IsNullOrWhiteSpace(prototypeRecordPath))
        {
            return new PrototypeWorkflowResult("", "prototype_validation_not_available", 404, "", "", "No prototype workflow record is available for validation.", [], []);
        }

        if (RequireCompletedIterationPlan)
        {
            var iterationReadiness = await ValidateIterationReadinessAsync(project.ProjectId, cancellationToken);
            if (iterationReadiness is not null)
            {
                return iterationReadiness;
            }
        }

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var routeSkill = PrototypeRouteSkillPolicy.EnsureAvailable(project);
        if (!routeSkill.IsAvailable)
        {
            return new PrototypeWorkflowResult("", routeSkill.FailureCode, 428, prototypeRecordPath, "", routeSkill.FailureMessage, [], []);
        }

        var slug = ReadSlugFromPrototypeRecord(project.RepoPath, prototypeRecordPath)
            ?? ExtractSlugFromPrototypeRecordPath(prototypeRecordPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var validationLabel = SkeletonValidationOnly
            ? "Validating the prototype skeleton without requiring a completed game module."
            : "Validating the current prototype without triggering generation.";
        await SetProgressAsync(runId, "validating", "completion_state", validationLabel, cancellationToken);
        var locked = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
        if (!locked)
        {
            await _metadataStore.CompleteRunAsync(runId, "blocked", 423, "", "runner lock already held", "{}", cancellationToken);
            return new PrototypeWorkflowResult(runId, "project_busy", 423, prototypeRecordPath, "", "Project runner is busy.", [], [], await GetProgressForProjectAsync(project, cancellationToken));
        }

        try
        {
        await using var heavyRunnerLease = await _heavyRunnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, cancellationToken);

        var dotnetBuild = await RunPrototypeDotnetBuildValidationAsync(project, cancellationToken);
        var validation = dotnetBuild.Passed
            ? ValidateCompletedPrototypeState(project.RepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_dotnet_build_failed");
        var smoke = dotnetBuild.Passed && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunPostPrototypeGodotSmokeAsync(project.RepoPath, validation.SmokeScene, cancellationToken)
            : PrototypeGodotSmokeResult.NotRun(dotnetBuild.Passed ? "prototype_completion_validation_failed" : "prototype_dotnet_build_failed");
        var rpgGdUnitValidation = dotnetBuild.Passed && validation.Succeeded && smoke.ExitCode == 0
            ? await PrototypeGodotSmokeService.RunRpgGdUnitValidationAsync(_options, _processRunner, project, slug, cancellationToken: cancellationToken)
            : PrototypeRpgGdUnitValidationResult.NotRequired(dotnetBuild.Passed ? "prototype_smoke_validation_failed" : "prototype_dotnet_build_failed");
        var status = dotnetBuild.Passed && validation.Succeeded && smoke.ExitCode == 0 && rpgGdUnitValidation.Passed ? "succeeded" : "failed";
        var validationExitCode = rpgGdUnitValidation.Required && !rpgGdUnitValidation.Passed && rpgGdUnitValidation.ExitCode == 0
            ? 1
            : Math.Max(dotnetBuild.ExitCode, Math.Max(smoke.ExitCode, rpgGdUnitValidation.ExitCode));
        var exitCode = ResolveRunExitCode(0, validationExitCode, dotnetBuild.Passed && validation.Succeeded && rpgGdUnitValidation.Passed);
        var stdout = CombineProcessText(CombineProcessText(CombineProcessText("Prototype validation-only acceptance executed.", dotnetBuild.Stdout), smoke.Stdout), rpgGdUnitValidation.Stdout);
        var rpgValidationFailure = rpgGdUnitValidation.Required && !rpgGdUnitValidation.Passed
            ? BuildRpgGdUnitValidationFailure(project, rpgGdUnitValidation)
            : "";
        var stderr = CombineProcessText(
            CombineProcessText(dotnetBuild.Passed ? "" : dotnetBuild.FailureSummary ?? "", validation.Error ?? ""),
            CombineProcessText(CombineProcessText(smoke.Stderr, rpgValidationFailure), rpgGdUnitValidation.Stderr));
        var discoveredArtifacts = _artifactIndexer.Discover(project.RepoPath, runId, project.ProjectId, slug, prototypeRecordPath);

        foreach (var artifact in discoveredArtifacts)
        {
            await _metadataStore.AddArtifactAsync(artifact, cancellationToken);
        }

        var contract = _contractService.Read(project);
        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            validation_only = true,
            skeleton_validation_only = SkeletonValidationOnly,
            prototype_record = prototypeRecordPath,
            prototype_contract = contract.RelativePath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            dotnet_build = dotnetBuild.ToEvidence(),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence(),
            rpg_gdunit_validation = rpgGdUnitValidation.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, cancellationToken);
        WritePrototypeRouteState(project, runId, status, exitCode, prototypeRecordPath, contract.RelativePath, slug, validation, smoke, rpgGdUnitValidation);
        await SetProgressAsync(
            runId,
            status,
            SkeletonValidationOnly ? "skeleton_validation" : "validation",
            status == "succeeded"
                ? SkeletonValidationOnly ? "Prototype skeleton validation passed." : "Prototype validation passed."
                : rpgGdUnitValidation.Required && !rpgGdUnitValidation.Passed
                    ? "RPG behavior validation failed. Generate or continue a repair plan before packaging."
                    : SkeletonValidationOnly ? "Prototype skeleton validation failed. Generate or continue a repair plan before creating game modules." : "Prototype validation failed. Generate or continue a repair plan before packaging.",
            cancellationToken);

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
        return new PrototypeWorkflowResult(runId, status, exitCode, prototypeRecordPath, stdout, stderr, artifacts, [], await GetProgressForProjectAsync(project, cancellationToken));
        }
        catch (Exception ex)
        {
            await _metadataStore.CompleteRunAsync(runId, "failed", 500, "", ex.ToString(), FailureEvidenceJson(prototypeRecordPath), CancellationToken.None);
            await SetProgressAsync(
                runId,
                "failed",
                SkeletonValidationOnly ? "skeleton_validation" : "validation",
                SkeletonValidationOnly
                    ? "Prototype skeleton validation failed. Generate or continue a repair plan before creating game modules."
                    : "Prototype validation failed. Generate or continue a repair plan before packaging.",
                CancellationToken.None);
            return new PrototypeWorkflowResult(runId, "failed", 500, prototypeRecordPath, "", ex.ToString(), [], [], await GetProgressForProjectAsync(project, CancellationToken.None));
        }
        finally
        {
            await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
        }
    }

    private async Task<PrototypeWorkflowResult?> ValidateIterationReadinessAsync(
        string projectId,
        CancellationToken cancellationToken)
    {
        var details = await _metadataStore.GetLatestProjectIterationSessionAsync(projectId, cancellationToken);
        if (details is null || details.Goals.Count == 0)
        {
            return new PrototypeWorkflowResult("", "iteration_plan_not_complete", 409, "", "", "Create and complete the game module before prototype acceptance.", [], []);
        }

        if (details.Goals.Any(goal => !IsCompletedIterationGoalStatus(goal.Status)))
        {
            return new PrototypeWorkflowResult("", "iteration_plan_not_complete", 409, "", "", "Complete the iteration plan before prototype acceptance.", [], []);
        }

        return null;
    }

    private async Task<PrototypeDotnetBuildValidation> RunPrototypeDotnetBuildValidationAsync(
        ProjectSnapshot project,
        CancellationToken cancellationToken)
    {
        var projectPath = ResolvePrototypeBuildProjectPath(project.RepoPath);
        if (string.IsNullOrWhiteSpace(projectPath))
        {
            return PrototypeDotnetBuildValidation.NotRequired("No C# project file was found for prototype build validation.");
        }

        using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(3));
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(timeout.Token, cancellationToken);
        try
        {
            var validationEnvironment = PrototypeValidationProcessEnvironment.Create(project.RepoPath);
            var buildArguments = IsGodotBuildProject(project.RepoPath, projectPath)
                ? PrototypeValidationProcessEnvironment.CreateMsBuildStabilityArguments()
                : PrototypeValidationProcessEnvironment.CreateMsBuildIsolationArguments(validationEnvironment, "prototype-lightweight-build");
            var result = await _processRunner.RunAsync(
                new HostedProcessCommand(
                    "dotnet",
                    [
                        "build",
                        projectPath,
                        "-c",
                        "Debug",
                        "-v",
                        "minimal",
                        .. buildArguments
                    ],
                    project.RepoPath,
                    validationEnvironment),
                linked.Token);

            return PrototypeDotnetBuildValidation.FromResult(project.RepoPath, projectPath, result);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested && timeout.IsCancellationRequested)
        {
            return PrototypeDotnetBuildValidation.Timeout(project.RepoPath, projectPath);
        }
    }

    private static string? ResolvePrototypeBuildProjectPath(string repoPath)
    {
        var candidates = new[]
        {
            Path.Combine(repoPath, "GodotGame.csproj"),
            Path.Combine(repoPath, "Game.Core", "Game.Core.csproj")
        };

        return candidates.FirstOrDefault(File.Exists);
    }

    private static bool IsGodotBuildProject(string repoPath, string projectPath)
    {
        return string.Equals(
            Path.GetFullPath(projectPath),
            Path.GetFullPath(Path.Combine(repoPath, "GodotGame.csproj")),
            StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsCompletedIterationGoalStatus(string? status)
    {
        return string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase);
    }

    public async Task<PrototypeWorkflowProgress> GetProgressAsync(string accountId, string projectId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        return await GetProgressForProjectAsync(project, cancellationToken);
    }

    private async Task<PrototypeWorkflowProgress> GetProgressForProjectAsync(ProjectSnapshot project, CancellationToken cancellationToken)
    {
        var runs = await _metadataStore.ListRunsForProjectAsync(project.ProjectId, cancellationToken);
        var latestRun = runs.FirstOrDefault(item => item.RunType == RunType);
        if (latestRun is null)
        {
            return new PrototypeWorkflowProgress("idle", "", "", "尚未开始游戏场景创建。", null, null, null, null, null, null, null);
        }

        latestRun = await RecoverCompletedPrototypeRunIfNeededAsync(project, latestRun, cancellationToken);
        var effectiveRuns = latestRun == runs.FirstOrDefault(item => item.RunType == RunType)
            ? runs
            : runs.Select(item => item.RunId == latestRun.RunId ? latestRun : item).ToArray();
        var latestIteration = await _metadataStore.GetLatestProjectIterationSessionAsync(project.ProjectId, cancellationToken);
        var latestIterationCompletionUtc = LatestIterationCompletionUtc(latestIteration);
        var creationRun = ResolvePrototypeCreationRun(effectiveRuns, latestRun);
        var finalValidationRun = ResolveFinalValidationRun(effectiveRuns, latestIterationCompletionUtc);
        var progressRun = IsFinalValidationOnlyRun(latestRun) &&
                          finalValidationRun is null &&
                          latestIterationCompletionUtc.HasValue
            ? creationRun ?? latestRun
            : latestRun;
        var readbackRun = creationRun ?? progressRun;
        var step = string.IsNullOrWhiteSpace(progressRun.ProgressStep) ? progressRun.Status : progressRun.ProgressStep;
        var label = string.IsNullOrWhiteSpace(progressRun.ProgressLabel) ? DefaultLabel(progressRun.Status) : progressRun.ProgressLabel;
        var completionSummary = ReadCompletionSummaryFromRun(progressRun);
        var nextStepSource = ReadNextStepSourceFromRun(progressRun);
        var nextStepEvaluation = ReadNextStepEvaluationFromRun(progressRun);
        var nextStepEvaluationReason = ReadNextStepEvaluationReasonFromRun(progressRun);
        var packaging = ReadPackagingSummaryFromRun(project.RepoPath, readbackRun);
        var prototypeCreationStatus = creationRun?.Status ?? (IsAnyValidationOnlyRun(progressRun) ? "missing" : progressRun.Status);
        var prototypeCreationFailure = string.Equals(prototypeCreationStatus, "failed", StringComparison.OrdinalIgnoreCase)
            ? ResolveUserFacingFailure(creationRun ?? progressRun)
            : null;
        var acceptanceFailure = finalValidationRun is not null &&
                                string.Equals(finalValidationRun.Status, "failed", StringComparison.OrdinalIgnoreCase)
            ? ResolveUserFacingFailure(finalValidationRun)
            : null;
        return new PrototypeWorkflowProgress(
            progressRun.Status,
            step,
            progressRun.ProgressSubstep,
            label,
            progressRun.ProgressUpdatedUtc,
            progressRun.RunId,
            string.Equals(progressRun.Status, "failed", StringComparison.OrdinalIgnoreCase)
                ? ResolveUserFacingFailure(progressRun)
                : null,
            completionSummary,
            nextStepSource,
            nextStepEvaluation,
            nextStepEvaluationReason,
            packaging?.DefaultScene,
            packaging?.DefaultSceneLabel,
            packaging?.TddSummaryCount,
            packaging?.TddRedCount,
            packaging?.TddGreenCount,
            packaging?.TddRefactorCount,
            packaging?.PlaytestFocusPoints,
            ReadPrototypeFormSnapshot(project.RepoPath, readbackRun),
            prototypeCreationStatus,
            prototypeCreationFailure,
            creationRun?.RunId,
            finalValidationRun?.Status,
            acceptanceFailure,
            finalValidationRun?.RunId);
    }

    private static RunSnapshot? ResolvePrototypeCreationRun(IReadOnlyList<RunSnapshot> runs, RunSnapshot latestRun)
    {
        return runs.FirstOrDefault(item =>
                   item.RunType == RunType &&
                   string.Equals(item.Status, "succeeded", StringComparison.OrdinalIgnoreCase) &&
                   !IsAnyValidationOnlyRun(item) &&
                   LatestPrototypeCompletionSucceeded(item.EvidenceJson)) ??
               (!IsAnyValidationOnlyRun(latestRun) ? latestRun : null);
    }

    private static RunSnapshot? ResolveFinalValidationRun(IReadOnlyList<RunSnapshot> runs, DateTimeOffset? latestIterationCompletionUtc)
    {
        var run = runs
            .Where(item => item.RunType == RunType && IsFinalValidationOnlyRun(item))
            .OrderByDescending(RunSortTimeUtc)
            .ThenByDescending(item => item.RunId, StringComparer.Ordinal)
            .FirstOrDefault();
        if (run is null || !latestIterationCompletionUtc.HasValue)
        {
            return run;
        }

        var runTime = RunSortTimeUtc(run);
        return runTime >= latestIterationCompletionUtc.Value ? run : null;
    }

    private static DateTimeOffset? LatestIterationCompletionUtc(ProjectIterationSessionDetails? iteration)
    {
        if (iteration is null || iteration.Goals.Count == 0 || !iteration.Goals.All(goal => IsDone(goal.Status)))
        {
            return null;
        }

        var times = iteration.Goals
            .Select(goal => ParseUtc(goal.CompletedUtc ?? goal.UpdatedUtc ?? goal.CreatedUtc))
            .Where(time => time.HasValue)
            .Select(time => time!.Value)
            .ToArray();
        return times.Length == 0 ? null : times.Max();
    }

    private static bool IsDone(string? status)
    {
        return string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "completed", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "done", StringComparison.OrdinalIgnoreCase);
    }

    private static DateTimeOffset RunSortTimeUtc(RunSnapshot run)
    {
        return ParseUtc(run.FinishedUtc) ??
               ParseUtc(run.ProgressUpdatedUtc) ??
               ParseUtc(run.StartedUtc) ??
               ParseUtc(run.CreatedUtc) ??
               DateTimeOffset.MinValue;
    }

    private static DateTimeOffset? ParseUtc(string? value)
    {
        return DateTimeOffset.TryParse(value, out var parsed) ? parsed : null;
    }

    private static bool IsFinalValidationOnlyRun(RunSnapshot run)
    {
        return IsAnyValidationOnlyRun(run) && !IsSkeletonValidationOnlyRun(run);
    }

    private static bool IsSkeletonValidationOnlyRun(RunSnapshot run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty("skeleton_validation_only", out var value) &&
                   value.ValueKind == JsonValueKind.True;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool IsAnyValidationOnlyRun(RunSnapshot run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty("validation_only", out var validationOnly) &&
                   validationOnly.ValueKind == JsonValueKind.True;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private async Task<RunSnapshot> RecoverCompletedPrototypeRunIfNeededAsync(ProjectSnapshot project, RunSnapshot run, CancellationToken cancellationToken)
    {
        if (!IsUnfinishedRunStatus(run.Status) ||
            !string.IsNullOrWhiteSpace(run.EvidenceJson) ||
            IsNonCreationPrototypeProgress(run))
        {
            return run;
        }

        var recovered = TryBuildRecoveredCompletion(project.RepoPath);
        if (recovered is null)
        {
            return run;
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            prototype_record = recovered.PrototypeRecordPath,
            prototype_contract = "",
            slug = recovered.Slug,
            prototype_artifacts = recovered.Artifacts,
            prototype_completion = recovered.Validation.ToEvidence(),
            godot_smoke = PrototypeGodotSmokeResult.NotRun("recovered_from_completion_artifacts").ToEvidence(),
            recovered_from_completion_artifacts = true
        });
        await _metadataStore.CompleteRunAsync(
            run.RunId,
            "succeeded",
            0,
            "Recovered completed prototype workflow from active prototype artifacts.",
            "",
            evidenceJson,
            cancellationToken);
        await SetProgressAsync(run.RunId, "succeeded", "", "游戏场景创建已完成。", cancellationToken);
        return await _metadataStore.GetRunSnapshotAsync(run.RunId, cancellationToken) ?? run;
    }

    private static bool IsNonCreationPrototypeProgress(RunSnapshot run)
    {
        return ContainsAny(
            string.Join("\n", run.ProgressStep, run.ProgressSubstep, run.ProgressLabel),
            "repair",
            "post_validation",
            "godot_diagnostic",
            "completion_state",
            "正在修复",
            "修复",
            "Validating the current prototype");
    }

    private static bool IsUnfinishedRunStatus(string status)
    {
        return string.Equals(status, "queued", StringComparison.OrdinalIgnoreCase) ||
               string.Equals(status, "running", StringComparison.OrdinalIgnoreCase);
    }

    private static RecoveredPrototypeCompletion? TryBuildRecoveredCompletion(string repositoryRoot)
    {
        var activeRoot = Path.Combine(repositoryRoot, "logs", "ci", "active-prototypes");
        if (!Directory.Exists(activeRoot))
        {
            return null;
        }

        foreach (var activePath in Directory.EnumerateFiles(activeRoot, "*.active.json")
                     .OrderByDescending(File.GetLastWriteTimeUtc))
        {
            var slug = Path.GetFileNameWithoutExtension(activePath).Replace(".active", "", StringComparison.OrdinalIgnoreCase);
            if (string.IsNullOrWhiteSpace(slug))
            {
                continue;
            }

            var validation = ValidateCompletedPrototypeState(repositoryRoot, slug);
            if (!validation.Succeeded)
            {
                continue;
            }

            var prototypeRecordPath = TryReadPrototypeFileFromActiveState(activePath);
            var packagingPath = Path.Combine("logs", "ci", "active-prototypes", $"{PrototypeRecordWriter.SanitizeSlug(slug)}.packaging.json")
                .Replace('\\', '/');
            var completionPath = Path.Combine("logs", "ci", "active-prototypes", $"{PrototypeRecordWriter.SanitizeSlug(slug)}.completion.md")
                .Replace('\\', '/');
            var artifacts = new[] { prototypeRecordPath, packagingPath, completionPath }
                .Where(path => !string.IsNullOrWhiteSpace(path))
                .Select(path => path!)
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();
            return new RecoveredPrototypeCompletion(slug, prototypeRecordPath ?? "", artifacts, validation);
        }

        return null;
    }

    private static string? TryReadPrototypeFileFromActiveState(string activePath)
    {
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(activePath, Encoding.UTF8));
            return document.RootElement.TryGetProperty("prototype_file", out var element) && element.ValueKind == JsonValueKind.String
                ? element.GetString()
                : null;
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

    private static PrototypeWorkflowFormSnapshot? ReadPrototypeFormSnapshot(string repositoryRoot, RunSnapshot run)
    {
        var relativePath = ReadPrototypeRecordPathFromRun(run);
        if (string.IsNullOrWhiteSpace(relativePath))
        {
            return null;
        }

        var normalized = relativePath.Replace('\\', '/').TrimStart('/');
        if (normalized.Contains("..", StringComparison.Ordinal) ||
            !normalized.StartsWith("docs/prototypes/", StringComparison.OrdinalIgnoreCase) ||
            !normalized.EndsWith(".md", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var absolutePath = Path.Combine(repositoryRoot, normalized.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(absolutePath))
        {
            return null;
        }

        var markdown = File.ReadAllText(absolutePath, Encoding.UTF8);
        return new PrototypeWorkflowFormSnapshot(
            PrototypeSlug: ReadPrototypeField(markdown, "slug"),
            Hypothesis: ReadPrototypeField(markdown, "hypothesis"),
            CorePlayerFantasy: ReadPrototypeField(markdown, "core_player_fantasy"),
            MinimumPlayableLoop: ReadPrototypeField(markdown, "minimum_playable_loop"),
            SuccessCriteria: SplitSuccessCriteria(ReadPrototypeField(markdown, "success_criteria")),
            GameFeature: ReadPrototypeField(markdown, "game_feature"),
            CoreGameplayLoop: ReadPrototypeField(markdown, "core_gameplay_loop"),
            WinFailConditions: ReadPrototypeField(markdown, "win_fail_conditions"),
            SourcePath: normalized);
    }

    private static string? ReadPrototypeRecordPathFromRun(RunSnapshot run)
    {
        if (string.IsNullOrWhiteSpace(run.EvidenceJson))
        {
            return null;
        }

        try
        {
            using var document = JsonDocument.Parse(run.EvidenceJson);
            return document.RootElement.TryGetProperty("prototype_record", out var element)
                ? element.GetString()
                : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string? ReadPrototypeField(string markdown, string field)
    {
        var pattern = @"^\|\s*" + Regex.Escape(field) + @"\s*\|\s*(.*?)\s*\|";
        var match = Regex.Match(markdown, pattern, RegexOptions.Multiline | RegexOptions.IgnoreCase);
        if (!match.Success)
        {
            return null;
        }

        var value = match.Groups[1].Value.Trim();
        return string.Equals(value, "TBD", StringComparison.OrdinalIgnoreCase)
            ? null
            : value.Replace("<br>", "\n", StringComparison.OrdinalIgnoreCase).Replace("\\|", "|", StringComparison.Ordinal);
    }

    private static IReadOnlyList<string>? SplitSuccessCriteria(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var items = value.Split(';', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        return items.Length == 0 ? null : items;
    }

    private async Task RunQueuedAsync(
        string projectId,
        string? workspaceId,
        string projectRepoPath,
        string runId,
        string prototypeRecordPath,
        string prototypeContractPath,
        PrototypeWorkflowRequest request,
        int queuePositionAtStart)
    {
        await _metadataStore.MarkRunStartedAsync(runId, queuePositionAtStart, CancellationToken.None);
        await SetProgressAsync(runId, "preparing", "write_record", "正在写入原型记录并准备执行环境。", CancellationToken.None);
        await AdvancePrototypeStepsAsync(runId, CancellationToken.None);

        _workspaceSeeder.EnsureSeeded(projectRepoPath);
        EnsureGameTypeTemplateBaseline(projectRepoPath, request);
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, CancellationToken.None)
            ?? throw new InvalidOperationException("Project not found.");
        var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
        var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
        var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None);
        var process = await RunPrototypeCreationCodexAsync(
            runId,
            _commandBuilder.Build(request, prototypeRecordPath, projectRepoPath),
            runtimeCredential,
            CancellationToken.None);
        var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None));
        var slug = ResolvePrototypeSlug(projectRepoPath, prototypeRecordPath, request.Slug!);
        var validation = process.ExitCode == 0
            ? ValidateCompletedPrototypeState(projectRepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_workflow_failed");
        var smoke = process.ExitCode == 0 && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunQueuedPostPrototypeGodotSmokeAsync(projectRepoPath, validation.SmokeScene, CancellationToken.None)
            : PrototypeGodotSmokeResult.NotRun(process.ExitCode != 0 ? "prototype_workflow_failed" : "prototype_completion_validation_failed");
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
            prototype_contract = prototypeContractPath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        WritePrototypeRouteState(project, runId, status, exitCode, prototypeRecordPath, prototypeContractPath, slug, validation, smoke);
        var projectSnapshot = await _metadataStore.GetProjectSnapshotAsync(projectId, CancellationToken.None);
        if (projectSnapshot is not null)
        {
            await WriteSkeletonEngineeringClosureAsync(projectSnapshot, runId, status, smoke.ExitCode, discoveredArtifacts.Select(a => a.RelativePath).ToArray(), CancellationToken.None);
        }
        await SetProgressAsync(
            runId,
            status,
            "",
            status == "succeeded" ? "游戏场景创建已完成。" : "游戏场景创建失败，请查看运行记录错误输出。",
            CancellationToken.None);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            PrototypeModelPolicy.Normalize(request.Model),
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: RunType,
                model: PrototypeModelPolicy.Normalize(request.Model),
                tokenUsage: CodexUsageExtractor.Extract(process.Stdout, process.Stderr),
                runType: RunType,
                projectId: projectId,
                route: "prototype",
                exitCode: exitCode,
                providerBilling: providerBilling),
            CancellationToken.None);
    }

    private async Task RunRepairQueuedAsync(
        string projectId,
        string? workspaceId,
        string projectRepoPath,
        string runId,
        string prototypeRecordPath,
        RunSnapshot failedRun,
        RunSnapshot? postValidationFailureRun,
        string? model,
        int queuePositionAtStart)
    {
        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, CancellationToken.None)
            ?? throw new InvalidOperationException("Project not found.");
        await _metadataStore.MarkRunStartedAsync(runId, queuePositionAtStart, CancellationToken.None);
        await SetProgressAsync(runId, "repairing", "prepare", "正在基于上一次失败原因修复原型。", CancellationToken.None);
        await AdvancePrototypeStepsAsync(runId, CancellationToken.None);

        _workspaceSeeder.EnsureSeeded(projectRepoPath);
        var effectiveSlug = ReadSlugFromPrototypeRecord(projectRepoPath, prototypeRecordPath)
            ?? ExtractSlugFromPrototypeRecordPath(prototypeRecordPath);
        var repairBasisRun = postValidationFailureRun ?? failedRun;
        var godotDiagnostic = GodotFailureDiagnosticService.Analyze(project, repairBasisRun);
        await SetProgressAsync(runId, "repairing", "godot_diagnostic", "Checking recent Godot validation errors before repair.", CancellationToken.None);
        var godotCleanup = await GodotFailureDiagnosticService.CleanupIfRecommendedAsync(project, godotDiagnostic, CancellationToken.None);
        if (ShouldUsePostValidationRepair(repairBasisRun))
        {
            await RunPostValidationRepairQueuedAsync(project, runId, prototypeRecordPath, effectiveSlug, repairBasisRun, model, godotDiagnostic, godotCleanup);
            return;
        }

        var repairRequest = new PrototypeWorkflowRequest(
            Slug: effectiveSlug,
            GameName: project.GameName,
            GameType: ResolveCanonicalGameType(project),
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
        var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
        var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
        var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None);
        HostedProcessResult process;
        try
        {
            using var timeout = new CancellationTokenSource(RepairExecutionTimeout);
            process = await _processRunner.RunAsync(CodexHostedProcessCommandFactory.ApplyRuntime(_commandBuilder.Build(repairRequest, prototypeRecordPath, projectRepoPath), runtimeCredential).WithRunId(runId), timeout.Token);
        }
        catch (OperationCanceledException)
        {
            process = new HostedProcessResult(408, "", $"Prototype repair exceeded the {RepairExecutionTimeout.TotalMinutes:0} minute timeout.");
        }
        var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None));
        var slug = ReadSlugFromPrototypeRecord(projectRepoPath, prototypeRecordPath)
            ?? effectiveSlug;
        var validation = process.ExitCode == 0
            ? ValidateCompletedPrototypeState(projectRepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_repair_failed");
        var smoke = process.ExitCode == 0 && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunPostPrototypeGodotSmokeAsync(projectRepoPath, validation.SmokeScene, CancellationToken.None)
            : PrototypeGodotSmokeResult.NotRun(process.ExitCode != 0 ? "prototype_repair_failed" : "prototype_completion_validation_failed");
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
            prototype_contract = _contractService.Read(project).RelativePath,
            slug,
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            prototype_completion = validation.ToEvidence(),
            godot_diagnostic = GodotFailureDiagnosticService.ToEvidence(godotDiagnostic, godotCleanup),
            godot_smoke = smoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        await SetProgressAsync(
            runId,
            status,
            "repair",
            status == "succeeded" ? "原型修复已完成。" : "原型修复失败，请查看新的失败原因。",
            CancellationToken.None);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            PrototypeModelPolicy.Normalize(model),
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: RunType,
                model: PrototypeModelPolicy.Normalize(model),
                tokenUsage: CodexUsageExtractor.Extract(process.Stdout, process.Stderr),
                runType: RunType,
                projectId: project.ProjectId,
                route: "prototype-repair",
                exitCode: exitCode,
                providerBilling: providerBilling),
            CancellationToken.None);
    }

    private async Task<HostedProcessResult> RunPrototypeCreationCodexAsync(
        string runId,
        HostedProcessCommand command,
        AiCodeMirrorRuntimeCredential runtimeCredential,
        CancellationToken cancellationToken)
    {
        try
        {
            await SetProgressAsync(runId, "running_step07_review", "generation", "Prototype skeleton creation is running.", CancellationToken.None);
            return await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(command, runtimeCredential)
                    .WithRunId(runId)
                    .WithTimeouts(totalTimeout: _creationTotalTimeout, inactivityTimeout: _creationInactivityTimeout)
                    .WithActivityWatchPaths(PrototypeCreationActivityWatchPaths(), TimeSpan.FromSeconds(10)),
                cancellationToken);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            return new HostedProcessResult(
                408,
                "",
                $"Prototype skeleton creation exceeded the {_creationTotalTimeout.TotalMinutes:0.##} minute timeout.");
        }
    }

    private static IReadOnlyList<string> PrototypeCreationActivityWatchPaths()
    {
        return
        [
            Path.Combine("logs", "ci"),
            Path.Combine("Game.Core", "Prototypes"),
            Path.Combine("Game.Core.Tests", "Prototypes"),
            Path.Combine("Game.Godot", "Prototypes"),
            Path.Combine("Tests.Godot", "tests", "Prototype"),
            Path.Combine("meta", "routes")
        ];
    }

    private async Task RunPostValidationRepairQueuedAsync(
        ProjectSnapshot project,
        string runId,
        string prototypeRecordPath,
        string slug,
        RunSnapshot failedRun,
        string? model,
        GodotFailureDiagnostic godotDiagnostic,
        GodotCacheCleanupResult godotCleanup)
    {
        await SetProgressAsync(runId, "repairing", "post_validation", "正在修复原型后置验收失败项。", CancellationToken.None);
        var contract = _contractService.Read(project);
        var preferredShellScene = ResolvePreferredPrototypeShellScene(project.RepoPath, slug);
        var previousRepairState = _routeStateWriter.ReadLatestPrototypeRepairState(project);
        var projectExecutionGuide = _routeStateWriter.ReadOrCreateProjectExecutionGuide(project, contract);
        var outputPath = CreateShortRuntimeOutputPath(runId);
        var normalizedModel = PrototypeModelPolicy.Normalize(model);
        var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, CancellationToken.None);
        var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
        var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None);
        HostedProcessResult codexResult;
        try
        {
            using var timeout = new CancellationTokenSource(RepairExecutionTimeout);
            codexResult = await _processRunner.RunAsync(
                CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexRepairCommand(BuildPostValidationRepairPrompt(project, prototypeRecordPath, slug, preferredShellScene, previousRepairState, projectExecutionGuide, failedRun, contract, godotDiagnostic, godotCleanup), outputPath, normalizedModel, project.RepoPath), runtimeCredential).WithRunId(runId),
                timeout.Token);
        }
        catch (OperationCanceledException)
        {
            codexResult = new HostedProcessResult(408, "", $"Prototype post-validation repair exceeded the {RepairExecutionTimeout.TotalMinutes:0} minute timeout.");
        }
        var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None));
        var codexOutput = File.Exists(outputPath)
            ? await File.ReadAllTextAsync(outputPath, Encoding.UTF8, CancellationToken.None)
            : "";

        var validation = codexResult.ExitCode == 0
            ? ValidateCompletedPrototypeState(project.RepoPath, slug)
            : PrototypeCompletionValidation.Failure("prototype_post_validation_repair_failed");
        var smoke = codexResult.ExitCode == 0 && validation.Succeeded && !string.IsNullOrWhiteSpace(validation.SmokeScene)
            ? await RunPostPrototypeGodotSmokeAsync(project.RepoPath, validation.SmokeScene, CancellationToken.None)
            : PrototypeGodotSmokeResult.NotRun(codexResult.ExitCode != 0 ? "prototype_post_validation_repair_failed" : "prototype_completion_validation_failed");
        var status = codexResult.ExitCode == 0 && smoke.ExitCode == 0 && validation.Succeeded ? "succeeded" : "failed";
        var exitCode = ResolveRunExitCode(codexResult.ExitCode, smoke.ExitCode, validation.Succeeded);
        var stdout = CombineProcessText(CombineProcessText(codexResult.Stdout, codexOutput), smoke.Stdout);
        var stderr = codexResult.ExitCode == 0
            ? CombineProcessText(codexResult.Stderr, CombineProcessText(smoke.Stderr, validation.Error ?? ""))
            : CombineProcessText(codexResult.Stderr, smoke.Stderr);
        var discoveredArtifacts = _artifactIndexer.Discover(project.RepoPath, runId, project.ProjectId, slug, prototypeRecordPath);

        foreach (var artifact in discoveredArtifacts)
        {
            await _metadataStore.AddArtifactAsync(artifact, CancellationToken.None);
        }

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            repair = true,
            repair_mode = "post_validation",
            model = normalizedModel,
            prototype_record = prototypeRecordPath,
            prototype_contract = contract.RelativePath,
            slug,
            previous_failure = BuildCompactFailure(failedRun),
            prototype_artifacts = discoveredArtifacts.Select(a => a.RelativePath).ToArray(),
            prototype_completion = validation.ToEvidence(),
            godot_diagnostic = GodotFailureDiagnosticService.ToEvidence(godotDiagnostic, godotCleanup),
            godot_smoke = smoke.ToEvidence()
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        WritePrototypeRouteState(project, runId, status, exitCode, prototypeRecordPath, contract.RelativePath, slug, validation, smoke);
        WritePrototypeRepairState(project, runId, status, exitCode, prototypeRecordPath, slug, preferredShellScene, failedRun, validation, smoke);
        await SetProgressAsync(
            runId,
            status,
            "repair",
            status == "succeeded" ? "原型后置验收修复已完成。" : "原型后置验收修复失败，请查看新的失败原因。",
            CancellationToken.None);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            normalizedModel,
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: RunType,
                model: normalizedModel,
                tokenUsage: CodexUsageExtractor.Extract(codexResult.Stdout, codexResult.Stderr),
                runType: RunType,
                projectId: project.ProjectId,
                route: "prototype-post-validation-repair",
                exitCode: exitCode,
                providerBilling: providerBilling),
            CancellationToken.None);
    }

    private async Task WriteSkeletonEngineeringClosureAsync(
        ProjectSnapshot project,
        string runId,
        string status,
        int smokeExitCode,
        IReadOnlyList<string> changedFiles,
        CancellationToken cancellationToken)
    {
        _engineeringClosure.EnsureProjectFiles(project);
        await _engineeringClosure.WriteEvidenceAsync(
            project,
            new PrototypeEngineeringEvidence(
                runId,
                "skeleton-m1",
                string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ? "passed" : "failed",
                "M1",
                DotnetBuild: PrototypeEngineeringCheckResult.Skipped("skeleton route owns full route evidence in run metadata"),
                GodotImport: PrototypeEngineeringCheckResult.Skipped("skeleton route owns full route evidence in run metadata"),
                HeadlessLoad: smokeExitCode == 0
                    ? PrototypeEngineeringCheckResult.Passed()
                    : PrototypeEngineeringCheckResult.Failed(reason: $"smoke_exit_code={smokeExitCode}"),
                MilestoneSmoke: smokeExitCode == 0
                    ? PrototypeEngineeringCheckResult.Passed()
                    : PrototypeEngineeringCheckResult.Failed(reason: $"smoke_exit_code={smokeExitCode}"),
                AssetValidation: PrototypeEngineeringCheckResult.Skipped("not an asset-library route"),
                FrameCheck: PrototypeEngineeringCheckResult.Skipped("not required for skeleton route"),
                ChangedFiles: changedFiles,
                FailureSummary: string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase) ? [] : [$"status={status}; smoke_exit_code={smokeExitCode}"]),
            cancellationToken);
        await _engineeringClosure.TouchMemoryAsync(project, "skeleton-m1", runId, status, "M1", cancellationToken);
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

    private HostedProcessCommand BuildCodexRepairCommand(string prompt, string outputPath, string model, string repositoryRoot)
    {
        return CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            repositoryRoot,
            outputPath,
            prompt,
            model,
            RepairReasoningEffort,
            ExtraEnvironment: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["PATH"] = CodexHostedProcessCommandFactory.ResolvePathWithRipgrep()
            }));
    }

    private static string CreateShortRuntimeOutputPath(string runId)
    {
        var root = Path.Combine(Path.GetTempPath(), "phasea-prototype-repair", runId);
        Directory.CreateDirectory(root);
        return Path.Combine(root, "codex-output.txt");
    }

    private async Task<string> ResolveBillingApiKeyNameAsync(string accountId, CancellationToken cancellationToken)
    {
        return await (_keyPoolService?.ResolveKeyNameForAccountAsync(accountId, cancellationToken) ?? Task.FromResult<string?>(null))
               ?? accountId;
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

    private async Task<PrototypeGodotSmokeResult> RunPostPrototypeGodotSmokeAsync(string projectRepoPath, string scenePath, CancellationToken cancellationToken)
    {
        return await PrototypeGodotSmokeService.RunPostPrototypeAcceptanceAsync(_options, _processRunner, projectRepoPath, scenePath, cancellationToken);
    }

    private async Task<PrototypeGodotSmokeResult> RunQueuedPostPrototypeGodotSmokeAsync(string projectRepoPath, string scenePath, CancellationToken cancellationToken)
    {
        return await PrototypeGodotSmokeService.RunPostPrototypeAcceptanceAsync(_options, _processRunner, projectRepoPath, scenePath, cancellationToken);
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

    private static string BuildRpgGdUnitValidationFailure(ProjectSnapshot project, PrototypeRpgGdUnitValidationResult validation)
    {
        var lines = new List<string>
        {
            $"RPG project-specific GdUnit validation failed: {validation.Reason}"
        };

        var summaryPath = ResolveRpgGdUnitReportFile(project.RepoPath, validation.ReportDir, "run-summary.json");
        if (!string.IsNullOrWhiteSpace(summaryPath) && File.Exists(summaryPath))
        {
            lines.Add($"GDUNIT_SUMMARY: {TrimForPromptExcerpt(File.ReadAllText(summaryPath, Encoding.UTF8), 700)}");
        }

        var consolePath = ResolveRpgGdUnitReportFile(project.RepoPath, validation.ReportDir, "gdunit-console.txt");
        if (!string.IsNullOrWhiteSpace(consolePath) && File.Exists(consolePath))
        {
            var failures = ExtractGdUnitFailureSummary(File.ReadAllText(consolePath, Encoding.UTF8), 18);
            if (failures.Count > 0)
            {
                lines.Add("GDUNIT_FAILURES:");
                lines.AddRange(failures.Select(line => $"- {line}"));
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string? ResolveRpgGdUnitReportFile(string repoPath, string? reportDir, string fileName)
    {
        if (string.IsNullOrWhiteSpace(reportDir) || Path.IsPathRooted(reportDir))
        {
            return null;
        }

        var fullPath = Path.GetFullPath(Path.Combine(repoPath, reportDir.Replace('/', Path.DirectorySeparatorChar), fileName));
        var root = Path.GetFullPath(repoPath);
        return fullPath.StartsWith(root, StringComparison.OrdinalIgnoreCase) ? fullPath : null;
    }

    private static IReadOnlyList<string> ExtractGdUnitFailureSummary(string consoleText, int maxLines)
    {
        if (string.IsNullOrWhiteSpace(consoleText))
        {
            return [];
        }

        var cleaned = Regex.Replace(consoleText, @"\x1B\[[0-?]*[ -/]*[@-~]", "");
        var result = new List<string>();
        var captureFailure = false;
        foreach (var rawLine in cleaned.Split(['\r', '\n'], StringSplitOptions.RemoveEmptyEntries))
        {
            var line = rawLine.Trim();
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var isImportant = ContainsAny(
                line,
                "Statistics:",
                "Overall Summary:",
                "Exit code:",
                "ERROR:",
                "SCRIPT ERROR",
                "Node not found",
                "Parse Error",
                "Invalid call",
                "No test cases found",
                "FAILED",
                "Expecting:",
                "do contains");
            if (line.StartsWith("res://tests/Prototype/", StringComparison.OrdinalIgnoreCase))
            {
                captureFailure = line.Contains("FAILED", StringComparison.OrdinalIgnoreCase);
                isImportant = captureFailure;
            }
            else if (line.StartsWith("Report:", StringComparison.OrdinalIgnoreCase))
            {
                isImportant = true;
                captureFailure = true;
            }
            else if (captureFailure && (line.StartsWith("'", StringComparison.Ordinal) || line.Contains(" but is ", StringComparison.OrdinalIgnoreCase)))
            {
                isImportant = true;
            }

            if (!isImportant)
            {
                continue;
            }

            AddDistinctLine(result, TrimForPromptExcerpt(line, 500));
            if (result.Count >= maxLines)
            {
                break;
            }
        }

        return result;
    }

    private static void AddDistinctLine(List<string> lines, string line)
    {
        if (!string.IsNullOrWhiteSpace(line) &&
            !lines.Any(existing => string.Equals(existing, line, StringComparison.OrdinalIgnoreCase)))
        {
            lines.Add(line);
        }
    }

    private static bool ContainsAny(string text, params string[] values)
    {
        return values.Any(value => text.Contains(value, StringComparison.OrdinalIgnoreCase));
    }

    private static string TrimForPromptExcerpt(string value, int maxLength)
    {
        var compact = string.IsNullOrWhiteSpace(value)
            ? ""
            : Regex.Replace(value.Trim(), @"\s+", " ");
        return PrototypePromptText.TrimHeadAndTail(compact, maxLength);
    }

    private static bool ShouldUsePostValidationRepair(RunSnapshot failedRun)
    {
        if (!string.Equals(failedRun.Status, "failed", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (!LatestPrototypeCompletionSucceeded(failedRun.EvidenceJson))
        {
            return false;
        }

        var combined = string.Join("\n", failedRun.StdoutText, failedRun.StderrText, failedRun.EvidenceJson);
        return combined.Contains("MAIN_MENU_PROTOTYPE_NAV FAIL", StringComparison.OrdinalIgnoreCase) ||
               combined.Contains("prototype_main_menu_navigation_failed", StringComparison.OrdinalIgnoreCase) ||
               combined.Contains("rpg_start_button_missing", StringComparison.OrdinalIgnoreCase) ||
               combined.Contains("strict_headless_prototype_scene", StringComparison.OrdinalIgnoreCase);
    }

    private static bool SamePrototypeRecord(string? left, string? right)
    {
        if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right))
        {
            return false;
        }

        return string.Equals(
            left.Replace('\\', '/').Trim(),
            right.Replace('\\', '/').Trim(),
            StringComparison.OrdinalIgnoreCase);
    }

    private static bool LatestPrototypeCompletionSucceeded(string? evidenceJson)
    {
        if (string.IsNullOrWhiteSpace(evidenceJson))
        {
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(evidenceJson);
            if (!document.RootElement.TryGetProperty("prototype_completion", out var completion) ||
                completion.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            var succeededFlag = completion.TryGetProperty("succeeded", out var succeeded) &&
                                succeeded.ValueKind is JsonValueKind.True;
            var completedAllDays = completion.TryGetProperty("completed_through_day", out var day) &&
                                   day.ValueKind == JsonValueKind.Number &&
                                   day.TryGetInt32(out var completedThroughDay) &&
                                   completedThroughDay >= CurrentWorkflowMaxDay;
            return succeededFlag || completedAllDays;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static string BuildCompactFailure(RunSnapshot failedRun)
    {
        return FirstNonEmpty(failedRun.StderrText, failedRun.StdoutText, TryReadFailureCodeFromEvidence(failedRun.EvidenceJson), "previous prototype validation failed");
    }

    private static string BuildPostValidationRepairPrompt(
        ProjectSnapshot project,
        string prototypeRecordPath,
        string slug,
        string preferredShellScene,
        string previousRepairState,
        string projectExecutionGuide,
        RunSnapshot failedRun,
        PrototypeContractSnapshot contract,
        GodotFailureDiagnostic godotDiagnostic,
        GodotCacheCleanupResult godotCleanup)
    {
        var godotDiagnosticBlock = GodotFailureDiagnosticService.BuildPromptBlock(godotDiagnostic, godotCleanup);
        return $"""
            You are running a Phase A post-validation prototype repair.

            This is not a fresh prototype workflow and not a TDD red-stage rerun. The previous prototype route already reached the end of the prototype workflow, but post-validation failed. Repair the existing prototype artifacts directly, then leave the normal completion artifacts intact or update them consistently.

            Project:
            - ProjectId: {project.ProjectId}
            - Name: {project.Name}
            - GameName: {project.GameName}
            - GameType: {project.GameTypeSource}
            - Slug: {slug}
            - PrototypeRecord: {prototypeRecordPath}
            - PreferredPrototypeShellScene: {preferredShellScene}

            {PrototypeRouteSkillPolicy.BuildPromptBlock(project)}
            {PrototypeContractService.BuildPromptBlock(contract)}
            {godotDiagnosticBlock}

            Project Execution Guide:
            {TrimPromptText(projectExecutionGuide, 2400)}

            Previous prototype repair state:
            {TrimRepairStateForPrompt(previousRepairState)}

            Previous failure:
            {BuildCompactFailure(failedRun)}

            Mandatory repair scope:
            - Repair only the hosted Godot prototype project files needed for the failed post-validation.
            - Use Prototype Chapter 6 Lite semantics: repair the existing prototype route evidence path, update lightweight route state, and do not create Taskmaster triplets, formal acceptance files, overlays, architecture contracts, or Chapter 6 review pipeline artifacts.
            - Do not regenerate the iteration plan.
            - Do not rerun or rewrite the prototype TDD red stage.
            - Treat the preferred prototype shell scene as the main navigation entry for smoke verification.
            - Do not use BattleScene or MapScene as the main entry scene for the repair route.
            - For RPG prototypes, ensure the main menu entry can navigate to this prototype scene, Start Adventure is visible and clickable, and Start Adventure reveals a non-empty map scene.
            - For RPG prototypes, prefer dedicated MapScene and BattleScene files under the prototype slug when missing, and keep map art, grid, and token overlay in one shared coordinate layer.
            - Main.tscn SOP: root-level VBox, Overlays, and ScreenRoot must exist and default to visible = false so template/debug UI does not cover the prototype route.
            - If the failure says rpg_start_button_missing, add or repair the Start Adventure button and the script path that reveals the RPG map scene.
            - Output must be browser-safe: no local paths, command lines, script names, log names, or environment variable values.

            Output format:
            STATUS: completed|needs_fix
            SUMMARY: 2-4 browser-safe sentences.
            CHANGED: 1-3 browser-safe lines.
            VERIFY: 1-3 browser-safe lines. If you cannot run engine validation, say what remains for platform smoke.
            REMAINING: none if complete, otherwise list blockers.
            """;
    }

    private void WritePrototypeRepairState(
        ProjectSnapshot project,
        string runId,
        string status,
        int exitCode,
        string prototypeRecordPath,
        string slug,
        string preferredShellScene,
        RunSnapshot failedRun,
        PrototypeCompletionValidation validation,
        PrototypeGodotSmokeResult smoke)
    {
        var failureCode = ResolveRepairFailureCode(validation, smoke);
        _routeStateWriter.WritePrototypeRepairState(project, new
        {
            route = $"{RunType}:repair",
            repair_mode = "post_validation",
            run_id = runId,
            status,
            exit_code = exitCode,
            prototype_record = prototypeRecordPath,
            slug,
            preferred_shell_scene = preferredShellScene,
            consumed_failure_run_id = failedRun.RunId,
            last_failure_code = failureCode,
            last_failure_summary = BuildRepairFailureSummary(failureCode),
            next_repair_focus = BuildNextRepairFocus(failureCode, preferredShellScene),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence(),
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
    }

    private static string ResolveRepairFailureCode(PrototypeCompletionValidation validation, PrototypeGodotSmokeResult smoke)
    {
        if (!validation.Succeeded)
        {
            return FirstNonEmpty(validation.Error, "prototype_completion_validation_failed");
        }

        if (smoke.Ran && smoke.ExitCode != 0)
        {
            return ExtractKnownRepairFailureCode(smoke.Stderr, smoke.Stdout, smoke.Reason);
        }

        return "none";
    }

    private static string ExtractKnownRepairFailureCode(params string?[] values)
    {
        var combined = string.Join("\n", values.Where(value => !string.IsNullOrWhiteSpace(value)));
        var knownCodes = new[]
        {
            "rpg_map_visible_markers_missing_after_start",
            "rpg_map_scene_has_no_visible_size_after_start",
            "rpg_map_scene_not_visible_after_start",
            "rpg_map_scene_missing_after_start",
            "rpg_start_button_missing",
            "prototype_scene_mismatch",
            "prototype_scene_not_loaded",
            "prototype_main_menu_navigation_failed",
            "strict_headless_prototype_scene"
        };

        return knownCodes.FirstOrDefault(code => combined.Contains(code, StringComparison.OrdinalIgnoreCase))
               ?? FirstNonEmpty(values)
               ?? "prototype_repair_failed";
    }

    private static string BuildRepairFailureSummary(string failureCode)
    {
        return failureCode switch
        {
            "none" => "Repair passed platform validation.",
            "rpg_map_visible_markers_missing_after_start" => "Start Adventure reached the map path, but the map scene is missing required visible markers.",
            "rpg_map_scene_has_no_visible_size_after_start" => "The map scene exists after Start Adventure but has no visible size.",
            "rpg_map_scene_not_visible_after_start" => "The map scene exists after Start Adventure but is not visible.",
            "rpg_map_scene_missing_after_start" => "Start Adventure did not reveal a map scene.",
            "rpg_start_button_missing" => "The RPG prototype shell is missing the Start Adventure button.",
            "main_scene_default_ui_not_hidden" => "Main.tscn root-level VBox, Overlays, or ScreenRoot is missing or default-visible.",
            "prototype_scene_mismatch" => "Main menu navigation reached a different scene than the expected prototype shell scene.",
            "prototype_scene_not_loaded" => "Main menu navigation did not load the prototype scene.",
            _ => failureCode
        };
    }

    private static string BuildNextRepairFocus(string failureCode, string preferredShellScene)
    {
        return failureCode switch
        {
            "none" => "No repair needed.",
            "rpg_map_visible_markers_missing_after_start" => "Keep the prototype shell as the main entry, then ensure the map scene shown after Start Adventure contains Grid plus either the legacy Title/StatusLabel markers or the current HeaderLabel/StatsLabel/ObjectiveLabel HUD markers.",
            "rpg_map_scene_has_no_visible_size_after_start" => "Set the map scene Control size to a visible non-zero area after Start Adventure.",
            "rpg_map_scene_not_visible_after_start" => "Ensure Start Adventure makes the map scene visible and hides only the intro shell UI.",
            "rpg_map_scene_missing_after_start" => "Wire Start Adventure to reveal or instantiate the map scene under the prototype shell.",
            "rpg_start_button_missing" => $"Ensure the prototype shell scene contains a visible Start Adventure button. Preferred shell: {preferredShellScene}",
            "main_scene_default_ui_not_hidden" => "Set Main.tscn root-level VBox, Overlays, and ScreenRoot to visible = false by default, without removing runtime navigation wiring.",
            "prototype_scene_mismatch" => $"Keep Main.tscn prototype navigation pointed at the preferred prototype shell scene: {preferredShellScene}",
            _ => "Use the latest platform validation error as the repair target and keep the prototype shell as the main entry scene."
        };
    }

    private static string TrimRepairStateForPrompt(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "none";
        }

        var trimmed = value.Trim();
        return trimmed.Length <= 4000 ? trimmed : trimmed[..4000];
    }

    private static string TrimPromptText(string value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "none";
        }

        var trimmed = value.Trim();
        return trimmed.Length <= maxLength ? trimmed : trimmed[..maxLength];
    }

    private static string ResolvePreferredPrototypeShellScene(string repositoryRoot, string slug)
    {
        var prototypeSceneDirectory = Path.Combine(
            repositoryRoot,
            "Game.Godot",
            "Prototypes",
            PrototypeRecordWriter.SanitizeSlug(slug));
        if (!Directory.Exists(prototypeSceneDirectory))
        {
            return "";
        }

        var exactName = $"{ToPascalCase(PrototypeRecordWriter.SanitizeSlug(slug))}Prototype.tscn";
        var exactPath = Path.Combine(prototypeSceneDirectory, exactName);
        if (IsValidGodotSceneFile(exactPath))
        {
            return $"res://{Path.GetRelativePath(repositoryRoot, exactPath).Replace(Path.DirectorySeparatorChar, '/')}";
        }

        return Directory.EnumerateFiles(prototypeSceneDirectory, "*.tscn", SearchOption.AllDirectories)
            .Where(IsValidGodotSceneFile)
            .Select(file => new
            {
                Path = file,
                Priority = GetPrototypeScenePriority(file)
            })
            .OrderBy(item => item.Priority, StringComparer.Ordinal)
            .ThenBy(item => item.Path, StringComparer.OrdinalIgnoreCase)
            .Select(item => $"res://{Path.GetRelativePath(repositoryRoot, item.Path).Replace(Path.DirectorySeparatorChar, '/')}")
            .FirstOrDefault() ?? "";
    }

    private static string ToPascalCase(string value)
    {
        var parts = value.Split(['-', '_'], StringSplitOptions.RemoveEmptyEntries);
        return string.Concat(parts.Select(part => char.ToUpperInvariant(part[0]) + part[1..]));
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

    private static string? ReadNextStepSourceFromRun(RunSnapshot run)
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
                !completion.TryGetProperty("next_step_source", out var sourceElement) ||
                sourceElement.ValueKind != JsonValueKind.String)
            {
                return null;
            }

            return sourceElement.GetString();
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string? ReadNextStepEvaluationFromRun(RunSnapshot run)
    {
        return ReadPrototypeCompletionStringField(run, "next_step_evaluation");
    }

    private static string? ReadNextStepEvaluationReasonFromRun(RunSnapshot run)
    {
        return ReadPrototypeCompletionStringField(run, "next_step_evaluation_reason");
    }

    private static string? ReadPrototypeCompletionStringField(RunSnapshot run, string fieldName)
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
                !completion.TryGetProperty(fieldName, out var fieldElement) ||
                fieldElement.ValueKind != JsonValueKind.String)
            {
                return null;
            }

            return fieldElement.GetString();
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

            var expectedEntryScene = BuildExpectedProjectEntryScene(slug);
            if (!string.Equals(smokeScene, expectedEntryScene, StringComparison.OrdinalIgnoreCase))
            {
                return PrototypeCompletionValidation.Failure($"prototype_project_entry_scene_mismatch:expected={expectedEntryScene};actual={smokeScene}");
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
            var nextStepSource = root.TryGetProperty("next_step_source", out var nextStepSourceElement) && nextStepSourceElement.ValueKind == JsonValueKind.String
                ? nextStepSourceElement.GetString()
                : null;
            var nextStepEvaluation = root.TryGetProperty("next_step_evaluation", out var nextStepEvaluationElement) && nextStepEvaluationElement.ValueKind == JsonValueKind.String
                ? nextStepEvaluationElement.GetString()
                : null;
            var nextStepEvaluationReason = root.TryGetProperty("next_step_evaluation_reason", out var nextStepEvaluationReasonElement) && nextStepEvaluationReasonElement.ValueKind == JsonValueKind.String
                ? nextStepEvaluationReasonElement.GetString()
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

            return PrototypeCompletionValidation.Success(status, completedThroughDay, smokeScene, completionSummary, nextStepSource, nextStepEvaluation, nextStepEvaluationReason);
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

        if ((day == 3 || day == 4) && string.Equals(status, "skipped", StringComparison.OrdinalIgnoreCase))
        {
            var reason = step.TryGetProperty("reason", out var reasonElement)
                ? reasonElement.GetString() ?? ""
                : "";
            return string.Equals(reason, "existing_project_specific_prototype_ready_for_green", StringComparison.OrdinalIgnoreCase);
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
                     .OrderBy(path => GetPrototypeScenePriority(path), StringComparer.OrdinalIgnoreCase)
                     .ThenBy(path => path, StringComparer.OrdinalIgnoreCase))
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

    private static string GetPrototypeScenePriority(string path)
    {
        var fileName = Path.GetFileNameWithoutExtension(path);
        if (fileName.Contains("prototype", StringComparison.OrdinalIgnoreCase))
        {
            return "0";
        }

        if (fileName.Contains("main", StringComparison.OrdinalIgnoreCase))
        {
            return "1";
        }

        return "2";
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

    private static string BuildExpectedProjectEntryScene(string slug)
    {
        var normalizedSlug = PrototypeRecordWriter.SanitizeSlug(slug);
        return $"res://Game.Godot/Prototypes/{normalizedSlug}/{ToPascalCase(normalizedSlug)}Prototype.tscn";
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
            "running" => "游戏场景创建运行中。",
            "succeeded" => "游戏场景创建已完成。",
            "failed" => "游戏场景创建失败。",
            _ => "尚未开始游戏场景创建。"
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
        if (!string.Equals(translatedTrace, "游戏场景创建失败，请查看运行记录。", StringComparison.Ordinal))
        {
            return translatedTrace;
        }

        var rawFailure = FirstNonEmpty(
            TryReadFailureCodeFromEvidence(run.EvidenceJson),
            run.StderrText,
            run.StdoutText,
            "游戏场景创建失败。");
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
            return "游戏场景创建失败。";
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
            return "游戏场景创建执行记录缺失。";
        }

        if (rawFailure.Contains("prototype_completion_step_not_ok", StringComparison.OrdinalIgnoreCase))
        {
            if (rawFailure.Contains(":3:skipped", StringComparison.OrdinalIgnoreCase))
            {
                return "TDD 红灯阶段未出现预期失败，当前原型不符合严格 TDD 预期。";
            }

            return "游戏场景创建未完整跑通，至少有一个步骤未达到成功条件。";
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
            return "服务器未配置 Godot，无法完成原型项目验收。";
        }

        if (rawFailure.Contains("prototype_completion_validation_failed", StringComparison.OrdinalIgnoreCase))
        {
            return "原型项目验收未通过。";
        }

        return "游戏场景创建失败，请查看运行记录。";
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
            Model: request.Model,
            SourceDocumentPath: request.SourceDocumentPath,
            SourceDocumentSummary: request.SourceDocumentSummary);
    }

    private static PrototypeWorkflowRequest EnrichRequestFromProject(ProjectSnapshot project, PrototypeWorkflowRequest request)
    {
        ArgumentNullException.ThrowIfNull(project);
        ArgumentNullException.ThrowIfNull(request);

        var normalizedGameType = ResolveCanonicalGameType(project);
        return request with
        {
            GameName = PreferProjectText(request.GameName, project.GameName),
            GameType = FirstNonEmpty(normalizedGameType, NormalizeGameType(request.GameType)),
            GameTypeSource = PreferProjectText(request.GameTypeSource, project.GameTypeSource)
        };
    }

    private static PrototypeWorkflowRequest NormalizePrototypeSlug(ProjectSnapshot project, PrototypeWorkflowRequest request)
    {
        var slug = PrototypeRecordWriter.ResolveProjectSlug(
            request.Slug,
            project.ProjectId,
            request.GameName,
            project.GameName,
            project.Name);

        return request with { Slug = slug };
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

    private static PrototypeWorkflowRequest BuildPrototypeRequestFromGdd(
        ProjectSnapshot project,
        string gddText,
        PrototypeFromGddRequest request)
    {
        var title = FirstMarkdownHeading(gddText) ?? FirstNonEmpty(project.GameName, project.Name, "prototype");
        var compact = CompactText(RemoveMarkdownNoise(gddText));
        var summary = TrimText(compact, 1800);
        var slug = PrototypeRecordWriter.ResolveProjectSlug(
            FirstNonEmpty(project.GameName, project.Name, title, "prototype"),
            project.ProjectId,
            project.GameName,
            project.Name,
            title);
        var loop = ExtractSection(gddText, "核心玩法", "核心循环", "玩法循环", "Core Loop", "Gameplay Loop", "Minimum Playable Loop");
        var controls = ExtractSection(gddText, "键盘", "鼠标", "操作", "Controls", "Input");
        var scenes = ExtractSection(gddText, "场景", "关卡", "地城", "地图", "World", "Level", "Scene");
        var milestones = ExtractSection(gddText, "里程碑", "Milestone", "Prototype", "验收", "Acceptance");
        var successCriteria = BuildGddSuccessCriteria(gddText, controls, scenes, loop, milestones);
        var physicsPolicy = PrototypePhysicsRequirementPolicy.BuildPromptBlock(project, gddText);
        var m1Title = ExtractFirstMilestoneTitle(gddText) ?? "M1：首个可玩场景与基础操作";
        var m1SpecPath = GddMilestoneSpecDocumentWriter.StepSpecRelativePath("M1", m1Title);

        return new PrototypeWorkflowRequest(
            Slug: slug,
            GameName: FirstNonEmpty(project.GameName, title),
            GameType: ResolveCanonicalGameType(project),
            GameTypeSource: project.GameTypeSource,
            Hypothesis: $"以当前项目 GDD 和 M1 spec 为设计来源，完成 M1 首个可玩模块；这一步同时承担游戏场景创建，验证 {FirstNonEmpty(title, project.GameName, project.Name)} 的基本操作、场景和首轮手感。",
            CorePlayerFantasy: TrimText(FirstNonEmpty(ExtractSection(gddText, "玩家幻想", "体验", "风格", "参考游戏", "Player Fantasy"), summary), 700),
            MinimumPlayableLoop: TrimText(FirstNonEmpty(loop, summary), 900),
            SuccessCriteria: successCriteria,
            GameFeature: TrimText(FirstNonEmpty(scenes, loop, summary) + $"\n\nM1 spec: {m1SpecPath}\nPrototype plan: docs/prototype-v1-plan.md\n\n" + physicsPolicy, 1200),
            CoreGameplayLoop: TrimText(FirstNonEmpty(loop, controls, summary) + $"\n\n游戏场景创建必须按 M1 首个可玩模块执行，而不是创建空壳。执行前必须读取 docs/gdd/GDD.md、docs/prototype-v1-plan.md 和 {m1SpecPath}。", 1100),
            WinFailConditions: TrimText(FirstNonEmpty(ExtractSection(gddText, "胜利", "失败", "目标", "Win", "Fail", "Goal"), milestones, summary), 700),
            Confirm: request.Confirm,
            StopAfterDay: request.StopAfterDay,
            ScoreEngine: string.IsNullOrWhiteSpace(request.ScoreEngine) ? "deterministic" : request.ScoreEngine,
            Model: request.Model,
            SourceDocumentPath: GddRelativePath,
            SourceDocumentSummary: TrimText($"{summary}\n\nRequired module spec for skeleton/M1: {m1SpecPath}\nThe skeleton route completes M1 first playable module: basic scene, controls, and first feel validation.", 2200));
    }

    private static string? ExtractFirstMilestoneTitle(string gddText)
    {
        foreach (Match match in Regex.Matches(gddText, @"(?im)^\s*(?:[-*]\s*)?(M1)\s*[:：\-]\s*(.+)$"))
        {
            var title = CompactText(match.Groups[2].Value);
            if (!string.IsNullOrWhiteSpace(title))
            {
                return $"M1：{TrimText(title, 80)}";
            }
        }

        return null;
    }

    private static IReadOnlyList<string> BuildGddSuccessCriteria(
        string gddText,
        string? controls,
        string? scenes,
        string? loop,
        string? milestones)
    {
        var criteria = new List<string>();
        AddCriterion(criteria, "游戏场景必须直接反映当前 GDD，不再使用旧表单或导入文件作为设计来源。");
        AddCriterion(criteria, FirstNonEmpty(controls, "键盘鼠标基础操作必须在首个可玩场景中有明确映射。"));
        AddCriterion(criteria, FirstNonEmpty(scenes, "必须创建能表达参考游戏方向的首个可玩场景或场景占位。"));
        AddCriterion(criteria, FirstNonEmpty(loop, "必须具备可进入、可操作、可反馈的基础玩法循环。"));
        AddCriterion(criteria, FirstNonEmpty(milestones, "后续游戏模块 step 必须能从 GDD 的里程碑或验收内容继续拆分。"));

        foreach (var bullet in ExtractAcceptanceBullets(gddText).Take(3))
        {
            AddCriterion(criteria, bullet);
        }

        return criteria;
    }

    private static IEnumerable<string> ExtractAcceptanceBullets(string text)
    {
        var capture = false;
        foreach (var rawLine in text.Split('\n'))
        {
            var line = rawLine.Trim();
            if (line.StartsWith("##", StringComparison.Ordinal))
            {
                capture = ContainsAny(line, "验收", "验证", "Acceptance", "Verification", "里程碑", "Milestone");
                continue;
            }

            if (!capture || line.Length < 4)
            {
                continue;
            }

            if (line.StartsWith("-", StringComparison.Ordinal) ||
                line.StartsWith("*", StringComparison.Ordinal) ||
                Regex.IsMatch(line, @"^\d+[\.)]\s+"))
            {
                yield return TrimText(Regex.Replace(line, @"^[-*]\s+|^\d+[\.)]\s+", ""), 220);
            }
        }
    }

    private static void AddCriterion(List<string> criteria, string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return;
        }

        var normalized = TrimText(CompactText(value), 260);
        if (!criteria.Any(item => string.Equals(item, normalized, StringComparison.OrdinalIgnoreCase)))
        {
            criteria.Add(normalized);
        }
    }

    private static string? FirstMarkdownHeading(string text)
    {
        foreach (var line in text.Split('\n'))
        {
            var trimmed = line.Trim();
            if (trimmed.StartsWith("# ", StringComparison.Ordinal))
            {
                return trimmed[2..].Trim();
            }
        }

        return null;
    }

    private static string? ExtractSection(string text, params string[] headingKeywords)
    {
        var lines = text.Split('\n');
        var capture = false;
        var captured = new List<string>();
        foreach (var rawLine in lines)
        {
            var line = rawLine.TrimEnd();
            if (line.TrimStart().StartsWith("#", StringComparison.Ordinal))
            {
                if (capture && captured.Count > 0)
                {
                    break;
                }

                capture = headingKeywords.Any(keyword => line.Contains(keyword, StringComparison.OrdinalIgnoreCase));
                continue;
            }

            if (capture)
            {
                captured.Add(line);
                if (captured.Count >= 18)
                {
                    break;
                }
            }
        }

        var value = CompactText(string.Join(" ", captured));
        return string.IsNullOrWhiteSpace(value) ? null : TrimText(value, 900);
    }

    private static string RemoveMarkdownNoise(string text)
    {
        var lines = text.Split('\n')
            .Select(line => Regex.Replace(line, @"^\s{0,3}#{1,6}\s*", ""))
            .Select(line => Regex.Replace(line, @"^\s*[-*]\s*", ""))
            .Select(line => Regex.Replace(line, @"\*\*|__|`", ""))
            .Where(line => !string.IsNullOrWhiteSpace(line));
        return string.Join(" ", lines);
    }

    private static string CompactText(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "" : Regex.Replace(value.Trim(), @"\s+", " ");
    }

    private static string TrimText(string? value, int maxLength)
    {
        var compact = CompactText(value);
        return compact.Length <= maxLength ? compact : compact[..maxLength].TrimEnd() + "...";
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

    private static string ResolveCanonicalGameType(ProjectSnapshot project)
    {
        var evidence = ProjectGameTypeMatchEvidence.FromJson(project.GameTypeMatchJson);
        return NormalizeGameType(evidence.MatchedGameTypeId) ?? "";
    }

    private static string? NormalizeGameType(string? gameTypeSource)
    {
        if (string.IsNullOrWhiteSpace(gameTypeSource))
        {
            return null;
        }

        var lowered = Regex.Replace(gameTypeSource.Trim().ToLowerInvariant(), "[^a-z0-9]+", "-").Trim('-');
        return string.IsNullOrWhiteSpace(lowered) ? null : lowered;
    }

    private void EnsureTemplateManifestExistsForGameType(PrototypeWorkflowRequest request)
    {
        var template = _templateCatalog.Find(request.GameType);
        if (template is null || !template.Enabled)
        {
            return;
        }

        var manifestPath = Path.Combine(_options.RepositoryRoot, template.ManifestPath.Replace('/', Path.DirectorySeparatorChar));
        if (!File.Exists(manifestPath))
        {
            throw new InvalidOperationException($"Game type template manifest missing for {template.GameType}: {template.ManifestPath}");
        }
    }

    private void WritePrototypeRouteState(
        ProjectSnapshot project,
        string runId,
        string status,
        int exitCode,
        string prototypeRecordPath,
        string prototypeContractPath,
        string slug,
        PrototypeCompletionValidation validation,
        PrototypeGodotSmokeResult smoke,
        PrototypeRpgGdUnitValidationResult? rpgGdUnitValidation = null)
    {
        var localEntry = BuildLocalEntryContract(project.RepoPath, slug, validation);
        _routeStateWriter.WritePrototypeState(project, new
        {
            route = RunType,
            game_type_profile = PrototypeRouteSkillPolicy.ResolveProfile(project),
            source_boundary = "gdd_derived_contract_only_after_gdd_generation",
            run_id = runId,
            status,
            exit_code = exitCode,
            prototype_record = prototypeRecordPath,
            prototype_contract = prototypeContractPath,
            slug,
            default_scene = localEntry.DefaultScene,
            smoke_scene = localEntry.SmokeScene,
            playable_scene = localEntry.PlayableScene,
            local_entry_contract = localEntry.ToEvidence(),
            prototype_completion = validation.ToEvidence(),
            godot_smoke = smoke.ToEvidence(),
            rpg_gdunit_validation = rpgGdUnitValidation?.ToEvidence(),
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
        var newChainGuard = _contractFreezeService.EvaluateNewChainGuard(project);
        var contractStatus = newChainGuard.ContractStatus;
        var verifiedSceneIds = ReadConfirmedSceneIds(project);
        var verifiedRequirementIds = ReadSkeletonVerifiedRequirementIds(project, verifiedSceneIds);
        _routeStateWriter.WritePrototypeSkeletonState(project, new
        {
            schema_version = "prototype-skeleton-readback.v1",
            route = "prototype-skeleton",
            status_dimension = RouteStatusVocabulary.RouteReadback,
            status_allowed_values = RouteStatusVocabulary.Values(RouteStatusVocabulary.RouteReadback),
            status,
            source_boundary_enforced = true,
            recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
            source_boundary = new
            {
                recovery_source_order_ref = HostedRouteRecoveryContract.ContractId,
                recovery_source_order = HostedRouteRecoveryContract.SourceOrder,
                authority_sources = new[]
                {
                    "source_gdd_hash",
                    "source_scene_route_hash",
                    "source_requirement_map_hash",
                    "source_contract_hash",
                    "source_contract_snapshot_hash",
                    "source_godot_ui_contract_hash",
                    "source_ui_style_contract_hash",
                    "ui_style_snapshot_hash"
                },
                source_hashes = new
                {
                    source_gdd_hash = contractStatus.SourceGddHash,
                    source_scene_route_hash = contractStatus.SourceSceneRouteHash,
                    source_requirement_map_hash = contractStatus.SourceRequirementMapHash,
                    source_contract_hash = contractStatus.ContractHash,
                    source_contract_snapshot_hash = contractStatus.SourceContractSnapshotHash,
                    source_godot_ui_contract_hash = contractStatus.SourceGodotUiContractHash,
                    source_ui_style_contract_hash = contractStatus.SourceUiStyleContractHash,
                    ui_style_snapshot_hash = contractStatus.UiStyleSnapshotHash
                },
                forbidden_source_patterns = new[]
                {
                    "docs/game-type-guides/** raw excerpts",
                    "assistant summary as acceptance authority"
                }
            },
            freshness = newChainGuard.NewChainActive && newChainGuard.Allowed && string.Equals(status, "succeeded", StringComparison.OrdinalIgnoreCase)
                ? "fresh"
                : "stale",
            legacy_compatibility_reason = newChainGuard.NewChainActive ? "" : "legacy_chain_without_frozen_contract",
            source_gdd_hash = contractStatus.SourceGddHash,
            source_scene_route_hash = contractStatus.SourceSceneRouteHash,
            source_requirement_map_hash = contractStatus.SourceRequirementMapHash,
            source_contract_hash = contractStatus.ContractHash,
            source_contract_snapshot_hash = contractStatus.SourceContractSnapshotHash,
            source_godot_ui_contract_hash = contractStatus.SourceGodotUiContractHash,
            source_ui_style_contract_hash = contractStatus.SourceUiStyleContractHash,
            ui_style_snapshot_hash = contractStatus.UiStyleSnapshotHash,
            verified_scene_ids = verifiedSceneIds,
            verified_requirement_ids = verifiedRequirementIds,
            evidence_refs = new[]
            {
                new { kind = "sidecar", path = "meta/routes/prototype/latest.json" },
                new { kind = "sidecar", path = "routes/prototype-contract/latest.json" },
                new { kind = "sidecar", path = "meta/routes/gdd-requirements/latest.json" }
            },
            updated_utc = DateTimeOffset.UtcNow.ToString("O")
        });
        _routeStateWriter.WriteProjectExecutionGuide(
            project,
            _contractService.Read(project),
            prototypeRecordPath,
            slug,
            RunType,
            runId,
            status,
            localEntry.DefaultScene,
            localEntry.PlayableScene,
            localEntry.SmokeScene);
    }

    private static IReadOnlyList<string> ReadConfirmedSceneIds(ProjectSnapshot project)
    {
        return ReadStringArrayFromRouteState(
            Path.Combine(project.RepoPath, "meta", "routes", "scene-route", "latest.json"),
            "scenes",
            "scene_id");
    }

    private static IReadOnlyList<string> ReadSkeletonVerifiedRequirementIds(
        ProjectSnapshot project,
        IReadOnlyList<string> verifiedSceneIds)
    {
        if (verifiedSceneIds.Count == 0)
        {
            return [];
        }

        var path = Path.Combine(project.RepoPath, "meta", "routes", "gdd-requirements", "latest.json");
        if (!File.Exists(path))
        {
            return [];
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            if (!document.RootElement.TryGetProperty("requirements", out var requirements) ||
                requirements.ValueKind != JsonValueKind.Array)
            {
                return [];
            }

            var sceneSet = verifiedSceneIds.ToHashSet(StringComparer.OrdinalIgnoreCase);
            return requirements.EnumerateArray()
                .Where(static row => row.ValueKind == JsonValueKind.Object)
                .Where(row => ReadString(row, "status") == "mapped")
                .Where(row => ReadStringArray(row, "mapped_scene_ids").Any(sceneSet.Contains))
                .Select(row => ReadString(row, "requirement_id"))
                .Where(static id => !string.IsNullOrWhiteSpace(id))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(static id => id, StringComparer.Ordinal)
                .ToArray();
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static IReadOnlyList<string> ReadStringArrayFromRouteState(
        string path,
        string arrayProperty,
        string valueProperty)
    {
        if (!File.Exists(path))
        {
            return [];
        }

        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            if (!document.RootElement.TryGetProperty(arrayProperty, out var values) ||
                values.ValueKind != JsonValueKind.Array)
            {
                return [];
            }

            return values.EnumerateArray()
                .Select(item => ReadString(item, valueProperty))
                .Where(static value => !string.IsNullOrWhiteSpace(value))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .OrderBy(static value => value, StringComparer.Ordinal)
                .ToArray();
        }
        catch (JsonException)
        {
            return [];
        }
    }

    private static string ReadString(JsonElement root, string propertyName)
    {
        return root.ValueKind == JsonValueKind.Object &&
               root.TryGetProperty(propertyName, out var value) &&
               value.ValueKind == JsonValueKind.String
            ? value.GetString()?.Trim() ?? ""
            : "";
    }

    private static IReadOnlyList<string> ReadStringArray(JsonElement root, string propertyName)
    {
        if (root.ValueKind != JsonValueKind.Object ||
            !root.TryGetProperty(propertyName, out var value) ||
            value.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        return value.EnumerateArray()
            .Where(static item => item.ValueKind == JsonValueKind.String)
            .Select(static item => item.GetString()?.Trim() ?? "")
            .Where(static item => item.Length > 0)
            .ToArray();
    }

    private static PrototypeLocalEntryContract BuildLocalEntryContract(
        string repositoryRoot,
        string slug,
        PrototypeCompletionValidation validation)
    {
        var defaultScene = string.IsNullOrWhiteSpace(validation.SmokeScene) ? null : validation.SmokeScene.Trim();
        var smokeScene = defaultScene;
        var playableScene = defaultScene;
        var entryInstancesPlayable = false;
        string? status = string.IsNullOrWhiteSpace(defaultScene) ? "missing_default_scene" : "ready";
        string? error = string.IsNullOrWhiteSpace(defaultScene) ? "prototype_smoke_scene_missing" : null;

        if (!string.IsNullOrWhiteSpace(defaultScene) &&
            PrototypeSceneReferenceInspector.TryFindFirstInstancedPrototypeScene(repositoryRoot, defaultScene, slug, out var instancedPlayableScene))
        {
            playableScene = instancedPlayableScene;
            entryInstancesPlayable = !string.Equals(defaultScene, instancedPlayableScene, StringComparison.OrdinalIgnoreCase);
        }

        return new PrototypeLocalEntryContract(
            defaultScene,
            smokeScene,
            playableScene,
            entryInstancesPlayable,
            status,
            error);
    }

    private void EnsureGameTypeTemplateBaseline(string projectRepoPath, PrototypeWorkflowRequest request)
    {
        var template = _templateCatalog.Find(request.GameType);
        if (template is null || !template.Enabled)
        {
            return;
        }

        var repoTemplateRoot = CombineRepoPath(_options.RepositoryRoot, template.RepoTemplatePath);
        var projectTemplateRoot = CombineRepoPath(projectRepoPath, template.RepoTemplatePath);
        if (!Directory.Exists(repoTemplateRoot))
        {
            return;
        }

        if (!ShouldSeedTemplateBaseline(projectRepoPath, request.GameType, projectTemplateRoot))
        {
            return;
        }

        CopyDirectoryIfMissing(repoTemplateRoot, projectTemplateRoot);
        TryCopyFileIfMissing(
            CombineRepoPath(_options.RepositoryRoot, "Game.Core/Prototypes/DefaultRpgPrototypeLoop.cs"),
            CombineRepoPath(projectRepoPath, "Game.Core/Prototypes/DefaultRpgPrototypeLoop.cs"));
        TryCopyFileIfMissing(
            CombineRepoPath(_options.RepositoryRoot, "Game.Core.Tests/Prototypes/DefaultRpgPrototypeLoopTests.cs"),
            CombineRepoPath(projectRepoPath, "Game.Core.Tests/Prototypes/DefaultRpgPrototypeLoopTests.cs"));
        TryCopyFileIfMissing(
            CombineRepoPath(_options.RepositoryRoot, "Tests.Godot/tests/Prototype/DefaultRpgPrototype/test_default_rpg_prototype_scene.gd"),
            CombineRepoPath(projectRepoPath, "Tests.Godot/tests/Prototype/DefaultRpgPrototype/test_default_rpg_prototype_scene.gd"));
    }

    private static bool ShouldSeedTemplateBaseline(string projectRepoPath, string? gameType, string projectTemplateRoot)
    {
        if (!string.Equals(gameType, "rpg", StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (!Directory.Exists(projectTemplateRoot))
        {
            return true;
        }

        var projectSpecificScene = CombineRepoPath(projectRepoPath, "Game.Godot/Prototypes/dq-rpg/DqRpgPrototype.tscn");
        return !File.Exists(projectSpecificScene);
    }

    private static void CopyDirectoryIfMissing(string sourceRoot, string targetRoot)
    {
        foreach (var directory in Directory.EnumerateDirectories(sourceRoot, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceRoot, directory);
            Directory.CreateDirectory(Path.Combine(targetRoot, relative));
        }

        foreach (var file in Directory.EnumerateFiles(sourceRoot, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceRoot, file);
            TryCopyFileIfMissing(file, Path.Combine(targetRoot, relative));
        }
    }

    private static void TryCopyFileIfMissing(string sourcePath, string targetPath)
    {
        if (!File.Exists(sourcePath) || File.Exists(targetPath))
        {
            return;
        }

        var parent = Path.GetDirectoryName(targetPath);
        if (!string.IsNullOrWhiteSpace(parent))
        {
            Directory.CreateDirectory(parent);
        }

        File.Copy(sourcePath, targetPath, overwrite: false);
    }

    private static string CombineRepoPath(string root, string relativePath)
    {
        return Path.Combine(root, relativePath.Replace('/', Path.DirectorySeparatorChar));
    }

    private static readonly (string Step, string Substep, string Label)[] ProgressSteps =
    [
        ("running_step01_intake", "", "任务 01：正在整理输入信息。"),
        ("running_step02_brief", "", "任务 02：正在形成原型简报。"),
        ("running_step03_design", "analyzing", "任务 03：正在分析玩法方向。"),
        ("running_step03_design", "planning", "任务 03：正在规划最小可玩循环。"),
        ("running_step03_design", "freezing_scope", "任务 03：正在冻结本次原型范围。"),
        ("running_step04_implementation", "scaffolding", "任务 04：正在搭建实现骨架。"),
        ("running_step04_implementation", "coding", "任务 04：正在实现核心逻辑。"),
        ("running_step04_implementation", "asset_wiring", "任务 04：正在接线资源与占位资产。"),
        ("running_step04_implementation", "scene_wiring", "任务 04：正在接线 Godot 原型场景。"),
        ("running_step05_verification", "unit_tests", "任务 05：正在运行单元测试。"),
        ("running_step05_verification", "godot_smoke", "任务 05：正在运行 Godot 冒烟验证。"),
        ("running_step05_verification", "playability_check", "任务 05：正在检查可玩性。"),
        ("running_step05_verification", "fixing", "任务 05：正在处理验证发现的问题。"),
        ("running_step06_packaging", "", "任务 06：正在整理产物与报告。"),
        ("running_step07_review", "", "任务 07：正在生成最终摘要。")
    ];

    private sealed record PrototypeCompletionValidation(
        bool Succeeded,
        string Status,
        int CompletedThroughDay,
        string? Error,
        string? SmokeScene,
        string? CompletionSummary,
        string? NextStepSource,
        string? NextStepEvaluation,
        string? NextStepEvaluationReason)
    {
        public static PrototypeCompletionValidation Failure(string error)
        {
            return new PrototypeCompletionValidation(false, "", 0, error, null, null, null, null, null);
        }

        public static PrototypeCompletionValidation Success(string status, int completedThroughDay, string smokeScene, string? completionSummary, string? nextStepSource, string? nextStepEvaluation, string? nextStepEvaluationReason)
        {
            return new PrototypeCompletionValidation(true, status, completedThroughDay, null, smokeScene, completionSummary, nextStepSource, nextStepEvaluation, nextStepEvaluationReason);
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
                completion_summary = CompletionSummary,
                next_step_source = NextStepSource,
                next_step_evaluation = NextStepEvaluation,
                next_step_evaluation_reason = NextStepEvaluationReason
            };
        }
    }

    private sealed record PrototypeLocalEntryContract(
        string? DefaultScene,
        string? SmokeScene,
        string? PlayableScene,
        bool EntrySceneInstancesPlayableScene,
        string Status,
        string? Error)
    {
        public object ToEvidence()
        {
            return new
            {
                status = Status,
                default_scene = DefaultScene,
                smoke_scene = SmokeScene,
                playable_scene = PlayableScene,
                entry_scene_instances_playable_scene = EntrySceneInstancesPlayableScene,
                error = Error
            };
        }
    }

    private sealed record PrototypeDotnetBuildValidation(
        bool Required,
        bool Passed,
        string? ProjectPath,
        int ExitCode,
        string Stdout,
        string Stderr,
        string? FailureSummary)
    {
        public static PrototypeDotnetBuildValidation NotRequired(string reason)
        {
            return new PrototypeDotnetBuildValidation(false, true, null, 0, "", "", reason);
        }

        public static PrototypeDotnetBuildValidation Timeout(string repoPath, string projectPath)
        {
            return new PrototypeDotnetBuildValidation(
                true,
                false,
                ToSlash(Path.GetRelativePath(repoPath, projectPath)),
                408,
                "",
                "dotnet build validation timed out.",
                "dotnet build validation timed out.");
        }

        public static PrototypeDotnetBuildValidation FromResult(string repoPath, string projectPath, HostedProcessResult result)
        {
            var passed = result.ExitCode == 0;
            return new PrototypeDotnetBuildValidation(
                true,
                passed,
                ToSlash(Path.GetRelativePath(repoPath, projectPath)),
                result.ExitCode,
                result.Stdout,
                result.Stderr,
                passed ? null : ExtractBuildFailureSummary(result));
        }

        public object ToEvidence()
        {
            return new
            {
                required = Required,
                passed = Passed,
                project = ProjectPath,
                exit_code = ExitCode,
                failure_summary = FailureSummary
            };
        }

        private static string ExtractBuildFailureSummary(HostedProcessResult result)
        {
            var text = string.Join(
                Environment.NewLine,
                new[] { result.Stdout, result.Stderr }.Where(value => !string.IsNullOrWhiteSpace(value)));
            if (string.IsNullOrWhiteSpace(text))
            {
                return "dotnet build failed without process output.";
            }

            var lines = text
                .Replace("\r\n", "\n", StringComparison.Ordinal)
                .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            var details = new List<string>();
            foreach (var line in lines)
            {
                if (IsBuildFailureSignal(line) &&
                    !details.Any(existing => string.Equals(existing, line, StringComparison.OrdinalIgnoreCase)))
                {
                    details.Add(line.Length <= 700 ? line : line[..700]);
                }

                if (details.Count >= 16)
                {
                    break;
                }
            }

            return details.Count == 0
                ? (text.Length <= 1600 ? text : text[..1600])
                : string.Join(" | ", details);
        }

        private static bool IsBuildFailureSignal(string line)
        {
            return line.Contains(": error ", StringComparison.OrdinalIgnoreCase) ||
                   line.Contains(" error CS", StringComparison.OrdinalIgnoreCase) ||
                   line.Contains(" error MSB", StringComparison.OrdinalIgnoreCase) ||
                   line.Contains(".cs(", StringComparison.OrdinalIgnoreCase) ||
                   line.Contains("Build FAILED", StringComparison.OrdinalIgnoreCase) ||
                   line.Contains("生成失败", StringComparison.OrdinalIgnoreCase);
        }

        private static string ToSlash(string path)
        {
            return path.Replace('\\', '/');
        }
    }

    private sealed record RecoveredPrototypeCompletion(
        string Slug,
        string PrototypeRecordPath,
        IReadOnlyList<string> Artifacts,
        PrototypeCompletionValidation Validation);

    private sealed record PrototypePackagingSummaryReadback(
        string? DefaultScene,
        string? DefaultSceneLabel,
        int TddSummaryCount,
        int TddRedCount,
        int TddGreenCount,
        int TddRefactorCount,
        IReadOnlyList<string> PlaytestFocusPoints);

}
