using System.Text.Json;
using System.Security.Cryptography;
using System.Text;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Runs;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Llm;

public sealed class ChatService
{
    private const string RunType = "prototype-chat";
    private const decimal EstimatedChatCostCny = 0.10m;
    private const int MaxMessageLength = 8000;
    private const int MaxHistoryMessages = 3;
    private const int MaxTextAttachments = 5;
    private const int MaxTextAttachmentChars = 12000;
    private const int MaxChatMemoryChars = 1500;
    private const int MaxMemorySourceChars = 400;

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly LlmBindingService _llmBindingService;
    private readonly LlmStopLossService _llmStopLossService;
    private readonly INewApiChatClient _chatClient;
    private readonly ILlmRouteEngine _llmRouteEngine;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly SkillActionCatalog _skillActionCatalog;
    private readonly ChatConcurrencyLimiter _concurrencyLimiter;
    private readonly RunCancellationService _runCancellation;
    private readonly HostedContextManifestIssuer? _contextManifestIssuer;

    public ChatService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        LlmBindingService llmBindingService,
        LlmStopLossService llmStopLossService,
        INewApiChatClient chatClient,
        ICodexChatClient codexChatClient)
        : this(metadataStore, options, llmBindingService, llmStopLossService, chatClient, codexChatClient, new ProjectWorkspaceSeeder(options), new SkillActionCatalog())
    {
    }

    public ChatService(
        PhaseAMetadataStore metadataStore,
        PhaseAPlatformOptions options,
        LlmBindingService llmBindingService,
        LlmStopLossService llmStopLossService,
        INewApiChatClient chatClient,
        ICodexChatClient codexChatClient,
        IProjectWorkspaceSeeder workspaceSeeder,
        SkillActionCatalog skillActionCatalog,
        ILlmRouteEngine? llmRouteEngine = null,
        ChatConcurrencyLimiter? concurrencyLimiter = null,
        RunCancellationService? runCancellation = null,
        HostedContextManifestIssuer? contextManifestIssuer = null)
    {
        _metadataStore = metadataStore;
        _options = options;
        _llmBindingService = llmBindingService;
        _llmStopLossService = llmStopLossService;
        _chatClient = chatClient;
        _llmRouteEngine = llmRouteEngine ?? new LlmRouteEngine(codexChatClient);
        _workspaceSeeder = workspaceSeeder;
        _skillActionCatalog = skillActionCatalog;
        _concurrencyLimiter = concurrencyLimiter ?? new ChatConcurrencyLimiter();
        _runCancellation = runCancellation ?? new RunCancellationService();
        _contextManifestIssuer = contextManifestIssuer;
    }

    public async Task<ChatResult> SendAsync(string accountId, string projectId, ChatRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(accountId);
        ArgumentException.ThrowIfNullOrWhiteSpace(projectId);
        ArgumentNullException.ThrowIfNull(request);

        if (string.IsNullOrWhiteSpace(request.Message))
        {
            return new ChatResult("", "missing_message", 2, null, "message_required", request.Model);
        }

        if (request.Message.Length > MaxMessageLength)
        {
            return new ChatResult("", "message_too_long", 2, null, "message_too_long", request.Model);
        }

        if ((request.Attachments?.Count ?? 0) > MaxTextAttachments)
        {
            return new ChatResult("", "too_many_attachments", 2, null, "too_many_attachments", request.Model);
        }

        var concurrency = await _concurrencyLimiter.TryAcquireAsync(accountId, cancellationToken);
        if (concurrency.Lease is null)
        {
            return new ChatResult("", concurrency.FailureCode!, 429, null, concurrency.FailureCode, request.Model);
        }

        await using var concurrencyLease = concurrency.Lease;

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null || !string.Equals(project.AccountId, accountId, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("Project not found.");
        }

        var model = ResolveRequestedModel(request.Model);
        if (IsDeterministicTestMode())
        {
            return await CompleteDeterministicAsync(project, request, model, cancellationToken);
        }

        if (!UsesNewApiBackend())
        {
            return await CompleteWithCodexAsync(project, request, model, cancellationToken);
        }

        return await CompleteWithNewApiAsync(project, request, model, cancellationToken);
    }

    private async Task<ChatResult> CompleteWithNewApiAsync(
        ProjectSnapshot project,
        ChatRequest request,
        string model,
        CancellationToken cancellationToken)
    {
        var binding = await _llmBindingService.GetAsync(project.AccountId, cancellationToken);
        if (binding is null)
        {
            return new ChatResult("", "llm_binding_required", 402, null, "llm_binding_required", model);
        }

        var token = LlmTokenResolver.Resolve(binding.TokenRef);
        if (string.IsNullOrWhiteSpace(token))
        {
            return new ChatResult("", "llm_token_unresolved", 424, null, "llm_token_unresolved", model);
        }

        var estimate = new LlmCostEstimate(EstimatedChatCostCny, model);
        var stopLoss = await _llmStopLossService.CheckAsync(project.AccountId, estimate, cancellationToken);
        if (!stopLoss.Allowed)
        {
            return new ChatResult("", stopLoss.FailureCode!, 402, null, stopLoss.FailureCode, model);
        }

        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);
        using var runCancellation = _runCancellation.CreateLinkedTokenSource(runId, cancellationToken);
        var runToken = runCancellation.Token;

        try
        {
        var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, runToken);
        var memorySummary = memory?.MemorySummary;
        var messages = BuildMessages(request, memorySummary);
        var completion = await _chatClient.CompleteAsync(binding, token, model, messages, runToken);
        var status = completion.Succeeded ? "succeeded" : "failed";
        var exitCode = completion.Succeeded ? 0 : 1;
        var sanitizedAssistantMessage = PublicChatSanitizer.Sanitize(completion.AssistantMessage);
        var stdout = sanitizedAssistantMessage ?? "";
        var stderr = completion.RawError ?? completion.FailureCode ?? "";
        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            model,
            gateway_provider = binding.GatewayProvider,
            external_account_ref = binding.ExternalAccountRef,
            message_length = request.Message!.Length,
            history_count = Math.Min(request.History?.Count ?? 0, MaxHistoryMessages),
            memory_chars = memorySummary?.Length ?? 0
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            binding.GatewayProvider,
            completion.RequestId,
            model,
            LlmStopLossService.BuildCostJson(estimate, stopLoss),
            CancellationToken.None);

        if (completion.Succeeded &&
            !string.IsNullOrWhiteSpace(sanitizedAssistantMessage) &&
            ShouldUpdateProjectChatMemory(request))
        {
            await UpdateProjectChatMemoryAsync(project, request, sanitizedAssistantMessage, completion.RequestId, CancellationToken.None);
        }

        return new ChatResult(runId, status, exitCode, sanitizedAssistantMessage, completion.FailureCode, model);
        }
        catch (OperationCanceledException) when (_runCancellation.IsCancellationRequested(runId))
        {
            return new ChatResult(runId, "cancel", 499, "", "cancel", model);
        }
        finally
        {
            _runCancellation.Unregister(runId);
        }
    }

    private async Task<ChatResult> CompleteWithCodexAsync(
        ProjectSnapshot project,
        ChatRequest request,
        string model,
        CancellationToken cancellationToken)
    {
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);
        using var runCancellation = _runCancellation.CreateLinkedTokenSource(runId, cancellationToken);
        var runToken = runCancellation.Token;

        try
        {
        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var skillAction = ResolveSkillAction(request.SkillActionId);
        var memory = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, runToken);
        var memorySummary = memory?.MemorySummary;
        var prompt = BuildCodexPrompt(project, request, skillAction, memorySummary);
        HostedContextEnvelope? envelope = null;
        if (_contextManifestIssuer is not null)
        {
            try
            {
                envelope = await _contextManifestIssuer.IssueAsync(
                    new HostedContextManifestIssue(
                        project.AccountId,
                        project.ProjectId,
                        "llm:project-chat",
                        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", project.ProjectId, project.AccountId, request.Message, memorySummary)))).ToLowerInvariant(),
                        "project-chat.v1",
                        TimeSpan.FromMinutes(5)),
                    runToken);
            }
            catch (InvalidOperationException)
            {
                envelope = null;
            }
        }
        var completion = _contextManifestIssuer is not null && envelope is null
            ? new LlmRouteResult(false, null, null, model, "context_manifest_issue_failed", null, 1, "", "", null, 0, prompt.Length, Encoding.UTF8.GetByteCount(prompt), 0)
            : await _llmRouteEngine.CompleteAsync(
                new LlmRouteRequest(
                    project.RepoPath,
                    "project-chat",
                    model,
                    prompt,
                    null,
                    project.AccountId,
                    OperationKey: "llm:project-chat",
                    ContextEnvelope: envelope),
                runToken);
        var status = completion.Succeeded ? "succeeded" : "failed";
        var sanitizedAssistantMessage = PublicChatSanitizer.Sanitize(completion.AssistantMessage);
        var stdout = sanitizedAssistantMessage ?? "";
        var stderr = completion.Succeeded ? completion.Stderr : completion.Stderr + completion.Stdout;
        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            backend = "codex-cli",
            model,
            project_id = project.ProjectId,
            skill_action_id = skillAction?.ActionId,
            skill_name = skillAction?.SkillName,
            message_length = request.Message!.Length,
            history_count = Math.Min(request.History?.Count ?? 0, MaxHistoryMessages),
            memory_chars = memorySummary?.Length ?? 0,
            failure_code = completion.FailureCode
        });
        await _metadataStore.CompleteRunAsync(runId, status, completion.ExitCode, stdout, stderr, evidenceJson, CancellationToken.None);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            model,
            LlmUsageAuditJson.BuildCodexUsageJson(
                operation: "prototype-chat",
                model: model,
                tokenUsage: completion.RawResult?.TokenUsage ?? new CodexTokenUsage(null, null, null),
                runType: RunType,
                projectId: project.ProjectId,
                providerBilling: completion.RawResult?.ProviderBilling),
            CancellationToken.None);

        if (completion.Succeeded &&
            !string.IsNullOrWhiteSpace(sanitizedAssistantMessage) &&
            ShouldUpdateProjectChatMemory(request))
        {
            await UpdateProjectChatMemoryAsync(project, request, sanitizedAssistantMessage, null, CancellationToken.None);
        }

        return new ChatResult(runId, status, completion.ExitCode, sanitizedAssistantMessage, completion.FailureCode, model);
        }
        catch (OperationCanceledException) when (_runCancellation.IsCancellationRequested(runId))
        {
            return new ChatResult(runId, "cancel", 499, "", "cancel", model);
        }
        finally
        {
            _runCancellation.Unregister(runId);
        }
    }

    private async Task<ChatResult> CompleteDeterministicAsync(
        ProjectSnapshot project,
        ChatRequest request,
        string model,
        CancellationToken cancellationToken)
    {
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        var reply = PublicChatSanitizer.Sanitize(BuildDeterministicReply(request.Message!.Trim()));
        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            model,
            gateway_provider = "deterministic-local",
            external_account_ref = "local-test",
            message_length = request.Message.Length,
            history_count = request.History?.Count ?? 0,
            test_mode = "deterministic"
        });
        await _metadataStore.CompleteRunAsync(runId, "succeeded", 0, reply, "", evidenceJson, cancellationToken);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "deterministic-local",
            null,
            model,
            JsonSerializer.Serialize(new
            {
                estimated_cost_cny = 0m,
                model,
                test_mode = "deterministic"
            }),
            cancellationToken);

        return new ChatResult(runId, "succeeded", 0, reply, null, model);
    }

    private SkillActionDefinition? ResolveSkillAction(string? actionId)
    {
        if (string.IsNullOrWhiteSpace(actionId) ||
            string.Equals(actionId.Trim(), "normal", StringComparison.Ordinal))
        {
            return null;
        }

        return _skillActionCatalog.Find(actionId.Trim());
    }

    private static string BuildDeterministicReply(string message)
    {
        if (ContainsAny(message, "能力", "会哪些", "能做什么", "help", "帮助"))
        {
            return """
                我现在处于本机测试模式，可以帮你验证 Phase A 页面交互和产品流程，但不会访问外部 LLM。
                当前可用能力：
                1. 解释 Phase A 控制台怎么用。
                2. 梳理原型想法、假设、最小可玩循环和成功标准。
                3. 根据你的游戏想法，给出可填写到游戏场景创建的草稿。
                4. 提醒哪些操作需要用固定工作流按钮执行。
                5. 验证聊天链路、鉴权、run 记录和 LLM 审计是否工作。
                """;
        }

        return $"""
            我已收到：{message}

            当前是本机测试模式。我可以按规则帮你整理 Phase A 原型想法、解释控制台使用方式，或说明如何使用服务器后台生成服务。
            """;
    }

    private static bool ContainsAny(string value, params string[] terms)
    {
        return terms.Any(term => value.Contains(term, StringComparison.OrdinalIgnoreCase));
    }

    private static bool IsDeterministicTestMode()
    {
        return string.Equals(
            Environment.GetEnvironmentVariable("PHASEA_CHAT_TEST_MODE"),
            "deterministic",
            StringComparison.OrdinalIgnoreCase);
    }

    private static bool UsesNewApiBackend()
    {
        return string.Equals(
            Environment.GetEnvironmentVariable("PHASEA_CHAT_BACKEND"),
            "new-api",
            StringComparison.OrdinalIgnoreCase);
    }

    private static string ResolveRequestedModel(string? requestedModel)
    {
        if (string.IsNullOrWhiteSpace(requestedModel))
        {
            return CodexModelCatalog.DefaultModel();
        }

        var model = requestedModel.Trim();
        return CodexModelCatalog.IsAllowed(model) ? model : CodexModelCatalog.DefaultModel();
    }

    private static string BuildChatMemoryContext(string? memorySummary)
    {
        return string.IsNullOrWhiteSpace(memorySummary)
            ? "无。"
            : memorySummary.Trim();
    }

    private static string BuildRecentHistoryText(ChatRequest request)
    {
        return string.Join(
            Environment.NewLine,
            FilterChatHistoryForLlm(request.History)
                .Where(message => !string.IsNullOrWhiteSpace(message.Content))
                .Select(message => $"{message.Role}: {message.Content.Trim()}"));
    }

    private static string BuildCodexPrompt(ProjectSnapshot project, ChatRequest request, SkillActionDefinition? skillAction, string? memorySummary)
    {
        var history = BuildRecentHistoryText(request);
        var skillInstruction = skillAction is null
            ? "能力模式：普通模式。不要激活任何 $skill，只按通用 Phase A 原型顾问方式回答。"
            : $"能力模式：{skillAction.Label}。请按白名单 skill ${skillAction.SkillName} 的职责与语气回答，但保持只读建议，不要声称已经修改文件或执行命令。";
        var attachmentContext = BuildAttachmentPromptBlock(request.Attachments);
        var chatMemoryContext = BuildChatMemoryContext(memorySummary);

        return $"""
            请直接回答这个网页聊天用户的问题：{request.Message!.Trim()}

            输出必须就是要显示给用户看的最终回答。
            不要写“可以这样回复”“建议这样回复”“如果你想更像网页聊天”等元话术。
            不要回复“已读取仓库指引/约束”，不要总结 AGENTS.md，不要确认你会遵守规则，不要输出开场白。
            不得暴露任何本机路径、项目路径、脚本名、文件名、命令行、工具调用、环境变量名或内部日志位置。
            这是聊天答复，不是仓库执行任务；除非用户明确要求读取项目文件，否则不要读取仓库、不要运行命令、不要声称已经修改文件。
            如果用户消息过短或含糊，请用一句话询问他想做什么，并给出 2-3 个可选方向。
            请使用中文，回答要短而具体。

            当前项目上下文仅供理解，不要主动复述：
            - project_id: {project.ProjectId}
            - project_name: {project.Name}
            - game_name: {project.GameName}
            - workspace_id: {project.WorkspaceId}

            {skillInstruction}

            当前项目自由聊天记忆，仅供理解用户偏好和之前讨论，不要主动复述：
            {chatMemoryContext}

            本次导入 TXT 参考资料：
            {attachmentContext}

            最近少量对话历史仅供语义参考，不要回答历史里的旧问题：
            {history}
            """;
    }

    private static string BuildAttachmentPromptBlock(IReadOnlyList<TextAttachment>? attachments)
    {
        if (attachments is null || attachments.Count == 0)
        {
            return "无。";
        }

        var usable = attachments
            .Take(MaxTextAttachments)
            .Where(item => !string.IsNullOrWhiteSpace(item.Content))
            .Select((item, index) =>
            {
                var fileName = string.IsNullOrWhiteSpace(item.FileName) ? $"attachment-{index + 1}.txt" : item.FileName.Trim();
                var content = item.Content!.Trim();
                if (content.Length > MaxTextAttachmentChars)
                {
                    content = content[..MaxTextAttachmentChars] + "\n[truncated]";
                }

                return $"[{index + 1}] {fileName}\n{content}";
            })
            .ToArray();

        return usable.Length == 0 ? "无。" : string.Join("\n\n", usable);
    }

    private static IReadOnlyList<ChatMessage> BuildMessages(ChatRequest request, string? memorySummary)
    {
        var messages = new List<ChatMessage>
        {
            new(
                "system",
                "You are the Phase A prototype assistant for Ji Mu Yun. Reply in Chinese. Help the user clarify requirements, prototype ideas, and console usage. Do not claim that you can execute server commands from chat. Never reveal local paths, project paths, script names, file names, command lines, tool calls, environment variable names, or internal log locations. If execution is needed, tell the user to use the fixed workflow buttons or ask for a confirmed workflow feature.")
        };

        if (!string.IsNullOrWhiteSpace(memorySummary))
        {
            messages.Add(new ChatMessage(
                "system",
                $"Current project free-chat memory for continuity only. Do not repeat it unless directly useful:\n{memorySummary.Trim()}"));
        }

        foreach (var message in FilterChatHistoryForLlm(request.History))
        {
            if ((message.Role == "user" || message.Role == "assistant") &&
                !string.IsNullOrWhiteSpace(message.Content))
            {
                messages.Add(new ChatMessage(message.Role, message.Content.Trim()));
            }
        }

        var attachmentContext = BuildAttachmentPromptBlock(request.Attachments);
        var userMessage = attachmentContext == "无。"
            ? request.Message!.Trim()
            : $"""
                {request.Message!.Trim()}

                本次导入 TXT 参考资料：
                {attachmentContext}
                """;
        messages.Add(new ChatMessage("user", userMessage));
        return messages;
    }

    private static IReadOnlyList<ChatMessage> FilterChatHistoryForLlm(IReadOnlyList<ChatMessage>? history)
    {
        return (history ?? [])
            .Where(IsAllowedChatHistoryMessage)
            .TakeLast(MaxHistoryMessages)
            .ToArray();
    }

    private static bool IsAllowedChatHistoryMessage(ChatMessage message)
    {
        if (message.Role is not ("user" or "assistant") || string.IsNullOrWhiteSpace(message.Content))
        {
            return false;
        }

        var content = message.Content.Trim();
        return !content.StartsWith("系统扫描结果：", StringComparison.Ordinal) &&
               !content.Contains("系统不会自动启动 run。需要你点击下方一次性按钮确认。", StringComparison.Ordinal) &&
               !content.Contains("系统不会自动启动 run。需要你点击下方一次性按钮打开对应页面，再在页面内确认执行。", StringComparison.Ordinal) &&
               !content.Contains("推荐 run：", StringComparison.Ordinal) &&
               !content.Contains("推荐页面：", StringComparison.Ordinal);
    }

    private async Task UpdateProjectChatMemoryAsync(
        ProjectSnapshot project,
        ChatRequest request,
        string assistantMessage,
        string? providerSessionRef,
        CancellationToken cancellationToken)
    {
        var previous = await _metadataStore.GetProjectChatMemoryAsync(project.AccountId, project.ProjectId, cancellationToken);
        var summary = BuildUpdatedChatMemory(previous?.MemorySummary, request.Message ?? "", assistantMessage);
        await _metadataStore.UpsertProjectChatMemoryAsync(project.AccountId, project.ProjectId, summary, providerSessionRef, cancellationToken);
    }

    private static bool ShouldUpdateProjectChatMemory(ChatRequest request)
    {
        return request.Attachments is null || request.Attachments.Count == 0;
    }

    private static string BuildUpdatedChatMemory(string? previousMemory, string userMessage, string assistantMessage)
    {
        var lines = new List<string>();
        if (!string.IsNullOrWhiteSpace(previousMemory))
        {
            lines.AddRange(previousMemory.Split('\n').Select(line => line.Trim()).Where(line => line.Length > 0));
        }

        var user = CompactMemoryText(userMessage);
        var assistant = CompactMemoryText(assistantMessage);
        if (!string.IsNullOrWhiteSpace(user) || !string.IsNullOrWhiteSpace(assistant))
        {
            lines.Add($"最近讨论：用户提到“{user}”；助手回应“{assistant}”。");
        }

        var compact = new List<string>();
        foreach (var line in lines.AsEnumerable().Reverse())
        {
            if (compact.Contains(line, StringComparer.Ordinal))
            {
                continue;
            }

            compact.Add(line);
            var candidate = string.Join("\n", compact.AsEnumerable().Reverse());
            if (candidate.Length > MaxChatMemoryChars)
            {
                compact.RemoveAt(compact.Count - 1);
                break;
            }
        }

        return string.Join("\n", compact.AsEnumerable().Reverse());
    }

    private static string CompactMemoryText(string value)
    {
        var sanitized = PublicChatSanitizer.Sanitize(value)
            .Replace("\r", " ", StringComparison.Ordinal)
            .Replace("\n", " ", StringComparison.Ordinal)
            .Trim();
        return sanitized.Length <= MaxMemorySourceChars ? sanitized : sanitized[..MaxMemorySourceChars] + "...";
    }

}
