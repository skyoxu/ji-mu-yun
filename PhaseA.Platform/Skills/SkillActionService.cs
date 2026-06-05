using System.Text;
using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Workspaces;

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

    public SkillActionService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        SkillActionCatalog catalog,
        IHostedProcessRunner processRunner,
        IProjectWorkspaceSeeder workspaceSeeder,
        IAiCodeMirrorBillingClient? billingClient = null,
        AiCodeMirrorKeyPoolService? keyPoolService = null,
        ILlmRouteEngine? llmRouteEngine = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _catalog = catalog;
        _processRunner = processRunner;
        _workspaceSeeder = workspaceSeeder;
        _billingClient = billingClient ?? new DisabledAiCodeMirrorBillingClient();
        _keyPoolService = keyPoolService;
        _llmRouteEngine = llmRouteEngine;
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

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

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
            cancellationToken);

        var prompt = BuildPrompt(action, project, request);
        var routeResult = _llmRouteEngine is null
            ? await RunLegacyCodexProcessAsync(project, outputAbsolutePath, prompt, cancellationToken)
            : await _llmRouteEngine.CompleteAsync(
                new LlmRouteRequest(
                    EnsureSkillActionPromptWorkspace(project),
                    "skill-action",
                    "gpt-5.4",
                    prompt,
                    new CodexChatClientOptions(IgnoreRules: false, ReasoningEffort: "high"),
                    project.AccountId),
                cancellationToken);
        var output = FirstNonEmpty(routeResult.AssistantMessage, routeResult.Stderr, routeResult.Stdout, "");
        await File.WriteAllTextAsync(outputAbsolutePath, output, Encoding.UTF8, cancellationToken);
        var status = routeResult.Succeeded ? "succeeded" : "failed";

        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "skill-action-request",
            requestRelativePath,
            "Skill action request payload"), cancellationToken);
        await _metadataStore.AddArtifactAsync(new ArtifactCreationCommand(
            runId,
            project.ProjectId,
            "skill-action-output",
            outputRelativePath,
            "Skill action output"), cancellationToken);

        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            action_id = action.ActionId,
            skill_name = action.SkillName,
            execution_mode = action.ExecutionMode,
            request = requestRelativePath,
            output = outputRelativePath
        });
        await _metadataStore.CompleteRunAsync(runId, status, routeResult.ExitCode, routeResult.Stdout, routeResult.Stderr, evidenceJson, cancellationToken);
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
            cancellationToken);

        var artifacts = await _metadataStore.ListArtifactsForRunAsync(runId, cancellationToken);
        return new SkillActionRunResult(runId, status, routeResult.ExitCode, action.ActionId, action.SkillName, output.Trim(), artifacts);
    }

    private async Task<LlmRouteResult> RunLegacyCodexProcessAsync(
        ProjectSnapshot project,
        string outputAbsolutePath,
        string prompt,
        CancellationToken cancellationToken)
    {
        var runtimeCredential = await ResolveRuntimeCredentialAsync(project.AccountId, cancellationToken);
        var billingApiKeyName = runtimeCredential.BillingKeyName ?? project.AccountId;
        var billingBefore = await _billingClient.CaptureAsync(billingApiKeyName, cancellationToken);
        var process = await _processRunner.RunAsync(CodexHostedProcessCommandFactory.ApplyRuntime(BuildCodexReadOnlyCommand(project.RepoPath, outputAbsolutePath, prompt), runtimeCredential), cancellationToken);
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

    private HostedProcessCommand BuildCodexReadOnlyCommand(string repositoryRoot, string outputPath, string prompt)
    {
        return CodexHostedProcessCommandFactory.Build(new CodexHostedProcessRequest(
            repositoryRoot,
            outputPath,
            prompt,
            "gpt-5.4",
            "high",
            Sandbox: "read-only"));
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
        return $"""
            请使用 ${action.SkillName} 这个白名单 skill。
            你正在积木云 Phase A 的项目级 workspace 中运行，只允许只读分析和输出建议，不要修改文件，不要执行破坏性操作。

            项目信息：
            - ProjectId: {project.ProjectId}
            - ProjectName: {project.Name}
            - GameName: {project.GameName}
            - GameTypeSource: {project.GameTypeSource}

            用户输入：
            {request.Input?.Trim() ?? "请基于当前项目状态输出下一步建议。"}

            输出要求：
            - 用中文回答。
            - 明确说明调用的 skill 名称。
            - 给出可执行建议、风险和下一步。
            - 不要声称已经修改代码。
            """;
    }

    private static string EnsureSkillActionPromptWorkspace(ProjectSnapshot project)
    {
        var repoParent = Path.GetDirectoryName(project.RepoPath);
        var workspaceRoot = string.IsNullOrWhiteSpace(repoParent) ? project.RepoPath : repoParent;
        var root = Path.Combine(workspaceRoot, "_phasea_llm", "skill-action");
        Directory.CreateDirectory(root);
        return root;
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
