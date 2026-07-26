using System.Text;
using System.Security.Cryptography;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;
using Microsoft.Extensions.DependencyInjection;

namespace PhaseA.Platform.Skills;

public sealed class SkillActionService
{
    private const string RunType = "skill-action";
    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly SkillActionCatalog _catalog;
    private readonly IHostedProcessRunner _processRunner;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly IAiCodeMirrorBillingClient _billingClient;
    private readonly AiCodeMirrorKeyPoolService? _keyPoolService;
    private readonly ILlmRouteEngine? _llmRouteEngine;
    private readonly HostedContextManifestIssuer? _contextManifestIssuer;
    private readonly HostedContextGatePolicy _contextGatePolicy;
    private readonly IHostedContextManifestValidator? _contextManifestValidator;
    private readonly HeavyRunnerQueueService _heavyRunnerQueue;
    private readonly HeavyRunnerQueueService? _assetRunnerQueue;
    private readonly RunCancellationService _runCancellation;

    public SkillActionService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        SkillActionCatalog catalog,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        IAiCodeMirrorBillingClient? billingClient = null,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        ILlmRouteEngine? llmRouteEngine = null,
        HeavyRunnerQueueService? heavyRunnerQueue = null,
        [FromKeyedServices("asset-generation")] HeavyRunnerQueueService? assetRunnerQueue = null,
        RunCancellationService? runCancellation = null,
        HostedContextManifestIssuer? contextManifestIssuer = null,
        HostedContextGatePolicy? contextGatePolicy = null,
        IHostedContextManifestValidator? contextManifestValidator = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _catalog = catalog;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _billingClient = billingClient ?? new DisabledAiCodeMirrorBillingClient();
        _keyPoolService = keyPoolService;
        _llmRouteEngine = llmRouteEngine;
        _contextManifestIssuer = contextManifestIssuer;
        _contextGatePolicy = contextGatePolicy ?? new HostedContextGatePolicy();
        _contextManifestValidator = contextManifestValidator;
        _heavyRunnerQueue = heavyRunnerQueue ?? new HeavyRunnerQueueService();
        _assetRunnerQueue = assetRunnerQueue;
        _runCancellation = runCancellation ?? new RunCancellationService();
    }

    public IReadOnlyList<SkillActionDefinition> ListAllowed(string role)
    {
        return _catalog.ListAllowed(role);
    }

    public async Task<SkillActionRunResult> RunAsync(
        string accountId,
        string projectId,
        string actionId,
        SkillActionRunRequest request,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentException.ThrowIfNullOrWhiteSpace(actionId);
        ArgumentNullException.ThrowIfNull(request);

        var action = _catalog.Find(actionId);
        if (action is null)
        {
            return new SkillActionRunResult("", "skill_action_not_allowed", 404, actionId, "", "", [], "skill_action_not_allowed");
        }

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var isWorkspaceWrite = string.Equals(action.ExecutionMode, "codex-workspace-write", StringComparison.Ordinal);
        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        var runnerLockAcquired = false;
        if (isWorkspaceWrite)
        {
            runnerLockAcquired = await _metadataStore.TryAcquireRunnerLockAsync(project.ProjectId, runId, cancellationToken);
            if (!runnerLockAcquired)
            {
                var busyEvidence = JsonSerializer.Serialize(new
                {
                    run_type = RunType,
                    action_id = action.ActionId,
                    skill_name = action.SkillName,
                    execution_mode = action.ExecutionMode,
                    failure_code = "project_busy"
                });
                await _metadataStore.CompleteRunAsync(runId, "failed", 409, "", "Project is busy.", busyEvidence, cancellationToken);
                return new SkillActionRunResult(runId, "project_busy", 409, action.ActionId, action.SkillName, "", [], "project_busy");
            }
        }

        var runnerQueue = string.Equals(request.QueueLane, "asset-generation", StringComparison.Ordinal)
            ? _assetRunnerQueue ?? _heavyRunnerQueue
            : _heavyRunnerQueue;
        var queueRunType = string.Equals(request.QueueLane, "asset-generation", StringComparison.Ordinal)
            ? "asset-generation"
            : RunType;
        await using var heavyRunnerLease = await runnerQueue.EnterAsync(runId, project.AccountId, project.ProjectId, queueRunType, CancellationToken.None);
        await _metadataStore.MarkRunStartedAsync(runId, heavyRunnerLease.QueuePositionAtStart, cancellationToken);
        using var runCancellation = _runCancellation.CreateLinkedTokenSource(runId, cancellationToken);
        var runToken = runCancellation.Token;
        try
        {

        var relativeDir = ToSlash(Path.Combine("logs", "phase-a-skills", project.ProjectId, runId));
        var outputRelativePath = ToSlash(Path.Combine(relativeDir, "skill-output.md"));
        var requestRelativePath = ToSlash(Path.Combine(relativeDir, "skill-request.json"));
        var outputAbsolutePath = Path.Combine(project.RepoPath, outputRelativePath.Replace('/', Path.DirectorySeparatorChar));
        var requestAbsolutePath = Path.Combine(project.RepoPath, requestRelativePath.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(outputAbsolutePath)!);

        await File.WriteAllTextAsync(
            requestAbsolutePath,
            JsonSerializer.Serialize(new
            {
                action.ActionId,
                action.SkillName,
                request.Input,
                project.ProjectId,
                project.Name,
                project.GameName,
                project.GameTypeSource
            }, new JsonSerializerOptions { WriteIndented = true }),
            Encoding.UTF8,
            runToken);

        var prompt = BuildPrompt(action, project, request);
        var sandbox = isWorkspaceWrite ? "workspace-write" : "read-only";
        var useCodexProcess = _llmRouteEngine is null || isWorkspaceWrite;
        var operationKey = useCodexProcess ? "codex:skill-action" : "llm:skill-action";
        HostedContextEnvelope? envelope = null;
        if (_contextManifestIssuer is not null)
        {
            try
            {
                envelope = await _contextManifestIssuer.IssueAsync(new HostedContextManifestIssue(
                    project.AccountId,
                    project.ProjectId,
                    operationKey,
                    Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", project.ProjectId, project.AccountId, runId, action.ActionId, request.Input, prompt)))).ToLowerInvariant(),
                    "skill-action.v1",
                    TimeSpan.FromMinutes(5)), runToken);
            }
            catch (InvalidOperationException)
            {
                envelope = null;
            }
        }

        var routeResult = _contextManifestIssuer is not null && envelope is null
            ? new LlmRouteResult(false, null, null, "gpt-5.4", "context_manifest_issue_failed", "context_gate", 1, "", "", null, 0, prompt.Length, Encoding.UTF8.GetByteCount(prompt), 0)
            : useCodexProcess
            ? await RunLegacyCodexProcessAsync(runId, project, outputAbsolutePath, prompt, sandbox, ReasoningEffortFor(request), envelope, runToken)
            : await _llmRouteEngine!.CompleteAsync(
                new LlmRouteRequest(
                    project.RepoPath,
                    "skill-action",
                    "gpt-5.4",
                    prompt,
                    new CodexChatClientOptions(IgnoreRules: false, ReasoningEffort: "high"),
                    project.AccountId,
                    OperationKey: operationKey,
                    ContextEnvelope: envelope),
                runToken);
        var output = FirstNonEmpty(routeResult.AssistantMessage, routeResult.Stderr, routeResult.Stdout, "");
        await File.WriteAllTextAsync(outputAbsolutePath, output, Encoding.UTF8, runToken);
        var status = routeResult.Succeeded ? "succeeded" : "failed";

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "skill-action-request",
            requestRelativePath,
            "Skill action request payload"), CancellationToken.None);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "skill-action-output",
            outputRelativePath,
            "Skill action output"), CancellationToken.None);

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            action_id = action.ActionId,
            skill_name = action.SkillName,
            execution_mode = action.ExecutionMode,
            request = requestRelativePath,
            output = outputRelativePath
        });
        await _metadataStore.CompleteRunAsync(runId, status, routeResult.ExitCode, routeResult.Stdout, routeResult.Stderr, evidenceJson, CancellationToken.None);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            "gpt-5.4",
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: RunType,
                model: "gpt-5.4",
                tokenUsage: routeResult.RawResult?.TokenUsage ?? CodexUsageExtractor.Extract(routeResult.Stdout, routeResult.Stderr),
                runType: RunType,
                projectId: project.ProjectId,
                skillActionId: action.ActionId,
                skillName: action.SkillName,
                route: "skill-action",
                exitCode: routeResult.ExitCode,
                providerBilling: routeResult.RawResult?.ProviderBilling),
            CancellationToken.None);

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, CancellationToken.None);
        return new SkillActionRunResult(runId, status, routeResult.ExitCode, action.ActionId, action.SkillName, output.Trim(), artifacts);
        }
        catch (OperationCanceledException) when (_runCancellation.IsCancellationRequested(runId))
        {
            return new SkillActionRunResult(runId, "cancel", 499, action.ActionId, action.SkillName, "", [], "cancel");
        }
        finally
        {
            _runCancellation.Unregister(runId);
            if (runnerLockAcquired)
            {
                await _metadataStore.ReleaseRunnerLockAsync(project.ProjectId, runId, CancellationToken.None);
            }
        }
    }

    private async Task<LlmRouteResult> RunLegacyCodexProcessAsync(
        string runId,
        ProjectSnapshot project,
        string outputAbsolutePath,
        string prompt,
        string sandbox,
        string reasoningEffort,
        HostedContextEnvelope? envelope,
        CancellationToken cancellationToken)
    {
        var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, cancellationToken);
        var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
        var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, cancellationToken);
        var command = await BuildCodexCommandAsync(project, outputAbsolutePath, prompt, sandbox, reasoningEffort, envelope, cancellationToken);
        var process = await _processRunner.RunAsync(CodexHostedProcessCommandFactory.ApplyRuntime(command, runtimeCredential).WithRunId(runId), cancellationToken);
        var providerBilling = new AiCodeMirrorBillingDelta(billingBefore, await _billingClient.CaptureAsync(billingApiKeyName, CancellationToken.None));
        var output = File.Exists(outputAbsolutePath)
            ? await File.ReadAllTextAsync(outputAbsolutePath, Encoding.UTF8, cancellationToken)
            : FirstNonEmpty(process.Stdout, process.Stderr, "");
        var rawResult = new CodexChatClientResult(
            process.ExitCode == 0,
            output,
            process.ExitCode == 0 ? null : "codex_failed",
            process.ExitCode,
            process.Stdout,
            process.Stderr,
            CodexUsageExtractor.Extract(process.Stdout, process.Stderr),
            providerBilling);
        return new LlmRouteResult(
            process.ExitCode == 0,
            output,
            null,
            "gpt-5.4",
            rawResult.FailureCode,
            process.ExitCode == 0 ? null : "llm_failed",
            process.ExitCode,
            process.Stdout,
            process.Stderr,
            rawResult,
            0,
            prompt.Length,
            Encoding.UTF8.GetByteCount(prompt),
            Math.Max(1, (int)Math.Ceiling(Encoding.UTF8.GetByteCount(prompt) / 4.0d)));
    }

    private async Task<HostedProcessCommand> BuildCodexCommandAsync(
        ProjectSnapshot project,
        string outputPath,
        string prompt,
        string sandbox,
        string reasoningEffort,
        HostedContextEnvelope? envelope,
        CancellationToken cancellationToken)
    {
        return await CodexHostedProcessCommandFactory.BuildAsync(new CodexHostedProcessRequest(
            project.RepoPath,
            outputPath,
            prompt,
            "gpt-5.4",
            reasoningEffort,
            Sandbox: sandbox,
            OperationKey: "codex:skill-action",
            ContextEnvelope: envelope),
            _contextGatePolicy,
            _contextManifestValidator,
            cancellationToken);
    }

    private static string ReasoningEffortFor(SkillActionRunRequest request)
    {
        return string.Equals(request.QueueLane, "asset-generation", StringComparison.Ordinal)
            ? "medium"
            : "high";
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

    private static string BuildPrompt(SkillActionDefinition action, ProjectSnapshot project, SkillActionRunRequest request)
    {
        var modeRules = string.Equals(action.ExecutionMode, "codex-workspace-write", StringComparison.Ordinal)
            ? """
            Workspace write mode:
            - Use the named whitelist skill.
            - You may create or update files only when the user input explicitly provides an output directory or asset-library target inside this project repository.
            - Keep generated asset files, prompts, manifests, and notes under the provided output directory.
            - Do not modify gameplay scenes, scripts, tests, platform code, or unrelated project files from this skill action.
            - If real image generation is unavailable, write a concrete generation prompt/specification file in the output directory and explain the blocker.
            """
            : """
            Read-only mode:
            - Use the named whitelist skill.
            - Only analyze and output advice.
            - Do not modify files.
            - Do not execute destructive operations.
            """;
        return $"""
            Please use ${action.SkillName} for this whitelist skill action.
            You are running inside a Phase A project workspace.

            Project:
            - ProjectId: {project.ProjectId}
            - ProjectName: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}
            - ExecutionMode: {action.ExecutionMode}

            {modeRules}

            User input:
            {request.Input?.Trim() ?? "Analyze the current project and provide the next actionable recommendation."}

            Output requirements:
            - Answer in Chinese for the browser user.
            - Clearly state the skill name used.
            - Summarize generated files or state why no real asset file could be generated.
            - Do not claim files were modified unless you actually wrote them.
            """;
    }

    private static string FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value.Length > 6000 ? value[^6000..] : value;
            }
        }

        return "";
    }

    private static string ToSlash(string path)
    {
        return path.Replace('\\', '/');
    }
}
