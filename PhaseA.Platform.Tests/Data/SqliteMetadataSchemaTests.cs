using FluentAssertions;
using PhaseA.Platform.Configuration;
using PhaseA.Platform.Data;
using PhaseA.Platform.Llm;
using PhaseA.Platform.Projects;
using PhaseA.Platform.Security;
using Xunit;

namespace PhaseA.Platform.Tests.Data;

public sealed class SqliteMetadataSchemaTests
{
    [Fact]
    public async Task InitializeAsync_CreatesExpectedTables_AndIsRepeatable()
    {
        using var database = TempSqliteDatabase.Create();

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);

        var tables = await database.ReadTableNamesAsync();

        tables.Should().Contain([
            "accounts",
            "projects",
            "workspaces",
            "runs",
            "artifacts",
            "approvals",
            "project_limits",
            "runner_locks",
            "account_llm_bindings",
            "aicodemirror_key_pool",
            "project_chat_messages",
            "project_chat_memories",
            "admin_account_audit_events",
            "project_prototype_drafts",
            "project_iteration_sessions",
            "project_iteration_goals",
            "project_iteration_goal_runs"
        ]);
    }

    [Fact]
    public async Task InitializeAsync_MigratesLegacyProjectsBeforeCreatingLastActivityIndexesAndTriggers()
    {
        using var database = TempSqliteDatabase.Create();
        await CreateLegacyDatabaseWithoutProjectLastActivityAsync(database.ConnectionString);

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);

        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString);
        await connection.OpenAsync();
        var columns = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        await using (var command = connection.CreateCommand())
        {
            command.CommandText = "PRAGMA table_info(projects);";
            await using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                columns.Add(reader.GetString(1));
            }
        }

        columns.Should().Contain("last_activity_utc");
        var lastActivityUtc = await ScalarStringAsync(connection, "SELECT last_activity_utc FROM projects WHERE id = 'legacy-project';");
        var lastActivityIndexCount = await ScalarLongAsync(connection, "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = 'ix_projects_account_last_activity';");
        var lastActivityTriggerCount = await ScalarLongAsync(connection, "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name LIKE '%last_activity%';");

        lastActivityUtc.Should().Be("2099-01-02T00:00:00.0000000Z");
        lastActivityIndexCount.Should().Be(1);
        lastActivityTriggerCount.Should().BeGreaterThan(0);
    }

    [Fact]
    public async Task EnsureSingleAdminAsync_BootstrapsAdminWithDefaultProjectLimit()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);

        var accountId = await store.EnsureSingleAdminAsync();
        var repeatedAccountId = await store.EnsureSingleAdminAsync();
        var projectLimit = await store.GetProjectLimitAsync(accountId);

        repeatedAccountId.Should().Be(accountId);
        projectLimit.Should().Be(2);
    }

    [Fact]
    public async Task CreateUserAccountAsync_StoresTokenHashAndProjectLimit()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);

        var result = await store.CreateUserAccountAsync("phaseb-user", 1);
        var resolved = await store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(result.Token));
        var projectLimit = await store.GetProjectLimitAsync(result.AccountId);

        resolved.Should().NotBeNull();
        resolved!.AccountId.Should().Be(result.AccountId);
        resolved.Username.Should().Be("phaseb-user");
        resolved.IsAdmin.Should().BeFalse();
        resolved.IsDisabled.Should().BeFalse();
        projectLimit.Should().Be(1);
    }

    [Fact]
    public async Task AiCodeMirrorKeyPool_ImportsAndAssignsKeysToAccounts()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var first = await store.CreateUserAccountAsync("key-user-one", 1);
        var second = await store.CreateUserAccountAsync("key-user-two", 1);
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("upstream-key-one", CredentialImported: true));
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("upstream-key-two", CredentialImported: true));

        var assigned = await store.AssignAiCodeMirrorKeyToAccountAsync("upstream-key-one", first.AccountId);
        var conflict = await store.AssignAiCodeMirrorKeyToAccountAsync("upstream-key-one", second.AccountId);
        var reassigned = await store.AssignAiCodeMirrorKeyToAccountAsync("upstream-key-two", first.AccountId);
        var keys = await store.ListAiCodeMirrorKeysAsync();

        assigned.Succeeded.Should().BeTrue();
        assigned.Entry!.AccountId.Should().Be(first.AccountId);
        conflict.Succeeded.Should().BeFalse();
        conflict.FailureCode.Should().Be("aicodemirror_key_already_assigned");
        reassigned.Succeeded.Should().BeTrue();
        reassigned.Entry!.KeyName.Should().Be("upstream-key-two");
        keys.Should().Contain(item => item.KeyName == "upstream-key-one" && item.AccountId == null && item.Status == "available");
        keys.Should().Contain(item => item.KeyName == "upstream-key-two" && item.AccountId == first.AccountId && item.Status == "assigned");
    }

    [Fact]
    public async Task AiCodeMirrorKeyPool_ImportedApiKeyCreatesIsolatedCodexHome()
    {
        using var database = TempSqliteDatabase.Create();
        var codexHomeRoot = Path.Combine(Path.GetTempPath(), "phasea-test-codex-home", Guid.NewGuid().ToString("N"));
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>
        {
            ["AICODEMIRROR_CODEX_HOME_ROOT"] = codexHomeRoot
        });

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var user = await store.CreateUserAccountAsync("key-user-runtime", 1);
        var keyPool = new AiCodeMirrorKeyPoolService(store, options);

        var imported = await keyPool.ImportAsync(new AiCodeMirrorKeyImportRequest(
            KeyName: "runtime-key-one",
            ApiKey: "sk-test-runtime-secret",
            Notes: "runtime credential"));
        var assigned = await keyPool.AssignAsync(new AiCodeMirrorKeyAssignRequest(user.AccountId, "runtime-key-one"));
        var credential = await keyPool.ResolveRuntimeCredentialForAccountAsync(user.AccountId);

        imported.Should().NotBeNull();
        assigned.Succeeded.Should().BeTrue();
        credential.Ready.Should().BeTrue();
        credential.BillingKeyName.Should().Be("runtime-key-one");
        credential.CodexHomePath.Should().NotBeNullOrWhiteSpace();
        File.Exists(Path.Combine(credential.CodexHomePath!, "auth.json")).Should().BeTrue();
        File.Exists(Path.Combine(credential.CodexHomePath!, "config.toml")).Should().BeTrue();
        (await store.ListAiCodeMirrorKeysAsync()).Should().OnlyContain(item => !item.ToString()!.Contains("sk-test-runtime-secret", StringComparison.Ordinal));
    }

    [Fact]
    public async Task CreateUserAccountAsync_WhenRequired_AssignsNextAvailableAiCodeMirrorKey()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("first-key", CredentialImported: true));
        await store.UpsertAiCodeMirrorKeyAsync(new AiCodeMirrorKeyImportCommand("second-key", CredentialImported: true));

        var user = await store.CreateUserAccountAsync("auto-key-user", 1, validDays: 7, spendLimitCny: 12.5m, requireAiCodeMirrorKey: true);
        var keys = await store.ListAiCodeMirrorKeysAsync();
        var users = await store.ListAccountsAsync();

        user.AiCodeMirrorKeyName.Should().Be("first-key");
        user.ValidUntilUtc.Should().NotBeNullOrWhiteSpace();
        user.SpendLimitCny.Should().Be(12.5m);
        keys.Should().Contain(item => item.KeyName == "first-key" && item.AccountId == user.AccountId && item.Status == "assigned");
        users.Should().Contain(item => item.AccountId == user.AccountId && item.AiCodeMirrorKeyName == "first-key" && item.SpendLimitCny == 12.5m);
    }

    [Fact]
    public async Task ProjectBelongsToAccountAsync_ReturnsFalseForOtherAccounts()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var owner = await store.EnsureSingleAdminAsync();
        var other = await store.CreateUserAccountAsync("other-user", 1);
        var project = await store.CreateProjectAsync(CreateCommand(owner, "project-one", "Game One"));

        (await store.ProjectBelongsToAccountAsync(owner, project.ProjectId!)).Should().BeTrue();
        (await store.ProjectBelongsToAccountAsync(other.AccountId, project.ProjectId!)).Should().BeFalse();
    }

    [Fact]
    public async Task ListAccountsAsync_ReturnsProjectCountsAndLimits()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var admin = await store.EnsureSingleAdminAsync();
        var user = await store.CreateUserAccountAsync("listed-user", 1);
        await store.CreateProjectAsync(CreateCommand(user.AccountId, "project-one", "Game One"));

        var accounts = await store.ListAccountsAsync();

        accounts.Should().Contain(account => account.AccountId == admin && account.IsAdmin);
        accounts.Should().Contain(account =>
            account.AccountId == user.AccountId &&
            account.Username == "listed-user" &&
            !account.IsAdmin &&
            !account.IsDisabled &&
            account.ProjectLimit == 1 &&
            account.ProjectCount == 1);
    }

    [Fact]
    public async Task SetUserDisabledAsync_BlocksTokenResolution()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var user = await store.CreateUserAccountAsync("disabled-user", 1);
        var tokenHash = PhaseAAuth.HashTokenForStorage(user.Token);

        (await store.SetUserDisabledAsync(user.AccountId, true)).Should().BeTrue();
        (await store.ResolveAccountByTokenHashAsync(tokenHash)).Should().BeNull();

        (await store.SetUserDisabledAsync(user.AccountId, false)).Should().BeTrue();
        (await store.ResolveAccountByTokenHashAsync(tokenHash)).Should().NotBeNull();
    }

    [Fact]
    public async Task RotateUserTokenAsync_InvalidatesPreviousToken()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var user = await store.CreateUserAccountAsync("rotate-user", 1);
        var oldHash = PhaseAAuth.HashTokenForStorage(user.Token);

        var rotated = await store.RotateUserTokenAsync(user.AccountId);

        rotated.Should().NotBeNull();
        rotated!.Token.Should().NotBe(user.Token);
        (await store.ResolveAccountByTokenHashAsync(oldHash)).Should().BeNull();
        (await store.ResolveAccountByTokenHashAsync(PhaseAAuth.HashTokenForStorage(rotated.Token))).Should().NotBeNull();
    }

    [Fact]
    public async Task AdminAccountAuditEvents_AreRecordedAndListed()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var admin = await store.EnsureSingleAdminAsync();
        var user = await store.CreateUserAccountAsync("audit-user", 1);

        await store.RecordAdminAccountAuditEventAsync(
            admin,
            "user_created",
            user.AccountId,
            new { username = user.Username, project_limit = user.ProjectLimit });

        var events = await store.ListAdminAccountAuditEventsAsync();

        events.Should().ContainSingle();
        events[0].ActorAccountId.Should().Be(admin);
        events[0].TargetAccountId.Should().Be(user.AccountId);
        events[0].Action.Should().Be("user_created");
        events[0].MetadataJson.Should().Contain("audit-user");
        events[0].MetadataJson.Should().NotContain(user.Token);
    }

    [Fact]
    public async Task ListAdminAccountAuditEventsAsync_FiltersAndOffsetsResults()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var admin = await store.EnsureSingleAdminAsync();
        var first = await store.CreateUserAccountAsync("audit-first", 1);
        var second = await store.CreateUserAccountAsync("audit-second", 1);

        await store.RecordAdminAccountAuditEventAsync(admin, "user_created", first.AccountId, new { username = first.Username });
        await store.RecordAdminAccountAuditEventAsync(admin, "user_disabled", first.AccountId, new { disabled = true });
        await store.RecordAdminAccountAuditEventAsync(admin, "user_created", second.AccountId, new { username = second.Username });

        var filtered = await store.ListAdminAccountAuditEventsAsync(
            new AdminAccountAuditQuery(Limit: 10, Offset: 0, Action: "user_created", TargetAccountId: first.AccountId));
        var offset = await store.ListAdminAccountAuditEventsAsync(
            new AdminAccountAuditQuery(Limit: 1, Offset: 1, Action: "user_created", TargetAccountId: null));

        filtered.Should().ContainSingle();
        filtered[0].Action.Should().Be("user_created");
        filtered[0].TargetAccountId.Should().Be(first.AccountId);
        offset.Should().ContainSingle();
        offset[0].TargetAccountId.Should().Be(first.AccountId);
    }

    [Fact]
    public async Task CreateProjectAsync_EnforcesDefaultAccountQuota()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();

        var first = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        first.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(first.ProjectId!, "succeeded", null);
        var second = await store.CreateProjectAsync(CreateCommand(accountId, "project-two", "Game Two"));
        second.Succeeded.Should().BeTrue();
        await store.SetProjectBootstrapStatusAsync(second.ProjectId!, "succeeded", null);
        var third = await store.CreateProjectAsync(CreateCommand(accountId, "project-three", "Game Three"));

        third.Succeeded.Should().BeFalse();
        third.FailureCode.Should().Be("project_quota_exceeded");
        third.ProjectLimit.Should().Be(2);
    }

    [Fact]
    public async Task ListProjectsAsync_ReturnsCreatedUtcAndLastActivityUtc()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();

        var first = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        first.Succeeded.Should().BeTrue();
        var second = await store.CreateProjectAsync(CreateCommand(accountId, "project-two", "Game Two"));
        second.Succeeded.Should().BeTrue();
        var firstCreatedUtc = "2099-06-01T00:00:00.0000000Z";
        var secondCreatedUtc = "2099-06-02T00:00:00.0000000Z";
        var firstRunFinishedUtc = "2099-06-03T00:00:00.0000000Z";

        await SetProjectCreatedUtcAsync(database.ConnectionString, first.ProjectId!, firstCreatedUtc);
        await SetProjectCreatedUtcAsync(database.ConnectionString, second.ProjectId!, secondCreatedUtc);
        var firstRun = await store.CreateRunAsync(first.ProjectId!, first.WorkspaceId, "prototype-chat");
        await SetRunTimingAsync(database.ConnectionString, firstRun, firstCreatedUtc, firstCreatedUtc, firstRunFinishedUtc);

        var projects = await store.ListProjectsAsync(accountId);

        projects.Should().HaveCount(2);
        projects.Single(project => project.ProjectId == first.ProjectId).CreatedUtc.Should().Be(firstCreatedUtc);
        projects.Single(project => project.ProjectId == first.ProjectId).LastActivityUtc.Should().Be(firstRunFinishedUtc);
        projects.Single(project => project.ProjectId == second.ProjectId).LastActivityUtc.Should().Be(secondCreatedUtc);
        projects.Last().ProjectId.Should().Be(first.ProjectId);
    }

    [Fact]
    public async Task ProjectChatMessages_AreAccountAndProjectScoped_AndRetained()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));

        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "user", "hello", retainLatest: 2);
        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "assistant", "world", retainLatest: 2);
        await store.AddProjectChatMessageAsync(accountId, project.ProjectId!, "user", "latest", retainLatest: 2);

        var messages = await store.ListProjectChatMessagesAsync(accountId, project.ProjectId!, limit: 10);
        var otherAccountMessages = await store.ListProjectChatMessagesAsync("other-account", project.ProjectId!, limit: 10);

        messages.Select(message => message.Content).Should().Equal("world", "latest");
        messages.Select(message => message.Role).Should().Equal("assistant", "user");
        otherAccountMessages.Should().BeEmpty();
    }

    [Fact]
    public async Task ProjectChatMemory_IsAccountAndProjectScoped()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));

        await store.UpsertProjectChatMemoryAsync(accountId, project.ProjectId!, "memory v1", "session-1");
        await store.UpsertProjectChatMemoryAsync(accountId, project.ProjectId!, "memory v2", "session-2");

        var memory = await store.GetProjectChatMemoryAsync(accountId, project.ProjectId!);
        var otherAccountMemory = await store.GetProjectChatMemoryAsync("other-account", project.ProjectId!);

        memory.Should().NotBeNull();
        memory!.MemorySummary.Should().Be("memory v2");
        memory.ProviderSessionRef.Should().Be("session-2");
        otherAccountMemory.Should().BeNull();
    }

    [Fact]
    public async Task ProjectChatHistory_MarksLatestSuggestedAssistantMessageConsumed_AfterFormalFeedback()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        var chatHistory = new ProjectChatHistoryService(store);

        await store.AddProjectChatMessageAsync(
            accountId,
            project.ProjectId!,
            "assistant",
            "本轮继续优化已完成。\n\n下一步建议：继续优化首分钟体验。",
            "formal-feedback-result",
            retainLatest: 10);
        await store.AddProjectChatMessageAsync(
            accountId,
            project.ProjectId!,
            "user",
            "我同意，继续。",
            "formal-feedback",
            retainLatest: 10);

        var result = await chatHistory.ListAsync(accountId, project.ProjectId!);

        result.Should().NotBeNull();
        result!.Messages.Should().HaveCount(2);
        result.Messages[0].SuggestedFeedback.Should().Be("继续优化首分钟体验。");
        result.Messages[0].ContinueConsumed.Should().BeTrue();
        result.Messages[1].ContinueConsumed.Should().BeFalse();
    }

    [Fact]
    public async Task ProjectChatHistory_RemovesInternalRouteBlocks_WhenListingStoredMessages()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        var chatHistory = new ProjectChatHistoryService(store);

        await store.AddProjectChatMessageAsync(
            accountId,
            project.ProjectId!,
            "assistant",
            "目标 1 修复已执行。\n本轮目标：\nDirection lock:\nProject README:\nC:\\host\\secret",
            "needs-fix-route-result",
            retainLatest: 10);

        var result = await chatHistory.ListAsync(accountId, project.ProjectId!);

        result.Should().NotBeNull();
        result!.Messages.Single().Content.Should().Be("目标 1 修复已执行。");
    }

    [Fact]
    public async Task ReconcileAbandonedRunsAsync_FailsOnlyRunsThatExceededHeartbeatTimeout()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var staleCreated = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Stale Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(staleCreated.ProjectId!, "succeeded", null);
        var freshCreated = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Fresh Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(freshCreated.ProjectId!, "succeeded", null);
        var staleProject = await store.GetProjectSnapshotAsync(staleCreated.ProjectId!);
        var freshProject = await store.GetProjectSnapshotAsync(freshCreated.ProjectId!);
        var staleRunId = await store.CreateRunAsync(staleProject!.ProjectId, staleProject.WorkspaceId, "prototype-feedback-iteration");
        var freshRunId = await store.CreateRunAsync(freshProject!.ProjectId, freshProject.WorkspaceId, "prototype-feedback-iteration");
        await store.MarkRunStartedAsync(staleRunId);
        await store.MarkRunStartedAsync(freshRunId);
        await store.TryAcquireRunnerLockAsync(staleProject.ProjectId, staleRunId);
        await store.TryAcquireRunnerLockAsync(freshProject.ProjectId, freshRunId);

        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                UPDATE runs
                SET started_utc = $old_utc,
                    progress_updated_utc = $old_utc
                WHERE id = $run_id;
                """;
            command.Parameters.AddWithValue("$old_utc", DateTimeOffset.UtcNow.AddHours(-2).ToString("O"));
            command.Parameters.AddWithValue("$run_id", staleRunId);
            await command.ExecuteNonQueryAsync();
        }

        var recovered = await store.ReconcileAbandonedRunsAsync(
            run => run.RunType == "prototype-feedback-iteration" ? TimeSpan.FromHours(1) : null,
            run => $"timeout:{run.RunType}");
        var staleRun = await store.GetRunSnapshotAsync(staleRunId);
        var freshRun = await store.GetRunSnapshotAsync(freshRunId);

        recovered.Should().Be(1);
        staleRun!.Status.Should().Be("failed");
        staleRun.StderrText.Should().Contain("timeout:prototype-feedback-iteration");
        freshRun!.Status.Should().Be("running");
        (await store.HasRunnerLockAsync(staleProject.ProjectId)).Should().BeFalse();
        (await store.HasRunnerLockAsync(freshProject.ProjectId)).Should().BeTrue();
    }

    [Fact]
    public async Task HasActiveRunAsync_IgnoresRunningChatRuns()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Chat Game", "manual", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var chatRunId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-chat");
        await store.MarkRunStartedAsync(chatRunId);

        var chatOnlyActive = await store.HasActiveRunAsync(project.ProjectId);

        chatOnlyActive.Should().BeFalse();

        var workflowRunId = await store.CreateRunAsync(project.ProjectId, project.WorkspaceId, "prototype-iteration-goal");
        await store.MarkRunStartedAsync(workflowRunId);

        var workflowActive = await store.HasActiveRunAsync(project.ProjectId);

        workflowActive.Should().BeTrue();
    }

    [Fact]
    public async Task ReconcileAbandonedRunsAsync_CanRecoverPrototypeQuickFixRuns()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var service = new ProjectCreationService(store, options, new ProjectRuleCatalog());
        var created = await service.CreateProjectAsync(accountId, new ProjectCreationRequest(null, "Quick Fix Game", "RPG", null, null, null, null));
        await store.SetProjectBootstrapStatusAsync(created.ProjectId!, "succeeded", null);
        var project = await store.GetProjectSnapshotAsync(created.ProjectId!);
        var runId = await store.CreateRunAsync(project!.ProjectId, project.WorkspaceId, "prototype-quick-fix");
        await store.MarkRunStartedAsync(runId);
        await store.TryAcquireRunnerLockAsync(project.ProjectId, runId);

        await using (var connection = new Microsoft.Data.Sqlite.SqliteConnection(database.ConnectionString))
        {
            await connection.OpenAsync();
            await using var command = connection.CreateCommand();
            command.CommandText = """
                UPDATE runs
                SET started_utc = $old_utc,
                    progress_updated_utc = $old_utc
                WHERE id = $run_id;
                """;
            command.Parameters.AddWithValue("$old_utc", DateTimeOffset.UtcNow.AddMinutes(-10).ToString("O"));
            command.Parameters.AddWithValue("$run_id", runId);
            await command.ExecuteNonQueryAsync();
        }

        var recovered = await store.ReconcileAbandonedRunsAsync(
            run => run.RunType == "prototype-quick-fix" ? TimeSpan.FromMinutes(3) : null,
            run => $"timeout:{run.RunType}");
        var recoveredRun = await store.GetRunSnapshotAsync(runId);

        recovered.Should().Be(1);
        recoveredRun!.Status.Should().Be("failed");
        recoveredRun.StderrText.Should().Contain("timeout:prototype-quick-fix");
        (await store.HasRunnerLockAsync(project.ProjectId)).Should().BeFalse();
    }

    [Fact]
    public async Task GetLatestProjectIterationSessionAsync_ReturnsStructuredGoalRuns()
    {
        using var database = TempSqliteDatabase.Create();
        var options = PhaseAPlatformOptionsLoader.FromDictionary(new Dictionary<string, string?>());

        await SqliteMetadataSchema.InitializeAsync(database.ConnectionString);
        var store = new PhaseAMetadataStore(database.ConnectionString, options);
        var accountId = await store.EnsureSingleAdminAsync();
        var project = await store.CreateProjectAsync(CreateCommand(accountId, "project-one", "Game One"));
        await store.SetProjectBootstrapStatusAsync(project.ProjectId!, "succeeded", null);

        var session = await store.CreateProjectIterationSessionAsync(
            accountId,
            project.ProjectId!,
            "manual_feedback",
            "improve prototype",
            "overall goal",
            [
                new ProjectIterationGoalCreateCommand(1, "Goal 1", "Desc 1", "Hint 1"),
                new ProjectIterationGoalCreateCommand(2, "Goal 2", "Desc 2", "Hint 2")
            ]);

        var runId = await store.CreateRunAsync(project.ProjectId!, project.WorkspaceId, "prototype-iteration-goal");
        var details = await store.GetLatestProjectIterationSessionAsync(project.ProjectId!);
        details.Should().NotBeNull();
        await store.LinkProjectIterationGoalRunAsync(session.SessionId, details!.Goals[0].GoalId, runId, "prototype-iteration-goal");

        details = await store.GetLatestProjectIterationSessionAsync(project.ProjectId!);

        details.Should().NotBeNull();
        details!.Goals.Should().HaveCount(2);
        details.GoalRuns.Should().ContainSingle();
        details.GoalRuns[0].GoalId.Should().Be(details.Goals[0].GoalId);
        details.GoalRuns[0].RunId.Should().Be(runId);
        details.GoalRuns[0].RunType.Should().Be("prototype-iteration-goal");
    }

    private static ProjectCreationCommand CreateCommand(string accountId, string projectName, string gameName)
    {
        var projectId = Guid.NewGuid().ToString("N");
        var root = Path.Combine(Path.GetTempPath(), projectId);
        return new ProjectCreationCommand(
            projectId,
            accountId,
            projectName,
            gameName,
            "admin-rule",
            "godot-prototype-default",
            true,
            ["chapter2-bootstrap", "prototype-7day-playable", "prototype-tdd", "prototype-scene"],
            root,
            Path.Combine(root, "repo"),
            Path.Combine(root, "runtime"),
            Path.Combine(root, "meta"));
    }

    private static async Task SetProjectCreatedUtcAsync(string connectionString, string projectId, string createdUtc)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = "UPDATE projects SET created_utc = $created_utc, last_activity_utc = $created_utc WHERE id = $project_id;";
        command.Parameters.AddWithValue("$project_id", projectId);
        command.Parameters.AddWithValue("$created_utc", createdUtc);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task SetRunTimingAsync(string connectionString, string runId, string createdUtc, string startedUtc, string finishedUtc)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            UPDATE runs
            SET created_utc = $created_utc,
                started_utc = $started_utc,
                finished_utc = $finished_utc,
                progress_updated_utc = $finished_utc
            WHERE id = $run_id;
            """;
        command.Parameters.AddWithValue("$run_id", runId);
        command.Parameters.AddWithValue("$created_utc", createdUtc);
        command.Parameters.AddWithValue("$started_utc", startedUtc);
        command.Parameters.AddWithValue("$finished_utc", finishedUtc);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task CreateLegacyDatabaseWithoutProjectLastActivityAsync(string connectionString)
    {
        await using var connection = new Microsoft.Data.Sqlite.SqliteConnection(connectionString);
        await connection.OpenAsync();
        await using var command = connection.CreateCommand();
        command.CommandText = """
            CREATE TABLE accounts (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NULL,
                token_hash TEXT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                name TEXT NOT NULL,
                game_name TEXT NOT NULL,
                game_type_source TEXT NOT NULL,
                template_rule_id TEXT NOT NULL,
                llm_binding_required INTEGER NOT NULL DEFAULT 0,
                allowed_workflows_json TEXT NOT NULL DEFAULT '[]',
                bootstrap_status TEXT NOT NULL DEFAULT 'initial',
                bootstrap_error TEXT NULL,
                created_utc TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );
            CREATE TABLE runs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT NULL,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                started_utc TEXT NULL,
                finished_utc TEXT NULL,
                exit_code INTEGER NULL,
                stdout_text TEXT NULL,
                stderr_text TEXT NULL,
                evidence_json TEXT NULL,
                progress_step TEXT NOT NULL DEFAULT '',
                progress_substep TEXT NOT NULL DEFAULT '',
                progress_label TEXT NOT NULL DEFAULT '',
                progress_updated_utc TEXT NULL,
                queue_position_at_start INTEGER NULL,
                llm_gateway TEXT NULL,
                llm_request_id TEXT NULL,
                llm_model TEXT NULL,
                llm_cost_json TEXT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            INSERT INTO accounts (id, username, is_admin, created_utc)
            VALUES ('legacy-account', 'legacy', 0, '2099-01-01T00:00:00.0000000Z');
            INSERT INTO projects (
                id,
                account_id,
                name,
                game_name,
                game_type_source,
                template_rule_id,
                llm_binding_required,
                allowed_workflows_json,
                bootstrap_status,
                created_utc)
            VALUES (
                'legacy-project',
                'legacy-account',
                'Legacy Project',
                'Legacy Game',
                'manual',
                'godot-prototype-default',
                0,
                '[]',
                'succeeded',
                '2099-01-01T00:00:00.0000000Z');
            INSERT INTO runs (
                id,
                project_id,
                run_type,
                status,
                created_utc,
                started_utc,
                finished_utc,
                progress_updated_utc)
            VALUES (
                'legacy-run',
                'legacy-project',
                'prototype-chat',
                'succeeded',
                '2099-01-01T00:00:00.0000000Z',
                '2099-01-01T00:00:00.0000000Z',
                '2099-01-02T00:00:00.0000000Z',
                '2099-01-02T00:00:00.0000000Z');
            """;
        await command.ExecuteNonQueryAsync();
    }

    private static async Task<string?> ScalarStringAsync(Microsoft.Data.Sqlite.SqliteConnection connection, string sql)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        return await command.ExecuteScalarAsync() as string;
    }

    private static async Task<long> ScalarLongAsync(Microsoft.Data.Sqlite.SqliteConnection connection, string sql)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = sql;
        var value = await command.ExecuteScalarAsync();
        return Convert.ToInt64(value);
    }
}
