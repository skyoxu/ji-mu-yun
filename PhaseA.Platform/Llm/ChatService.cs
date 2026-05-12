using System.Text.Json;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Skills;
using PhaseA.Platform.Workspaces;

namespace PhaseA.Platform.Llm;

public sealed class ChatService
{
    private const string RunType = "prototype-chat";
    private const decimal EstimatedChatCostCny = 0.10m;
    private const int MaxMessageLength = 8000;
    private const int MaxHistoryMessages = 10;

    private readonly PhaseAMetadataStore _metadataStore;
    private readonly PhaseAPlatformOptions _options;
    private readonly LlmBindingService _llmBindingService;
    private readonly LlmStopLossService _llmStopLossService;
    private readonly INewApiChatClient _chatClient;
    private readonly ICodexChatClient _codexChatClient;
    private readonly IProjectWorkspaceSeeder _workspaceSeeder;
    private readonly SkillActionCatalog _skillActionCatalog;

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
        SkillActionCatalog skillActionCatalog)
    {
        _metadataStore = metadataStore;
        _options = options;
        _llmBindingService = llmBindingService;
        _llmStopLossService = llmStopLossService;
        _chatClient = chatClient;
        _codexChatClient = codexChatClient;
        _workspaceSeeder = workspaceSeeder;
        _skillActionCatalog = skillActionCatalog;
    }

    public async Task<ChatResult> SendAsync(string projectId, ChatRequest request, CancellationToken cancellationToken = default)
    {
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

        var project = await _metadataStore.GetProjectSnapshotAsync(projectId, cancellationToken);
        if (project is null)
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

        var messages = BuildMessages(request);
        var completion = await _chatClient.CompleteAsync(binding, token, model, messages, cancellationToken);
        var status = completion.Succeeded ? "succeeded" : "failed";
        var exitCode = completion.Succeeded ? 0 : 1;
        var stdout = completion.AssistantMessage ?? "";
        var stderr = completion.RawError ?? completion.FailureCode ?? "";
        var evidenceJson = JsonSerializer.Serialize(new
        {
            run_type = RunType,
            model,
            gateway_provider = binding.GatewayProvider,
            external_account_ref = binding.ExternalAccountRef,
            message_length = request.Message!.Length,
            history_count = request.History?.Count ?? 0
        });
        await _metadataStore.CompleteRunAsync(runId, status, exitCode, stdout, stderr, evidenceJson, cancellationToken);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            binding.GatewayProvider,
            completion.RequestId,
            model,
            LlmStopLossService.BuildCostJson(estimate, stopLoss),
            cancellationToken);

        return new ChatResult(runId, status, exitCode, completion.AssistantMessage, completion.FailureCode, model);
    }

    private async Task<ChatResult> CompleteWithCodexAsync(
        ProjectSnapshot project,
        ChatRequest request,
        string model,
        CancellationToken cancellationToken)
    {
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        _workspaceSeeder.EnsureSeeded(project.RepoPath);
        var skillAction = ResolveSkillAction(request.SkillActionId);
        var prompt = BuildCodexPrompt(project, request, skillAction);
        var completion = await _codexChatClient.CompleteAsync(project.RepoPath, model, prompt, cancellationToken);
        var status = completion.Succeeded ? "succeeded" : "failed";
        var stdout = completion.AssistantMessage ?? completion.Stdout;
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
            history_count = request.History?.Count ?? 0,
            failure_code = completion.FailureCode
        });
        await _metadataStore.CompleteRunAsync(runId, status, completion.ExitCode, stdout, stderr, evidenceJson, cancellationToken);
        await _metadataStore.RecordRunLlmAuditAsync(
            runId,
            "codex-cli",
            null,
            model,
            JsonSerializer.Serialize(new
            {
                estimated_cost_cny = 0m,
                model,
                backend = "codex-cli"
            }),
            cancellationToken);

        return new ChatResult(runId, status, completion.ExitCode, completion.AssistantMessage, completion.FailureCode, model);
    }

    private async Task<ChatResult> CompleteDeterministicAsync(
        ProjectSnapshot project,
        ChatRequest request,
        string model,
        CancellationToken cancellationToken)
    {
        var runId = await _metadataStore.CreateRunAsync(project.ProjectId, project.WorkspaceId, RunType, cancellationToken);
        await _metadataStore.MarkRunStartedAsync(runId, cancellationToken);

        var reply = BuildDeterministicReply(request.Message!.Trim());
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
                3. 根据你的游戏想法，给出可填写到 7 步可玩原型表单的草稿。
                4. 提醒哪些操作需要用固定工作流按钮执行。
                5. 验证聊天链路、鉴权、run 记录和 LLM 审计是否工作。
                """;
        }

        return $"""
            我已收到：{message}

            当前是本机测试模式。我可以按规则帮你整理 Phase A 原型想法、解释控制台使用方式，或说明如何使用服务器 Codex CLI 后端。
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

    private static string BuildCodexPrompt(ProjectSnapshot project, ChatRequest request, SkillActionDefinition? skillAction)
    {
        var history = string.Join(
            Environment.NewLine,
            (request.History ?? [])
                .TakeLast(MaxHistoryMessages)
                .Where(message => !string.IsNullOrWhiteSpace(message.Content))
                .Select(message => $"{message.Role}: {message.Content.Trim()}"));
        var skillInstruction = skillAction is null
            ? "能力模式：普通模式。不要激活任何 $skill，只按通用 Phase A 原型顾问方式回答。"
            : $"能力模式：{skillAction.Label}。请按白名单 skill ${skillAction.SkillName} 的职责与语气回答，但保持只读建议，不要声称已经修改文件或执行命令。";

        return $"""
            你是积木云 Phase A 浏览器自由对话助手，运行在服务器本机 Codex CLI 中。
            请使用中文回答。
            {skillInstruction}

            当前项目：
            - project_id: {project.ProjectId}
            - project_name: {project.Name}
            - game_name: {project.GameName}
            - workspace_id: {project.WorkspaceId}

            安全边界：
            - 当前通过网页聊天调用，只允许给出建议、解释、拆解需求、指导用户使用 Phase A 控制台。
            - 不要声称你已经执行了服务器命令或修改了文件。
            - 如果用户需要执行工作流，请让用户使用页面上的固定按钮，或说明需要走“提交反馈并继续优化原型”。

            对话历史：
            {history}

            用户消息：
            {request.Message!.Trim()}
            """;
    }

    private static IReadOnlyList<ChatMessage> BuildMessages(ChatRequest request)
    {
        var messages = new List<ChatMessage>
        {
            new(
                "system",
                "You are the Phase A prototype assistant for Ji Mu Yun. Reply in Chinese. Help the user clarify requirements, prototype ideas, and console usage. Do not claim that you can execute server commands from chat. If execution is needed, tell the user to use the fixed workflow buttons or ask for a confirmed workflow feature.")
        };

        foreach (var message in (request.History ?? []).TakeLast(MaxHistoryMessages))
        {
            if ((message.Role == "user" || message.Role == "assistant") &&
                !string.IsNullOrWhiteSpace(message.Content))
            {
                messages.Add(new ChatMessage(message.Role, message.Content.Trim()));
            }
        }

        messages.Add(new ChatMessage("user", request.Message!.Trim()));
        return messages;
    }
}
