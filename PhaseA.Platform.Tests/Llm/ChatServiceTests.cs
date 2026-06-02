
using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Tests.Data;
using Xunit;

namespace PhaseA.Platform.Tests.Llm;

public sealed class ChatServiceTests
{
    [Fact]
    public async Task SendAsync_RequiresLlmBinding_WhenNewApiBackendIsSelected()
    {
        using var database = TempSqliteDatabase.Create();
        Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", "new-api");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            var service = Service(store, options, new FakeChatClient("reply"));

            var result = await service.SendAsync(accountId, projectId, new ChatRequest("hello"));

            result.Status.Should().Be("llm_binding_required");
            result.ExitCode.Should().Be(402);
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", null);
        }
    }

    [Fact]
    public async Task SendAsync_BlocksWhenTokenRefCannotResolve_WhenNewApiBackendIsSelected()
    {
        using var database = TempSqliteDatabase.Create();
        Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", "new-api");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            await store.UpsertLlmBindingAsync(new LlmBindingCommand(
                accountId,
                "new-api",
                "https://new-api.example.com/v1",
                "new-api-user-1",
                "env:PHASEA_TEST_TOKEN_MISSING"));
            var service = Service(store, options, new FakeChatClient("reply"));

            var result = await service.SendAsync(accountId, projectId, new ChatRequest("hello"));

            result.Status.Should().Be("llm_token_unresolved");
            result.ExitCode.Should().Be(424);
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", null);
        }
    }

    [Fact]
    public async Task SendAsync_CallsGateway_AndRecordsRunAudit_WhenNewApiBackendIsSelected()
    {
        using var database = TempSqliteDatabase.Create();
        var variableName = "PHASEA_TEST_TOKEN_" + Guid.NewGuid().ToString("N").ToUpperInvariant();
        Environment.SetEnvironmentVariable(variableName, "test-token");
        Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", "new-api");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            await store.UpsertLlmBindingAsync(new LlmBindingCommand(
                accountId,
                "new-api",
                "https://new-api.example.com/v1",
                "new-api-user-1",
                $"env:{variableName}"));
            var client = new FakeChatClient("assistant reply");
            var service = Service(store, options, client);

            var result = await service.SendAsync(accountId, projectId, new ChatRequest("hello", "gpt-5.4"));

            result.Status.Should().Be("succeeded");
            result.AssistantMessage.Should().Be("assistant reply");
            result.Model.Should().Be("gpt-5.4");
            client.LastToken.Should().Be("test-token");
            client.LastMessages.Should().Contain(message => message.Role == "user" && message.Content == "hello");
            var run = await store.GetRunSnapshotAsync(result.RunId);
            run!.RunType.Should().Be("prototype-chat");
            run.Status.Should().Be("succeeded");
            run.StdoutText.Should().Be("assistant reply");
            run.LlmGateway.Should().Be("new-api");
            run.LlmModel.Should().Be("gpt-5.4");
            run.LlmCostJson.Should().Contain("estimated_cost_cny");
        }
        finally
        {
            Environment.SetEnvironmentVariable(variableName, null);
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", null);
        }
    }

    [Fact]
    public async Task SendAsync_UsesProjectChatMemory_AndOnlyRecentThreeMessages_WhenNewApiBackendIsSelected()
    {
        using var database = TempSqliteDatabase.Create();
        var variableName = "PHASEA_TEST_TOKEN_" + Guid.NewGuid().ToString("N").ToUpperInvariant();
        Environment.SetEnvironmentVariable(variableName, "test-token");
        Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", "new-api");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            await store.UpsertLlmBindingAsync(new LlmBindingCommand(
                accountId,
                "new-api",
                "https://new-api.example.com/v1",
                "new-api-user-1",
                $"env:{variableName}"));
            await store.UpsertProjectChatMemoryAsync(accountId, projectId, "The user prefers fast concise RPG feedback.", "previous-session");
            var client = new FakeChatClient("assistant reply");
            var service = Service(store, options, client);
            var history = Enumerable.Range(1, 6)
                .Select(index => new ChatMessage(index % 2 == 0 ? "assistant" : "user", $"history-{index}"))
                .ToArray();

            var result = await service.SendAsync(accountId, projectId, new ChatRequest("hello", "gpt-5.4", history));

            result.Status.Should().Be("succeeded");
            client.LastMessages.Should().Contain(message => message.Role == "system" && message.Content.Contains("The user prefers fast concise RPG feedback", StringComparison.Ordinal));
            client.LastMessages.Should().NotContain(message => message.Content == "history-1");
            client.LastMessages.Should().NotContain(message => message.Content == "history-2");
            client.LastMessages.Should().NotContain(message => message.Content == "history-3");
            client.LastMessages.Should().Contain(message => message.Content == "history-4");
            client.LastMessages.Should().Contain(message => message.Content == "history-5");
            client.LastMessages.Should().Contain(message => message.Content == "history-6");
            var updatedMemory = await store.GetProjectChatMemoryAsync(accountId, projectId);
            updatedMemory.Should().NotBeNull();
            updatedMemory!.MemorySummary.Should().Contain("hello");
            updatedMemory.MemorySummary.Should().Contain("assistant reply");
            updatedMemory.ProviderSessionRef.Should().Be("req-test");
        }
        finally
        {
            Environment.SetEnvironmentVariable(variableName, null);
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", null);
        }
    }

    [Fact]
    public async Task SendAsync_DoesNotPersistTxtAttachmentContentIntoProjectChatMemory_WhenNewApiBackendIsSelected()
    {
        using var database = TempSqliteDatabase.Create();
        var variableName = "PHASEA_TEST_TOKEN_" + Guid.NewGuid().ToString("N").ToUpperInvariant();
        Environment.SetEnvironmentVariable(variableName, "test-token");
        Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", "new-api");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            await store.UpsertLlmBindingAsync(new LlmBindingCommand(
                accountId,
                "new-api",
                "https://new-api.example.com/v1",
                "new-api-user-1",
                $"env:{variableName}"));
            var client = new FakeChatClient("assistant reply");
            var service = Service(store, options, client);

            var result = await service.SendAsync(
                accountId,
                projectId,
                new ChatRequest(
                    "use the imported reference",
                    "gpt-5.4",
                    Attachments: [new TextAttachment("secret-notes.txt", "Sensitive imported reference content.")]));

            result.Status.Should().Be("succeeded");
            client.LastMessages.Should().Contain(message => message.Content.Contains("Sensitive imported reference content.", StringComparison.Ordinal));
            var memory = await store.GetProjectChatMemoryAsync(accountId, projectId);
            memory.Should().BeNull();
        }
        finally
        {
            Environment.SetEnvironmentVariable(variableName, null);
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", null);
        }
    }

    [Fact]
    public async Task SendAsync_CapsProjectChatMemory_WhenNewApiBackendIsSelected()
    {
        using var database = TempSqliteDatabase.Create();
        var variableName = "PHASEA_TEST_TOKEN_" + Guid.NewGuid().ToString("N").ToUpperInvariant();
        Environment.SetEnvironmentVariable(variableName, "test-token");
        Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", "new-api");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            await store.UpsertLlmBindingAsync(new LlmBindingCommand(
                accountId,
                "new-api",
                "https://new-api.example.com/v1",
                "new-api-user-1",
                $"env:{variableName}"));
            await store.UpsertProjectChatMemoryAsync(
                accountId,
                projectId,
                string.Join("\n", Enumerable.Range(1, 20).Select(index => $"old memory line {index}: {new string('x', 120)}")),
                null);
            var client = new FakeChatClient(new string('y', 2000));
            var service = Service(store, options, client);

            var result = await service.SendAsync(accountId, projectId, new ChatRequest(new string('z', 2000), "gpt-5.4"));

            result.Status.Should().Be("succeeded");
            var memory = await store.GetProjectChatMemoryAsync(accountId, projectId);
            memory.Should().NotBeNull();
            memory!.MemorySummary.Length.Should().BeLessThanOrEqualTo(1500);
            memory.MemorySummary.Should().Contain("...");
        }
        finally
        {
            Environment.SetEnvironmentVariable(variableName, null);
            Environment.SetEnvironmentVariable("PHASEA_CHAT_BACKEND", null);
        }
    }

    [Fact]
    public async Task SendAsync_UsesCodexCliBackend_ByDefault()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var binding = new LlmBindingService(store, options);
        var codex = new FakeCodexChatClient("codex says hello");
        var service = new ChatService(store, options, binding, new LlmStopLossService(store, options), new FakeChatClient("new-api should not be called"), codex);

        var result = await service.SendAsync(accountId, projectId, new ChatRequest("hello codex", "gpt-5.4-mini"));

        result.Status.Should().Be("succeeded");
        result.AssistantMessage.Should().Be("codex says hello");
        result.Model.Should().Be("gpt-5.4-mini");
        codex.LastModel.Should().Be("gpt-5.4-mini");
        codex.LastBillingApiKeyName.Should().Be(accountId);
        codex.LastPrompt.Should().Contain("hello codex");
        codex.LastPrompt.Should().Contain("请直接回答这个网页聊天用户的问题：hello codex");
        codex.LastPrompt.Should().Contain("输出必须就是要显示给用户看的最终回答");
        codex.LastPrompt.Should().Contain("不要写“可以这样回复”");
        codex.LastPrompt.Should().Contain("不要回复“已读取仓库指引/约束”");
        codex.LastPrompt.Should().Contain("不得暴露任何本机路径、项目路径、脚本名、文件名、命令行");
        codex.LastPrompt.Should().Contain("这是聊天答复，不是仓库执行任务");
        codex.LastPrompt.Should().NotContain("你是积木云 Phase A 浏览器自由对话助手");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.LlmGateway.Should().Be("codex-cli");
        run.LlmModel.Should().Be("gpt-5.4-mini");
        run.LlmCostJson.Should().Contain("billing_source").And.Contain("codex-cli").And.Contain("usage_status").And.Contain("unknown");
    }

    [Fact]
    public async Task SendAsync_RejectsProjectOwnedByAnotherAccount()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var ownerAccountId = await store.EnsureSingleAdminAsync();
        var otherAccount = await store.CreateUserAccountAsync("chat-other-account", 1);
        var projectId = await CreateProjectAsync(store, options, ownerAccountId);
        var binding = new LlmBindingService(store, options);
        var codex = new FakeCodexChatClient("should not run");
        var service = new ChatService(store, options, binding, new LlmStopLossService(store, options), new FakeChatClient("should not run"), codex);

        var act = () => service.SendAsync(otherAccount.AccountId, projectId, new ChatRequest("hello"));

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("Project not found.");
        codex.CallCount.Should().Be(0);
    }

    [Fact]
    public async Task SendAsync_RedactsSensitivePathsScriptsAndCommands_FromCodexReply()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var binding = new LlmBindingService(store, options);
        var codex = new FakeCodexChatClient(
            "请查看 C:\\jimuyun\\secret\\repo\\scripts\\python\\dev_cli.py，然后运行 dotnet test PhaseA.Platform.Tests\\PhaseA.Platform.Tests.csproj --no-restore。");
        var service = new ChatService(store, options, binding, new LlmStopLossService(store, options), new FakeChatClient("new-api should not be called"), codex);

        var result = await service.SendAsync(accountId, projectId, new ChatRequest("怎么验证？", "gpt-5.4"));

        result.AssistantMessage.Should().NotContain("C:\\");
        result.AssistantMessage.Should().NotContain("dev_cli.py");
        result.AssistantMessage.Should().NotContain("dotnet test");
        result.AssistantMessage.Should().NotContain("[已隐藏]");
        var run = await store.GetRunSnapshotAsync(result.RunId);
        run!.StdoutText.Should().Be(result.AssistantMessage);
    }

    [Fact]
    public async Task SendAsync_FallsBackToDefaultCodexModel_WhenRequestedModelIsNotAllowed()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var binding = new LlmBindingService(store, options);
        var codex = new FakeCodexChatClient("codex says hello");
        var service = new ChatService(store, options, binding, new LlmStopLossService(store, options), new FakeChatClient("new-api should not be called"), codex);

        var result = await service.SendAsync(accountId, projectId, new ChatRequest("hello codex", "not-allowed-model"));

        result.Status.Should().Be("succeeded");
        result.Model.Should().Be(CodexModelCatalog.DefaultModel());
        codex.LastModel.Should().Be(CodexModelCatalog.DefaultModel());
    }

    [Fact]
    public async Task SendAsync_IncludesSelectedSkillModeInCodexPrompt()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var binding = new LlmBindingService(store, options);
        var codex = new FakeCodexChatClient("codex says hello");
        var service = new ChatService(store, options, binding, new LlmStopLossService(store, options), new FakeChatClient("new-api should not be called"), codex);

        await service.SendAsync(accountId, projectId, new ChatRequest("help design", "gpt-5.4", SkillActionId: "game-design-master"));

        codex.LastPrompt.Should().Contain("游戏策划大师");
        codex.LastPrompt.Should().Contain("$bmad-agent-game-designer");
    }

    [Fact]
    public async Task SendAsync_IncludesTxtAttachmentsInCodexPrompt()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var binding = new LlmBindingService(store, options);
        var codex = new FakeCodexChatClient("codex says hello");
        var service = new ChatService(store, options, binding, new LlmStopLossService(store, options), new FakeChatClient("new-api should not be called"), codex);

        await service.SendAsync(
            accountId,
            projectId,
            new ChatRequest(
                "summarize references",
                "gpt-5.4",
                Attachments: [new TextAttachment("notes.txt", "Important boss design reference.")]));

        codex.LastPrompt.Should().Contain("notes.txt");
        codex.LastPrompt.Should().Contain("Important boss design reference.");
    }

    [Fact]
    public async Task SendAsync_RejectsMoreThanFiveTxtAttachments()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var projectId = await CreateProjectAsync(store, options, accountId);
        var binding = new LlmBindingService(store, options);
        var codex = new FakeCodexChatClient("codex should not run");
        var service = new ChatService(store, options, binding, new LlmStopLossService(store, options), new FakeChatClient("new-api should not be called"), codex);

        var result = await service.SendAsync(
            accountId,
            projectId,
            new ChatRequest(
                "summarize references",
                "gpt-5.4",
                Attachments: Enumerable.Range(1, 6).Select(index => new TextAttachment($"{index}.txt", "content")).ToArray()));

        result.Status.Should().Be("too_many_attachments");
    }

    [Fact]
    public async Task SendAsync_UsesDeterministicLocalMode_WhenEnabled()
    {
        using var database = TempSqliteDatabase.Create();
        Environment.SetEnvironmentVariable("PHASEA_CHAT_TEST_MODE", "deterministic");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            var client = new FakeChatClient("should not be called");
            var service = Service(store, options, client);

            var result = await service.SendAsync(accountId, projectId, new ChatRequest("hello local"));

            result.Status.Should().Be("succeeded");
            result.AssistantMessage.Should().Contain("hello local").And.Contain("Phase A");
            client.CallCount.Should().Be(0);
            var run = await store.GetRunSnapshotAsync(result.RunId);
            run!.RunType.Should().Be("prototype-chat");
            run.LlmGateway.Should().Be("deterministic-local");
            run.LlmCostJson.Should().Contain("estimated_cost_cny\":0");
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_CHAT_TEST_MODE", null);
        }
    }

    [Fact]
    public async Task SendAsync_DeterministicLocalMode_AnswersCapabilityQuestions()
    {
        using var database = TempSqliteDatabase.Create();
        Environment.SetEnvironmentVariable("PHASEA_CHAT_TEST_MODE", "deterministic");
        try
        {
            var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());
            await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
            var store = new PhaseAMetadataStore(database.ConnectionString, options);
            var accountId = await store.EnsureSingleAdminAsync();
            var projectId = await CreateProjectAsync(store, options, accountId);
            var service = Service(store, options, new FakeChatClient("should not be called"));

            var result = await service.SendAsync(accountId, projectId, new ChatRequest("help"));

            result.Status.Should().Be("succeeded");
            result.AssistantMessage.Should().Contain("Phase A").And.Contain("LLM");
        }
        finally
        {
            Environment.SetEnvironmentVariable("PHASEA_CHAT_TEST_MODE", null);
        }
    }

    private static ChatService Service(PhaseAMetadataStore store, PhaseAPlatformOptions options, INewApiChatClient client)
    {
        var binding = new LlmBindingService(store, options);
        return new ChatService(store, options, binding, new LlmStopLossService(store, options), client, new FakeCodexChatClient("codex reply"));
    }

    private static async Task<string> CreateProjectAsync(PhaseAMetadataStore store, PhaseAPlatformOptions options, string accountId)
    {
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var result = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Demo Game", "manual", null, null, null, null));
        return result.ProjectId!;
    }

    private sealed class FakeChatClient : INewApiChatClient
    {
        private readonly string _reply;

        public FakeChatClient(string reply)
        {
            _reply = reply;
        }

        public string? LastToken { get; private set; }

        public int CallCount { get; private set; }

        public IReadOnlyList<ChatMessage> LastMessages { get; private set; } = [];

        public Task<NewApiChatClientResult> CompleteAsync(
            LlmBindingSnapshot binding,
            string bearerToken,
            string model,
            IReadOnlyList<ChatMessage> messages,
            CancellationToken cancellationToken = default)
        {
            CallCount++;
            LastToken = bearerToken;
            LastMessages = messages;
            return Task.FromResult(new NewApiChatClientResult(true, _reply, null, "req-test", null));
        }
    }

    private sealed class FakeCodexChatClient : ICodexChatClient
    {
        private readonly string _reply;

        public FakeCodexChatClient(string reply)
        {
            _reply = reply;
        }

        public string? LastModel { get; private set; }

        public string? LastPrompt { get; private set; }
        public string? LastBillingApiKeyName { get; private set; }
        public int CallCount { get; private set; }

        public Task<CodexChatClientResult> CompleteAsync(
            string projectRoot,
            string model,
            string prompt,
            CodexChatClientOptions? options = null,
            string? billingApiKeyName = null,
            CancellationToken cancellationToken = default)
        {
            CallCount++;
            LastModel = model;
            LastPrompt = prompt;
            LastBillingApiKeyName = billingApiKeyName;
            return Task.FromResult(new CodexChatClientResult(true, _reply, null, 0, "", ""));
        }
    }
}
